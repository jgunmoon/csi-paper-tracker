"""Build-time page generator for MkDocs (run by the mkdocs-gen-files plugin).

Reads papers/*.md at the repository root and writes, into the virtual docs tree:
  papers/<id>.md   one page per paper (conclusion box + metadata card + body)
  papers/index.md  list of all papers, newest first
  compare.md       comparison table with tag filters (see docs/assets/compare.js)
  rubric.md        scoring rubric copied from the skill's SKILL.md
  SUMMARY.md       site navigation (read by the literate-nav plugin)

Nothing here is committed; papers/*.md stay the single source of truth.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import sys
from pathlib import Path

import mkdocs_gen_files
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tdoc_companies import collect, company_anchor, link_section, normalise  # noqa: E402
from paper_schema import (  # noqa: E402
    ROOT, RUBRIC, RUBRIC_LABELS, TAG_GROUPS, agenda_short, as_list, first_sentence, load_agendas, load_papers,
    load_tdocs, plain, takeaway, tdoc_page_path,
)

KST = dt.timezone(dt.timedelta(hours=9), "KST")
WEEKLY_RUN = (0, 8)          # Monday 08:00 KST (claude.ai scheduled task "Weekly CSI paper review")
RECENT_DAYS = 14             # home page: papers reviewed within this many days of the newest review
RECENT_MAX = 6
HOME_MARKER = "<!-- home:latest -->"

GROUP_LABELS = {"topic": "주제", "method": "방법", "system": "시스템"}
AGENDAS = load_agendas()
NO_AGENDA = "agenda-none"
NO_POSITION = '<span class="csi-sub">입장 미표기 (요약에 Tdoc만)</span>'
TDOCS = {(str(m.get("meeting")), str(m.get("agenda"))): (p, m, b) for p, m, b in load_tdocs()}


def tdoc_url(item: dict, depth: int) -> str | None:
    """Site URL of the RAN1 summary for an agenda item, relative to a page `depth` levels deep."""
    if (item["meeting"], item["id"]) not in TDOCS:
        return None
    return "../" * depth + tdoc_page_path(item["meeting"], item["id"])[:-3] + "/"


def agenda_items(meta: dict) -> list[dict]:
    """Resolve a paper's ran1_agenda ids to snapshot items (unknown ids keep just the id)."""
    meeting = str(meta.get("ran1_meeting", ""))
    snap = AGENDAS.get(meeting, {})
    return [dict(snap.get(str(i), {"id": str(i), "title": ""}), meeting=meeting) for i in as_list(meta.get("ran1_agenda"))]


def agenda_key(item: dict) -> str:
    """Short URL key for an agenda filter, e.g. 'RAN1#127' + '9.1.1' -> '127-9.1.1'."""
    return f"{item['meeting'].replace('RAN1#', '')}-{item['id']}".replace(" ", "")


def compare_link(item: dict, depth: int) -> str:
    """Markdown link target: the compare table pre-filtered to one agenda item (query state, see compare.js).
    `depth` = folders between the linking page's source file and the docs root."""
    return "../" * depth + f"compare.md?agenda={agenda_key(item)}"


def agenda_token(item: dict) -> str:
    """Space-free filter token, e.g. 'agenda-RAN1#127-9.1.1'."""
    return f"agenda-{item['meeting']}-{item['id']}".replace(" ", "")


# Korean labels for agenda items without a RAN1 summary (those with one use the summary's own short title).
AGENDA_KO = {
    "9.1": "NR AI/ML", "9.2": "NR MIMO Phase 6", "10.5": "6GR 다중 안테나", "10.5.1.1": "6GR 동기·빔 측정",
    "10.5.2": "6GR MIMO 동작", "10.5.2.1": "6GR 하향 제어채널 전송", "10.5.2.2": "6GR 하향 데이터채널 전송",
    "10.5.2.3": "6GR 상향 전송", "10.5.3": "6GR CSI 획득·보고", "10.5.3.3": "6GR CSI 기타", "10.5.3.4": "6GR 빔 관리",
}


def agenda_label(item: dict) -> str:
    """'9.1.1 Case 0 CSI 압축 (two-sided 모델)'-style Korean label of an agenda item."""
    key = (item["meeting"], item["id"])
    if key in TDOCS:
        _, tmeta, tbody = TDOCS[key]
        return tdoc_short_title(tmeta, tbody)
    if item["id"] in AGENDA_KO:
        return f"{item['id']} {AGENDA_KO[item['id']]}"
    return agenda_short(item, 40)


