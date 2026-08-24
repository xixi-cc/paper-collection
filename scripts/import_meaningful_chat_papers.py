#!/usr/bin/env python3
"""Merge the finalized Meaningful Chat paper summary into the site catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
import urllib.parse
from datetime import date
from pathlib import Path
from typing import Any

from catalog_tags import paper_tags


ARXIV = re.compile(r"(?<!\d)(\d{4}\.\d{4,5})(?:v\d+)?(?!\d)", re.IGNORECASE)
DOI = re.compile(r"(10\.\d{4,9}/[^?#\s]+)", re.IGNORECASE)

CATEGORY_TAGS: dict[str, tuple[str, ...]] = {
    "AI agents and physical-law discovery": ("Machine Learning", "AI for Science"),
    "AI for science and neural operators": ("Machine Learning", "AI for Science", "Neural Operators"),
    "AI scaling": ("Machine Learning", "Scaling Laws"),
    "Active matter and control": ("Active Matter", "Machine Learning"),
    "Compression, intelligence, and world models": ("Machine Learning", "Information Theory", "World Models"),
    "Curated AI × physics papers": ("Machine Learning", "Statistical Physics"),
    "Data-driven active-matter hydrodynamics": ("Active Matter", "Fluid Dynamics", "Machine Learning"),
    "Field theory and path integrals for AI": ("Machine Learning", "Statistical Physics", "Field Theory"),
    "High-dimensional statistics and statistical field theory": ("Machine Learning", "Statistical Physics"),
    "Interpretable ML and physical computing": ("Machine Learning", "AI for Science"),
    "Neural operators and stochastic dynamics": ("Machine Learning", "Scientific ML", "Neural Operators"),
    "Physical Review AI/ML papers": ("Machine Learning",),
    "RG and neural scaling": ("Machine Learning", "Statistical Physics", "Renormalization Group", "Scaling Laws"),
    "RG × generative models": ("Machine Learning", "Statistical Physics", "Renormalization Group", "Generative Models"),
    "RG × information theory": ("Statistical Physics", "Renormalization Group", "Information Theory"),
    "RG, flows, and diffusion": ("Machine Learning", "Statistical Physics", "Renormalization Group", "Generative Models"),
    "Training dynamics and physics of learning": ("Machine Learning", "Statistical Physics", "Training Dynamics"),
    "Transformer theory": ("Machine Learning", "Transformer Theory"),
    "Video generation": ("Machine Learning", "Video Generation"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--date", default=date.today().isoformat())
    return parser.parse_args()


def normalized_title(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", errors="ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", ascii_value.casefold())


def arxiv_id(value: str) -> str | None:
    match = ARXIV.search(urllib.parse.unquote(value))
    return match.group(1).casefold() if match else None


def doi_id(value: str) -> str | None:
    match = DOI.search(urllib.parse.unquote(value))
    if not match:
        return None
    identifier = match.group(1).rstrip(".,;:)]}").casefold()
    return re.sub(r"(?:\.pdf|/pdf|/full|/abstract)$", "", identifier, flags=re.IGNORECASE)


def canonical_url(value: str) -> str:
    value = value.strip()
    arxiv = arxiv_id(value)
    if arxiv and "arxiv" in value.casefold():
        return f"https://arxiv.org/abs/{arxiv}"
    doi = doi_id(value)
    if doi and ("doi.org" in value.casefold() or value.casefold().startswith("doi:")):
        return f"https://doi.org/{doi}"
    parsed = urllib.parse.urlsplit(value)
    host = parsed.netloc.casefold().removeprefix("www.")
    path = re.sub(r"/$", "", parsed.path)
    return urllib.parse.urlunsplit(("https", host, path, parsed.query, ""))


def identity_keys(title: str, url: str) -> set[str]:
    keys = {f"title:{normalized_title(title)}", f"url:{canonical_url(url).casefold()}"}
    if identifier := arxiv_id(url):
        keys.add(f"arxiv:{identifier}")
    if identifier := doi_id(url):
        keys.add(f"doi:{identifier}")
    return keys


def source_tag(paper: dict[str, Any], url: str) -> str:
    identifier_type = str(paper.get("identifier_type", "")).casefold()
    host = urllib.parse.urlsplit(url).netloc.casefold()
    venue = str(paper.get("venue", "")).casefold()
    if identifier_type == "arxiv" or "arxiv.org" in host:
        return "arXiv"
    if identifier_type == "openreview" or "openreview.net" in host:
        return "OpenReview"
    if "proceedings" in host or "proceedings" in venue or "conference" in venue:
        return "Conference"
    return "Journal"


def topic_tags(categories: list[str]) -> list[str]:
    tags: list[str] = []
    for category in categories:
        key = category.partition(" / ")[0]
        for tag in CATEGORY_TAGS.get(key, ()):
            if tag not in tags:
                tags.append(tag)
    return tags


def main() -> None:
    args = parse_args()
    papers: list[dict[str, Any]] = json.loads(args.source.read_text(encoding="utf-8"))
    catalog: list[dict[str, Any]] = json.loads(args.catalog.read_text(encoding="utf-8"))

    key_to_index: dict[str, int] = {}
    for index, item in enumerate(catalog):
        for key in identity_keys(item["title"], item["url"]):
            key_to_index.setdefault(key, index)

    added: list[dict[str, str]] = []
    updated: list[dict[str, Any]] = []
    unchanged_duplicates: list[dict[str, str]] = []
    matched_catalog_ids: set[str] = set()

    for paper in papers:
        title = str(paper["title"]).strip()
        url = canonical_url(str(paper.get("canonical_link") or paper["link"]))
        incoming_tags = paper_tags(
            source_tag(paper, url),
            title,
            topic_tags(list(paper.get("categories", []))),
        )
        keys = identity_keys(title, url)
        duplicate_index = next((key_to_index[key] for key in keys if key in key_to_index), None)

        if duplicate_index is not None:
            item = catalog[duplicate_index]
            old_tags = list(item["tags"])
            item["tags"] = paper_tags(incoming_tags[0], item["title"], [*old_tags, incoming_tags[1]])
            matched_catalog_ids.add(item["id"])
            record = {"id": item["id"], "title": item["title"], "matched_title": title}
            if item["tags"] != old_tags:
                record["tags_added"] = [tag for tag in item["tags"] if tag not in old_tags]
                updated.append(record)
            else:
                unchanged_duplicates.append(record)
            continue

        stable_key = sorted(key for key in keys if not key.startswith("title:"))[0]
        item = {
            "id": hashlib.sha256(f"meaningful-chat:{stable_key}".encode("utf-8")).hexdigest()[:16],
            "date": args.date,
            "title": title,
            "url": url,
            "tags": incoming_tags,
        }
        catalog.append(item)
        matched_catalog_ids.add(item["id"])
        new_index = len(catalog) - 1
        for key in keys:
            key_to_index[key] = new_index
        added.append({"id": item["id"], "title": title, "url": url})

    ids = [item["id"] for item in catalog]
    urls = [canonical_url(item["url"]).casefold() for item in catalog]
    if len(ids) != len(set(ids)):
        raise ValueError("catalog contains duplicate IDs")
    if len(urls) != len(set(urls)):
        raise ValueError("catalog contains duplicate canonical URLs")
    if any(not item.get("title") or not item.get("tags") for item in catalog):
        raise ValueError("catalog contains an incomplete paper record")

    args.catalog.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    audit = {
        "source": str(args.source),
        "catalog": str(args.catalog),
        "import_date": args.date,
        "source_count": len(papers),
        "unique_catalog_matches": len(matched_catalog_ids),
        "added_count": len(added),
        "updated_count": len(updated),
        "unchanged_duplicate_count": len(unchanged_duplicates),
        "catalog_count": len(catalog),
        "added": added,
        "updated": updated,
        "unchanged_duplicates": unchanged_duplicates,
    }
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: audit[key] for key in (
        "source_count", "added_count", "updated_count", "unchanged_duplicate_count", "catalog_count"
    )}, ensure_ascii=False))


if __name__ == "__main__":
    main()
