---
name: udemy-study-guide-renderer
description: "Render a Dyer Innovation–branded study guide PDF (and optionally editable .docx) from a markdown source file. Embeds the design system (Newsreader display, Geist body, JetBrains Mono code; sprout/teal/forest palette; cover page + auto-TOC + numbered sections + 5 callout flavors + dark-header tables). Supports YAML frontmatter for cover-page metadata. Pure file output — no browser. Use when authoring downloadable PDF resources for a Udemy course."
allowed-tools: "Read, Glob, Grep, Write, Edit, Bash"
---

# Udemy Study Guide Renderer

Renders Dyer Innovation–branded study guides from markdown into print-ready PDFs (and optional editable `.docx`). Sibling to `udemy-slide-creator` (which targets `.pptx`). Where slide-creator turns lecture scripts into recording decks, this skill turns standalone study material into downloadable course resources.

## When to use

- You have a markdown study guide and need a branded PDF for upload as a Udemy lecture/section resource.
- You want to scale a single tested design across multiple guides without re-laying-out each one.
- You need a quick re-render after editing the source markdown (idempotent — overwrites the output PDF in place).

## When NOT to use

- **Slide deck for recording** → use `udemy-slide-creator`.
- **Coding exercise files** → use `udemy-coding-exercise-authoring`.
- **Pushing the rendered PDF into the Udemy dashboard** → use `udemy-resource-uploader` after this skill produces the PDF.
- **Editing the design itself** — the design lives in `assets/format.css` + `assets/colors_and_type.css`. Treat them as embedded; don't drift them out of sync with future Claude Design exports.

## Prerequisites

Verified on macOS 14+ with Apple Silicon. Other macOS / Linux paths likely work with a different `DYLD_FALLBACK_LIBRARY_PATH`.

| Dep | Install |
|---|---|
| Python 3.9+ | system or homebrew |
| `weasyprint` | `pip3 install --user weasyprint` |
| `pango` + `harfbuzz` (weasyprint native deps) | `brew install pango` (pulls harfbuzz, libdatrie, libthai) |
| `pandoc` | `brew install pandoc` |

**macOS quirk:** weasyprint needs `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` to find pango at runtime. The renderer sets this in its own environment via `os.environ.setdefault`, so direct CLI invocations work, but if you import the module in a different Python process you may need to set it yourself.

## Input format

A single markdown file. **Optional** YAML frontmatter for cover-page metadata:

```yaml
---
title: "Claude Code for Continuous Integration"
eyebrow: "Claude Certified Architect · Foundations"
subtitle: "Scenario 5 — a study guide for prompt-based output control, CLI flag awareness, severity calibration, and inline reasoning."
scenario_num: "05"
focus_list: ["Prompt-based output control", "CLI flag awareness", "Severity calibration", "Inline reasoning"]
version: "v2 · CCA-CI-05"
last_updated: "April 26, 2026"
closing_quote: "You've written a function. Now we're going to make it fail on purpose, and then fix it. This is how you learn to debug."
---
```

| Field | Required | Default |
|---|---|---|
| `title` | no | first H1 of body |
| `eyebrow` | no | `"Dyer Innovation · Learning Content"` |
| `subtitle` | no | omitted |
| `scenario_num` | no | omitted (reserved for future use; currently informational only) |
| `focus_list` | no | omitted (entire `.cover-emphasis` block hidden if absent) |
| `version` | no | `"v1"` |
| `last_updated` | no | today's date in `Month D, YYYY` format |
| `closing_quote` | no | the design's stock quote |

The frontmatter parser supports a strict YAML subset: `key: scalar` and `key: [list]`. No nested objects, no multi-line strings. Anything more complex requires a real YAML lib (out of scope for v1).

## Body conventions

The renderer treats markdown structurally. Conventions that matter for design fidelity:

- **One H1 per logical "chapter"** — each H1 starts a new numbered page section (`01`, `02`, …). Don't use H1 inside content; reserve it for chapter starts.
- **First paragraph after each H1 becomes `.lead`** (italic-suppressed display font, larger than body text).
- **Tables** auto-promote to `<table class="dyer">` — dark-forest header with mint text, alternating row backgrounds, fixed layout.
- **Blockquotes auto-classify into 5 callout flavors** by keyword in the first line:
  - "Trap" / "Anti-pattern" / "Warning" / "Don't" → `.callout.trap` (yellow, `!`)
  - "Decision Rule" / "Rule of Thumb" / "Principle" → `.callout.rule` (green, `→`)
  - "You missed" / "Common mistake" / "What went wrong" → `.callout.missed` (red, `✕`)
  - "Example" / "Sample" / "Walkthrough" / "Applied" → `.callout.example` (mint, `▤`)
  - "Tip" / "Note" / "Distractor" / "Caveat" / "Watch out" → `.callout.tip` (teal, `i`)
  - Default (no match) → `.callout.tip`
- **`<!-- pagebreak -->`** in the markdown forces a page break at that point. Useful for long content sections that auto-flow awkwardly.

## Invocation

### Direct CLI

