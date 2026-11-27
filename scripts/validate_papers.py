#!/usr/bin/env python3
"""Validate papers/*.md (front matter schema, score arithmetic, tags, body sections) and
tdocs/RAN1_<meeting>/<agenda>.md (RAN1 meeting summaries).

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
    EXCLUDED_FILE, STANDARD_LEVELS, TDOC_REQUIRED, TDOC_SECTIONS, TDOC_STATUS,
    RUBRIC_LABELS, TAKEAWAY_SECTION, score_reasons, takeaway,
    as_list, load_agendas, load_excluded, paper_files, split_front_matter, tdoc_files,
)

MAY_BE_EMPTY = {"ran1_agenda"}  # empty list = no direct current RAN1 agenda item

ABSTRACT_BANNER = "abstract only"


AGENDAS = load_agendas()


def check_standard(meta: dict) -> list[str]:
    """3GPP relevance: score level, agenda items, and the meeting they come from."""
    errs = []
    level = (meta.get("score_breakdown") or {}).get("standard")
    agenda = meta.get("ran1_agenda")
    meeting = str(meta.get("ran1_meeting", ""))
    if level not in STANDARD_LEVELS:
        errs.append(f"score_breakdown.standard must be one of {sorted(STANDARD_LEVELS)} "
                    f"(0 = not cellular -> do not summarise the paper)")
    if not isinstance(agenda, list):
        return errs + ["'ran1_agenda' must be a list of agenda item ids, e.g. [\"9.1.1\"] or []"]
    if level in (15, 11) and not agenda:
        errs.append(f"standard={level} needs at least one ran1_agenda item")
    if level == 7 and agenda:
        errs.append("standard=7 means no direct current agenda item; leave ran1_agenda empty or raise the level")
    if meeting not in AGENDAS:
        errs.append(f"ran1_meeting '{meeting}' has no snapshot in config/ran1_agenda/ "
                    f"(known: {sorted(AGENDAS)}); run scripts/ran1_agenda.py")
    else:
        for item in agenda:
            if str(item) not in AGENDAS[meeting]:
                errs.append(f"ran1_agenda item '{item}' is not in the {meeting} snapshot")
    return errs


def check(path: Path) -> list[str]:
    errs: list[str] = []
    try:
        meta, body = split_front_matter(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [str(exc)]

    for key in REQUIRED:
        if key not in meta or meta[key] is None or meta[key] == "":
            errs.append(f"missing '{key}'")
        elif meta[key] == [] and key not in MAY_BE_EMPTY:
            errs.append(f"'{key}' is empty")

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

    errs += check_standard(meta)

    headings = re.findall(r"^##\s+(.+?)\s*$", body, re.M)
    for sec in SECTIONS:
        if sec not in headings:
            errs.append(f"missing body section '## {sec}'")
    if "## 점수 근거" not in body:
        errs.append("missing body section '## 점수 근거'")
    else:
        # The site shows per-item scores only from this table, so it must match the front matter.
        reasons = score_reasons(body)
        for item, max_pts in RUBRIC.items():
            label, val = RUBRIC_LABELS[item], breakdown.get(item)
            want = f"{val:g}/{max_pts}" if isinstance(val, (int, float)) else None
            if label not in reasons:
                errs.append(f"'## 점수 근거' table has no '{label}' row (n/{max_pts})")
            elif want and reasons[label] != want:
                errs.append(f"'## 점수 근거' {label} is {reasons[label]} but score_breakdown.{item} is {want}")
    if TAKEAWAY_SECTION in headings and not takeaway(body):
        errs.append(f"'## {TAKEAWAY_SECTION}' needs a first bullet (the page's one-line conclusion)")
    if level == "abstract-only" and ABSTRACT_BANNER not in body.lower():
        errs.append("read_level is abstract-only but the body has no 'abstract only' banner")
    return errs


TDOC_LINK_RE = re.compile(r"https://www\.3gpp\.org/ftp/tsg_ran/WG1_RL1/(TSGR1_[0-9A-Za-z]+)/(?:Docs|Inbox)/(R1-\d{7})\.zip")


def check_tdoc(path: Path) -> list[str]:
    """tdocs/RAN1_<meeting>/<agenda>.md: front matter, agenda item in snapshot, sections, links."""
    errs: list[str] = []
    try:
        meta, body = split_front_matter(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [str(exc)]
    for key in TDOC_REQUIRED:
        if key not in meta or meta[key] in (None, ""):
            errs.append(f"missing '{key}'")
    meeting, agenda = str(meta.get("meeting", "")), str(meta.get("agenda", ""))
    if path.parent.name != meeting.replace("#", "_"):
        errs.append(f"folder '{path.parent.name}' does not match meeting '{meeting}' (expected {meeting.replace('#', '_')})")
    if path.stem != agenda:
        errs.append(f"file name '{path.name}' does not match agenda '{agenda}'")
    if meeting in AGENDAS and agenda not in AGENDAS[meeting]:
        errs.append(f"agenda '{agenda}' is not in the {meeting} snapshot")
    elif meeting not in AGENDAS:
        errs.append(f"no config/ran1_agenda snapshot for {meeting}; run scripts/ran1_agenda.py --meeting ...")
    if meta.get("status") not in TDOC_STATUS:
        errs.append(f"status must be one of {sorted(TDOC_STATUS)}")
    if meta.get("status") == "provisional" and "잠정" not in body:
        errs.append("status is provisional but the body never says '잠정'")
    for key in ("history", "sources"):
        if key in meta and not isinstance(meta[key], list):
            errs.append(f"'{key}' must be a list")
    if not isinstance(meta.get("tdoc_count"), int):
        errs.append("'tdoc_count' must be an integer")
    headings = re.findall(r"^##\s+(.+?)\s*$", body, re.M)
    for sec in TDOC_SECTIONS:
        if not any(sec in h for h in headings):
            errs.append(f"missing body section containing '## {sec}'")
    folder = "TSGR1_" + meeting.split("#", 1)[-1].replace("bis", "b")
    for f, tdoc in TDOC_LINK_RE.findall(body):
        if f != folder:
            errs.append(f"link to {tdoc} points at {f}, expected {folder}")
            break
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

    tbad = 0
    tfiles = [] if args.files else tdoc_files()
    for f in tfiles:
        errs = check_tdoc(f)
        if errs:
            tbad += 1
            print(f"FAIL {f}")
            for e in errs:
                print(f"     - {e}")
        else:
            print(f"ok   {f}")
    if tfiles:
        print(f"{len(tfiles) - tbad}/{len(tfiles)} tdoc summaries valid")
    return 1 if bad or tbad else 0


if __name__ == "__main__":
    sys.exit(main())
