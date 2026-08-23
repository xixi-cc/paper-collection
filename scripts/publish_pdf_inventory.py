#!/usr/bin/env python3
"""Convert the audited local-PDF inventory into a public paper catalog."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


ARXIV_NEW = re.compile(r"(?<!\d)(\d{4}\.\d{4,5})(?:v\d+)?(?!\d)", re.IGNORECASE)
ARXIV_OLD = re.compile(r"\b([a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?\b", re.IGNORECASE)
DOI = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.IGNORECASE)
NON_ARTICLE = re.compile(
    r"\b(master(?:['’]s)? thesis|master of science|internship thesis|doctoral thesis|dissertation|"
    r"term paper|working title|arxiv-style preprint workspace)\b",
    re.IGNORECASE,
)
TOPICS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Active Matter", ("active matter", "active particle", "flock", "vicsek", "quincke", "swarm")),
    ("Machine Learning", ("neural", "machine learning", "diffusion model", "transformer", "world model")),
    ("Robotics", ("robot", "embodied", "manipulation", "vision-language-action", "vla")),
    ("Statistical Physics", ("critical", "phase transition", "renormalization", "universality", "statistical")),
    ("Soft Matter", ("soft matter", "colloid", "polymer", "gel", "granular")),
    ("Fluid Dynamics", ("fluid", "hydrodynamic", "flow", "turbulence")),
    ("Biophysics", ("cell", "tissue", "protein", "bacteria")),
)
PUBLIC_OVERRIDES = {
    normalize_title: record
    for normalize_title, record in (
        ("emergence of self dual patterns in active colloids with periodical feedback to local density", ("Emergence of Self-dual Patterns in Active Colloids with Periodical Feedback to Local Density", "https://arxiv.org/abs/2204.07717", "arXiv")),
        ("generative diffusion for perceptrons", ("Generative diffusion for perceptron problems: statistical physics analysis and efficient algorithms", "https://arxiv.org/abs/2502.16292", "arXiv")),
        ("renormalization group flow as optimal transport jordan cotler1 2 3 and semon rezchikov4", ("Renormalization Group Flow as Optimal Transport", "https://arxiv.org/abs/2202.11737", "arXiv")),
        ("steap simultaneous trajectory estimation and planning mustafa mukadam1 jing dong1 frank dellaert1 byron boots1", ("STEAP: simultaneous trajectory estimation and planning", "https://arxiv.org/abs/1807.10425", "arXiv")),
        ("the physics of the vicsek model francesco ginellia", ("The Physics of the Vicsek Model", "https://arxiv.org/abs/1511.01451", "arXiv")),
        ("universitat wurzburg fakultat fur physik und astronomie", ("Non-equilibrium Phase Transitions with Long-Range Interactions", "https://arxiv.org/abs/cond-mat/0702169", "arXiv")),
        ("wasserstein flow matching generative modeling over families of distributions", ("Wasserstein Flow Matching: Generative Modeling Over Families of Distributions", "https://arxiv.org/abs/2411.00698", "arXiv")),
    )
}
EXCLUDED_TITLES = {
    "active matter",
    "active matter and collective motion",
    "city country",
    "electrohydrodynamics of particles and drops in strong electric fields",
    "modeling and numerical simulation of self propelled particles in viscous fluid",
    "order and fluctuations in collective dynamics of swimming bacteria experimental exploration of active matter physics",
    "this note gives a self contained organization of the field theory analysis of the active",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    return parser.parse_args()


def normalize(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", errors="ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", ascii_value.casefold()).strip()


def similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize(left), normalize(right)).ratio()


def read_first_pages(path: Path) -> str:
    try:
        result = subprocess.run(
            ["pdftotext", "-f", "1", "-l", "2", "-layout", str(path), "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=25,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.decode("utf-8", errors="replace")[:60000]


def request_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "XixiPaperCollection/1.0 (mailto:xixi@example.com)"},
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def fetch_arxiv(identifiers: set[str]) -> dict[str, str]:
    records: dict[str, str] = {}
    ordered = sorted(identifiers)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    for start in range(0, len(ordered), 30):
        batch = ordered[start:start + 30]
        url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({
            "id_list": ",".join(batch),
            "max_results": len(batch),
        })
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "XixiPaperCollection/1.0"})
            with urllib.request.urlopen(request, timeout=30) as response:
                root = ET.fromstring(response.read())
            for entry in root.findall("atom:entry", namespace):
                raw_id = entry.findtext("atom:id", default="", namespaces=namespace).partition("/abs/")[2]
                identifier = re.sub(r"v\d+$", "", raw_id)
                title = " ".join(entry.findtext("atom:title", default="", namespaces=namespace).split())
                if identifier and title:
                    records[identifier.casefold()] = title
        except Exception:
            pass
        time.sleep(0.35)
    return records


def crossref_by_doi(identifier: str) -> tuple[str, str] | None:
    url = "https://api.crossref.org/works/" + urllib.parse.quote(identifier, safe="")
    try:
        message = request_json(url)["message"]
        title = " ".join((message.get("title") or [""])[0].split())
        return title, f"https://doi.org/{identifier}"
    except Exception:
        return None


def crossref_by_title(title: str) -> tuple[str, str, str] | None:
    query = urllib.parse.urlencode({"query.title": title, "rows": 5, "select": "DOI,title,type"})
    try:
        items = request_json("https://api.crossref.org/works?" + query)["message"]["items"]
    except Exception:
        return None
    candidates: list[tuple[float, str, str, str]] = []
    for item in items:
        candidate_title = " ".join((item.get("title") or [""])[0].split())
        identifier = item.get("DOI")
        if candidate_title and identifier:
            candidates.append((similarity(title, candidate_title), candidate_title, identifier, item.get("type", "")))
    if not candidates:
        return None
    score, candidate_title, identifier, work_type = max(candidates)
    if score < 0.9:
        return None
    source = "Conference" if "proceedings" in work_type else "Journal"
    return candidate_title, f"https://doi.org/{identifier}", source


def infer_topic(title: str) -> str | None:
    lowered = title.casefold()
    for topic, terms in TOPICS:
        if any(term in lowered for term in terms):
            return topic
    return None


def main() -> None:
    args = parse_args()
    with args.inventory.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    prepared: list[dict[str, Any]] = []
    arxiv_ids: set[str] = set()
    for row in rows:
        path = Path(row["path"])
        text = read_first_pages(path)
        path_text = str(path)
        searchable = f"{path_text} {text}"
        path_ids = ARXIV_NEW.findall(path_text) + ARXIV_OLD.findall(path_text)
        new_ids = ARXIV_NEW.findall(searchable)
        old_ids = ARXIV_OLD.findall(searchable)
        doi_ids = [value.rstrip(".,;:)]}") for value in DOI.findall(searchable)]
        identifiers = list(dict.fromkeys(new_ids + old_ids))
        arxiv_ids.update(identifier.casefold() for identifier in identifiers)
        prepared.append({
            "row": row,
            "arxiv": identifiers,
            "path_arxiv": {identifier.casefold() for identifier in path_ids},
            "doi": list(dict.fromkeys(doi_ids)),
            "non_article_evidence": bool(NON_ARTICLE.search(f"{row['title']} {text[:5000]}")),
        })

    arxiv_records = fetch_arxiv(arxiv_ids)
    papers: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    collected = date.today().isoformat()

    for item in prepared:
        row = item["row"]
        title = row["title"].strip()
        if (
            item["non_article_evidence"]
            or normalize(title) in EXCLUDED_TITLES
        ):
            audit.append({"title": title, "status": "excluded_non_article"})
            continue

        resolved_title = title
        url = ""
        source = ""
        method = ""

        override = PUBLIC_OVERRIDES.get(normalize(title))
        if override:
            resolved_title, url, source = override
            method = "verified_override"

        arxiv_matches = [
            (similarity(title, arxiv_records[identifier.casefold()]), identifier, arxiv_records[identifier.casefold()])
            for identifier in item["arxiv"]
            if identifier.casefold() in arxiv_records
        ]
        if not url and arxiv_matches:
            score, identifier, candidate_title = max(arxiv_matches)
            if score >= 0.72 or identifier.casefold() in item["path_arxiv"]:
                resolved_title = candidate_title
                url = f"https://arxiv.org/abs/{identifier}"
                source = "arXiv"
                method = "verified_arxiv"

        if not url:
            doi_matches: list[tuple[float, str, str]] = []
            for identifier in item["doi"][:3]:
                record = crossref_by_doi(identifier)
                if record:
                    candidate_title, candidate_url = record
                    doi_matches.append((similarity(title, candidate_title), candidate_title, candidate_url))
                time.sleep(0.08)
            if doi_matches:
                score, candidate_title, candidate_url = max(doi_matches)
                if score >= 0.8:
                    resolved_title = candidate_title
                    url = candidate_url
                    source = "Journal"
                    method = "verified_doi"

        if not url:
            record = crossref_by_title(title)
            if record:
                resolved_title, url, source = record
                method = "crossref_title_match"
            time.sleep(0.1)

        if not url:
            url = "https://scholar.google.com/scholar?" + urllib.parse.urlencode({"q": f'"{title}"'})
            source = "Scholar search"
            method = "title_search"

        tags = [source]
        topic = infer_topic(resolved_title)
        if topic:
            tags.append(topic)
        paper = {
            "id": row["sha256"][:16],
            "date": collected,
            "title": resolved_title,
            "url": url,
            "tags": tags,
        }
        papers.append(paper)
        audit.append({"title": title, "published_title": resolved_title, "url": url, "status": method})

    deduplicated: dict[str, dict[str, Any]] = {}
    for paper in papers:
        key = paper["url"].casefold()
        if key in deduplicated:
            audit.append({"title": paper["title"], "url": paper["url"], "status": "duplicate_publication"})
            continue
        deduplicated[key] = paper
    papers = sorted(deduplicated.values(), key=lambda paper: paper["title"].casefold())
    args.output.write_text(json.dumps(papers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for entry in audit:
        counts[entry["status"]] = counts.get(entry["status"], 0) + 1
    args.audit.write_text(
        json.dumps({"input_rows": len(rows), "published": len(papers), "status_counts": counts, "entries": audit}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"input_rows": len(rows), "published": len(papers), "status_counts": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
