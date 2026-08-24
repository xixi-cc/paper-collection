#!/usr/bin/env python3
"""Replace discovery-platform labels and add venues to formal publications."""

from __future__ import annotations

import argparse
from collections import Counter
import html
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


USER_AGENT = "XncaoPaperCollection/3.0 (bibliographic metadata audit)"
DOI = re.compile(r"(10\.\d{4,9}/[^?#\s]+)", re.IGNORECASE)

UNVERIFIED_SCHOLAR_IDS = {
    "668c1c8e9353a533", "dd98670a3673c74e", "57aa2858399f5962",
    "70c81f9af49a8d3a", "59005da35cc413bd", "101391aaff8d052e",
    "27496310bb2b94ff",
}

PLATFORM_FIXES: dict[str, dict[str, Any]] = {
    "24be133138c9189b": {
        "title": "Foundations of Algorithmic Thermodynamics",
        "source": "Journal", "venue": "Physical Review E", "published": "2025-01-08",
        "publication": "https://doi.org/10.1103/PhysRevE.111.014118",
        "arxiv": "https://arxiv.org/abs/2308.06927",
    },
    "f094d310059a6320": {
        "title": "Scaling LLM Test-Time Compute Optimally Can be More Effective than Scaling Parameters for Reasoning",
        "source": "Conference", "venue": "ICLR 2025", "published": "2025",
        "publication": "https://proceedings.iclr.cc/paper_files/paper/2025/hash/1b623663fd9b874366f3ce019fdfdd44-Abstract-Conference.html",
        "arxiv": "https://arxiv.org/abs/2408.03314",
    },
    "e09961a5caff848f": {
        "title": "Tensor Programs VI: Feature Learning in Infinite Depth Neural Networks",
        "source": "Conference", "venue": "ICLR 2024", "published": "2024",
        "publication": "https://proceedings.iclr.cc/paper_files/paper/2024/hash/f2ce452a4a7352feb7a9fb885267ff24-Abstract-Conference.html",
        "arxiv": "https://arxiv.org/abs/2310.02244",
    },
    "5907a6891e0aea7f": {
        "title": "GUD: Generation with Unified Diffusion",
        "source": "arXiv", "published": "2024-10-03",
        "arxiv": "https://arxiv.org/abs/2410.02667",
    },
    "785b72b087f4ceeb": {
        "title": "Li₂: A Framework on Dynamics of Feature Emergence and Delayed Generalization",
        "source": "Conference", "venue": "ICLR 2026", "published": "2026",
        "publication": "https://proceedings.iclr.cc/paper_files/paper/2026/hash/7ce5da35e01cfa8d303c2dc71e61a470-Abstract-Conference.html",
        "arxiv": "https://arxiv.org/abs/2509.21519",
    },
    "53f45db2a0ac7222": {
        "title": "A Simple Mean Field Model of Feature Learning",
        "source": "arXiv", "published": "2025-10-16",
        "arxiv": "https://arxiv.org/abs/2510.15174",
    },
    "de7541eb8ecbcd8f": {
        "title": "How Feature Learning Can Improve Neural Scaling Laws",
        "source": "Journal", "venue": "Journal of Statistical Mechanics: Theory and Experiment",
        "published": "2025-08-05", "publication": "https://doi.org/10.1088/1742-5468/adefb1",
        "arxiv": "https://arxiv.org/abs/2409.17858",
    },
    "e61f03c44e0d83b5": {
        "title": "Scaling Laws and Spectra of Shallow Neural Networks in the Feature Learning Regime",
        "source": "Conference", "venue": "ICLR 2026", "published": "2026",
        "publication": "https://proceedings.iclr.cc/paper_files/paper/2026/hash/b117cd5a0af6f5ecfdac7b47b893b96f-Abstract-Conference.html",
        "arxiv": "https://arxiv.org/abs/2509.24882",
    },
    "d65f26b6af5cd650": {
        "title": "Understanding Scaling Laws in Deep Neural Networks via Feature Learning Dynamics",
        "source": "arXiv", "published": "2025-12-24",
        "arxiv": "https://arxiv.org/abs/2512.21075",
    },
    "dfc81cbdbbcf1b33": {
        "title": "Discrete Diffusion Language Modeling by Estimating the Ratios of the Data Distribution",
        "source": "OpenReview submission", "publication_status": "submission",
        "submission": "https://openreview.net/pdf/6dcf56ae64ecd6ffb39c0b5f3064025b9e2a297a.pdf",
    },
    "af0b5a5bd95c883c": {
        "title": "Discrete Flow Matching for Graph Generation",
        "source": "Conference", "venue": "ICML 2025", "published": "2025",
        "publication": "https://proceedings.mlr.press/v267/qin25d.html",
        "arxiv": "https://arxiv.org/abs/2410.04263",
    },
    "16deea2a8042b097": {
        "title": "Action-Minimization Meets Generative Modeling: Efficient Transition Path Sampling with the Onsager-Machlup Functional",
        "source": "Conference", "venue": "ICML 2025", "published": "2025",
        "publication": "https://proceedings.mlr.press/v267/raja25a.html",
        "arxiv": "https://arxiv.org/abs/2504.18506",
    },
    "3ef68ddd10603589": {
        "title": "Relay Diffusion: Unifying Diffusion Process across Resolutions for Image Synthesis",
        "source": "Conference", "venue": "ICLR 2024", "published": "2024",
        "publication": "https://proceedings.iclr.cc/paper_files/paper/2024/hash/522ef98b1e52f5918e5abc868651175d-Abstract-Conference.html",
        "arxiv": "https://arxiv.org/abs/2309.03350",
    },
    "6fbd8b62646ecbe8": {
        "title": "Score-based Data Assimilation",
        "source": "Conference", "venue": "NeurIPS 2023", "published": "2023",
        "publication": "https://doi.org/10.52202/075280-1763",
        "arxiv": "https://arxiv.org/abs/2306.10574",
    },
}