def trim(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def agenda_anchor(agenda_id: str | None) -> str:
    """Heading id of an agenda group on the paper list, e.g. '9.1.1' -> 'a-9-1-1', None -> 'a-none'."""
    return "a-" + (agenda_id.replace(".", "-") if agenda_id else "none")


def agenda_md(item: dict, base: str = "") -> str:
    """Markdown label of an agenda item: the Korean short title of its RAN1 summary (linked) when one
    exists, else the snapshot title. `base` is the relative prefix to the docs root ('' or '../')."""
    key = (item["meeting"], item["id"])
    if key in TDOCS:
        _, tmeta, tbody = TDOCS[key]
        return f"[{esc(tdoc_short_title(tmeta, tbody))}]({base}{tdoc_page_path(*key)})"
    return esc(agenda_label(item))


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def score_class(score) -> str:
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "csi-score--na"
    return "csi-score--high" if s >= 70 else "csi-score--mid" if s >= 50 else "csi-score--low"


def paper_page(meta: dict, body: str) -> str:
    """Paper page: conclusion box (score, agenda, headline, takeaway) first, then the info card and the body.
    The per-item scores live in the body's '## 점수 근거' table (validated against the front matter)."""
    aid = meta["arxiv_id"]
    fm = {"title": meta["title"], "hide": ["navigation"]}  # not in the menu, so no empty left column
    lines = ["---", yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip(), "---", ""]
    # Paper pages are not in the menu (it would grow every week); this path shows where the page sits.
    crumbs = [f'<a href="../#{agenda_anchor(it["id"])}">{esc(agenda_label(it))}</a>' for it in agenda_items(meta)]
    crumbs = crumbs or [f'<a href="../#{agenda_anchor(None)}">직접 해당 없음</a>']
    lines.append(f'<p class="csi-crumb"><a href="../">논문 목록</a> › {" · ".join(crumbs)}</p>')
    lines.append("")
    lines.append(f"# {meta['title']}")
    lines.append("")
    if meta.get("read_level") == "abstract-only":
        lines += ['!!! warning "abstract only"',
                  "    전문을 읽지 못해 초록만으로 요약·채점했습니다. 수치와 점수는 잠정치입니다.", ""]
    level = (meta.get("score_breakdown") or {}).get("standard", "?")
    items = agenda_items(meta)
    meeting = str(meta.get("ran1_meeting", ""))
    agenda = (" · ".join(agenda_md(it, "../") for it in items) + f" ({meeting})") if items else "현재 안건에 직접 해당 없음"
    lines += [
        '<div class="csi-verdict" markdown>',
        "",
        f'<span class="csi-score {score_class(meta.get("score"))}">{esc(meta.get("score", "?"))}</span> / 100 · '
        f"[3GPP 관련성](../rubric.md#relevance) {esc(level)}/15 · [점수 근거 ↓](#점수-근거)",
        "",
        f'<span class="csi-label">3GPP 안건</span>{agenda}',
        "",
        f'<span class="csi-label">핵심 결과</span>{meta.get("headline_result", "?")}',
        "",
        f'<span class="csi-label">우리 업무 관점</span>{takeaway(body) or "?"}',
        "",
        "</div>",
        "",
    ]
    def tag_link(tag: str) -> str:
        group = next((g for g, tags in TAG_GROUPS.items() if tag in tags), None)
        href = f"../../compare/?{group}={tag}" if group else "../../compare/"
        return f'<a class="csi-tag" href="{esc(href)}" title="비교 표에서 {esc(tag)} 논문만 보기">{esc(tag)}</a>'
    tag_html = " ".join(tag_link(t) for t in as_list(meta.get("tags")))
    read = "전문 읽음" if meta.get("read_level") == "full" else "초록만 읽음"
    lines += [
        '<div class="csi-card" markdown>',
        "",
        "| | |",
        "|---|---|",
        f"| **arXiv** | [{aid}]({meta['link']}) · v1 {meta.get('date', '?')} |",
        f"| **저자** | {', '.join(as_list(meta.get('authors')))} |",
        f"| **소속** | {'; '.join(as_list(meta.get('affiliation')))} |",
        f"| **게재** | {meta.get('venue', '?')} |",
        f"| **태그** | {tag_html} |",
        f"| **지표** | {', '.join(as_list(meta.get('metrics')))} |",
        f"| **채널 모델** | {meta.get('channel_model', '?')} |",
        f"| **압축률 / payload** | {meta.get('compression_ratio', '?')} |",
        f"| **리뷰** | {meta.get('reviewed', '?')} · {read} |",
        "",
        "</div>",
        "",
        body.strip(),
        "",
    ]
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
        "버튼으로 거르고 정렬 메뉴나 열 제목으로 정렬합니다. 같은 그룹 안의 버튼은 OR, 그룹끼리는 AND로 적용됩니다. "
        "고른 조건은 주소에 저장되므로 **링크 복사**로 팀원에게 같은 화면을 보낼 수 있습니다. "
        "기간은 arXiv v1 제출일 기준이고, 수치 앞의 `≈`는 논문 그래프에서 읽은 값입니다.",
        "",
        '<div class="csi-filters">',
    ]
    for group, tags in TAG_GROUPS.items():
        out.append(f'<div class="csi-filter-group" data-group="{group}"><span class="csi-filter-label">{GROUP_LABELS[group]}</span>')
        for t in sorted(tags, key=lambda x: (x.startswith("non"), x)):
            out.append(f'<button type="button" class="csi-filter" data-tag="{esc(t)}" data-key="{esc(t)}" aria-pressed="false">{esc(t)}</button>')
        out.append("</div>")
    # One button per agenda item that at least one paper maps to, plus "no direct item".
    seen: dict[str, dict] = {}
    for m in papers:
        for it in agenda_items(m):
            seen.setdefault(agenda_token(it), it)
    out.append('<div class="csi-filter-group" data-group="agenda"><span class="csi-filter-label">3GPP 안건</span>')
    for token, it in sorted(seen.items(), key=lambda kv: [int(x) for x in kv[1]["id"].split(".") if x.isdigit()]):
        out.append(f'<button type="button" class="csi-filter" data-tag="{esc(token)}" data-key="{esc(agenda_key(it))}" aria-pressed="false" '
                   f'title="{esc(it["meeting"] + " " + it["id"] + " " + it.get("title", ""))}">{esc(trim(agenda_label(it), 26))}</button>')
    out.append(f'<button type="button" class="csi-filter" data-tag="{NO_AGENDA}" data-key="none" aria-pressed="false">직접 해당 없음</button>')
    out.append("</div>")
    # Single-choice groups: v1 period and minimum total score ("all" = no limit).
    for param, label, options in (("period", "기간", [("4w", "최근 4주"), ("3m", "최근 3개월"), ("all", "전체")]),
                                  ("min", "점수", [("all", "전체"), ("50", "50+"), ("60", "60+"), ("70", "70+")])):
        out.append(f'<div class="csi-filter-group" data-param="{param}"><span class="csi-filter-label">{label}</span>')
        for value, text in options:
            pressed = "true" if value == "all" else "false"
            out.append(f'<button type="button" class="csi-choice" data-value="{value}" aria-pressed="{pressed}">{text}</button>')
        out.append("</div>")
    sort_options = [("date", "최신순 (v1)"), ("score", "총점")] + [(k, RUBRIC_LABELS[k]) for k in RUBRIC]
    out += [
        '<div class="csi-filter-group"><label class="csi-filter-label" for="csi-sort">정렬</label>'
        '<select id="csi-sort" class="csi-sort"><option value="" hidden>열 제목 기준</option>'
        + "".join(f'<option value="{k}">{esc(t)}</option>' for k, t in sort_options) + "</select></div>",
        '<input type="search" class="csi-search" placeholder="제목·저자·채널 모델·코멘트 검색" aria-label="검색">',
        '<button type="button" class="csi-reset">초기화</button>',
        '<button type="button" class="csi-copy">링크 복사</button>',
        '<span class="csi-count" aria-live="polite"></span>',
        "</div>",
        "",
        '<div class="csi-table-wrap"><table class="csi-compare">',
        "<thead><tr>"
        '<th data-key="title">논문</th><th data-key="date">v1</th><th>3GPP 안건</th><th>태그</th><th>지표</th>'
        '<th data-key="channel">채널 모델</th><th>압축률 / payload</th><th>주요 성능 (baseline 대비)</th>'
        '<th data-key="score">점수</th></tr></thead>',
        "<tbody>",
    ]
    for m in papers:
        tags = as_list(m.get("tags"))
        items = agenda_items(m)
        tokens = tags + ([agenda_token(it) for it in items] or [NO_AGENDA])
        level = (m.get("score_breakdown") or {}).get("standard", "?")
        cells = []
        for it in items:
            text = f'<span title="{esc(it["meeting"] + " " + it.get("title", ""))}">{esc(agenda_label(it))}</span>'
            url = tdoc_url(it, 1)
            if url:
                text += f'<div class="csi-sub"><a href="{esc(url)}">Tdoc 요약 →</a></div>'
            cells.append(text)
        agenda_cell = "<br>".join(cells) or '<span class="csi-sub">직접 해당 없음</span>'
        agenda_cell += f'<div class="csi-sub"><a href="../rubric/#relevance" title="3GPP 관련성 등급 기준">관련성</a> {esc(level)}/15</div>'
        point = plain(first_sentence(m.get("_takeaway", "")))
        search_blob = " ".join([m["title"], *as_list(m.get("authors")), *as_list(m.get("affiliation")),
                                str(m.get("channel_model", "")), str(m.get("venue", "")), point]).lower()
        abstract_flag = ' <span class="csi-flag" title="abstract only">abs</span>' if m.get("read_level") == "abstract-only" else ""
        title_cell = (f'<a href="../papers/{esc(m["arxiv_id"])}/">{esc(m["title"])}</a>'
                      f'<div class="csi-sub">{esc(m["arxiv_id"])} · {esc(m.get("venue", ""))}</div>')
        if point:
            title_cell += f'<div class="csi-takeaway">{esc(point)}</div>'
        scores = json.dumps({k: (m.get("score_breakdown") or {}).get(k, 0) for k in RUBRIC}, separators=(",", ":"))
        out.append(
            f'<tr data-tags="{esc(" ".join(tokens))}" data-search="{esc(search_blob)}" data-date="{esc(m.get("date", ""))}" '
            f'data-score="{esc(m.get("score", 0))}" data-scores="{esc(scores)}">'
            f'<td>{title_cell}</td>'
            f'<td>{esc(m.get("date", ""))}</td>'
            f'<td>{agenda_cell}</td>'
            f'<td>{" ".join(f"<span class=csi-tag>{esc(t)}</span>" for t in tags)}</td>'
            f'<td>{esc(", ".join(as_list(m.get("metrics"))))}</td>'
            f'<td>{esc(m.get("channel_model", ""))}</td>'
            f'<td>{esc(m.get("compression_ratio", ""))}</td>'
            f'<td>{esc(m.get("headline_result", ""))}</td>'
            f'<td data-value="{esc(m.get("score", 0))}"><span class="csi-score {score_class(m.get("score"))}">'
            f'{esc(m.get("score", "?"))}</span>{abstract_flag}</td>'
            "</tr>"
        )
    out += ['<tr class="csi-empty" hidden><td colspan="9">조건에 맞는 논문이 없습니다. 조건을 줄이거나 <b>초기화</b>를 누르세요.</td></tr>',
            "</tbody></table></div>", ""]
    if not papers:
        out.append("아직 등록된 논문이 없습니다.")
    return "\n".join(out)


