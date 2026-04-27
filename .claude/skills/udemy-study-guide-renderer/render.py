#!/usr/bin/env python3
"""Render a Dyer Innovation–branded study guide PDF from a markdown source.

Pipeline: markdown (with optional YAML frontmatter)
  → pandoc → HTML5
  → callout/lead/table/page-break transforms (stdlib regex + html.parser)
  → cover + TOC + body pages + closing wrapped in <div class="doc">
  → weasyprint → PDF
  → optional: pandoc → docx (vanilla, no design overlay in v1)

Skill: udemy-study-guide-renderer (udemy-course-builder plugin).
Design source: Claude Design handoff bundle dyer-innovation-study-document-format.
"""
from __future__ import annotations

import argparse
import datetime
import html
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SKILL_DIR = Path(__file__).resolve().parent
ASSETS_DIR = SKILL_DIR / "assets"

DEFAULT_EYEBROW = "Dyer Innovation · Learning Content"
DEFAULT_QUOTE = (
    "You've written a function. Now we're going to make it fail on purpose, "
    "and then fix it. This is how you learn to debug."
)
DEFAULT_VERSION = "v1"

# Heuristic dispatch: (flavor, icon, [keywords lower-cased]).
# First match wins. Default → ("tip", "i").
CALLOUT_RULES = [
    ("trap",    "!", ["trap", "anti-pattern", "anti pattern", "warning", "do not", "don't"]),
    ("rule",    "→", ["decision rule", "rule of thumb", "principle"]),
    ("missed",  "✕", ["you missed", "common mistake", "what went wrong", "missed concept"]),
    ("example", "▤", ["example", "sample", "walkthrough", "applied"]),
    ("tip",     "i", ["tip", "note", "distractor", "caveat", "watch out"]),
]
DEFAULT_FLAVOR = ("tip", "i")


# ---------------------------------------------------------------------------
# 1. Frontmatter parsing (lightweight stdlib YAML subset)
# ---------------------------------------------------------------------------

def parse_frontmatter(src: str) -> tuple[dict, str]:
    """Split a markdown source into (frontmatter dict, body).

    Supports two YAML shapes only:
      key: value
      key: [a, b, c]
    """
    if not src.startswith("---\n"):
        return {}, src
    end = src.find("\n---\n", 4)
    if end == -1:
        # No closing fence — treat whole thing as body.
        return {}, src
    yaml_block = src[4:end]
    body = src[end + 5:]
    fm: dict = {}
    list_re = re.compile(r"^([\w_]+):\s*\[(.*)\]\s*$")
    kv_re = re.compile(r"^([\w_]+):\s*(.+?)\s*$")
    for line in yaml_block.splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        m = list_re.match(line)
        if m:
            items = [
                s.strip().strip('"').strip("'")
                for s in m.group(2).split(",")
                if s.strip()
            ]
            fm[m.group(1)] = items
            continue
        m = kv_re.match(line)
        if m:
            val = m.group(2).strip().strip('"').strip("'")
            fm[m.group(1)] = val
    return fm, body


# ---------------------------------------------------------------------------
# 2. Pandoc invocation
# ---------------------------------------------------------------------------

def md_to_html(md_body: str) -> str:
    """Convert markdown body to HTML5 via pandoc subprocess."""
    proc = subprocess.run(
        [
            "pandoc",
            "--from=gfm+yaml_metadata_block-yaml_metadata_block",
            "--to=html5",
            "--no-highlight",
            "--wrap=preserve",
        ],
        input=md_body,
        text=True,
        capture_output=True,
        check=True,
    )
    return proc.stdout


def md_to_docx(md_path: Path, docx_path: Path) -> None:
    """Vanilla docx via pandoc — no design overlay in v1."""
    subprocess.run(
        ["pandoc", str(md_path), "-o", str(docx_path)],
        check=True,
    )


# ---------------------------------------------------------------------------
# 3. HTML transforms
# ---------------------------------------------------------------------------

