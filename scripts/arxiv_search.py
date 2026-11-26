#!/usr/bin/env python3
"""Search arXiv for new CSI compression / prediction papers.

Builds one arXiv API query from config/search.yaml, keeps papers whose first
version (v1) was submitted within the last N weeks, drops IDs that already have
a papers/<id>.md file, and writes the candidates as JSON.

Usage:
    python scripts/arxiv_search.py --weeks 2 --out candidates.json
    python scripts/arxiv_search.py --ids 2611.25378,2611.11275 --out candidates.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
API = "https://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
PAGE = 100
USER_AGENT = "csi-paper-tracker/1.0 (arXiv API client)"


def existing_ids(papers_dir: Path) -> set[str]:
    return {p.stem for p in papers_dir.glob("*.md") if not p.name.startswith("_")}


def phrase(term: str) -> str:
    term = term.replace('"', "")
    if " " in term or "/" in term or "-" in term:
        return f'"{term}"'
    return term


def clause(entry) -> str:
    """One keyword entry -> (ti:x OR abs:x) [AND ...]."""
    terms = entry if isinstance(entry, list) else [entry]
    parts = [f"(ti:{phrase(t)} OR abs:{phrase(t)})" for t in terms]
    return parts[0] if len(parts) == 1 else "(" + " AND ".join(parts) + ")"


def build_query(entry, start: dt.date, end: dt.date) -> str:
    # arXiv's parser mishandles large nested OR groups (it silently returns a
    # fraction of the hits), so we send one small query per keyword entry and
    # filter categories client-side (which also covers cross-lists).
    span = f"submittedDate:[{start:%Y%m%d}0000 TO {end:%Y%m%d}2359]"
    return f"{clause(entry)} AND {span}"


def label(entry) -> str:
    return " + ".join(entry) if isinstance(entry, list) else entry


def fetch(params: dict) -> ET.Element:
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return ET.fromstring(resp.read())
        except Exception as exc:  # network hiccups / 503 throttling
            if attempt == 3:
                raise
            wait = 3 * 2**attempt
            print(f"arXiv request failed ({exc}); retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError("unreachable")


def text(el: ET.Element | None) -> str:
    return re.sub(r"\s+", " ", el.text or "").strip() if el is not None else ""


def parse_entry(e: ET.Element) -> dict:
    raw_id = text(e.find("a:id", NS)).rsplit("/abs/", 1)[-1]
    base_id = re.sub(r"v\d+$", "", raw_id)
    primary = e.find("arxiv:primary_category", NS)
    authors, affiliations = [], []
    for a in e.findall("a:author", NS):
        authors.append(text(a.find("a:name", NS)))
        affiliations += [text(x) for x in a.findall("arxiv:affiliation", NS)]
    return {
        "id": base_id,
        "version": raw_id[len(base_id):] or "v1",
        "title": text(e.find("a:title", NS)),
        "authors": authors,
        "affiliations": sorted(set(affiliations)),
        "abstract": text(e.find("a:summary", NS)),
        "categories": [c.get("term") for c in e.findall("a:category", NS)],
        "primary_category": primary.get("term") if primary is not None else None,
        "comment": text(e.find("arxiv:comment", NS)),
        "journal_ref": text(e.find("arxiv:journal_ref", NS)),
        "doi": text(e.find("arxiv:doi", NS)),
        "published": text(e.find("a:published", NS))[:10],
        "updated": text(e.find("a:updated", NS))[:10],
        "abs_url": f"https://arxiv.org/abs/{base_id}",
        "html_url": f"https://arxiv.org/html/{base_id}",
        "pdf_url": f"https://arxiv.org/pdf/{base_id}",
    }


def search_one(query: str, max_results: int) -> list[dict]:
    out: list[dict] = []
    offset = 0
    while offset < max_results:
        feed = fetch({
            "search_query": query,
            "start": offset,
            "max_results": min(PAGE, max_results - offset),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        })
        entries = feed.findall("a:entry", NS)
        out += [parse_entry(e) for e in entries if e.find("a:title", NS) is not None]
        total = int(text(feed.find("{http://a9.com/-/spec/opensearch/1.1/}totalResults")) or 0)
        offset += PAGE
        if offset >= total or not entries:
            break
        time.sleep(3)
    return out


def search(cfg: dict, start: dt.date, end: dt.date, max_results: int) -> list[dict]:
    cats = set(cfg["categories"])
    merged: dict[str, dict] = {}
    for i, entry in enumerate(cfg["keywords"]):
        if i:
            time.sleep(3)  # arXiv API etiquette: one request every 3 seconds
        hits = search_one(build_query(entry, start, end), max_results)
        kept = 0
        for p in hits:
            if not cats.intersection(p["categories"]):
                continue
            kept += 1
            merged.setdefault(p["id"], {**p, "matched_keywords": []})["matched_keywords"].append(label(entry))
        print(f"  {label(entry):<32} {len(hits):>3} hits, {kept:>3} in {sorted(cats)}", file=sys.stderr)
    return list(merged.values())


def by_ids(ids: list[str]) -> list[dict]:
    feed = fetch({"id_list": ",".join(ids), "max_results": len(ids)})
    return [parse_entry(e) for e in feed.findall("a:entry", NS) if e.find("a:title", NS) is not None]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weeks", type=int, default=2, help="look back this many weeks (default 2)")
    ap.add_argument("--ids", help="comma-separated arXiv IDs; skips the keyword search")
    ap.add_argument("--max-results", type=int, default=300)
    ap.add_argument("--config", type=Path, default=ROOT / "config" / "search.yaml")
    ap.add_argument("--papers-dir", type=Path, default=ROOT / "papers")
    ap.add_argument("--include-existing", action="store_true", help="do not drop IDs already in papers/")
    ap.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--out", type=Path, help="write JSON here (default: stdout)")
    args = ap.parse_args()

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    start = args.today - dt.timedelta(weeks=args.weeks)

    if args.ids:
        ids = [re.sub(r"v\d+$", "", i.strip()) for i in args.ids.split(",") if i.strip()]
        found = by_ids(ids)
        mode = "ids"
    else:
        found = search(cfg, start, args.today, args.max_results)
        mode = "search"

    # De-duplicate (cross-lists can repeat) and keep v1 submissions inside the window.
    seen: dict[str, dict] = {}
    for p in found:
        seen.setdefault(p["id"], p)
    papers = list(seen.values())
    if mode == "search":
        papers = [p for p in papers if p["published"] >= start.isoformat()]

    must = [m.lower() for m in cfg.get("must_mention_any", [])]
    off_topic = []
    if must and mode == "search":
        keep = []
        for p in papers:
            blob = (p["title"] + " " + p["abstract"]).lower()
            (keep if any(m in blob for m in must) else off_topic).append(p)
        papers = keep

    have = set() if args.include_existing else existing_ids(args.papers_dir)
    duplicates = sorted(p["id"] for p in papers if p["id"] in have)
    papers = [p for p in papers if p["id"] not in have]

    result = {
        "mode": mode,
        "window": {"from": start.isoformat(), "to": args.today.isoformat(), "weeks": args.weeks},
        "counts": {
            "returned_by_arxiv": len(found),
            "unique_in_window": len(seen) if mode == "ids" else len(papers) + len(duplicates),
            "dropped_off_topic": len(off_topic),
            "skipped_existing": len(duplicates),
            "candidates": len(papers),
        },
        "skipped_existing": duplicates,
        "dropped_off_topic": [{"id": p["id"], "title": p["title"]} for p in off_topic],
        "candidates": papers,
    }
    blob = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(blob + "\n", encoding="utf-8")
        c = result["counts"]
        print(f"{c['candidates']} candidates ({c['skipped_existing']} already in papers/, "
              f"{c['dropped_off_topic']} off-topic) -> {args.out}", file=sys.stderr)
    else:
        print(blob)
    return 0


if __name__ == "__main__":
    sys.exit(main())