def index_page(papers: list[dict]) -> str:
    """Paper list grouped by 3GPP agenda item (score order inside a group); 'no direct item' last.
    A paper mapped to two items is listed under both."""
    groups: dict[str | None, dict] = {}
    for m in papers:
        for it in agenda_items(m) or [None]:
            key = it["id"] if it else None
            g = groups.setdefault(key, {"label": agenda_label(it) if it else "현재 안건에 직접 해당 없음", "papers": []})
            g["papers"].append(m)
    order = sorted((k for k in groups if k), key=agenda_sort_key) + ([None] if None in groups else [])
    out = ["---", "title: 논문 목록", "hide: [toc]", "---", "", "# 논문 목록", "",
           f"리뷰한 논문 {len(papers)}편을 **대응하는 3GPP RAN1 안건별로** 묶었습니다. 묶음 안에서는 점수 높은 순이고, "
           "제목 아래 회색 글은 우리 업무 관점의 한 줄 결론입니다. 지표·채널 모델·성능을 나란히 보거나 여러 조건으로 거르려면 "
           "**[비교 표](../compare.md)** 를 쓰세요. 점수 뜻은 [점수 기준](../rubric.md)에 있습니다.", "",
           '<div class="csi-chips">']
    for key in order:
        g = groups[key]
        out.append(f'<a class="csi-chip" href="#{agenda_anchor(key)}">{esc(trim(g["label"], 30))} <span>{len(g["papers"])}</span></a>')
    out += ["</div>", ""]
    for key in order:
        g = groups[key]
        out += [f"## {g['label']} {{#{agenda_anchor(key)}}}", ""]
        if key:
            sample = next(it for it in agenda_items(g["papers"][0]) if it["id"] == key)
            if (sample["meeting"], key) in TDOCS:
                out += [f'<p class="csi-sub">이 안건의 RAN1 논의: <a href="../{tdoc_url(sample, 0)}">{esc(sample["meeting"])} Tdoc 요약 →</a></p>', ""]
        out += ["| 점수 | 논문 | v1 | 태그 |", "|---:|---|---|---|"]
        for m in sorted(g["papers"], key=lambda x: (-float(x.get("score", 0)), str(x.get("arxiv_id")))):
            score = f'<span class="csi-score {score_class(m.get("score"))}">{esc(m.get("score", "?"))}</span>'
            point = first_sentence(m.get("_takeaway", "")).replace("|", "\\|")
            title = f"[{esc(m['title'])}]({m['arxiv_id']}.md)"
            if m.get("read_level") == "abstract-only":
                title += ' <span class="csi-flag" title="abstract only">abs</span>'
            if point:
                title += f'<br><span class="csi-takeaway">{point}</span>'
            tags = " ".join(f'<span class="csi-tag">{esc(t)}</span>' for t in as_list(m.get("tags")))
            out.append(f"| {score} | {title} | {m.get('date', '')} | {tags} |")
        out.append("")
    if not papers:
        out.append("아직 등록된 논문이 없습니다.")
    return "\n".join(out) + "\n"