def add_table_class(html_doc: str) -> str:
    """Add the design's `.dyer` class to every <table>."""
    return re.sub(r"<table>", '<table class="dyer">', html_doc)


def honor_pagebreak_markers(html_doc: str) -> str:
    """`<!-- pagebreak -->` in the source markdown → forced page break."""
    return html_doc.replace(
        "<!-- pagebreak -->",
        '<div style="page-break-after: always; break-after: page;"></div>',
    )


_BLOCKQUOTE_RE = re.compile(
    r"<blockquote>\s*(.*?)\s*</blockquote>",
    re.DOTALL,
)

# A bold paragraph that may be a callout title — e.g. <p><strong>Trap: …</strong></p>
# optionally followed by a single <ul>/<ol> block which forms the callout body.
# Non-greedy and conservative: ONLY captures a single <strong> at the start
# of the paragraph + any inline tail + an optional immediate list sibling.
_BOLD_CALLOUT_RE = re.compile(
    r'<p>\s*<strong>([^<]+?)</strong>([^<]*?)</p>'
    r'(\s*(?:<ul>.*?</ul>|<ol>.*?</ol>))?',
    re.DOTALL,
)


def _classify_blockquote_text(first_line: str) -> tuple[str, str]:
    """Pick (flavor, icon) by keyword match on the first non-empty line."""
    needle = first_line.lower()
    for flavor, icon, keywords in CALLOUT_RULES:
        if any(k in needle for k in keywords):
            return flavor, icon
    return DEFAULT_FLAVOR


def _has_callout_keyword(text: str) -> bool:
    needle = text.lower()
    return any(
        any(k in needle for k in keywords)
        for _, _, keywords in CALLOUT_RULES
    )


def classify_callouts(html_doc: str) -> str:
    """Rewrite each <blockquote> as a styled .callout.<flavor> container.

    Heuristic: extract the first textual line of the blockquote (after stripping
    inner HTML), match against the keyword table, pick a flavor.
    """
    def _replace(match: re.Match) -> str:
        inner = match.group(1)
        # Pull the first line of plain text (strip HTML tags) for classification.
        plain = re.sub(r"<[^>]+>", " ", inner).strip()
        first_line = plain.split("\n", 1)[0].strip()[:140]
        flavor, icon = _classify_blockquote_text(first_line)
        # Try to lift a title (first <strong>...</strong> OR first sentence ≤ 80 chars)
        title_match = re.search(r"<strong>(.*?)</strong>", inner)
        if title_match:
            title_html = title_match.group(1).strip()
            # Drop the leading <strong>...</strong> from the body to avoid duplication.
            body_inner = inner.replace(title_match.group(0), "", 1).lstrip(" :—-")
        else:
            # Use the first line as the title; rest is body.
            title_html = html.escape(first_line)
            body_inner = inner
        return (
            f'<div class="callout {flavor}">'
            f'<span class="icon">{icon}</span>'
            f'<div class="label">{html.escape(flavor.upper())}</div>'
            f'<h4 class="title">{title_html}</h4>'
            f'{body_inner}'
            f'</div>'
        )

    return _BLOCKQUOTE_RE.sub(_replace, html_doc)


def classify_bold_paragraph_callouts(html_doc: str) -> str:
    """Detect bold-paragraph callouts in markdown like:

        **Trap: the conservatism instruction.**

        - bullet 1
        - bullet 2

    These render as <p><strong>...</strong></p><ul>...</ul> after pandoc, and
    we want them styled as `.callout.<flavor>` boxes when the bold lead-in
    contains a callout keyword. Conservative: ONLY converts when the bold
    text matches a known keyword — plain bold paragraphs stay as prose.
    """
    def _replace(match: re.Match) -> str:
        bold_text = match.group(1).strip()
        inline_tail = match.group(2).strip()
        following_list = match.group(3) or ""

        if not _has_callout_keyword(bold_text):
            return match.group(0)  # leave unchanged

        flavor, icon = _classify_blockquote_text(bold_text)
        # Body: anything after the bold (e.g. trailing colon + sentence) plus
        # the immediately-following list. Wrap in a <div> so layout is clean.
        body_parts = []
        if inline_tail:
            body_parts.append(f'<p>{inline_tail.lstrip(" :—-")}</p>')
        if following_list:
            body_parts.append(following_list.strip())
        body_html = "".join(body_parts) if body_parts else ""

        return (
            f'<div class="callout {flavor}">'
            f'<span class="icon">{icon}</span>'
            f'<div class="label">{html.escape(flavor.upper())}</div>'
            f'<h4 class="title">{html.escape(bold_text)}</h4>'
            f'{body_html}'
            f'</div>'
        )

    return _BOLD_CALLOUT_RE.sub(_replace, html_doc)


