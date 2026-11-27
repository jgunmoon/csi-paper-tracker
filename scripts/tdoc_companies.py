"""Link companies to their Tdocs inside a RAN1 summary's '## 업체별 주요 제안' section.

Used at site build time (gen_pages.py) and by validate_papers.py; the summary files themselves
are never rewritten.

- company_tdocs(): company -> Tdoc links, read from the section's company table rows
  ("| Huawei, HiSilicon | [R1-…](…) | …") and inline lists ("Nokia [R1-…](…) [R1-…](…), …").
- link_section(): rewrites the topic tables (first header cell '주제') so every recognised
  company name becomes a link to its Tdoc, and appends a collapsed "업체별 입장 모아 보기"
  table built from the same topic tables.
"""
from __future__ import annotations

import re

SECTION = "업체별 주요 제안"
LINK = re.compile(r"\[(R1-\d{7})\]\((https?://[^)\s]+)\)")
# Capitalised word runs such as "NTT DOCOMO", "China Telecom", "Southeast Univ.", "1Finity".
NAME = re.compile(r"(?<![\w\[/#-])([A-Za-z0-9][A-Za-z0-9&.\-]*(?: [A-Z][A-Za-z0-9&.\-]*)*)")  # "vivo" is lowercase
BOLD = re.compile(r"\*\*(.+?)\*\*")
PLAIN_LABEL = re.compile(r"(?:^|(?<=\.\s))([A-Za-z0-9가-힣][\w가-힣 +\-]{0,14}):\s")

# Different spellings of the same company -> one key (after normalise()).
ALIASES = {
    "lge": "lg",
    "lgelectronics": "lg",
    "docomo": "nttdocomo",
    "samsungelectronics": "samsung",
    "nokiashanghaibell": "nokia",
    "southeastuniversity": "southeastuniv",
}
# Words that look like names in the tables but are not companies.
NOT_COMPANY = re.compile(r"^(Alt\d*|Option|Case|Type|NR|SQ|VQ|NW|UE|gNB|L\d|M|PMI|CRI|LI|SGCS|NMSE|TD|FR\d|SRS|CSI|"
                         r"MAC|RB|OCC|SIB|MSG\d|RAN\d|TS|FL|FFS|CBSR|DMRS|PUSCH|PAPR|OLLA|AI|ML|LS|SA\d|S\+U|U\+U|\d+)\b")


def normalise(name: str) -> str:
    name = re.sub(r"\((?:FL|Moderator)\)", "", name, flags=re.I).split(",")[0]
    # Legal-form / brand suffixes: "Qualcomm Incorporated", "Rakuten Mobile", "LG Electronics"
    name = re.sub(r"\s+(Incorporated|Inc\.?|Corporation|Corp\.?|Ltd\.?|Limited|Co\.|Mobile|Electronics)\s*$", "", name.strip(), flags=re.I)
    key = re.sub(r"[^a-z0-9]", "", name.lower())
    return ALIASES.get(key, key)


def section_bounds(body: str) -> tuple[int, int] | None:
    m = re.search(rf"^## {SECTION}\s*$", body, re.M)
    if not m:
        return None
    nxt = re.search(r"^## ", body[m.end():], re.M)
    return m.end(), (m.end() + nxt.start()) if nxt else len(body)


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def company_tdocs(section: str) -> dict[str, dict]:
    """{normalised key: {"name": display name, "links": [(tdoc, url), ...]}} in first-seen order."""
    out: dict[str, dict] = {}

    def add(name: str, links: list[tuple[str, str]]) -> None:
        name = re.sub(r"\((?:FL|Moderator)\)", "", name).strip(" ,:·")
        key = normalise(name)
        if not key or not links or NOT_COMPANY.match(name):
            return
        entry = out.setdefault(key, {"name": name.split(",")[0].strip(), "links": []})
        for link in links:
            if link not in entry["links"]:
                entry["links"].append(link)

    for line in section.splitlines():
        if not line.lstrip().startswith("|"):
            # Inline lists outside tables, e.g. "평가 결과를 낸 업체 Tdoc: Huawei [R1-…](…), vivo […](…)"
            _inline(line, add)
            continue
        cells = _cells(line)
        if len(cells) >= 2 and cells[1].startswith("[R1-") and not cells[0].startswith(("그 밖", "전체")):
            add(cells[0], LINK.findall(cells[1])[:1] + LINK.findall(cells[1])[1:])
        else:
            for cell in cells:
                _inline(cell, add)
    return out


def _inline(text: str, add) -> None:
    """'Nokia [R1-a](u) [R1-b](u), vivo [R1-c](u)' -> add(Nokia,[a,b]); add(vivo,[c])."""
    last_end, current, links = 0, None, []
    for m in LINK.finditer(text):
        gap = text[last_end:m.start()]
        name = re.split(r"[,:;|]|\bTdoc\b", gap)[-1].strip()
        if name and not gap.strip().startswith(("(", ")")):
            if current and links:
                add(current, links)
            current, links = name, []
        links.append((m.group(1), m.group(2)))
        last_end = m.end()
    if current and links:
        add(current, links)


