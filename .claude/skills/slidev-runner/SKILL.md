---
name: slidev-runner
description: "Run, build, export, and create Slidev (slide.dev) presentations for Udemy courses. Use this skill whenever the user mentions Slidev, slide.dev, running slides locally, launching a presentation server, or viewing markdown-based presentations in the browser. Also trigger when the user has .md files that look like Slidev decks (frontmatter with theme/transition/mdc fields) and wants to preview, build, export, or create them. Handles npm setup, multi-lecture port management, PDF export, SPA builds, and generating new branded Slidev presentations from udemy-lecture-writer scripts. Preferred slide format — replaced udemy-slide-creator (.pptx) as of 2026-03."
---

# Slidev Runner

You help users run, preview, build, export, and create Slidev presentations for Udemy courses using the Dyer Innovation brand system.

Slidev is now the preferred slide format for this course system. The older `udemy-slide-creator` skill (which produced `.pptx` via python-pptx) is considered legacy.

## What Slidev Is

Slidev is a markdown-based presentation framework powered by Vue.js. Each presentation is a `.md` file with YAML frontmatter (theme, transition, highlighter, etc.) and slides separated by `---`. It supports speaker notes in HTML comments, Vue components, animations via `<v-click>`, and custom CSS.

---

## Creating New Slides from Lecture Scripts

When asked to build or create slides for a lecture:

### Step 1 — Locate the script

Scripts live in `<course-dir>/scripts/section-XX-<slug>/<lecture>.md`. Read the script fully.

### Step 2 — Determine output path

Slidev files go in `<course-dir>/slidev/` alongside the other presentations:
```
<course-dir>/slidev/lecture-<N.N>.md
```

### Step 3 — Confirm project assets exist

The `slidev/` directory needs:
- `style.css` — Dyer Innovation brand CSS (copy from existing project if missing)
- `public/logo.png` — Dyer Innovation logo (copy from existing project if missing)
- `package.json` — Slidev dependencies (see Prerequisites section)

### Step 4 — Build the Slidev markdown

Each lecture follows this structure:

**Frontmatter + style import (once, at top):**
```yaml
---
theme: default
title: "Lecture N.M: <Title>"
info: |
  Claude Certified Architect – Foundations
  Section X: <Section Name>
highlighter: shiki
transition: fade-out
mdc: true
---

<style>
@import './style.css';
</style>
```

**Slide 1 — Title/Cover (layout: cover):**
```html
<div class="di-cover-accent"></div>

<div style="height: 100%; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center;">
  <div class="di-course-label">Claude Certified Architect – Foundations</div>
  <div class="di-cover-title"><Lecture Title></div>
  <div class="di-cover-subtitle">Lecture N.M · Section X: <Section Name></div>
</div>

<img src="/logo.png" class="di-logo-centered" />

<!--
<opening narration from script>
-->
```

**Content slides (layout: default):**
```yaml
---
layout: default
---
```
Followed by:
```html
<div class="di-header"><Slide Title></div>

<div class="di-body">
  <v-click><p>First point</p></v-click>
  <v-click><p>Second point</p></v-click>
</div>

<img src="/logo.png" class="di-logo" />

<!--
<narration for this slide>
-->
```

**Exam Tip slides:**
```yaml
---
layout: default
class: di-exam-slide
---
```
```html
<div class="di-exam-banner">⚡ EXAM TIP</div>

<v-click>
<div class="di-exam-subtitle"><Topic></div>
<div class="di-exam-body"><Context></div>
</v-click>

<v-click>
<div class="di-trap-box">
  <div class="di-trap-label">❌ Wrong Approach</div>
  <trap description>
</div>
</v-click>

<v-click>
<div class="di-correct-box">
  <div class="di-correct-label">✓ Right Approach</div>
  <correct description>
</div>
</v-click>

<img src="/logo.png" class="di-logo" />
```

**Takeaway / Key Takeaways slides:**
```yaml
---
layout: default
class: di-takeaway-slide
---
```
```html
<div class="di-takeaway-title">What to Remember</div>

<ul class="di-takeaway-list">
  <v-click><li>Takeaway point one</li></v-click>
  <v-click><li>Takeaway point two</li></v-click>
  <v-click><li>Takeaway point three</li></v-click>
</ul>

<img src="/logo.png" class="di-logo" style="opacity: 0.75;" />

<!--
<closing narration>
-->
```

**Two-column comparison slides:**
```yaml
---
layout: two-cols
---
```
```html
<div class="di-header">Slide Title</div>

::left::
<div class="di-col-left-label">Left Label</div>
<div class="di-col-body">
<v-click at="1"><p>Left item one</p></v-click>
<v-click at="2"><p>Left item two</p></v-click>
</div>

::right::
<div class="di-col-right-label">Right Label</div>
<div class="di-col-body">
<v-click at="1"><p>Right item one</p></v-click>
<v-click at="2"><p>Right item two</p></v-click>
</div>

<img src="/logo.png" class="di-logo" />
```

