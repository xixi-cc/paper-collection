#!/usr/bin/env python3
"""Add verified Paper Card links to matching Paper Collection records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=Path("public/papers.json"))
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    papers = load_json(args.catalog)
    ledger = load_json(args.ledger)
    if not isinstance(papers, list) or not isinstance(ledger, list):
        raise SystemExit("catalog and ledger must both be JSON arrays")

    by_id = {str(paper.get("id")): paper for paper in papers}
    missing: list[str] = []
    changed = 0
    for entry in ledger:
        record_id = str(entry["catalog_record_id"])
        paper = by_id.get(record_id)
        if paper is None:
            missing.append(record_id)
            continue
        links = paper.setdefault("links", {})
        card_url = str(entry["card_url"])
        if links.get("card") != card_url:
            links["card"] = card_url
            changed += 1

    if missing:
        raise SystemExit(f"ledger records missing from catalog: {missing}")

    linked = sum(bool(paper.get("links", {}).get("card")) for paper in papers)
    if args.check:
        if changed:
            raise SystemExit(f"catalog is stale: {changed} Paper Card links differ")
    else:
        args.catalog.write_text(
            json.dumps(papers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(f"Paper Card links: {linked}; changed: {changed}; catalog records: {len(papers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
