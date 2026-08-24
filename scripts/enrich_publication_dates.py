#!/usr/bin/env python3
"""Add publication dates to catalog records from public bibliographic metadata."""

from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ARXIV = re.compile(r"arxiv\.org/abs/((?:\d{4}\.\d{4,5})|(?:[^/]+/\d{7}))", re.IGNORECASE)
DOI = re.compile(r"(10\.\d{4,9}/[^?#\s]+)", re.IGNORECASE)
ISO_DATE = re.compile(r"\b((?:19|20)\d{2})(?:[-/](\d{1,2})(?:[-/](\d{1,2}))?)?\b")
USER_AGENT = "XncaoPaperCollection/1.0 (https://xixi-paper-collection.lezontbukercfdvs4.chatgpt.site)"


class MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        attributes = {key.casefold(): value or "" for key, value in attrs}
        key = (attributes.get("name") or attributes.get("property") or attributes.get("itemprop")).casefold()
        if key in {
            "article:published_time",
            "citation_date",
            "citation_online_date",
            "citation_publication_date",
            "date",
            "datepublished",
            "dc.date",
            "dc.date.issued",
            "prism.publicationdate",
        }:
            self.values.append(attributes.get("content", ""))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--metadata-source", action="append", type=Path, default=[])
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--refresh", action="store_true")
    return parser.parse_args()


def normalized_title(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", errors="ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", ascii_value.casefold())


def format_date(parts: list[int] | tuple[int, ...]) -> str | None:
    if not parts or not 1800 <= int(parts[0]) <= 2100:
        return None
    values = [int(value) for value in parts[:3]]
    if len(values) == 1:
        return f"{values[0]:04d}"
    if not 1 <= values[1] <= 12:
        return f"{values[0]:04d}"
    if len(values) == 2 or not 1 <= values[2] <= 31:
        return f"{values[0]:04d}-{values[1]:02d}"
    return f"{values[0]:04d}-{values[1]:02d}-{values[2]:02d}"


def parse_date(value: str) -> str | None:
    match = ISO_DATE.search(value)
    if not match:
        return None
    return format_date([int(part) for part in match.groups() if part])


def arxiv_date(url: str) -> str | None:
    match = ARXIV.search(url)
    if not match:
        return None
    identifier = match.group(1)
    if "." in identifier:
        return f"20{identifier[:2]}-{identifier[2:4]}"
    digits = identifier.rsplit("/", 1)[1]
    year = int(digits[:2])
    return f"{1900 + year if year >= 91 else 2000 + year:04d}-{digits[2:4]}"


def doi_from_url(url: str) -> str | None:
    match = DOI.search(urllib.parse.unquote(url))
    return match.group(1).rstrip(".,;:)]}") if match else None


def request_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read(4_000_000).decode("utf-8"))


def crossref_date(doi: str) -> str | None:
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    message = request_json(url)["message"]
    candidates: list[str] = []
    for key in ("published-online", "published-print", "published", "issued"):
        parts = ((message.get(key) or {}).get("date-parts") or [[]])[0]
        if value := format_date(parts):
            candidates.append(value)
    return min(candidates) if candidates else None


def crossref_title_date(title: str) -> str | None:
    clean_title = re.split(r"\s+(?:[-|])\s+(?:PMC|PubMed|ScienceDirect|OpenReview)", title, maxsplit=1)[0]
    query = urllib.parse.urlencode({
        "query.bibliographic": clean_title,
        "rows": 3,
        "select": "title,published,published-online,published-print,issued",
    })
    items = request_json("https://api.crossref.org/works?" + query)["message"]["items"]
    expected = normalized_title(clean_title)
    matches: list[tuple[float, str]] = []
    for item in items:
        candidate = str((item.get("title") or [""])[0])
        score = SequenceMatcher(None, expected, normalized_title(candidate)).ratio()
        dates: list[str] = []
        for key in ("published-online", "published-print", "published", "issued"):
            parts = ((item.get(key) or {}).get("date-parts") or [[]])[0]
            if value := format_date(parts):
                dates.append(value)
        if dates:
            matches.append((score, min(dates)))
    if not matches:
        return None
    score, date = max(matches)
    return date if score >= 0.9 else None