def detect_lead(section_html: str) -> str:
    """Promote the first <p>...</p> immediately after the H1 to <p class="lead">."""
    return re.sub(
        r"(</h1>\s*)<p>",
        r'\1<p class="lead">',
        section_html,
        count=1,
    )


# ---------------------------------------------------------------------------
# 4. Split body into per-H1 sections
# ---------------------------------------------------------------------------

_H1_OPEN_RE = re.compile(
    r'<h1(?:\s+id="[^"]*")?(?:\s+class="[^"]*")?>',
    re.IGNORECASE,
)
_H2_OPEN_RE = re.compile(
    r'<h2(?:\s+id="[^"]*")?(?:\s+class="[^"]*")?>',
    re.IGNORECASE,
)


def _split_on_pattern(body_html: str, opener_re: re.Pattern,
                      heading_re: re.Pattern, child_re: re.Pattern) -> list[dict]:
    """Generic splitter — wraps each section starting at `opener_re`."""
    starts = [m.start() for m in opener_re.finditer(body_html)]
    if not starts:
        return []
    starts.append(len(body_html))
    sections = []
    for i in range(len(starts) - 1):
        chunk = body_html[starts[i] : starts[i + 1]]
        title_match = heading_re.search(chunk)
        title_html = title_match.group(1) if title_match else ""
        title_text = re.sub(r"<[^>]+>", "", title_html).strip()
        # Normalize the chapter heading down to <h1>...</h1> shape so the
        # rest of the pipeline (build_body_pages, detect_lead) can target
        # it uniformly even when the source used <h2>.
        normalized = chunk
        if heading_re.pattern.startswith("<h2"):
            normalized = heading_re.sub(
                lambda m: f"<h1>{m.group(1)}</h1>", chunk, count=1
            )
        children = [
            re.sub(r"<[^>]+>", "", m).strip()
            for m in child_re.findall(chunk)
        ]
        sections.append({
            "title": title_text,
            "h2_titles": children,
            "html": normalized,
        })
    return sections


_H1_HEADING_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.DOTALL)
_H2_HEADING_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.DOTALL)
_H3_HEADING_FINDALL = re.compile(r"<h3[^>]*>(.*?)</h3>", re.DOTALL)


def split_on_h1(body_html: str) -> list[dict]:
    """Split body into chapter sections.

    Behavior:
      - If body has 2+ H1s → split on H1 (each H1 = chapter), H2s = chapter sub-titles
      - If body has exactly 1 H1 → treat that H1 as the doc title (consumed elsewhere),
        then split on H2 (each H2 = chapter), H3s = chapter sub-titles
      - If body has 0 H1s but >=1 H2 → split on H2
      - Otherwise → empty list
    """
    h1_count = len(_H1_OPEN_RE.findall(body_html))
    h2_count = len(_H2_OPEN_RE.findall(body_html))

    if h1_count >= 2:
        return _split_on_pattern(
            body_html, _H1_OPEN_RE, _H1_HEADING_RE, _H2_HEADING_RE,
        )
    if h1_count == 1 and h2_count >= 1:
        # Strip the doc-title H1 from the body before splitting on H2.
        # The doc title has already been captured into frontmatter fallbacks
        # by the caller via raw HTML inspection.
        first_h1_end = re.search(r"</h1>", body_html, re.IGNORECASE)
        body_after_title = body_html[first_h1_end.end():] if first_h1_end else body_html
        return _split_on_pattern(
            body_after_title, _H2_OPEN_RE, _H2_HEADING_RE, _H3_HEADING_FINDALL,
        )
    if h1_count == 0 and h2_count >= 1:
        return _split_on_pattern(
            body_html, _H2_OPEN_RE, _H2_HEADING_RE, _H3_HEADING_FINDALL,
        )
    if h1_count == 1 and h2_count == 0:
        # Single-H1 doc with no H2s — treat as one chapter.
        return _split_on_pattern(
            body_html, _H1_OPEN_RE, _H1_HEADING_RE, _H2_HEADING_RE,
        )
    return []