def _skill_block(text: str, name: str) -> str | None:
    try:
        return text.split(f"<!-- {name}:start -->", 1)[1].split(f"<!-- {name}:end -->", 1)[0].strip()
    except IndexError:
        return None


def rubric_page() -> str:
    """Copy the 3GPP relevance grades and the rubric out of SKILL.md so the site never drifts from the skill."""
    skill = Path(__file__).resolve().parent.parent / ".claude/skills/csi-paper-review/SKILL.md"
    text = skill.read_text(encoding="utf-8")
    relevance = _skill_block(text, "relevance") or "3GPP 관련성 등급 구간을 SKILL.md에서 찾지 못했습니다."
    # Skill-internal step names mean nothing on the site.
    relevance = (relevance.replace("0.5단계 안건 항목의", "현재 RAN1 안건 항목의")
                 .replace("0.5단계 스냅샷", "안건 스냅샷(아래 표)")
                 .replace("| `ran1_agenda` |", "| 논문에 표시되는 안건 |"))
    rubric = _skill_block(text, "rubric") or "rubric 구간을 SKILL.md에서 찾지 못했습니다."
    rubric = rubric.replace("### ", "## ", 1).replace("(2단계 표)", "([3GPP 관련성 등급](#relevance) 표)")
    # Current agenda snapshot the relevance grades are judged against.
    latest = max(AGENDAS, key=lambda m: meeting_sort_key(m)) if AGENDAS else None
    agenda_rows = []
    if latest:
        agenda_rows = [f"현재 기준 안건: **{latest}** 스냅샷 (`config/ran1_agenda/`, 논문 수집 때마다 갱신)", "",
                       "| 안건 | 제목 | 구분 |", "|---|---|---|"]
        for aid in sorted(AGENDAS[latest], key=agenda_sort_key):
            it = AGENDAS[latest][aid]
            agenda_rows.append(f"| {aid} | {esc(it.get('title', ''))} | {esc(release_label(it.get('release', '')))} |")
    return "\n".join([
        "---", "title: 점수 기준", "---", "", "# 점수 기준", "",
        "논문 점수는 **3GPP 관련성(15점)** 과 신뢰도·재현성 항목을 합친 100점 만점입니다. "
        "이 페이지는 `.claude/skills/csi-paper-review/SKILL.md` 의 기준을 그대로 가져온 것이라, 수집 규칙과 항상 같습니다. "
        "기준을 바꾸려면 SKILL.md를 수정하세요 (`scripts/paper_schema.py` 의 배점도 함께).",
        "",
        "점수 색: 70 이상 높음 · 50–69 중간 · 50 미만 낮음.",
        "",
        "## 3GPP 관련성 등급 {#relevance}",
        "",
        "논문이 지금 RAN1에서 논의 중인 안건과 얼마나 직접 닿는지를 15 / 11 / 7 세 단계로 매깁니다. "
        "11 이상이면 대응 안건이 논문 페이지·비교 표에 표시되고, 7이면 \"직접 해당 없음\"으로 표시됩니다.",
        "",
        relevance,
        "",
        *agenda_rows,
        "",
        rubric,
        "",
    ])