def openreview_date(url: str) -> str | None:
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    identifier = (query.get("id") or [None])[0]
    if not identifier:
        return None
    payload = request_json(
        "https://api2.openreview.net/notes?" + urllib.parse.urlencode({"forum": identifier, "limit": 20})
    )
    notes = payload.get("notes") or []
    text = json.dumps(notes, ensure_ascii=False)
    venue_years = [
        int(year)
        for year in re.findall(
            r"\b(?:ICLR|ICML|NeurIPS|AISTATS|UAI|TMLR)\s*((?:19|20)\d{2})\b",
            text,
            re.IGNORECASE,
        )
    ]
    if venue_years:
        return str(min(venue_years))
    timestamps = [note.get("pdate") or note.get("odate") or note.get("cdate") for note in notes]
    timestamps = [int(value) for value in timestamps if value]
    if timestamps:
        return time.strftime("%Y-%m-%d", time.gmtime(min(timestamps) / 1000))
    return None


def page_date(url: str) -> str | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=25) as response:
        text = response.read(2_000_000).decode("utf-8", errors="replace")
    parser = MetadataParser()
    parser.feed(text)
    dates = [value for value in (parse_date(item) for item in parser.values) if value]
    if dates:
        return min(dates)
    json_ld_dates = re.findall(r'"datePublished"\s*:\s*"([^"]+)"', text, re.IGNORECASE)
    dates = [value for value in (parse_date(item) for item in json_ld_dates) if value]
    return min(dates) if dates else None


def url_date(url: str) -> str | None:
    if match := re.search(r"proceedings\.mlr\.press/v\d+/[^/]*?(\d{2})[a-z]\.html", url, re.IGNORECASE):
        return f"20{match.group(1)}"
    patterns = (
        r"/(?:paper_files/paper|paper)/(20\d{2})/",
        r"/v\d+/[^/]*?((?:19|20)\d{2})[a-z]?\.html",
        r"/article/(20\d{2})/",
    )
    for pattern in patterns:
        if match := re.search(pattern, url, re.IGNORECASE):
            return match.group(1)
    return None


def metadata_years(paths: list[Path]) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in paths:
        for paper in json.loads(path.read_text(encoding="utf-8")):
            if paper.get("year"):
                result[normalized_title(str(paper["title"]))] = str(paper["year"])
    return result


def resolve_publication(paper: dict[str, Any], local_years: dict[str, str]) -> tuple[str | None, str]:
    url = str(paper.get("url", ""))
    if value := arxiv_date(url):
        return value, "arxiv_identifier"
    if doi := doi_from_url(url):
        try:
            if value := crossref_date(doi):
                return value, "crossref"
        except Exception:
            pass
    if "openreview.net" in urllib.parse.urlsplit(url).netloc.casefold():
        try:
            if value := openreview_date(url):
                return value, "openreview"
        except Exception:
            pass
    if value := local_years.get(normalized_title(str(paper["title"]))):
        return value, "verified_local_metadata"
    if value := url_date(url):
        return value, "url"
    try:
        if value := page_date(url):
            return value, "page_metadata"
    except Exception:
        pass
    try:
        if value := crossref_title_date(str(paper["title"])):
            return value, "crossref_title"
    except Exception:
        pass
    return None, "unresolved"


def main() -> None:
    args = parse_args()
    catalog: list[dict[str, Any]] = json.loads(args.catalog.read_text(encoding="utf-8"))
    local_years = metadata_years(args.metadata_source)
    targets = [paper for paper in catalog if args.refresh or not paper.get("published")]
    results: dict[str, tuple[str | None, str]] = {}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {executor.submit(resolve_publication, paper, local_years): paper for paper in targets}
        for future in as_completed(futures):
            paper = futures[future]
            try:
                results[str(paper["id"])] = future.result()
            except Exception:
                results[str(paper["id"])] = (None, "unresolved")

    counts: dict[str, int] = {}
    unresolved: list[dict[str, str]] = []
    for paper in targets:
        published, method = results[str(paper["id"])]
        counts[method] = counts.get(method, 0) + 1
        if published:
            paper["published"] = published
        else:
            paper.pop("published", None)
            unresolved.append({
                "id": str(paper["id"]),
                "title": str(paper["title"]),
                "url": str(paper.get("url", "")),
            })

    args.catalog.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit = {
        "catalog_count": len(catalog),
        "method_counts": counts,
        "unresolved_count": len(unresolved),
        "unresolved": unresolved,
    }
    if args.audit:
        args.audit.parent.mkdir(parents=True, exist_ok=True)
        args.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        key: audit[key]
        for key in ("catalog_count", "method_counts", "unresolved_count")
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
