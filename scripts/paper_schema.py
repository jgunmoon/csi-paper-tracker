"""Shared schema for papers/<arxiv-id>.md files.

Used by validate_papers.py (checks) and gen_pages.py (site build), so the rubric
and tag vocabulary live in one place. Keep in sync with
.claude/skills/csi-paper-review/SKILL.md (rubric table).
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PAPERS_DIR = ROOT / "papers"

# Rubric item -> max points (total 100).
RUBRIC = {
    "venue": 20,
    "channel": 15,
    "assumptions": 15,
    "baselines": 10,
    "reproducibility": 10,
    "complexity": 10,
    "industry": 5,
    "tr38843": 15,
}
RUBRIC_LABELS = {
    "venue": "게재처",
    "channel": "채널 모델",
    "assumptions": "가정 현실성",
    "baselines": "Baseline 공정성",
    "reproducibility": "재현성",
    "complexity": "복잡도 분석",
    "industry": "산업체 저자",
    "tr38843": "TR 38.843 준수",
}

# Each paper needs at least one tag from every group.
TAG_GROUPS = {
    "topic": {"compression", "prediction"},
    "method": {"AI", "non-AI"},
    "system": {"NR", "6G"},
}
ALL_TAGS = set().union(*TAG_GROUPS.values())

REQUIRED = [
    "arxiv_id", "title", "authors", "affiliation", "venue", "date", "link", "tags",
    "read_level", "reviewed", "score", "score_breakdown",
    "metrics", "channel_model", "compression_ratio", "headline_result",
]
READ_LEVELS = {"full", "abstract-only"}
SECTIONS = [
    "Key idea",
    "System model",
    "Simulation setup",
    "Results (baseline 대비)",
    "Limitations",
    "우리 업무 관점 코멘트",
]
ARXIV_ID = re.compile(r"^\d{4}\.\d{4,5}$")

_FM = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.S)


def split_front_matter(text: str) -> tuple[dict, str]:
    m = _FM.match(text)
    if not m:
        raise ValueError("missing YAML front matter (--- ... ---)")
    meta = yaml.safe_load(m.group(1)) or {}
    if not isinstance(meta, dict):
        raise ValueError("front matter is not a mapping")
    return meta, m.group(2)


def paper_files(papers_dir: Path = PAPERS_DIR) -> list[Path]:
    return sorted(p for p in papers_dir.glob("*.md") if not p.name.startswith("_"))


def load_papers(papers_dir: Path = PAPERS_DIR) -> list[tuple[Path, dict, str]]:
    out = []
    for path in paper_files(papers_dir):
        meta, body = split_front_matter(path.read_text(encoding="utf-8"))
        out.append((path, meta, body))
    return out


def as_list(value) -> list[str]:
    if value is None:
        return []
    return [str(v) for v in value] if isinstance(value, list) else [str(value)]
