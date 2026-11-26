"""Build-time page generator for MkDocs (run by the mkdocs-gen-files plugin).

Reads papers/*.md at the repository root and writes, into the virtual docs tree:
  papers/<id>.md   one page per paper (metadata card + score table + body)
  papers/index.md  list of all papers, newest first
  compare.md       comparison table with tag filters (see docs/assets/compare.js)
  rubric.md        scoring rubric copied from the skill's SKILL.md
  SUMMARY.md       site navigation (read by the literate-nav plugin)

Nothing here is committed; papers/*.md stay the single source of truth.
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

import mkdocs_gen_files
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_schema import RUBRIC, RUBRIC_LABELS, TAG_GROUPS, as_list, load_papers  # noqa: E402

GROUP_LABELS = {"topic": "주제", "method": "방법", "system": "시스템"}


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def score_class(score) -> str:
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "csi-score--na"
    return "csi-score--high" if s >= 70 else "csi-score--mid" if s >= 50 else "csi-score--low"


def paper_page(meta: dict, body: str) -> str:
    aid = meta["arxiv_id"]
    fm = {"title": meta["title"], "tags": as_list(meta.get("tags"))}
    lines = ["---", yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip(), "---", ""]
    lines.append(f"# {meta['title']}")
    lines.append("")
    if meta.get("read_level") == "abstract-only":
        lines += ['!!! warning "abstract only"',
                  "    전문을 읽지 못해 초록만으로 요약·채점했습니다. 수치와 점수는 잠정치입니다.", ""]
    tag_html = " ".join(f'<span class="csi-tag">{esc(t)}</span>' for t in as_list(meta.get("tags")))
    lines += [
        '<div class="csi-card" markdown>',
        "",
        "| | |",
        "|---|---|",
        f"| **arXiv** | [{aid}]({meta['link']}) · v1 {meta.get('date', '?')} |",
        f"| **Authors** | {', '.join(as_list(meta.get('authors')))} |",
        f"| **Affiliation** | {'; '.join(as_list(meta.get('affiliation')))} |",
        f"| **Venue** | {meta.get('venue', '?')} |",
        f"| **Tags** | {tag_html} |",
        f"| **Metrics** | {', '.join(as_list(meta.get('metrics')))} |",
        f"| **Channel model** | {meta.get('channel_model', '?')} |",
        f"| **Compression / payload** | {meta.get('compression_ratio', '?')} |",
        f"| **Headline** | {meta.get('headline_result', '?')} |",
        f"| **Reviewed** | {meta.get('reviewed', '?')} ({meta.get('read_level', '?')}) |",
        "",
        "</div>",
        "",
        f'<p class="csi-total">신뢰도/효용 점수 '
        f'<span class="csi-score {score_class(meta.get("score"))}">{esc(meta.get("score", "?"))}</span> / 100</p>',
        "",
        "| 항목 | 점수 | 배점 |",
        "|---|---:|---:|",
    ]
    breakdown = meta.get("score_breakdown") or {}
    for item, max_pts in RUBRIC.items():
        lines.append(f"| {RUBRIC_LABELS[item]} | {breakdown.get(item, '?')} | {max_pts} |")
    lines += ["", body.strip(), ""]
    return "\n".join(lines)


def compare_page(papers: list[dict]) -> str:
    out = [
        "---",
        "title: 논문 비교",
        "hide: [navigation, toc]",
        "---",
        "",
        "# 논문 비교",
        "",
        "태그 버튼으로 거르고, 열 제목을 눌러 정렬합니다. 같은 그룹 안에서는 OR, 그룹끼리는 AND로 적용됩니다. "
        "수치 앞의 `≈`는 논문 그래프에서 읽은 값입니다.",
        "",
        '<div class="csi-filters">',
    ]
    for group, tags in TAG_GROUPS.items():
        out.append(f'<div class="csi-filter-group" data-group="{group}"><span class="csi-filter-label">{GROUP_LABELS[group]}</span>')
        for t in sorted(tags, key=lambda x: (x.startswith("non"), x)):
            out.append(f'<button type="button" class="csi-filter" data-tag="{esc(t)}" aria-pressed="false">{esc(t)}</button>')
        out.append("</div>")
    out += [
        '<input type="search" class="csi-search" placeholder="제목·저자·채널 모델 검색" aria-label="검색">',
        '<button type="button" class="csi-reset">초기화</button>',
        '<span class="csi-count"></span>',
        "</div>",
        "",
        '<div class="csi-table-wrap"><table class="csi-compare">',
        "<thead><tr>"
        '<th data-sort="text">논문</th><th data-sort="text">v1</th><th>태그</th><th>지표</th>'
        '<th data-sort="text">채널 모델</th><th>압축률 / payload</th><th>주요 성능 (baseline 대비)</th>'
        '<th data-sort="num">점수</th></tr></thead>',
        "<tbody>",
    ]
    for m in papers:
        tags = as_list(m.get("tags"))
        search_blob = " ".join([m["title"], *as_list(m.get("authors")), *as_list(m.get("affiliation")),
                                str(m.get("channel_model", "")), str(m.get("venue", ""))]).lower()
        abstract_flag = ' <span class="csi-flag" title="abstract only">abs</span>' if m.get("read_level") == "abstract-only" else ""
        out.append(
            f'<tr data-tags="{esc(" ".join(tags))}" data-search="{esc(search_blob)}">'
            f'<td><a href="../papers/{esc(m["arxiv_id"])}/">{esc(m["title"])}</a>'
            f'<div class="csi-sub">{esc(m["arxiv_id"])} · {esc(m.get("venue", ""))}</div></td>'
            f'<td>{esc(m.get("date", ""))}</td>'
            f'<td>{" ".join(f"<span class=csi-tag>{esc(t)}</span>" for t in tags)}</td>'
            f'<td>{esc(", ".join(as_list(m.get("metrics"))))}</td>'
            f'<td>{esc(m.get("channel_model", ""))}</td>'
            f'<td>{esc(m.get("compression_ratio", ""))}</td>'
            f'<td>{esc(m.get("headline_result", ""))}</td>'
            f'<td data-value="{esc(m.get("score", 0))}"><span class="csi-score {score_class(m.get("score"))}">'
            f'{esc(m.get("score", "?"))}</span>{abstract_flag}</td>'
            "</tr>"
        )
    out += ["</tbody></table></div>", ""]
    if not papers:
        out.append("아직 등록된 논문이 없습니다.")
    return "\n".join(out)


def index_page(papers: list[dict]) -> str:
    out = ["---", "title: 전체 논문", "---", "", "# 전체 논문", "", "최근 제출(v1) 순입니다.", "",
           "| v1 | 논문 | 태그 | 점수 |", "|---|---|---|---:|"]
    for m in papers:
        tags = " ".join(f"`{t}`" for t in as_list(m.get("tags")))
        flag = " ⚠️" if m.get("read_level") == "abstract-only" else ""
        out.append(f"| {m.get('date', '')} | [{m['title']}]({m['arxiv_id']}.md){flag} | {tags} | {m.get('score', '?')} |")
    if not papers:
        out.append("| | 아직 등록된 논문이 없습니다. | | |")
    return "\n".join(out) + "\n"


def rubric_page() -> str:
    """Copy the rubric section out of SKILL.md so the site never drifts from the skill."""
    skill = Path(__file__).resolve().parent.parent / ".claude/skills/csi-paper-review/SKILL.md"
    text = skill.read_text(encoding="utf-8")
    try:
        section = text.split("<!-- rubric:start -->", 1)[1].split("<!-- rubric:end -->", 1)[0]
    except IndexError:
        section = "rubric 구간을 SKILL.md에서 찾지 못했습니다."
    section = section.replace("### 신뢰도/효용 Rubric", "## 신뢰도/효용 Rubric")
    return "\n".join([
        "---", "title: 점수 기준", "---", "", "# 점수 기준", "",
        "이 페이지는 `.claude/skills/csi-paper-review/SKILL.md` 의 rubric을 그대로 가져온 것입니다. "
        "기준을 바꾸려면 SKILL.md를 수정하세요 (`scripts/paper_schema.py` 의 배점도 함께).",
        "",
        "점수 색: 70 이상 높음 · 50–69 중간 · 50 미만 낮음.",
        section.strip(), "",
    ])


def main() -> None:
    entries = load_papers()
    metas = []
    for path, meta, body in entries:
        meta.setdefault("arxiv_id", path.stem)
        metas.append(meta)
        virtual = f"papers/{meta['arxiv_id']}.md"
        with mkdocs_gen_files.open(virtual, "w") as f:
            f.write(paper_page(meta, body))
        mkdocs_gen_files.set_edit_path(virtual, f"../papers/{path.name}")

    metas.sort(key=lambda m: str(m.get("date", "")), reverse=True)
    with mkdocs_gen_files.open("papers/index.md", "w") as f:
        f.write(index_page(metas))
    with mkdocs_gen_files.open("compare.md", "w") as f:
        f.write(compare_page(metas))
    nav = ["* [홈](index.md)", "* [비교 표](compare.md)", "* [태그](tags.md)", "* [논문](papers/index.md)"]
    for m in metas:
        short = m["title"] if len(m["title"]) <= 60 else m["title"][:57].rstrip() + "…"
        nav.append(f"    * [{m['arxiv_id']} · {short}](papers/{m['arxiv_id']}.md)")
    nav.append("* [점수 기준](rubric.md)")
    with mkdocs_gen_files.open("SUMMARY.md", "w") as f:
        f.write("\n".join(nav) + "\n")
    with mkdocs_gen_files.open("rubric.md", "w") as f:
        f.write(rubric_page())
    mkdocs_gen_files.set_edit_path("rubric.md", "../.claude/skills/csi-paper-review/SKILL.md")


main()