def _protect(text: str) -> tuple[str, list[str]]:
    """Hide bold labels and existing links so names inside them are not linked."""
    saved: list[str] = []

    def keep(m):
        saved.append(m.group(0))
        return f"\x00{len(saved) - 1}\x00"
    text = LINK.sub(keep, text)
    text = re.sub(r"\[[^\]]*\]\([^)]*\)", keep, text)
    text = BOLD.sub(keep, text)
    return text, saved


def _restore(text: str, saved: list[str]) -> str:
    return re.sub(r"\x00(\d+)\x00", lambda m: saved[int(m.group(1))], text)


def _lookup(token: str, companies: dict[str, dict]) -> tuple[str, dict] | None:
    for cand in (token, token.split(" ")[0]):
        if NOT_COMPANY.match(cand):
            continue
        key = normalise(cand)
        if key in companies:
            return cand, companies[key]
    return None


def link_cell(cell: str, companies: dict[str, dict], unmatched: set[str] | None = None) -> str:
    text, saved = _protect(cell)

    def repl(m):
        token = m.group(1)
        hit = _lookup(token, companies)
        if not hit:
            if unmatched is not None and token[:1].isupper() and not NOT_COMPANY.match(token) and re.search(r"[A-Za-z]{2}", token):
                unmatched.add(token)
            return token
        cand, entry = hit
        tdoc, url = entry["links"][0]
        rest = token[len(cand):]
        return f"[{cand}]({url} \"{tdoc}\"){rest}"
    return _restore(NAME.sub(repl, text), saved)


def _segments(cell: str, header: str) -> list[tuple[str, str]]:
    """Split a position cell into (position label, text with company names)."""
    marks = [(m.start(), m.end(), m.group(1)) for m in re.finditer(r"\*\*(.+?)\*\*\s*:?", cell)]
    marks += [(m.start(), m.end(), m.group(1)) for m in PLAIN_LABEL.finditer(cell)
              if not any(s <= m.start() < e for s, e, _ in marks)]
    marks.sort()
    if not marks:
        return [(header, cell)]
    out = []
    if cell[:marks[0][0]].strip():
        out.append((header, cell[:marks[0][0]]))
    for i, (s, e, label) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(cell)
        out.append((label.strip(), cell[e:end]))
    return out


def _short(text: str, limit: int = 26) -> str:
    text = re.sub(r"\s+", " ", BOLD.sub(r"\1", text)).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def link_section(body: str) -> tuple[str, set[str]]:
    """Return (body with linked topic tables + per-company summary, unmatched names)."""
    bounds = section_bounds(body)
    if not bounds:
        return body, set()
    start, end = bounds
    section = body[start:end]
    companies = company_tdocs(section)
    unmatched: set[str] = set()
    positions: dict[str, list[str]] = {}
    lines, header = section.splitlines(), None
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            header = None
            continue
        cells = _cells(line)
        if header is None:
            header = cells
            continue
        if set("".join(cells)) <= set("-: ") or not header or header[0] != "주제":
            continue
        topic = cells[0]
        for col in range(1, len(cells) - 1):  # skip topic and the result column
            col_header = header[col] if col < len(header) else ""
            for label, text in _segments(cells[col], col_header):
                def record(key: str, position: str) -> None:
                    item = f"{_short(topic)}: {_short(position, 20)}"
                    if item not in positions.setdefault(key, []):
                        positions[key].append(item)
                label_hit = _lookup(label, companies)
                if label_hit:  # "CMCC: 필요성 연구" -> the label is the company, the text its position
                    record(normalise(label_hit[0]), text.strip(" .") or col_header)
                    continue
                plain, _ = _protect(text)
                # Side notes such as "OPPO (CMCC 연구)" name companies that do NOT hold this position.
                plain = re.sub(r"\s\([^()]*\)", "", plain)
                for m in NAME.finditer(plain):
                    hit = _lookup(m.group(1), companies)
                    if hit:
                        record(normalise(hit[0]), label)
            cells[col] = link_cell(cells[col], companies, unmatched)
        lines[i] = "| " + " | ".join(cells) + " |"
    new_section = "\n".join(lines)
    if positions:
        hint = ('\n<p class="csi-sub">주제별 표의 업체 이름을 누르면 그 업체의 Tdoc 원문(zip)을 받습니다. '
                '맨 아래 "업체별 입장 모아 보기"에서 업체마다 입장을 모아 볼 수 있습니다.</p>\n')
        new_section = hint + new_section
        rows = sorted(positions.items(), key=lambda kv: companies[kv[0]]["name"].lower())
        table = [
            "",
            f'??? note "업체별 입장 모아 보기 ({len(rows)}개 업체, 위 주제별 표에서 자동 생성)"',
            "",
            "    | 업체 | Tdoc | 주제별 입장 |",
            "    |---|---|---|",
        ]
        for key, items in rows:
            entry = companies[key]
            links = " ".join(f"[{t}]({u})" for t, u in entry["links"])
            table.append(f"    | {entry['name']} | {links} | {'<br>'.join(items)} |")
        new_section = new_section.rstrip("\n") + "\n" + "\n".join(table) + "\n\n"
    return body[:start] + new_section + body[end:], unmatched