VENUE_OVERRIDES: dict[str, dict[str, str]] = {
    "82e35b0590248725": {"source": "Preprint"},
    "5e3bfc21bacde26a": {
        "source": "Journal", "venue": "Nature Communications",
        "publication": "https://doi.org/10.1038/s41467-023-42633-4",
    },
    "003336f09dcac84a": {
        "source": "Conference",
        "venue": "3rd Conference on Statistical Physics: Modern Trends and Applications",
    },
    "abbbdd1f1314d86f": {"source": "Journal", "venue": "Journal of Mathematical Physics"},
    "344836b1342ec68f": {"source": "Journal", "venue": "Journal of Physics A: Mathematical and Theoretical"},
    "af3db7e12355e717": {"source": "Journal", "venue": "Nuclear Physics B"},
    "c60356ed39e9882a": {"source": "Journal", "venue": "Programmable Materials"},
    "1899272149a453cf": {"source": "Journal", "venue": "Cold Spring Harbor Perspectives in Biology"},
    "a592ef38f18db604": {"source": "Journal", "venue": "Physica D: Nonlinear Phenomena"},
    "1ae2eb274403f4be": {"source": "Journal", "venue": "Engineering"},
    "53f0bbe1eb06ac49": {"source": "Journal", "venue": "Journal of Computational Physics"},
    "c8d3e59a68e46938": {"source": "Journal", "venue": "Computer Methods in Applied Mechanics and Engineering"},
    "a31e711a0f0c5d20": {"source": "Journal", "venue": "Physics Letters A"},
    "770220f9508b5e10": {"source": "Journal", "venue": "Automatica"},
    "36071a0581a1017d": {"source": "Journal", "venue": "Journal of Computational Physics"},
    "e59dd3f1b8f69ef0": {"source": "Journal", "venue": "Science Advances"},
    "aa856c468aa42fde": {"source": "Journal", "venue": "Journal of Computational Physics"},
    "52733712d33cf0cd": {"source": "Journal", "venue": "Physical Review E"},
    "cd01d3578fe73e63": {"source": "Journal", "venue": "Journal de Mathématiques Pures et Appliquées"},
    "7fc155cd48360cde": {"source": "Journal", "venue": "Physica A: Statistical Mechanics and its Applications"},
    "9185034ca2d581a8": {"source": "Journal", "venue": "Progress of Theoretical and Experimental Physics"},
    "d264b597037f6edb": {"source": "Conference", "venue": "Active Inference"},
    "3526acd9c1713a6c": {
        "source": "Conference", "venue": "Anticipatory Behavior in Adaptive Learning Systems",
    },
    "d3593ea6cb44205b": {"source": "Conference", "venue": "ECCV 2024"},
    "9f515671e11b49f1": {"source": "Conference", "venue": "AISTATS 2024"},
    "ac099926b4ddd8a6": {"source": "Conference", "venue": "AAAI 2026"},
    "f4470a3ee5019c07": {"source": "Journal", "venue": "Proceedings of the National Academy of Sciences"},
    "13b194226b8b60fa": {"source": "Journal", "venue": "Proceedings of the National Academy of Sciences"},
    "bddffd6b3fd137d7": {"source": "Journal", "venue": "Proceedings of the National Academy of Sciences"},
    "baf3f2b22980bf29": {"source": "Journal", "venue": "Proceedings of the National Academy of Sciences"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--prior-audit", type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    return parser.parse_args()


def request_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read(4_000_000).decode("utf-8", errors="replace")


def request_json(url: str) -> dict[str, Any]:
    return json.loads(request_text(url))


def doi_from_url(url: str) -> str | None:
    match = DOI.search(urllib.parse.unquote(url))
    return match.group(1).rstrip(".,;:)]}") if match else None


def clean_venue(venue: str, source: str, published: str | None) -> str:
    venue = html.unescape(re.sub(r"\s+", " ", venue)).strip()
    year = (published or "")[:4]
    lower = venue.casefold()
    if source == "Conference":
        if "learning representations" in lower:
            return f"ICLR {year}".strip()
        if "neural information processing systems" in lower:
            return f"NeurIPS {year}".strip()
        if "international conference on machine learning" in lower:
            return f"ICML {year}".strip()
    return venue


def crossref_venue(doi: str) -> str | None:
    try:
        item = request_json("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe=""))["message"]
    except Exception:
        return None
    containers = item.get("container-title") or []
    return str(containers[0]).strip() if containers else None


def page_venue(url: str) -> str | None:
    try:
        page = request_text(url)
    except Exception:
        return None
    patterns = (
        r'<meta[^>]+name=["\']citation_journal_title["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']citation_journal_title["\']',
        r'<meta[^>]+name=["\']citation_conference_title["\'][^>]+content=["\']([^"\']+)',
    )
    for pattern in patterns:
        match = re.search(pattern, page, flags=re.IGNORECASE)
        if match:
            return html.unescape(match.group(1)).strip()
    return None


def inferred_venue(url: str, published: str | None) -> str | None:
    year = (published or "")[:4]
    if "proceedings.neurips.cc" in url:
        return f"NeurIPS {year}".strip()
    if "proceedings.iclr.cc" in url:
        return f"ICLR {year}".strip()
    if "jmlr.org" in url:
        return "Journal of Machine Learning Research"
    return None


def apply_platform_fix(paper: dict[str, Any], fix: dict[str, Any]) -> None:
    topic = paper["tags"][1]
    paper["title"] = fix["title"]
    paper["tags"] = [fix["source"], topic]
    paper.pop("venue", None)
    paper.pop("publication_status", None)
    paper.pop("source_detail", None)
    paper.pop("published", None)
    if fix.get("venue"):
        paper["venue"] = fix["venue"]
    if fix.get("publication_status"):
        paper["publication_status"] = fix["publication_status"]
    if fix.get("published"):
        paper["published"] = fix["published"]
    links = {key: fix[key] for key in ("publication", "arxiv", "submission") if fix.get(key)}
    paper["links"] = links
    paper["url"] = links.get("publication") or links.get("arxiv") or links.get("submission")


def main() -> None:
    args = parse_args()
    catalog: list[dict[str, Any]] = json.loads(args.catalog.read_text(encoding="utf-8"))
    original_count = len(catalog)
    catalog = [paper for paper in catalog if paper["id"] not in UNVERIFIED_SCHOLAR_IDS]

    fixes_applied = 0
    for paper in catalog:
        fix = PLATFORM_FIXES.get(paper["id"])
        if fix:
            apply_platform_fix(paper, fix)
            fixes_applied += 1

    for paper in catalog:
        override = VENUE_OVERRIDES.get(paper["id"])
        if not override:
            continue
        paper["tags"][0] = override["source"]
        paper.pop("source_detail", None)
        if override.get("venue"):
            paper["venue"] = override["venue"]
        else:
            paper.pop("venue", None)
            paper["publication_status"] = "preprint"
        if override.get("publication"):
            paper.setdefault("links", {})["publication"] = override["publication"]
            paper["url"] = override["publication"]

    prior_venues: dict[str, str] = {}
    if args.prior_audit and args.prior_audit.exists():
        prior = json.loads(args.prior_audit.read_text(encoding="utf-8"))
        prior_venues = {row["id"]: row["venue"] for row in prior["records"] if row.get("venue")}

    methods: dict[str, str] = {}
    unresolved: list[dict[str, str]] = []
    for paper in catalog:
        source = paper.get("publication_type") or paper["tags"][0]
        if source not in {"Journal", "Conference"}:
            paper.pop("venue", None)
            paper.pop("publication_type", None)
            continue
        if paper.get("venue"):
            methods[paper["id"]] = "curated_override" if paper["id"] in VENUE_OVERRIDES else "curated_platform_fix"
            continue
        venue = prior_venues.get(paper["id"])
        method = "prior_bibliographic_audit"
        publication = str((paper.get("links") or {}).get("publication") or paper.get("url") or "")
        if not venue:
            doi = doi_from_url(publication)
            if doi:
                venue = crossref_venue(doi)
                method = "crossref_doi"
        if not venue:
            venue = inferred_venue(publication, paper.get("published"))
            method = "canonical_url"
        if not venue:
            venue = page_venue(publication)
            method = "publisher_citation_metadata"
        if venue:
            paper["venue"] = clean_venue(venue, source, paper.get("published"))
            methods[paper["id"]] = method
        else:
            unresolved.append({"id": paper["id"], "title": paper["title"], "url": publication})

    source_details: list[str] = []
    for paper in catalog:
        source = paper.get("publication_type") or paper["tags"][0]
        if source in {"Journal", "Conference"} and paper.get("venue"):
            paper["publication_type"] = source
            detail = paper["venue"]
        else:
            detail = str(paper.get("source_detail") or paper["tags"][0])
        paper["source_detail"] = detail
        source_details.append(detail)

    source_counts = Counter(source_details)
    for paper in catalog:
        detail = paper["source_detail"]
        paper["tags"][0] = detail if source_counts[detail] >= 5 else "Others"

    args.catalog.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "original_count": original_count,
        "catalog_count": len(catalog),
        "excluded_unverified_scholar_search": len(UNVERIFIED_SCHOLAR_IDS),
        "removed_unverified_scholar_search_this_run": original_count - len(catalog),
        "platform_fixes": fixes_applied,
        "formal_records": sum(p.get("publication_type") in {"Journal", "Conference"} for p in catalog),
        "formal_with_venue": sum(bool(p.get("venue")) for p in catalog if p.get("publication_type") in {"Journal", "Conference"}),
        "grouped_source_labels": len({p["tags"][0] for p in catalog}),
        "records_grouped_as_others": sum(p["tags"][0] == "Others" for p in catalog),
        "venue_methods": methods,
        "unresolved": unresolved,
    }
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: audit[key] for key in (
        "catalog_count", "excluded_unverified_scholar_search", "removed_unverified_scholar_search_this_run", "platform_fixes",
        "formal_records", "formal_with_venue", "unresolved",
    )}, ensure_ascii=False, indent=2))
    if unresolved:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
