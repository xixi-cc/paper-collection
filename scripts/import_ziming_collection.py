#!/usr/bin/env python3
"""Import screened S/A+/A papers from Ziming Liu's paper collection."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
import urllib.parse
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


ARXIV = re.compile(r"(?<!\d)(\d{4}\.\d{4,5})(?:v\d+)?(?!\d)", re.IGNORECASE)
SOURCE_NAME = "Ziming Liu Paper Collection"
SOURCE_URL = "https://metacircleai.github.io/ziming-paper-collection/collection.html"
ALLOWED_TIERS = {"S", "A+", "A"}

TOPIC_MAP = {
    "Representation, geometry & information": "Representation Learning",
    "Learning dynamics & optimization": "Training Dynamics",
    "Architectures, efficiency & systems": "Machine Learning",
    "Learning theory & mathematical foundations": "Learning Theory",
    "Transformer algorithms & in-context learning": "Transformer Theory",
    "Agents, reasoning & reliability": "AI Agents",
    "Mechanistic interpretability": "Mechanistic Interpretability",
    "Generative-model foundations": "Generative Models",
    "Scaling, generalization & data laws": "Scaling Laws",
    "AI for science & scientific discovery": "AI for Science",
    "Domain applications": "Machine Learning",
    "Neuroscience, cognition & bio-inspired AI": "Neuroscience",
    "Physics / complex systems": "Statistical Physics",
    "Predictive learning & world models": "World Models",
    "Other / unresolved": "Machine Learning",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def normalized_title(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", errors="ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", ascii_value.casefold())


def arxiv_id(value: str) -> str | None:
    match = ARXIV.search(urllib.parse.unquote(value))
    return match.group(1).casefold() if match else None


def canonical_url(value: str) -> str:
    value = value.strip()
    if identifier := arxiv_id(value):
        return f"https://arxiv.org/abs/{identifier}"
    parsed = urllib.parse.urlsplit(value)
    host = parsed.netloc.casefold().removeprefix("www.")
    path = re.sub(r"/$", "", parsed.path)
    return urllib.parse.urlunsplit(("https", host, path, parsed.query, ""))


def identity_keys(paper: dict[str, Any]) -> set[str]:
    keys = {f"title:{normalized_title(str(paper.get('title', '')))}"}
    urls = [str(paper.get("url") or ""), *map(str, (paper.get("links") or {}).values())]
    for url in filter(None, urls):
        keys.add(f"url:{canonical_url(url).casefold()}")
        if identifier := arxiv_id(url):
            keys.add(f"arxiv:{identifier}")
    return keys


def publication_source(url: str) -> tuple[str, str | None]:
    host = urllib.parse.urlsplit(url).netloc.casefold().removeprefix("www.")
    if host.endswith("arxiv.org"):
        return "arXiv", "preprint"
    if host.endswith("openreview.net"):
        return "OpenReview", "submission"
    return "Others", "published"


def paper_links(url: str) -> dict[str, str]:
    host = urllib.parse.urlsplit(url).netloc.casefold().removeprefix("www.")
    if host.endswith("arxiv.org"):
        return {"arxiv": url}
    if host.endswith("openreview.net"):
        return {"submission": url}
    return {"publication": url}


def curation_record(row: dict[str, Any], screened_at: str) -> dict[str, Any]:
    return {
        "name": SOURCE_NAME,
        "url": SOURCE_URL,
        "tier": row["tier"],
        "screening": "Quality top 50%; retained tiers S/A+/A",
        "screened_at": screened_at,
        "quality_score": row.get("quality_selection_score"),
    }


def merge_curation(item: dict[str, Any], record: dict[str, Any]) -> bool:
    previous = list(item.get("curation_sources") or [])
    next_records = [entry for entry in previous if entry.get("url") != SOURCE_URL]
    next_records.append(record)
    if previous == next_records:
        return False
    item["curation_sources"] = next_records
    return True


def main() -> None:
    args = parse_args()
    screened: list[dict[str, Any]] = json.loads(args.source.read_text(encoding="utf-8"))
    selected = [row for row in screened if row.get("tier") in ALLOWED_TIERS]
    catalog: list[dict[str, Any]] = json.loads(args.catalog.read_text(encoding="utf-8"))

    key_to_index: dict[str, int] = {}
    for index, item in enumerate(catalog):
        for key in identity_keys(item):
            key_to_index.setdefault(key, index)

    added: list[dict[str, str]] = []
    updated: list[dict[str, str]] = []
    unchanged: list[dict[str, str]] = []

    for row in selected:
        title = str(row["title"]).strip()
        url = canonical_url(str(row["url"]))
        incoming = {"title": title, "url": url, "links": paper_links(url)}
        duplicate_index = next((key_to_index[key] for key in identity_keys(incoming) if key in key_to_index), None)
        record = curation_record(row, args.date)

        if duplicate_index is not None:
            item = catalog[duplicate_index]
            changed = merge_curation(item, record)
            if row.get("abstract") and not item.get("abstract"):
                item["abstract"] = row["abstract"]
                changed = True
            target = updated if changed else unchanged
            target.append({"id": str(item["id"]), "title": str(item["title"]), "tier": str(row["tier"])})
            continue

        identifier = arxiv_id(url)
        stable_id = identifier or hashlib.sha256(f"ziming:{url}".encode("utf-8")).hexdigest()[:16]
        source, status = publication_source(url)
        item: dict[str, Any] = {
            "id": stable_id,
            "date": args.date,
            "title": title,
            "url": url,
            "links": paper_links(url),
            "tags": [source, TOPIC_MAP.get(str(row.get("primary_topic")), "Machine Learning")],
            "source_detail": source if source != "Others" else urllib.parse.urlsplit(url).netloc,
            "publication_status": status,
            "curation_sources": [record],
        }
        if row.get("year"):
            item["published"] = str(row["year"])
        if row.get("abstract"):
            item["abstract"] = row["abstract"]
        catalog.append(item)
        new_index = len(catalog) - 1
        for key in identity_keys(item):
            key_to_index[key] = new_index
        added.append({"id": stable_id, "title": title, "tier": str(row["tier"])})

    ids = [str(item["id"]) for item in catalog]
    if len(ids) != len(set(ids)):
        raise ValueError("catalog contains duplicate IDs")
    if len(selected) != 472:
        raise ValueError(f"expected 472 selected records, found {len(selected)}")
    if any(len(item.get("tags", [])) != 2 for item in catalog):
        raise ValueError("catalog contains a noncanonical tag pair")

    audit = {
        "source_collection": SOURCE_URL,
        "screened_source": str(args.source),
        "import_date": args.date,
        "selection": "Quality top 50%; tiers S/A+/A",
        "selected_count": len(selected),
        "tier_counts": dict(sorted(Counter(row["tier"] for row in selected).items())),
        "added_count": len(added),
        "updated_count": len(updated),
        "unchanged_count": len(unchanged),
        "catalog_count": len(catalog),
        "added": added,
        "updated": updated,
        "unchanged": unchanged,
    }

    if not args.dry_run:
        args.catalog.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        args.audit.parent.mkdir(parents=True, exist_ok=True)
        args.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({key: audit[key] for key in (
        "selected_count", "tier_counts", "added_count", "updated_count", "unchanged_count", "catalog_count"
    )}, ensure_ascii=False))


if __name__ == "__main__":
    main()
