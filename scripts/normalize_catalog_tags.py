#!/usr/bin/env python3
"""Normalize every catalog record to exactly one source and one topic tag."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from catalog_tags import paper_tags, source_for, validate_tag_pair


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--check", action="store_true", help="Validate without writing changes")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    catalog: list[dict[str, Any]] = json.loads(args.catalog.read_text(encoding="utf-8"))
    changed = 0
    for paper in catalog:
        old_tags = list(paper.get("tags", []))
        paper["tags"] = paper_tags(
            source_for(paper.get("url"), old_tags),
            str(paper["title"]),
            old_tags,
        )
        changed += paper["tags"] != old_tags

    invalid = [paper.get("id", "<missing>") for paper in catalog if not validate_tag_pair(paper.get("tags"))]
    if invalid:
        raise ValueError(f"invalid tag pairs: {invalid[:5]}")
    if args.check and changed:
        raise SystemExit(f"catalog needs normalization: {changed} records")
    if not args.check:
        args.catalog.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"catalog_count": len(catalog), "changed_count": changed}))


if __name__ == "__main__":
    main()
