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
RECENT_MAX = 8
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


def agenda_md(item: dict, base: str = "") -> str:
    """Markdown label of an agenda item: the Korean short title of its RAN1 summary (linked) when one
    exists, else the snapshot title. `base` is the relative prefix to the docs root ('' or '../')."""
    key = (item["meeting"], item["id"])
    if key in TDOCS:
        _, tmeta, tbody = TDOCS[key]
        return f"[{esc(tdoc_short_title(tmeta, tbody))}]({base}{tdoc_page_path(*key)})"
    return esc(agenda_short(item, 40))


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
    fm = {"title": meta["title"], "tags": as_list(meta.get("tags"))}
    lines = ["---", yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip(), "---", ""]
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
        f"3GPP 관련성 {esc(level)}/15 · [점수 근거 ↓](#점수-근거)",
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
        f"| **Reviewed** | {meta.get('reviewed', '?')} ({meta.get('read_level', '?')}) |",
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
                   f'title="{esc(it["meeting"] + " " + it["id"] + " " + it.get("title", ""))}">{esc(agenda_short(it, 28))}</button>')
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
            text = f'<span title="{esc(it["meeting"] + " " + it.get("title", ""))}">{esc(agenda_short(it, 40))}</span>'
            url = tdoc_url(it, 1)
            if url:
                text += f'<div class="csi-sub"><a href="{esc(url)}">Tdoc 요약 →</a></div>'
            cells.append(text)
        agenda_cell = "<br>".join(cells) or '<span class="csi-sub">직접 해당 없음</span>'
        agenda_cell += f'<div class="csi-sub">관련성 {esc(level)}/15</div>'
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


def tdoc_index_page(entries: list[tuple[Path, dict, str]], papers: list[dict]) -> str:
    out = ["---", "title: 3GPP Tdoc", "---", "", "# 3GPP RAN1 Tdoc 요약", "",
           "RAN1 회의마다 트래커와 관련된 안건의 합의 사항, 업체별 입장, 평가 결과를 안건별로 정리합니다. "
           "각 안건 요약은 이전 회의의 합의 흐름부터 시작합니다. 갱신 방법은 저장소 README의 \"3GPP Tdoc 요약\" 절을 보세요.", "",
           "업체 한 곳이 여러 안건에서 낸 Tdoc과 입장을 모아 보려면 **[업체별 입장](companies.md)** 페이지를 보세요.", ""]
    by_meeting: dict[str, list] = {}
    for p, m, b in entries:
        by_meeting.setdefault(str(m["meeting"]), []).append(m)
    for meeting in sorted(by_meeting, reverse=True):
        out += [f"## {meeting}", "", "| 안건 | 제목 | 상태 | Tdoc 수 | 관련 논문 |", "|---|---|---|---:|---:|"]
        for m in sorted(by_meeting[meeting], key=lambda x: [int(t) for t in str(x["agenda"]).split(".") if t.isdigit()]):
            agenda = str(m["agenda"])
            n = sum(1 for pm in papers if str(pm.get("ran1_meeting")) == meeting and agenda in as_list(pm.get("ran1_agenda")))
            status = "최종" if m.get("status") == "final" else "잠정"
            out.append(f"| [{agenda}]({tdoc_page_path(meeting, agenda)[len('tdocs/'):]}) | {m['title']} | {status} | {m.get('tdoc_count', '?')} | {n} |")
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
                "| 점수 | 논문 | 3GPP 안건 | 주요 성능 (baseline 대비) |", "|---:|---|---|---|"]
        for m in recent[:RECENT_MAX]:
            agenda = "<br>".join(agenda_md(it) for it in agenda_items(m)) or '<span class="csi-sub">직접 해당 없음</span>'
            score = f'<span class="csi-score {score_class(m.get("score"))}">{esc(m.get("score", "?"))}</span>'
            point = first_sentence(m.get("_takeaway", "")).replace("|", "\\|")
            title = f"[{esc(m['title'])}](papers/{m['arxiv_id']}.md)"
            if point:
                title += f'<br><span class="csi-takeaway">{point}</span>'
            out.append(f"| {score} | {title} | {agenda} | {esc(m.get('headline_result', ''))} |")
        out += ["", "</div>", "", "[전체 비교 표 →](compare.md)", ""]
    else:
        out += ["아직 등록된 논문이 없습니다.", ""]
    if latest_meeting:
        out += [f"## 최신 3GPP RAN1 요약 ({latest_meeting})", "", "| 안건 | 핵심 |", "|---|---|"]
        rows = [(m, b) for _, m, b in tdoc_entries if str(m["meeting"]) == latest_meeting]
        rows.sort(key=lambda mb: [int(t) for t in str(mb[0]["agenda"]).split(".") if t.isdigit()])
        for m, b in rows:
            link = tdoc_page_path(str(m["meeting"]), str(m["agenda"]))
            out.append(f"| [{esc(tdoc_short_title(m, b))}]({link}) | {esc(m.get('headline', ''))} |")
        out += ["", "[3GPP Tdoc 전체 →](tdocs/index.md)", ""]
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
    nav = ["* [홈](index.md)", "* [비교 표](compare.md)", "* [태그](tags.md)", "* [논문](papers/index.md)"]
    for m in metas:
        short = m["title"] if len(m["title"]) <= 60 else m["title"][:57].rstrip() + "…"
        nav.append(f"    * [{m['arxiv_id']} · {short}](papers/{m['arxiv_id']}.md)")
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
    nav.append("* [3GPP Tdoc](tdocs/index.md)")
    nav.append("    * [업체별 입장](tdocs/companies.md)")
    for path, tmeta, _ in sorted(tdoc_entries, key=lambda e: (str(e[1]["meeting"]), [int(t) for t in str(e[1]["agenda"]).split(".") if t.isdigit()])):
        title = str(tmeta["title"])
        title = title if len(title) <= 40 else title[:39].rstrip() + "…"
        nav.append(f"    * [{tmeta['meeting']} {tmeta['agenda']} {title}]({tdoc_page_path(str(tmeta['meeting']), str(tmeta['agenda']))})")
    nav.append("* [점수 기준](rubric.md)")
    with mkdocs_gen_files.open("SUMMARY.md", "w") as f:
        f.write("\n".join(nav) + "\n")
    with mkdocs_gen_files.open("rubric.md", "w") as f:
        f.write(rubric_page())
    mkdocs_gen_files.set_edit_path("rubric.md", "../.claude/skills/csi-paper-review/SKILL.md")


main()