**Code slides:**
```yaml
---
layout: default
class: di-code-slide
---
```
```html
<div class="di-code-header">Slide Title</div>

\`\`\`python {1-5|6-10}
# Code here
\`\`\`

<img src="/logo.png" class="di-logo" />

<!--
<narration>
-->
```

### Step 5 — Map script content to slides

- `## SLIDE N: <Title>` markers → individual slides
- Narration text → speaker notes in HTML comments
- `[click]` → new `<v-click>` block
- `**Visual**: two-column...` → use `layout: two-cols`
- `**Visual**: code...` → use `di-code-slide` class
- "Exam Tip" slides → use `di-exam-slide` class with trap/correct boxes
- "Key Takeaways" / "What to Remember" → use `di-takeaway-slide` class

### Step 6 — Update package.json scripts

After creating a new presentation file, add a `dev`, `build`, and `export` script entry to `package.json`:
```json
"dev:N.M": "slidev lecture-N.M.md --open",
"build:N.M": "slidev build lecture-N.M.md --out dist/N.M",
"export:N.M": "slidev export lecture-N.M.md --output exports/lecture-N.M.pdf"
```

Also update `start-all.sh` to include the new presentation.

---

## Running Presentations

### Launch Dev Server (Preview)

1. Find the Slidev project directory. Look for a `package.json` with `@slidev/cli` in dependencies, or `.md` files with Slidev frontmatter.
2. Check if `node_modules` exists. If not, run `npm install`.
3. Start the dev server(s). If there's a single presentation, use `npx slidev <file>.md --open`. For multiple presentations, assign sequential ports starting at 3030:
   ```bash
   npx slidev lecture-1.md --port 3030 &
   npx slidev lecture-2.md --port 3031 &
   npx slidev lecture-3.md --port 3032 &
   ```
4. Report the URLs to the user.

If the project has npm scripts (like `dev:1.1`, `dev:2.1`), prefer those over raw npx commands.

**Port conflicts:** If a port is in use, increment. Check with `lsof -i :3030` before starting.

### Build Static SPA

```bash
npx slidev build <file>.md --out dist/<name>
```

### Export to PDF

```bash
npx slidev export <file>.md --output exports/<name>.pdf
```

Requires Playwright. If export fails, run `npx playwright install chromium` first.

### Batch Operations

1. Detect all Slidev `.md` files (look for frontmatter with `theme:`)
2. For dev servers: launch each on its own port, starting at 3030
3. For builds/exports: run sequentially to avoid resource contention
4. Create/update `start-all.sh` if it doesn't exist

---

## Slide Content Rules

### Progressive Reveal
All slides must use progressive reveal with `<v-click>`. Each slide starts with **only the title/header visible**. Every subsequent content element appears on click — including individual bullet points, cards, code blocks, and annotations.

**One object per click.** Each `<v-click>` must reveal exactly ONE visual element. Never bundle multiple elements in one click. Do NOT wrap entire layouts (grids, flex containers, two-column sections) in a single `<v-click>`.

```html
<!-- Correct: each element reveals on click -->
<div class="di-header">Slide Title</div>

<v-click>
<p>First point appears on click.</p>
</v-click>

<v-click>
<p>Second point appears on next click.</p>
</v-click>
```

**Two-column alignment.** When using `two-cols` layouts with progressive reveal, do NOT add vertical padding to offset columns. Both columns must start at the same vertical position below the header. Use `<v-click at="N">` to synchronize related elements appearing on the same click across columns.

Group logically related elements (e.g., a label + its body) in a single `<v-click>`, but keep independent items in separate `<v-click>` tags.

---

## Prerequisites

- **Node.js 18+** — check with `node --version`
- **npm** — comes with Node
- **@slidev/cli** — installed via package.json

Default `package.json`:
```json
{
  "name": "dyer-innovation-slides",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "slidev --open"
  },
  "dependencies": {
    "@slidev/cli": "^51.0.0",
    "@slidev/theme-default": "latest"
  }
}
```

---

## Troubleshooting

- **"Cannot find module @slidev/cli"** → Run `npm install` in the project directory
- **Port already in use** → Kill the existing process (`kill $(lsof -t -i:3030)`) or use a different port
- **PDF export fails** → Install Playwright: `npx playwright install chromium`
- **Styles not loading** → Make sure `style.css` is in the same directory and imported via `@import './style.css'` in the `<style>` block
- **Images not showing** → Images go in the `public/` subdirectory and are referenced as `/filename.png` (not `./public/filename.png`)

---

## Keyboard Shortcuts in the Browser

- **Space / Arrow Right** — Next slide/animation
- **Arrow Left** — Previous slide
- **O** — Slides overview
- **D** — Toggle dark mode
- **F** — Fullscreen
- **P** — Presenter mode (shows speaker notes)