def tdoc_page(meta: dict, body: str, papers: list[dict]) -> str:
    meeting, agenda = str(meta["meeting"]), str(meta["agenda"])
    fm = {"title": f"{meeting} {agenda} {meta['title']}"}
    lines = ["---", yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip(), "---", ""]
    if meta.get("status") == "provisional":
        lines += ['!!! warning "잠정"', "    회의 종료 의장 노트가 아직 없어 FL summary 기준으로 정리했습니다.", ""]
    # Company names in the topic tables -> their Tdoc links, plus a per-company position table.
    body, _ = link_section(body.strip(), company_page="../companies.md")
    # Keep the summary's own H1 above the info card.
    body = body.strip()
    if body.startswith("# "):
        h1, _, body = body.partition("\n")
        lines[4:4] = [h1, ""]
    related = [m for m in papers if str(m.get("ran1_meeting")) == meeting and agenda in as_list(m.get("ran1_agenda"))]
    rel = ", ".join(f"[{m['arxiv_id']}](../../papers/{m['arxiv_id']}.md)" for m in related) or "없음"
    if related:
        rel += f" · [비교 표에서 보기 →]({compare_link({'meeting': meeting, 'id': agenda}, 2)})"
    lines += [
        '<div class="csi-card" markdown>',
        "",
        "| | |",
        "|---|---|",
        f"| **회의** | {meeting} ({meta.get('venue', '?')}) |",
        f"| **안건** | {agenda} {meta['title']} |",
        f"| **구분** | {meta.get('release', '?')} |",
        f"| **상태** | {'최종 (회의 종료 의장 노트·세션 노트 기준)' if meta.get('status') == 'final' else '잠정 (FL summary 기준)'} |",
        f"| **합의 흐름에 포함한 회의** | {', '.join(as_list(meta.get('history')))} → {meeting} |",
        f"| **Tdoc 수** | {meta.get('tdoc_count', '?')} |",
        f"| **주요 출처** | {'<br>'.join(esc(x) for x in as_list(meta.get('sources')))} |",
        f"| **관련 논문** | {rel} |",
        f"| **정리일** | {meta.get('reviewed', '?')} |",
        "",
        "</div>",
        "",
        body.strip(),
        "",
    ]
    return "\n".join(lines)


