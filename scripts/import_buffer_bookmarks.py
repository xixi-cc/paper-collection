#!/usr/bin/env python3
"""Merge article bookmarks from a Netscape-exported ``buffer`` folder."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ARXIV = re.compile(r"(?<!\d)(\d{4}\.\d{4,5})(?:v\d+)?(?!\d)", re.IGNORECASE)
DOI = re.compile(r"(10\.\d{4,9}/[^?#\s]+)", re.IGNORECASE)
EXCLUDED_HOSTS = {
    "kindxiaoming.github.io",
    "mail.nju.edu.cn",
    "mathworld.wolfram.com",
    "theses.hal.science",
    "wiki.swarma.org",
    "z-library.rs",
}
TOPICS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Active Matter", ("active matter", "flock", "vicsek", "self-propelled", "brownian matter")),
    ("Machine Learning", ("neural", "machine learning", "diffusion model", "algorithmic", "perceptron")),
    ("Statistical Physics", ("critical", "phase transition", "renormalization", "universality", "statistical mechanics")),
    ("Fluid Dynamics", ("fluid", "hydrodynamic", "faraday", "stokesian", "viscosity")),
    ("Nonreciprocal Systems", ("nonreciprocal", "non-reciprocal", "odd viscosity")),
)


class BookmarkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.folder_stack: list[str | None] = []
        self.pending_folder: str | None = None
        self.capture: str | None = None
        self.text_parts: list[str] = []
        self.anchor_attributes: dict[str, str] = {}
        self.bookmarks: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        if tag == "h3":
            self.capture = "h3"
            self.text_parts = []
        elif tag == "a":
            self.capture = "a"
            self.text_parts = []
            self.anchor_attributes = attributes
        elif tag == "dl":
            self.folder_stack.append(self.pending_folder)
            self.pending_folder = None

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h3" and self.capture == "h3":
            self.pending_folder = clean_space("".join(self.text_parts))
            self.capture = None
        elif tag == "a" and self.capture == "a":
            self.bookmarks.append({
                "folders": [folder for folder in self.folder_stack if folder],
                "title": clean_space("".join(self.text_parts)),
                "url": self.anchor_attributes.get("href", ""),
                "add_date": self.anchor_attributes.get("add_date", ""),
            })
            self.capture = None
            self.anchor_attributes = {}
        elif tag == "dl" and self.folder_stack:
            self.folder_stack.pop()


class MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.metadata: dict[str, str] = {}
        self.in_title = False
        self.title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.casefold(): value or "" for key, value in attrs}
        if tag == "meta":
            key = (attributes.get("name") or attributes.get("property") or "").casefold()
            value = attributes.get("content", "")
            if key and value:
                self.metadata[key] = clean_space(value)
        elif tag == "title":
            self.in_title = True

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def best_title(self) -> str:
        for key in ("citation_title", "dc.title", "dc:title", "og:title", "twitter:title"):
            if self.metadata.get(key):
                return self.metadata[key]
        return clean_space("".join(self.title_parts))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("favorites", type=Path)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    return parser.parse_args()


def clean_space(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", html.unescape(value))
    value = re.sub(r"\b([A-Z])\s+\(\s*([A-Z])\s*\)", r"\1(\2)", value)
    return re.sub(r"\s+", " ", value).strip()


def normalized(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", errors="ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", ascii_value.casefold())


def request_bytes(url: str, limit: int = 2_000_000) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "XixiPaperCollection/1.0 (mailto:xixi@example.com)"})
    with urllib.request.urlopen(request, timeout=25) as response:
        return response.read(limit)


def fetch_arxiv_titles(identifiers: set[str]) -> dict[str, str]:
    titles: dict[str, str] = {}
    ordered = sorted(identifiers)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    for start in range(0, len(ordered), 30):
        batch = ordered[start:start + 30]
        query = urllib.parse.urlencode({"id_list": ",".join(batch), "max_results": len(batch)})
        try:
            root = ET.fromstring(request_bytes("https://export.arxiv.org/api/query?" + query))
            for entry in root.findall("atom:entry", namespace):
                raw_id = entry.findtext("atom:id", default="", namespaces=namespace).partition("/abs/")[2]
                identifier = re.sub(r"v\d+$", "", raw_id)
                title = clean_space(entry.findtext("atom:title", default="", namespaces=namespace))
                if identifier and title:
                    titles[identifier.casefold()] = title
        except Exception:
            pass
        time.sleep(0.3)
    return titles


def doi_from_url(url: str) -> str | None:
    decoded = urllib.parse.unquote(url)
    match = DOI.search(decoded)
    if not match:
        return None
    identifier = match.group(1).rstrip(".,;:)]}")
    identifier = re.sub(r"(?:\.pdf|/pdf|/meta|/abstract)$", "", identifier, flags=re.IGNORECASE)
    return identifier


def crossref_title(identifier: str) -> str | None:
    url = "https://api.crossref.org/works/" + urllib.parse.quote(identifier, safe="")
    try:
        message = json.loads(request_bytes(url).decode("utf-8"))["message"]
        return clean_space((message.get("title") or [""])[0]) or None
    except Exception:
        return None


def crossref_title_search(query_title: str) -> str | None:
    query = urllib.parse.urlencode({"query.title": query_title, "rows": 3, "select": "title"})
    try:
        items = json.loads(request_bytes("https://api.crossref.org/works?" + query).decode("utf-8"))["message"]["items"]
    except Exception:
        return None
    candidates = [clean_space((item.get("title") or [""])[0]) for item in items]
    candidates = [candidate for candidate in candidates if candidate]
    if not candidates:
        return None
    best = max(candidates, key=lambda candidate: SequenceMatcher(None, normalized(query_title), normalized(candidate)).ratio())
    score = SequenceMatcher(None, normalized(query_title), normalized(best)).ratio()
    return best if score >= 0.78 else None


def page_title(url: str) -> str | None:
    try:
        parser = MetadataParser()
        parser.feed(request_bytes(url).decode("utf-8", errors="replace"))
        return parser.best_title() or None
    except Exception:
        return None


def canonical_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    host = parsed.netloc.casefold()
    path = parsed.path
    if host in {"arxiv.org", "www.arxiv.org"}:
        match = ARXIV.search(path)
        if match:
            return f"https://arxiv.org/abs/{match.group(1)}"
    if host == "ar5iv.labs.arxiv.org":
        match = ARXIV.search(path)
        if match:
            return f"https://arxiv.org/abs/{match.group(1)}"
    if host == "journals.aps.org":
        path = path.replace("/pdf/", "/abstract/")
    if host == "link.springer.com":
        identifier = doi_from_url(url)
        if identifier:
            return f"https://doi.org/{identifier}"
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def clean_bookmark_title(title: str) -> str:
    if title.startswith("Phys. Rev.") and " - " in title:
        title = title.split(" - ", 1)[1]
    for separator in (" | Phys. Rev.", " |物理评论", " | Nature", " |自然物理", " | AIP", " |数学物理", " - ScienceDirect", " — Google DeepMind"):
        if separator in title:
            title = title.split(separator, 1)[0]
    return clean_space(title)


def source_tag(url: str) -> str:
    host = urllib.parse.urlsplit(url).netloc.casefold()
    if host == "arxiv.org":
        return "arXiv"
    if host == "deepmind.google":
        return "Research page"
    return "Journal"


def topic_tag(title: str) -> str | None:
    lowered = title.casefold()
    for topic, terms in TOPICS:
        if any(term in lowered for term in terms):
            return topic
    return None


def bookmark_date(raw_value: str) -> str:
    try:
        return datetime.fromtimestamp(int(raw_value), tz=timezone.utc).date().isoformat()
    except (OSError, OverflowError, TypeError, ValueError):
        return datetime.now(tz=timezone.utc).date().isoformat()


def main() -> None:
    args = parse_args()
    parser = BookmarkParser()
    parser.feed(args.favorites.read_text(encoding="utf-8", errors="replace"))
    buffer_items = [
        bookmark for bookmark in parser.bookmarks
        if any(folder.casefold() == "buffer" for folder in bookmark["folders"])
    ]

    candidates: list[dict[str, Any]] = []
    audit_entries: list[dict[str, Any]] = []
    for bookmark in buffer_items:
        parsed = urllib.parse.urlsplit(bookmark["url"])
        excluded = (
            parsed.scheme not in {"http", "https"}
            or parsed.netloc.casefold() in EXCLUDED_HOSTS
            or (parsed.netloc.casefold() == "www.uni-muenster.de" and parsed.path.endswith("/SH.pdf"))
        )
        if excluded:
            audit_entries.append({"title": bookmark["title"], "url": bookmark["url"], "status": "excluded_non_article"})
            continue
        bookmark["canonical_url"] = canonical_url(bookmark["url"])
        candidates.append(bookmark)

    arxiv_ids = {
        match.group(1)
        for bookmark in candidates
        if (match := ARXIV.search(bookmark["canonical_url"]))
    }
    arxiv_titles = fetch_arxiv_titles(arxiv_ids)
    existing: list[dict[str, Any]] = json.loads(args.catalog.read_text(encoding="utf-8"))
    existing_by_url = {
        canonical_url(paper["url"]).casefold(): paper
        for paper in existing
        if paper.get("url")
    }
    known_urls = set(existing_by_url)
    known_titles = {normalized(paper["title"]) for paper in existing}
    additions: list[dict[str, Any]] = []

    for bookmark in candidates:
        url = bookmark["canonical_url"]
        title = ""
        method = "bookmark_title"
        arxiv_match = ARXIV.search(url)
        if arxiv_match:
            title = arxiv_titles.get(arxiv_match.group(1).casefold(), "")
            if title:
                method = "arxiv_metadata"
        if not title:
            identifier = doi_from_url(url)
            if identifier:
                title = crossref_title(identifier) or ""
                if title:
                    method = "crossref_metadata"
                time.sleep(0.08)
        if not title:
            title = page_title(url) or ""
            if title:
                method = "page_metadata"
        if not title:
            query_title = clean_bookmark_title(bookmark["title"])
            if urllib.parse.urlsplit(url).netloc.casefold() == "pubs.aip.org":
                slug = urllib.parse.urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
                if "-" in slug:
                    query_title = clean_space(slug.replace("-", " "))
            title = crossref_title_search(query_title) or ""
            if title:
                method = "crossref_title_match"
                time.sleep(0.08)
        if not title:
            title = clean_bookmark_title(bookmark["title"])

        title_key = normalized(title)
        url_key = canonical_url(url).casefold()
        if url_key in known_urls:
            existing_paper = existing_by_url[url_key]
            if "Browser bookmark" in existing_paper.get("tags", []) and existing_paper["title"] != title:
                known_titles.discard(normalized(existing_paper["title"]))
                existing_paper["title"] = title
                known_titles.add(title_key)
                audit_entries.append({"title": title, "url": url, "status": "updated_existing", "title_method": method})
            else:
                audit_entries.append({"title": title, "url": url, "status": "duplicate_existing"})
            continue
        if title_key in known_titles:
            audit_entries.append({"title": title, "url": url, "status": "duplicate_existing"})
            continue

        tags = [source_tag(url), "Browser bookmark"]
        topic = topic_tag(title)
        if topic:
            tags.append(topic)
        additions.append({
            "id": hashlib.sha256(f"bookmark:{url_key}".encode()).hexdigest()[:16],
            "date": bookmark_date(bookmark["add_date"]),
            "title": title,
            "url": url,
            "tags": tags,
        })
        known_urls.add(url_key)
        known_titles.add(title_key)
        audit_entries.append({"title": title, "url": url, "status": "added", "title_method": method})

    merged = existing + additions
    args.catalog.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    status_counts: dict[str, int] = {}
    for entry in audit_entries:
        status_counts[entry["status"]] = status_counts.get(entry["status"], 0) + 1
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps({
        "buffer_bookmarks": len(buffer_items),
        "article_candidates": len(candidates),
        "catalog_before": len(existing),
        "catalog_after": len(merged),
        "status_counts": status_counts,
        "entries": audit_entries,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "buffer_bookmarks": len(buffer_items),
        "article_candidates": len(candidates),
        "catalog_before": len(existing),
        "catalog_after": len(merged),
        "status_counts": status_counts,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
