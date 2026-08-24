#!/usr/bin/env python3
"""Audit catalog dates and add formal-publication plus arXiv links.

For arXiv records, the arXiv Atom API is the authority for the initial
submission date and any DOI explicitly attached by the authors. Crossref is
used for DOI metadata and, when arXiv has no DOI, for conservative title and
author matching. Weak title-only matches are never promoted to publications.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


ARXIV = re.compile(r"arxiv\.org/(?:abs|pdf)/((?:\d{4}\.\d{4,5})|(?:[^/]+/\d{7}))(?:v\d+)?", re.IGNORECASE)
DOI = re.compile(r"(10\.\d{4,9}/[^?#\s]+)", re.IGNORECASE)
USER_AGENT = "XncaoPaperCollection/2.0 (https://xixi-paper-collection.lezontbukercfdvs4.chatgpt.site)"
ATOM = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
FORMAL_TYPES = {"book-chapter", "journal-article", "proceedings-article", "reference-entry"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--skip-title-search", action="store_true")
    return parser.parse_args()


def normalized_title(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", errors="ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", ascii_value.casefold())


def normalized_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", errors="ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def arxiv_id(url: str) -> str | None:
    match = ARXIV.search(url)
    return match.group(1) if match else None


def doi_from_url(url: str) -> str | None:
    match = DOI.search(urllib.parse.unquote(url))
    return match.group(1).rstrip(".,;:)]}") if match else None


def request_bytes(url: str, attempts: int = 4) -> bytes:
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read(8_000_000)
        except Exception:
            if attempt + 1 == attempts:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("unreachable")


def request_json(url: str) -> dict[str, Any]:
    return json.loads(request_bytes(url).decode("utf-8"))


def format_crossref_date(message: dict[str, Any]) -> str | None:
    dates: list[str] = []
    for key in ("published-online", "published-print", "published", "issued"):
        parts = ((message.get(key) or {}).get("date-parts") or [[]])[0]
        if not parts:
            continue
        year = int(parts[0])
        if not 1800 <= year <= 2100:
            continue
        value = f"{year:04d}"
        if len(parts) >= 2 and 1 <= int(parts[1]) <= 12:
            value += f"-{int(parts[1]):02d}"
        if len(parts) >= 3 and 1 <= int(parts[2]) <= 31:
            value += f"-{int(parts[2]):02d}"
        dates.append(value)
    return min(dates) if dates else None


def fetch_arxiv(records: dict[str, dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    result: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    identifiers = sorted(records)
    for offset in range(0, len(identifiers), 40):
        batch = identifiers[offset:offset + 40]
        query = urllib.parse.urlencode({"id_list": ",".join(batch), "max_results": len(batch)})
        try:
            root = ET.fromstring(request_bytes("https://export.arxiv.org/api/query?" + query))
            for entry in root.findall("atom:entry", ATOM):
                raw_id = entry.findtext("atom:id", default="", namespaces=ATOM)
                identifier = arxiv_id(raw_id)
                if not identifier:
                    continue
                title = " ".join(entry.findtext("atom:title", default="", namespaces=ATOM).split())
                authors = [
                    " ".join(node.findtext("atom:name", default="", namespaces=ATOM).split())
                    for node in entry.findall("atom:author", ATOM)
                ]
                result[identifier] = {
                    "title": title,
                    "authors": authors,
                    "submitted": entry.findtext("atom:published", default="", namespaces=ATOM)[:10],
                    "doi": entry.findtext("arxiv:doi", default="", namespaces=ATOM).strip() or None,
                    "journal_ref": entry.findtext("arxiv:journal_ref", default="", namespaces=ATOM).strip() or None,
                }
        except Exception as exc:
            failures.append(f"arXiv batch {offset // 40 + 1}: {type(exc).__name__}: {exc}")
        time.sleep(3.1)
    missing = sorted(set(identifiers) - set(result))
    failures.extend(f"arXiv missing entry: {identifier}" for identifier in missing)
    return result, failures


def crossref_by_doi(doi: str) -> dict[str, Any] | None:
    try:
        return request_json("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe=""))["message"]
    except Exception:
        return None


def crossref_title_match(meta: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    expected = normalized_title(str(meta["title"]))
    query = urllib.parse.urlencode({
        "query.title": str(meta["title"]),
        "rows": 5,
        "select": "DOI,title,author,type,container-title,published,published-online,published-print,issued,URL",
    })
    diagnostic: dict[str, Any] = {"accepted": False, "best_score": 0.0, "author_match": False}
    try:
        items = request_json("https://api.crossref.org/works?" + query)["message"]["items"]
    except Exception as exc:
        diagnostic["error"] = f"{type(exc).__name__}: {exc}"
        return None, diagnostic
    arxiv_surnames = {
        normalized_name(name.split()[-1])
        for name in meta.get("authors", [])
        if name.split()
    }
    best: tuple[float, bool, dict[str, Any]] | None = None
    for item in items:
        candidate = str((item.get("title") or [""])[0])
        score = SequenceMatcher(None, expected, normalized_title(candidate)).ratio()
        crossref_surnames = {
            normalized_name(str(author.get("family", "")))
            for author in item.get("author", [])
            if author.get("family")
        }
        author_match = bool(arxiv_surnames & crossref_surnames)
        if best is None or score > best[0]:
            best = (score, author_match, item)
    if best is None:
        return None, diagnostic
    score, author_match, item = best
    diagnostic.update({
        "best_score": round(score, 4),
        "author_match": author_match,
        "candidate_doi": item.get("DOI"),
        "candidate_type": item.get("type"),
    })
    exact = normalized_title(str((item.get("title") or [""])[0])) == expected
    accepted = (
        item.get("type") in FORMAL_TYPES
        and bool(item.get("DOI"))
        and author_match
        and (exact or score >= 0.985)
        and bool(format_crossref_date(item))
    )
    diagnostic["accepted"] = accepted
    return (item if accepted else None), diagnostic


def source_for_crossref(message: dict[str, Any]) -> str:
    container = " ".join(str(value) for value in message.get("container-title", []))
    conference_markers = (
        "conference",
        "proceedings",
        "advances in neural information processing systems",
        "lecture notes in computer science",
        "communications in computer and information science",
    )
    is_conference = (
        message.get("type") in {"proceedings-article", "book-chapter"}
        or any(marker in container.casefold() for marker in conference_markers)
    )
    return "Conference" if is_conference else "Journal"


def formal_record(message: dict[str, Any], method: str) -> dict[str, Any] | None:
    doi = str(message.get("DOI") or "").strip()
    published = format_crossref_date(message)
    if not doi or not published or message.get("type") not in FORMAL_TYPES:
        return None
    return {
        "doi": doi,
        "url": "https://doi.org/" + doi,
        "published": published,
        "source": source_for_crossref(message),
        "venue": str((message.get("container-title") or [""])[0]),
        "method": method,
    }


def main() -> None:
    args = parse_args()
    catalog: list[dict[str, Any]] = json.loads(args.catalog.read_text(encoding="utf-8"))
    arxiv_papers: dict[str, dict[str, Any]] = {}
    for paper in catalog:
        links = paper.get("links") or {}
        identifier = arxiv_id(str(links.get("arxiv") or paper.get("url", "")))
        if identifier:
            arxiv_papers[identifier] = paper

    arxiv_meta, failures = fetch_arxiv(arxiv_papers)
    doi_messages: dict[str, dict[str, Any] | None] = {}
    explicit_dois = sorted({str(meta["doi"]) for meta in arxiv_meta.values() if meta.get("doi")})
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {executor.submit(crossref_by_doi, doi): doi for doi in explicit_dois}
        for future in as_completed(futures):
            doi_messages[futures[future]] = future.result()

    title_matches: dict[str, tuple[dict[str, Any] | None, dict[str, Any]]] = {}
    if not args.skip_title_search:
        targets = [identifier for identifier, meta in arxiv_meta.items() if not meta.get("doi")]
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            futures = {executor.submit(crossref_title_match, arxiv_meta[identifier]): identifier for identifier in targets}
            for future in as_completed(futures):
                identifier = futures[future]
                try:
                    title_matches[identifier] = future.result()
                except Exception as exc:
                    title_matches[identifier] = (None, {"accepted": False, "error": str(exc)})

    audit_rows: list[dict[str, Any]] = []
    counts = {"arxiv_records": 0, "formal_explicit_doi": 0, "formal_strict_match": 0, "arxiv_only": 0}
    for identifier, paper in arxiv_papers.items():
        meta = arxiv_meta.get(identifier)
        row: dict[str, Any] = {
            "id": paper["id"],
            "arxiv_id": identifier,
            "catalog_title": paper["title"],
            "status": "unverified",
        }
        if not meta:
            audit_rows.append(row)
            continue
        counts["arxiv_records"] += 1
        paper["published"] = meta["submitted"]
        paper["links"] = {"arxiv": f"https://arxiv.org/abs/{identifier}"}
        formal: dict[str, Any] | None = None
        if meta.get("doi"):
            message = doi_messages.get(str(meta["doi"]))
            if message:
                formal = formal_record(message, "arxiv_explicit_doi")
            if formal:
                counts["formal_explicit_doi"] += 1
        elif identifier in title_matches:
            message, diagnostic = title_matches[identifier]
            row["title_match"] = diagnostic
            if message:
                formal = formal_record(message, "crossref_exact_title_author")
            if formal:
                counts["formal_strict_match"] += 1
        if formal:
            paper["published"] = formal["published"]
            paper["url"] = formal["url"]
            paper["links"]["publication"] = formal["url"]
            paper["tags"][0] = formal["source"]
            row.update({"status": "bibliographically_verified", **formal})
        else:
            paper["url"] = paper["links"]["arxiv"]
            paper["tags"][0] = "arXiv"
            counts["arxiv_only"] += 1
            row.update({
                "status": "arxiv_only",
                "published": meta["submitted"],
                "journal_ref": meta.get("journal_ref"),
                "arxiv_doi": meta.get("doi"),
            })
        audit_rows.append(row)

    for paper in catalog:
        if "links" not in paper:
            paper["links"] = {"publication": str(paper.get("url", ""))}

    args.catalog.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "catalog_count": len(catalog),
        "counts": counts,
        "failures": failures,
        "records": audit_rows,
    }
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"catalog_count": len(catalog), "counts": counts, "failures": len(failures)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