def companies_page(entries: list[tuple[Path, dict, str]], papers: list[dict]) -> str:
    """All meetings x agenda items, grouped by company: Tdocs, positions, key proposal, related papers."""
    by_company: dict[str, dict] = {}
    order = sorted(entries, key=lambda e: (str(e[1]["meeting"]), [int(t) for t in str(e[1]["agenda"]).split(".") if t.isdigit()]))
    for _, meta, body in order:
        meeting, agenda = str(meta["meeting"]), str(meta["agenda"])
        for key, c in collect(body).items():
            entry = by_company.setdefault(key, {"name": c["name"], "rows": []})
            entry["rows"].append((meeting, agenda, tdoc_short_title(meta, body), c))
    # Papers whose affiliation names the company ("Samsung Research", "Nokia Bell Labs" -> samsung, nokia).
    for m in papers:
        for aff in as_list(m.get("affiliation")):
            for key in {normalise(aff), normalise(aff.split(" ")[0])}:
                if key in by_company:
                    by_company[key].setdefault("papers", {})[m["arxiv_id"]] = m
    ranked = sorted(by_company.items(), key=lambda kv: (-len({(r[0], r[1]) for r in kv[1]["rows"]}), kv[1]["name"].lower()))
    out = ["---", "title: 업체별 입장", "---", "", "# 업체별 입장 (3GPP RAN1)", "",
           "Tdoc 요약의 \"업체별 주요 제안\" 절을 업체 기준으로 다시 모은 페이지입니다. 업체마다 안건별 Tdoc 원문 링크, "
           "주제별 입장(FL summary·Summary of proposals 기준), 핵심 제안, 소속이 같은 트래커 논문을 보여 줍니다. "
           "요약 파일에서 자동으로 만들어지며, 요약에 Tdoc 링크가 없는 업체는 나오지 않습니다.", "",
           f'<p class="csi-sub">업체 {len(ranked)}곳 · 괄호 안은 등장한 안건 수 · 많은 순</p>', "",
           '<div class="csi-chips">']
    for key, c in ranked:
        n = len({(r[0], r[1]) for r in c["rows"]})
        out.append(f'<a class="csi-chip" href="#{company_anchor(key)}">{esc(c["name"])} <span>{n}</span></a>')
    out += ["</div>", ""]
    for key, c in ranked:
        agendas = {(r[0], r[1]) for r in c["rows"]}
        tdocs = {t for r in c["rows"] for t, _ in r[3]["links"]}
        rel = list(c.get("papers", {}).values())
        out += [f"## {c['name']} {{#{company_anchor(key)}}}", "",
                f'<p class="csi-sub">안건 {len(agendas)}개 · Tdoc {len(tdocs)}편'
                + (f" · 관련 논문 {len(rel)}편" if rel else "") + "</p>", "",
                "| 회의 · 안건 | Tdoc | 입장 · 핵심 제안 |", "|---|---|---|"]
        for meeting, agenda, short, data in c["rows"]:
            link = tdoc_page_path(meeting, agenda)[len("tdocs/"):]
            links = " ".join(f"[{t}]({u})" for t, u in data["links"])
            detail = list(data["positions"])
            if data["proposal"]:
                detail.append(f"**핵심**: {data['proposal']}")
            cell = "<br>".join(detail) or NO_POSITION
            out.append(f"| {meeting} · [{esc(short)}]({link}) | {links} | {cell} |")
        if rel:
            out += ["", "관련 논문 (소속 기준): " + ", ".join(f"[{esc(m['title'])}](../papers/{m['arxiv_id']}.md)" for m in rel)]
        out.append("")
    if not ranked:
        out.append("아직 정리된 Tdoc 요약이 없습니다.")
    return "\n".join(out) + "\n"


# Parent agenda groups for the Tdoc menu and index (Korean labels; others fall back to the snapshot title).
TDOC_GROUP_LABELS = {"9.1": "NR AI/ML CSI", "9.2": "NR MIMO Phase 6", "10.5.3": "6GR CSI 획득·보고"}


def meeting_sort_key(meeting: str) -> list:
    """'RAN1#127' < 'RAN1#127bis' < 'RAN1#128'."""
    num = meeting.replace("RAN1#", "")
    digits = "".join(ch for ch in num if ch.isdigit())
    return [int(digits or 0), num[len(digits):]]


def agenda_sort_key(agenda: str) -> list:
    return [int(t) for t in agenda.split(".") if t.isdigit()]


def release_label(release: str) -> str:
    return "6GR study" if "6GR" in release else release.replace("Release ", "Rel-").replace(" NR", "")


def tdoc_groups(entries: list[tuple[Path, dict, str]]) -> list[dict]:
    """[{id, label, items: [{agenda, short, meetings: {meeting: (meta, body)}}]}] ordered by agenda number.

    An item's group is its nearest parent agenda item in the meeting's snapshot (9.1.1 -> 9.1,
    10.5.3.1 -> 10.5.3); a top-level item such as 9.2 is its own group. Grouping is by agenda id;
    if RAN1 renumbers a topic later, the snapshot titles show it and this needs a manual mapping.
    """
    groups: dict[str, dict] = {}
    for _, meta, body in entries:
        meeting, agenda = str(meta["meeting"]), str(meta["agenda"])
        snap = AGENDAS.get(meeting, {})
        parts = agenda.split(".")
        gid = next((".".join(parts[:k]) for k in range(len(parts) - 1, 0, -1) if ".".join(parts[:k]) in snap), agenda)
        gitem = snap.get(gid, {"title": str(meta.get("title", "")), "release": str(meta.get("release", ""))})
        title = TDOC_GROUP_LABELS.get(gid) or (gitem["title"] if len(gitem["title"]) <= 40 else gitem["title"][:39] + "…")
        group = groups.setdefault(gid, {"id": gid, "label": f"{title} ({gid}, {release_label(gitem.get('release', ''))})", "items": {}})
        item = group["items"].setdefault(agenda, {"agenda": agenda, "meetings": {}})
        item["meetings"][meeting] = (meta, body)
    out = []
    for gid in sorted(groups, key=agenda_sort_key):
        g = groups[gid]
        items = []
        for agenda in sorted(g["items"], key=agenda_sort_key):
            it = g["items"][agenda]
            latest = max(it["meetings"], key=meeting_sort_key)
            it["short"] = tdoc_short_title(*it["meetings"][latest])
            items.append(it)
        out.append({"id": gid, "label": g["label"], "items": items})
    return out