def extract_doc_title(body_html: str) -> str:
    """Pull the first H1 text (if any) for use as the cover title fallback."""
    m = _H1_HEADING_RE.search(body_html)
    if not m:
        return ""
    return re.sub(r"<[^>]+>", "", m.group(1)).strip()


# ---------------------------------------------------------------------------
# 5. Cover / TOC / body / closing builders
# ---------------------------------------------------------------------------

def build_cover(fm: dict) -> str:
    eyebrow = html.escape(fm.get("eyebrow", DEFAULT_EYEBROW))
    title = html.escape(fm.get("title", "Untitled"))
    subtitle = fm.get("subtitle", "")
    last_updated = html.escape(fm.get("last_updated", _today_str()))
    version = html.escape(fm.get("version", DEFAULT_VERSION))
    focus_list = fm.get("focus_list", [])

    subtitle_html = (
        f'<p class="cover-subtitle">{html.escape(subtitle)}</p>'
        if subtitle else ""
    )

    if focus_list:
        focus_inner = (
            '<span class="sep">·</span>'
            .join(html.escape(item) for item in focus_list)
        )
        emphasis_html = (
            '<div class="cover-emphasis">'
            '<span class="label">This guide emphasizes</span>'
            f'<div class="focus-list">{focus_inner}</div>'
            '</div>'
        )
    else:
        emphasis_html = ""

    return (
        '<section class="page cover">'
        '<header class="cover-mark">'
        '<img src="assets/logo-mark.png" alt="">'
        '<span class="wordmark">Dyer Innovation</span>'
        '</header>'
        '<div class="cover-body">'
        f'<div class="cover-eyebrow">{eyebrow}</div>'
        f'<h1 class="cover-title">{title}</h1>'
        f'{subtitle_html}'
        '<div class="cover-leaf-rule"><span class="dot"></span><span class="line"></span></div>'
        '<dl class="cover-meta">'
        f'<div><dt>Last Updated</dt><dd>{last_updated}</dd></div>'
        '</dl>'
        '</div>'
        f'{emphasis_html}'
        '<footer class="cover-foot">'
        '<span>DYER INNOVATION · LEARNING CONTENT</span>'
        f'<span>{version}</span>'
        '</footer>'
        '</section>'
    )


