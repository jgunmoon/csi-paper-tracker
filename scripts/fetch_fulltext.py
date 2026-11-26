#!/usr/bin/env python3
"""Download an arXiv paper's full text as plain text for reading.

Tries the arXiv HTML rendering first (keeps table/figure captions), then the PDF
(via `pdftotext` if installed, else pypdf). Prints the path of the text file and
which source worked, or exits 2 if neither is available ("abstract only").

Usage:
    python scripts/fetch_fulltext.py 2611.25378 --out-dir /tmp/fulltext
"""
from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

USER_AGENT = "csi-paper-tracker/1.0 (arXiv full-text reader)"
SKIP_TAGS = {"script", "style", "nav", "header", "footer", "math", "annotation", "svg"}
BLOCK_TAGS = {"p", "div", "section", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr",
              "figcaption", "caption", "table", "br", "article", "blockquote"}


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            # Keep LaTeX source of formulas: arXiv HTML puts it in alttext.
            if tag == "math":
                alt = dict(attrs).get("alttext")
                if alt:
                    self.out.append(f" ${alt}$ ")
            self.skip += 1
        elif tag in BLOCK_TAGS:
            self.out.append("\n")
        elif tag in ("td", "th"):
            self.out.append(" | ")

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
        elif tag in BLOCK_TAGS:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def get(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read()
    except Exception as exc:
        print(f"  {url}: {exc}", file=sys.stderr)
        return None


def from_html(arxiv_id: str) -> str | None:
    raw = get(f"https://arxiv.org/html/{arxiv_id}")
    if not raw:
        return None
    page = raw.decode("utf-8", "replace")
    if "ltx_document" not in page and "ltx_page" not in page:
        return None  # arXiv returns a "no HTML for this paper" page
    p = _Text()
    p.feed(page)
    text = html.unescape("".join(p.out))
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def from_pdf(arxiv_id: str, work: Path) -> str | None:
    raw = get(f"https://arxiv.org/pdf/{arxiv_id}")
    if not raw or not raw.startswith(b"%PDF"):
        return None
    pdf = work / f"{arxiv_id}.pdf"
    pdf.write_bytes(raw)
    if shutil.which("pdftotext"):
        txt = work / f"{arxiv_id}.pdf.txt"
        subprocess.run(["pdftotext", "-layout", str(pdf), str(txt)], check=False)
        if txt.exists():
            return txt.read_text(encoding="utf-8", errors="replace")
    try:
        from pypdf import PdfReader  # optional dependency
    except ImportError:
        return None
    return "\n".join(page.extract_text() or "" for page in PdfReader(str(pdf)).pages)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arxiv_id")
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    aid = re.sub(r"v\d+$", "", args.arxiv_id)

    text, source = from_html(aid), "html"
    if not text:
        text, source = from_pdf(aid, args.out_dir), "pdf"
    if not text or len(text) < 2000:
        print(f"{aid}: full text unavailable -> abstract only", file=sys.stderr)
        return 2
    out = args.out_dir / f"{aid}.txt"
    out.write_text(text, encoding="utf-8")
    print(f"{out}\t{source}\t{len(text)} chars")
    return 0


if __name__ == "__main__":
    sys.exit(main())