def tdoc_index_page(entries: list[tuple[Path, dict, str]], papers: list[dict]) -> str:
    """Agenda x meeting map: one table per parent agenda group, one column per meeting (newest first)."""
    out = ["---", "title: 3GPP Tdoc 요약", "---", "", "# 3GPP RAN1 Tdoc 요약", "",
           "RAN1 회의마다 트래커와 관련된 안건의 합의 사항, 업체별 입장, 평가 결과를 안건별로 정리합니다. "
           "각 안건 요약은 이전 회의의 합의 흐름부터 시작합니다. 갱신 방법은 저장소 README의 \"3GPP Tdoc 요약\" 절을 보세요.", "",
           "업체 한 곳이 여러 안건에서 낸 Tdoc과 입장을 모아 보려면 **[업체별 입장](companies.md)** 페이지를 보세요.", ""]
    meetings = sorted({str(m["meeting"]) for _, m, _ in entries}, key=meeting_sort_key, reverse=True)
    if meetings:
        out += ['<p class="csi-sub">안건 × 회의 지도: 칸마다 그 회의의 핵심 한 줄과 상태·Tdoc 수·관련 논문 수. 왼쪽 열이 최신 회의입니다.</p>', ""]
    for group in tdoc_groups(entries):
        out += [f"## {group['label']}", "",
                "| 안건 | " + " | ".join(meetings) + " |",
                "|---|" + "---|" * len(meetings)]
        for it in group["items"]:
            cells = []
            for meeting in meetings:
                if meeting not in it["meetings"]:
                    cells.append('<span class="csi-sub">–</span>')
                    continue
                meta, _ = it["meetings"][meeting]
                link = tdoc_page_path(meeting, it["agenda"])[len("tdocs/"):]
                n = sum(1 for pm in papers if str(pm.get("ran1_meeting")) == meeting and it["agenda"] in as_list(pm.get("ran1_agenda")))
                status = "최종" if meta.get("status") == "final" else "잠정"
                sub = f"{status} · Tdoc {meta.get('tdoc_count', '?')}편" + (f" · 관련 논문 {n}편" if n else "")
                cells.append(f"[{esc(meta.get('headline', '요약 보기'))}]({link})<br><span class=\"csi-sub\">{sub}</span>")
            out.append(f"| **{esc(it['short'])}** | " + " | ".join(cells) + " |")
        out.append("")
    if not entries:
        out.append("아직 정리된 회의가 없습니다.")
    return "\n".join(out) + "\n"


def next_weekly_run(now: dt.datetime) -> dt.datetime:
    weekday, hour = WEEKLY_RUN
    run = now.replace(hour=hour, minute=0, second=0, microsecond=0) + dt.timedelta(days=(weekday - now.weekday()) % 7)
    return run if run > now else run + dt.timedelta(days=7)


def tdoc_short_title(meta: dict, body: str) -> str:
    """'RAN1#127 · 9.1.1 Case 0 CSI 압축 (two-sided 모델)' -> '9.1.1 Case 0 CSI 압축 (two-sided 모델)'."""
    for line in body.strip().splitlines():
        if line.startswith("# "):
            return line[2:].split(" · ", 1)[-1].strip()
    return f"{meta['agenda']} {meta['title']}"