def build_toc(sections: list[dict], doc_title: str) -> str:
    """Auto-TOC. Page numbers are H1-ordinal-based; CSS handles `01`/`02` prefixes."""
    if not sections:
        return ""
    items = []
    # Real first body page = 3 (cover=1, TOC=2, then body starts at 3)
    page_cursor = 3
    for sec in sections:
        h1_pg = page_cursor
        h2_lines = "".join(
            f'<li><span>{html.escape(t)}</span><span class="pg">{h1_pg}</span></li>'
            for t in sec["h2_titles"]
        )
        items.append(
            '<li>'
            f'<div class="row"><span class="title">{html.escape(sec["title"])}</span>'
            f'<span class="pg">{h1_pg}</span></div>'
            + (f'<ol>{h2_lines}</ol>' if h2_lines else "")
            + '</li>'
        )
        # Each section conservatively occupies 1 page in the TOC numbering.
        # Real pagination handled by weasyprint @media print rules.
        page_cursor += max(1, len(sec["h2_titles"]) // 3 + 1)

    running_title = html.escape(f"{doc_title} · Contents")
    return (
        f'<section class="page" data-running-title="{running_title}" data-page-num="ii">'
        '<h2 class="toc-title">Contents</h2>'
        '<nav class="toc"><ol>'
        f'{"".join(items)}'
        '</ol></nav>'
        '</section>'
    )


_H1_REPLACE_RE = re.compile(
    r'<h1[^>]*>(.*?)</h1>',
    re.DOTALL,
)


def build_body_pages(sections: list[dict]) -> str:
    """Wrap each section in its own <section class="page"> with running title + page num."""
    pages = []
    page_cursor = 3
    for idx, sec in enumerate(sections, start=1):
        nn = f"{idx:02d}"
        title = sec["title"]
        # Rewrite the H1 with the design's two-span structure: [num] [text]
        new_h1 = (
            f'<h1 class="h1"><span class="num">{nn}</span>'
            f'<span>{html.escape(title)}</span></h1>'
        )
        section_html = _H1_REPLACE_RE.sub(new_h1, sec["html"], count=1)
        section_html = detect_lead(section_html)

        running = html.escape(f"{nn} · {title}")
        pages.append(
            f'<section class="page" data-running-title="{running}" '
            f'data-page-num="{page_cursor}">'
            f'{section_html}'
            '</section>'
        )
        page_cursor += max(1, len(sec["h2_titles"]) // 3 + 1)
    return "".join(pages)


def build_closing(fm: dict) -> str:
    quote = html.escape(fm.get("closing_quote", DEFAULT_QUOTE))
    return (
        '<section class="page cover" style="justify-content:center">'
        '<div style="margin:auto; text-align:center; max-width: 480px;">'
        '<img src="assets/logo-mark-on-mint.png" alt="" '
        'style="height:72px; width:auto; margin-bottom: 32px; border-radius: 16px;">'
        '<p style="font-family: var(--font-display); font-size: 18pt; '
        'font-style: italic; color: var(--forest-500); line-height: 1.4; '
        'max-width: none;">'
        f'{quote}'
        '</p>'
        '<div style="margin-top:48px; height:1px; background: var(--border); '
        'width: 80px; margin-left:auto; margin-right:auto;"></div>'
        '<p style="margin-top:24px; font-size: 9pt; color: var(--fg-subtle); '
        'letter-spacing: 0.08em; text-transform: uppercase;">'
        'Dyer Innovation · Learning Content'
        '</p>'
        '</div>'
        '</section>'
    )


# ---------------------------------------------------------------------------
# 6. Stitch + render
# ---------------------------------------------------------------------------

def stitch_html(cover: str, toc: str, body: str, closing: str, doc_title: str) -> str:
    title_safe = html.escape(doc_title)
    # Inline @page rules + forced page-break overrides — weasyprint doesn't always
    # honor `@media print` from external stylesheets in the same way browsers do
    # for screen-print toggling. We assert the print state here.
    forced_print_css = (
        '<style>'
        '@page { size: Letter; margin: 0; }'
        'html, body { background: white; }'
        # Critical: weasyprint doesn't honor page-break inside flex containers,
        # so override the design's `.doc { display: flex }` to plain block flow
        # for the print render.
        '.doc { '
        '  display: block !important; '
        '  padding: 0 !important; '
        '  gap: 0 !important; '
        '}'
        '.page { '
        '  box-shadow: none !important; '
        '  margin: 0 !important; '
        '  page-break-after: always; '
        '  break-after: page; '
        '  width: 100% !important; '
        '}'
        '.page:last-child { page-break-after: auto; break-after: auto; }'
        '</style>'
    )
    return (
        '<!doctype html><html lang="en"><head>'
        '<meta charset="utf-8">'
        f'<title>{title_safe}</title>'
        # Tokens MUST come before format.css so :root vars are defined when
        # format.css selectors reference them. format.css's own @import for
        # colors_and_type.css uses a relative path that 404s in the bundled
        # skill layout — explicit <link> bypasses that.
        '<link rel="stylesheet" href="assets/colors_and_type.css">'
        '<link rel="stylesheet" href="assets/format.css">'
        f'{forced_print_css}'
        '</head>'
        '<body>'
        f'<div class="doc">{cover}{toc}{body}{closing}</div>'
        '</body></html>'
    )


def render_pdf(html_doc: str, output: Path) -> None:
    """Render via weasyprint with base_url set to the skill dir so assets/ resolves."""
    # Ensure DYLD_FALLBACK_LIBRARY_PATH for macOS pango/harfbuzz libs.
    os.environ.setdefault(
        "DYLD_FALLBACK_LIBRARY_PATH", "/opt/homebrew/lib"
    )
    from weasyprint import HTML  # imported lazily so --help works without weasyprint
    HTML(string=html_doc, base_url=str(SKILL_DIR)).write_pdf(str(output))


# ---------------------------------------------------------------------------
# 7. Helpers
# ---------------------------------------------------------------------------

def _today_str() -> str:
    today = datetime.date.today()
    # Cross-platform date formatting (no %-d on Windows; %#d on Windows; we'll be safe).
    return today.strftime("%B ") + str(today.day) + today.strftime(", %Y")


# ---------------------------------------------------------------------------
# 8. CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="render.py",
        description=(
            "Render a Dyer Innovation–branded study guide PDF from a markdown "
            "source. Supports YAML frontmatter for cover-page metadata."
        ),
    )
    ap.add_argument("--input", required=True, type=Path,
                    help="Path to the markdown source")
    ap.add_argument("--output", type=Path, default=None,
                    help="Path to the output PDF (default: <input>.pdf)")
    ap.add_argument("--docx", action="store_true",
                    help="Also produce <output>.docx via vanilla pandoc")
    args = ap.parse_args(argv)

    if not args.input.exists():
        sys.exit(f"ERROR: input not found: {args.input}")

    src = args.input.read_text(encoding="utf-8")
    fm, body_md = parse_frontmatter(src)

    raw_html = md_to_html(body_md)
    raw_html = honor_pagebreak_markers(raw_html)
    raw_html = add_table_class(raw_html)
    raw_html = classify_callouts(raw_html)
    raw_html = classify_bold_paragraph_callouts(raw_html)

    # Capture the doc-title H1 (used as cover-title fallback) BEFORE splitting,
    # because the splitter strips it when the doc has only one H1 + ≥1 H2.
    doc_title_fallback = extract_doc_title(raw_html)

    sections = split_on_h1(raw_html)
    if not sections:
        sys.exit("ERROR: input has no H1 or H2 — at least one heading is required.")

    fm.setdefault("title", doc_title_fallback or sections[0]["title"])
    fm.setdefault("eyebrow", DEFAULT_EYEBROW)
    fm.setdefault("subtitle", "")
    fm.setdefault("version", DEFAULT_VERSION)
    fm.setdefault("last_updated", _today_str())

    cover = build_cover(fm)
    toc = build_toc(sections, fm["title"])
    body = build_body_pages(sections)
    closing = build_closing(fm)
    full = stitch_html(cover, toc, body, closing, fm["title"])

    out = args.output or args.input.with_suffix(".pdf")
    out.parent.mkdir(parents=True, exist_ok=True)
    if os.environ.get("RENDER_DEBUG_HTML"):
        debug_path = out.with_suffix(".debug.html")
        debug_path.write_text(full, encoding="utf-8")
        print(f"DEBUG HTML written: {debug_path}")
    render_pdf(full, out)
    print(f"PDF written: {out}")

    if args.docx:
        docx_out = out.with_suffix(".docx")
        md_to_docx(args.input, docx_out)
        print(f"DOCX written: {docx_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
