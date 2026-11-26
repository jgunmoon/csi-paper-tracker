"""MkDocs hooks: stamp every page footer with the build (= deploy) time.

Registered in mkdocs.yml under `hooks:`. The footer reads e.g.
"마지막 업데이트 2026-11-27 08:10 KST · 논문 4편 · Tdoc 요약 5개 · 6219859".
"""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

KST = dt.timezone(dt.timedelta(hours=9), "KST")
ROOT = Path(__file__).resolve().parent.parent


def build_stamp() -> str:
    now = dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    papers = sum(1 for p in (ROOT / "papers").glob("*.md") if not p.name.startswith("_"))
    tdocs = sum(1 for p in (ROOT / "tdocs").glob("*/*.md") if not p.name.startswith("_"))
    parts = [f"마지막 업데이트 {now}", f"논문 {papers}편", f"Tdoc 요약 {tdocs}개"]
    sha = os.environ.get("GITHUB_SHA", "")[:7]  # set by GitHub Actions
    if sha:
        parts.append(sha)
    return " · ".join(parts)


def on_config(config, **kwargs):
    config["copyright"] = build_stamp()
    return config