def home_latest(papers: list[dict], tdoc_entries: list[tuple[Path, dict, str]]) -> str:
    """Generated block for the home page: status line, recent papers, latest RAN1 summaries."""
    now = dt.datetime.now(KST)
    run = next_weekly_run(now)
    days = "월화수목금토일"
    meetings = sorted({str(m["meeting"]) for _, m, _ in tdoc_entries},
                      key=lambda x: [int(t) if t.isdigit() else 0 for t in x.replace("RAN1#", "").replace("bis", ".5").split(".")])
    latest_meeting = meetings[-1] if meetings else None
    out = [
        '<div class="csi-status" markdown>',
        "",
        f"**논문 {len(papers)}편** · **3GPP Tdoc 요약 {len(tdoc_entries)}개**"
        + (f" (최신 {latest_meeting})" if latest_meeting else "")
        + f" · 마지막 업데이트 {now:%Y-%m-%d %H:%M} KST"
        + f" · 다음 자동 수집 {run:%m월 %d일}({days[run.weekday()]}) {run:%H:%M}",
        "",
        "</div>",
        "",
        "## 최근 추가 논문",
        "",
    ]
    reviewed = [m for m in papers if m.get("reviewed")]
    if reviewed:
        newest = max(dt.date.fromisoformat(str(m["reviewed"])) for m in reviewed)
        since = newest - dt.timedelta(days=RECENT_DAYS - 1)
        recent = [m for m in reviewed if dt.date.fromisoformat(str(m["reviewed"])) >= since]
        recent.sort(key=lambda m: (-float(m.get("score", 0)), str(m.get("arxiv_id"))))
        out += [f'<p class="csi-sub">리뷰일 {since:%Y-%m-%d} ~ {newest:%Y-%m-%d}, 점수 순 (최대 {RECENT_MAX}편)</p>', "",
                '<div class="csi-recent" markdown>', "",
                "| 점수 | 논문 · 한 줄 결론 | 3GPP 안건 |", "|---:|---|---|"]
        for m in recent[:RECENT_MAX]:
            agenda = "<br>".join(agenda_md(it) for it in agenda_items(m)) or '<span class="csi-sub">직접 해당 없음</span>'
            score = f'<span class="csi-score {score_class(m.get("score"))}">{esc(m.get("score", "?"))}</span>'
            point = first_sentence(m.get("_takeaway", "")).replace("|", "\\|")
            title = f"[{esc(m['title'])}](papers/{m['arxiv_id']}.md)"
            if point:
                title += f'<br><span class="csi-takeaway">{point}</span>'
            out.append(f"| {score} | {title} | {agenda} |")
        out += ["", "</div>", "", "[논문 목록 →](papers/index.md) · [비교 표 →](compare.md)", ""]
    else:
        out += ["아직 등록된 논문이 없습니다.", ""]
    if latest_meeting:
        out += [f"## 최신 3GPP RAN1 요약 ({latest_meeting})", "", "| 안건 | 핵심 |", "|---|---|"]
        rows = [(m, b) for _, m, b in tdoc_entries if str(m["meeting"]) == latest_meeting]
        rows.sort(key=lambda mb: [int(t) for t in str(mb[0]["agenda"]).split(".") if t.isdigit()])
        for m, b in rows:
            link = tdoc_page_path(str(m["meeting"]), str(m["agenda"]))
            out.append(f"| [{esc(tdoc_short_title(m, b))}]({link}) | {esc(m.get('headline', ''))} |")
        out += ["", "[3GPP Tdoc 요약 전체 →](tdocs/index.md)", ""]
    return "\n".join(out)


def main() -> None:
    entries = load_papers()
    metas = []
    for path, meta, body in entries:
        meta.setdefault("arxiv_id", path.stem)
        meta["_takeaway"] = takeaway(body)  # build-time only; never written back
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
    # Individual papers stay out of the menu (it grows every week); the paper list groups them by agenda.
    nav = ["* [홈](index.md)", "* 논문", "    * [논문 목록](papers/index.md)", "    * [비교 표](compare.md)"]
    tdoc_entries = load_tdocs()
    for path, tmeta, tbody in tdoc_entries:
        virtual = tdoc_page_path(str(tmeta["meeting"]), str(tmeta["agenda"]))
        with mkdocs_gen_files.open(virtual, "w") as f:
            f.write(tdoc_page(tmeta, tbody, metas))
        mkdocs_gen_files.set_edit_path(virtual, f"../tdocs/{path.parent.name}/{path.name}")
    with mkdocs_gen_files.open("tdocs/index.md", "w") as f:
        f.write(tdoc_index_page(tdoc_entries, metas))
    with mkdocs_gen_files.open("tdocs/companies.md", "w") as f:
        f.write(companies_page(tdoc_entries, metas))
    home = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")
    if HOME_MARKER in home:
        with mkdocs_gen_files.open("index.md", "w") as f:
            f.write(home.replace(HOME_MARKER, home_latest(metas, tdoc_entries), 1))
    nav.append("* [3GPP Tdoc 요약](tdocs/index.md)")
    nav.append("    * [업체별 입장](tdocs/companies.md)")
    for group in tdoc_groups(tdoc_entries):
        nav.append(f"    * {group['label']}")
        for it in group["items"]:
            ms = sorted(it["meetings"], key=meeting_sort_key, reverse=True)
            if len(ms) == 1:
                nav.append(f"        * [{it['short']}]({tdoc_page_path(ms[0], it['agenda'])})")
            else:  # several meetings: agenda becomes a sub-section, newest meeting first
                nav.append(f"        * {it['short']}")
                nav += [f"            * [{m}]({tdoc_page_path(m, it['agenda'])})" for m in ms]
    nav += ["* 안내", "    * [사용 안내](guide.md)", "    * [점수 기준](rubric.md)"]
    with mkdocs_gen_files.open("SUMMARY.md", "w") as f:
        f.write("\n".join(nav) + "\n")
    with mkdocs_gen_files.open("rubric.md", "w") as f:
        f.write(rubric_page())
    mkdocs_gen_files.set_edit_path("rubric.md", "../.claude/skills/csi-paper-review/SKILL.md")


main()