```bash
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib python3 \
  ~/Documents/dev/udemy-courses/udemy-course-builder/.claude/skills/udemy-study-guide-renderer/render.py \
  --input ~/path/to/study-guide.md \
  --output ~/path/to/study-guide.pdf
```

### With editable .docx alongside the PDF

```bash
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib python3 \
  ~/.../render.py \
  --input X.md --output X.pdf --docx
```

The `.docx` is vanilla pandoc output — no design overlay in v1. (See "Out of scope" below.)

### As a Python module

```python
import subprocess, os
env = {**os.environ, "DYLD_FALLBACK_LIBRARY_PATH": "/opt/homebrew/lib"}
subprocess.run(
    ["python3", "/path/to/render.py",
     "--input", "/path/in.md",
     "--output", "/path/out.pdf"],
    env=env, check=True,
)
```

## Process steps (what the renderer does internally)

1. **Preflight** — verify input file exists; parse frontmatter; ensure body has at least one H1.
2. **Markdown → HTML5 via pandoc** subprocess (`--from=gfm --to=html5 --no-highlight --wrap=preserve`).
3. **Honor `<!-- pagebreak -->` markers** — replaced with forced page-break divs.
4. **Promote tables** — every `<table>` gets `class="dyer"`.
5. **Classify callouts** — every `<blockquote>` rewritten as `<div class="callout flavor">` with icon + label + title + body. Heuristic dispatch on first line; default flavor is `.tip`.
6. **Split body on H1** — each H1 becomes its own `<section class="page">` with `data-running-title="NN · <title>"` and `data-page-num="N"`.
7. **Promote first paragraph after each H1 to `<p class="lead">`**.
8. **Build cover page** — frontmatter + defaults; emphasis block hidden if no `focus_list`.
9. **Build TOC** — H1 + H2 hierarchy, design CSS handles `01`/`02` numeric prefixes via `counter(tocnum, decimal-leading-zero)`.
10. **Build closing page** — logo on mint + italic display quote (configurable via `closing_quote` frontmatter).
11. **Stitch full HTML** with `<link rel="stylesheet" href="assets/format.css">`.
12. **Render PDF via weasyprint** — `base_url` = skill directory so `assets/logo-mark.png` resolves.
13. **(Optional) Render `.docx` via pandoc** if `--docx` flag supplied.

## Constraints (HARD)

- **Embedded design assets only** — the skill bundles its own `format.css`, `colors_and_type.css`, and 5 image assets. No runtime dependency on the course repo or any external CDN beyond the Google Fonts `@import` (which weasyprint fetches if online; falls back to system serifs if offline).
- **Pure file output** — never opens a browser, never makes network calls except weasyprint's optional Google Fonts fetch.
- **Idempotent** — running twice on the same input produces the same output (modulo `last_updated` if not pinned in frontmatter).
- **Never modifies the source markdown.**
- **Never deletes the output if it exists** — overwrites in place.

## Worked example

Render the Structured Output study guide:

```bash
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib python3 \
  ~/Documents/dev/udemy-courses/udemy-course-builder/.claude/skills/udemy-study-guide-renderer/render.py \
  --input ~/Documents/dev/udemy-courses/claude-architect-udemy-course/Claude-Created-Exam-Section-guides/CCA-Structured-Output-Study-Guide.md \
  --output ~/Documents/dev/udemy-courses/claude-architect-udemy-course/Claude-Created-Exam-Section-guides/CCA-Structured-Output-Study-Guide.pdf
```

Expected: a 15–25 page PDF with cover + auto-TOC + 9 numbered sections + closing. Size 200 KB – 1 MB depending on whether Google Fonts were fetched at render time.

## Out of scope (v1)

- **Themed `.docx` output** — current `--docx` path is vanilla pandoc with no Dyer Innovation overlay. The course already has a `_dyer-innovation-template.docx` reference file; future work could thread it as `--reference-doc` to pandoc.
- **Real rendered pagination in the TOC** — page numbers are H1-ordinal-based estimates. To get true rendered page numbers we'd need a two-pass render (first to discover, second to embed). Acceptable for v1 since most readers scroll/scan rather than jump by page number.
- **Multi-language support** — design assumes English typography (font tracking, hyphenation).
- **Embedded fonts** — no `.woff2` bundling. Online runs fetch from Google Fonts CDN; offline runs fall back to system serif/sans/mono.
- **Footnotes / endnotes** — pandoc passes them through but the design CSS doesn't have explicit footnote styling.
- **Re-running with a different theme** — design system is hard-wired. Forking the skill is the path for variants.

## Cross-references

- **Sibling skills:** `udemy-slide-creator` (.pptx authoring), `udemy-resource-uploader` (pushes the rendered PDF into the Udemy dashboard), `udemy-curriculum-populator` (sections + lectures must exist before resources can attach).
- **Design source:** Claude Design handoff bundle `dyer-innovation-study-document-format` (extracted to `/tmp/anthropic-design-extract/` during initial build; assets copied verbatim into this skill's `assets/`).
- **Token reference:** `assets/colors_and_type.css` — same design tokens used in the course's Slidev decks (`slidev/design-system.css`).
