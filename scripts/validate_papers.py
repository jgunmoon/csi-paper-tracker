#!/usr/bin/env python3
"""Validate papers/*.md: front matter schema, score arithmetic, tags, body sections.

Exit code 0 when every file passes, 1 otherwise. Run before every commit:
    python scripts/validate_papers.py
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_schema import (  # noqa: E402
    ARXIV_ID, PAPERS_DIR, READ_LEVELS, REQUIRED, RUBRIC, SECTIONS, TAG_GROUPS, ALL_TAGS,
    EXCLUDED_FILE, as_list, load_excluded, paper_files, split_front_matter,
)

ABSTRACT_BANNER = "abstract only"


def check(path: Path) -> list[str]:
    errs: list[str] = []
    try:
        meta, body = split_front_matter(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [str(exc)]

    for key in REQUIRED:
        if key not in meta or meta[key] in (None, "", []):
            errs.append(f"missing or empty '{key}'")

    aid = str(meta.get("arxiv_id", ""))
    if not ARXIV_ID.match(aid):
        errs.append(f"arxiv_id '{aid}' is not like 2611.01234 (no version suffix)")
    elif path.stem != aid:
        errs.append(f"file name '{path.name}' does not match arxiv_id '{aid}'")
    if aid and str(meta.get("link", "")).rstrip("/") != f"https://arxiv.org/abs/{aid}":
        errs.append(f"link should be https://arxiv.org/abs/{aid}")

    for key in ("date", "reviewed"):
        val = meta.get(key)
        if val is not None and not isinstance(val, dt.date):
            try:
                dt.date.fromisoformat(str(val))
            except ValueError:
                errs.append(f"'{key}' must be YYYY-MM-DD, got {val!r}")

    for key in ("authors", "affiliation", "metrics"):
        if key in meta and not isinstance(meta[key], list):
            errs.append(f"'{key}' must be a list")

    tags = set(as_list(meta.get("tags")))
    unknown = tags - ALL_TAGS
    if unknown:
        errs.append(f"unknown tags {sorted(unknown)}; allowed: {sorted(ALL_TAGS)}")
    for group, allowed in TAG_GROUPS.items():
        if not tags & allowed:
            errs.append(f"tags need one of {sorted(allowed)} ({group})")

    level = meta.get("read_level")
    if level not in READ_LEVELS:
        errs.append(f"read_level must be one of {sorted(READ_LEVELS)}")

    breakdown = meta.get("score_breakdown") or {}
    if not isinstance(breakdown, dict):
        errs.append("score_breakdown must be a mapping")
        breakdown = {}
    if set(breakdown) != set(RUBRIC):
        errs.append(f"score_breakdown keys must be exactly {list(RUBRIC)}")
    total = 0
    for item, max_pts in RUBRIC.items():
        val = breakdown.get(item)
        if not isinstance(val, (int, float)) or not 0 <= val <= max_pts:
            errs.append(f"score_breakdown.{item}={val!r} must be a number in 0..{max_pts}")
        else:
            total += val
    score = meta.get("score")
    if not isinstance(score, (int, float)):
        errs.append(f"score must be a number, got {score!r}")
    elif abs(score - total) > 1e-9:
        errs.append(f"score {score} != sum of score_breakdown {total}")

    headings = re.findall(r"^##\s+(.+?)\s*$", body, re.M)
    for sec in SECTIONS:
        if sec not in headings:
            errs.append(f"missing body section '## {sec}'")
    if "## 점수 근거" not in body:
        errs.append("missing body section '## 점수 근거'")
    if level == "abstract-only" and ABSTRACT_BANNER not in body.lower():
        errs.append("read_level is abstract-only but the body has no 'abstract only' banner")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="*", type=Path, help="default: every papers/*.md")
    ap.add_argument("--excluded", type=Path, default=EXCLUDED_FILE, help="exclusion list to check against")
    args = ap.parse_args()
    files = args.files or paper_files(PAPERS_DIR)

    try:
        excluded = load_excluded(args.excluded)
    except Exception as exc:  # malformed YAML or entry
        print(f"FAIL {args.excluded}\n     - {exc}")
        return 1

    bad = 0
    for f in files:
        errs = check(f)
        if f.stem in excluded:
            errs.append(f"{f.stem} is in {args.excluded.name} (excluded: {excluded[f.stem].get('reason', '')}); "
                        f"delete the paper file or remove the exclusion entry")
        if errs:
            bad += 1
            print(f"FAIL {f}")
            for e in errs:
                print(f"     - {e}")
        else:
            print(f"ok   {f}")
    print(f"{len(files) - bad}/{len(files)} paper files valid")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
