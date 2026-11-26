#!/usr/bin/env python3
"""Fetch the current 3GPP RAN1 agenda and keep the CSI/MIMO/AI items.

Finds the newest RAN1 meeting folder on the 3GPP FTP server that has published
Agenda/agenda.csv, keeps the agenda items whose title (or a parent's title) matches
`ran1_agenda.terms` in config/search.yaml, and writes a snapshot to
config/ran1_agenda/RAN1_<meeting>.json. Paper files refer to these items by
(meeting, id), and the site shows their titles from the snapshots.

Usage:
    python scripts/ran1_agenda.py              # fetch newest, write snapshot, print items
    python scripts/ran1_agenda.py --meeting 127
    python scripts/ran1_agenda.py --offline    # print the newest saved snapshot only

Exit 0 on success. If 3GPP is unreachable it prints the newest saved snapshot and
exits 3, so a run can continue with the last known agenda.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/"
SNAP_DIR = ROOT / "config" / "ran1_agenda"
USER_AGENT = "csi-paper-tracker/1.0 (RAN1 agenda reader)"
DEFAULT_TERMS = ["CSI", "MIMO", "multi-antenna", "AI", "ML", "codebook", "beam", "SRS", "precod"]


def get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8-sig", "replace")


def meeting_key(folder: str) -> tuple[int, str]:
    m = re.match(r"TSGR1_(\d+)(.*)$", folder)
    return (int(m.group(1)), m.group(2)) if m else (-1, "")


def list_meetings() -> list[str]:
    html = get(BASE)
    folders = set(re.findall(r"WG1_RL1/(TSGR1_\d+[A-Za-z0-9-]*)/?\"", html))
    folders |= set(re.findall(r">(TSGR1_\d+[A-Za-z0-9-]*)<", html))
    return sorted(folders, key=meeting_key, reverse=True)


def fetch_agenda(folder: str) -> list[tuple[str, str]] | None:
    try:
        text = get(f"{BASE}{folder}/Agenda/agenda.csv")
    except Exception:
        return None
    rows = [r for r in csv.reader(io.StringIO(text)) if len(r) >= 2 and re.match(r"^\d+(\.\d+)*$", r[0].strip())]
    return [(r[0].strip(), r[1].strip()) for r in rows] or None


def meeting_name(folder: str) -> str:
    num, suffix = meeting_key(folder)
    return f"RAN1#{num}{suffix.lstrip('_-')}"


def term_pattern(terms: list[str]) -> re.Pattern:
    """Whole-word match; a trailing '*' makes a term a prefix (e.g. 'precod*')."""
    parts = [rf"\b{re.escape(t[:-1])}" if t.endswith("*") else rf"\b{re.escape(t)}\b" for t in terms]
    return re.compile("|".join(parts), re.I)


def select(items: list[tuple[str, str]], terms: list[str]) -> list[dict]:
    titles = dict(items)
    pattern = term_pattern(terms)
    out = []
    for aid, title in items:
        parts = aid.split(".")
        path = [f"{'.'.join(parts[:i])} {titles.get('.'.join(parts[:i]), '')}".strip()
                for i in range(1, len(parts))]
        own = bool(pattern.search(title))
        # Inherit relevance only from specific parents (x.y.z or deeper, e.g. "10.5.3 CSI
        # acquisition and report"), not from broad containers like "10.5 Multi-antenna system".
        parent_hit = any(pattern.search(titles.get(".".join(parts[:i]), "")) for i in range(3, len(parts)))
        if len(parts) >= 2 and (own or parent_hit) and not title.lower().startswith("maintenance"):
            top = titles.get(parts[0], "")
            out.append({"id": aid, "title": title, "path": path, "release": top})
    return out


def newest_snapshot() -> Path | None:
    snaps = sorted(SNAP_DIR.glob("RAN1_*.json"), key=lambda p: meeting_key("TSGR1_" + p.stem[5:]), reverse=True)
    return snaps[0] if snaps else None


def print_snapshot(snap: dict) -> None:
    print(f"{snap['meeting']} ({snap['source']}, fetched {snap['fetched']}) — {len(snap['items'])} items")
    for it in snap["items"]:
        print(f"  {it['id']:<10} {it['title']}   [{it['release']}]")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--meeting", help="meeting number/suffix, e.g. 127 or 128b (default: newest with an agenda)")
    ap.add_argument("--offline", action="store_true", help="do not fetch; print the newest saved snapshot")
    ap.add_argument("--config", type=Path, default=ROOT / "config" / "search.yaml")
    args = ap.parse_args()

    if not args.offline:
        cfg = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
        terms = (cfg.get("ran1_agenda") or {}).get("terms") or DEFAULT_TERMS
        try:
            folders = [f"TSGR1_{args.meeting}"] if args.meeting else list_meetings()
            for folder in folders[:6]:  # newest few; future meetings have empty Agenda folders
                items = fetch_agenda(folder)
                if not items:
                    print(f"{folder}: no agenda.csv yet", file=sys.stderr)
                    continue
                snap = {
                    "meeting": meeting_name(folder),
                    "folder": folder,
                    "source": f"{BASE}{folder}/Agenda/agenda.csv",
                    "fetched": dt.date.today().isoformat(),
                    "terms": terms,
                    "items": select(items, terms),
                }
                SNAP_DIR.mkdir(parents=True, exist_ok=True)
                path = SNAP_DIR / f"RAN1_{folder[len('TSGR1_'):]}.json"
                path.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print_snapshot(snap)
                print(f"-> {path.relative_to(ROOT)}", file=sys.stderr)
                return 0
            print("no RAN1 meeting with a published agenda.csv found", file=sys.stderr)
        except Exception as exc:
            print(f"3GPP FTP unreachable ({exc}); using the newest saved snapshot", file=sys.stderr)

    path = newest_snapshot()
    if not path:
        print("no saved snapshot in config/ran1_agenda/", file=sys.stderr)
        return 2
    print_snapshot(json.loads(path.read_text(encoding="utf-8")))
    return 0 if args.offline else 3


if __name__ == "__main__":
    sys.exit(main())
