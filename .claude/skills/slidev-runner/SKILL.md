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

## Design Heuristics (mandatory)

Every deck you generate MUST conform to these rules. They exist because violations produced concrete bugs in prior courses (dark-frame flashes during recording, invisible text, dumped content with no reveal rhythm, blank code blocks, mojibake). Do not skip any.

### 1. 24px (18pt) minimum body text

- Body text, bullets, code, table cells, schema fields, labels: **24px minimum**
- Eyebrow / kicker / pill text: **20px minimum** (can go to 20px since it carries less weight)
- Titles / heroes / BigNumber: keep at existing sizes (48px+)
- If content does not fit at 24px, the slide has too much content. **Split it — do NOT shrink the type.**

### 2. Progressive reveal on every multi-content slide

Every slide with more than one content block must reveal one block at a time via `<v-clicks>`. The slide loads with ONLY the title + eyebrow visible; each click reveals one more block.

- **Exempt slides** (render everything at once): cover, closing, section-break, pure-title.
- **Prefer reveal-aware components**: `<BulletReveal>`, `<StepSequence>`, `<DomainFocus>` wrap children in `<v-clicks>` internally.
- **For raw layouts**, wrap each content block at the deck level:
  ```html
  <v-clicks>
    <div>block 1</div>
    <div>block 2</div>
  </v-clicks>
  ```
- **Never dump two-column comparisons all at once** — wrap each column so left appears on click 1, right on click 2. Pros/cons, no-streaming/streaming, wrong/right — always sequential.

### 3. Global transition: `slide-left` (NEVER `fade-out`)

`fade-out` produces a dark intermediate frame during the cross-dissolve. It looks fine in the editor, terrible on a recorded video. Use `slide-left` globally:

```yaml
---
transition: slide-left
---
```

No per-slide `transition:` overrides unless there's a specific visual reason.

### 4. No dark-on-dark text

- Dark backgrounds (`var(--forest-*)`, `var(--clay-700)+`) → use light text (`var(--mint-100)`, `var(--paper-0)`).
- Dark text (`var(--forest-800)`) → only on light backgrounds (`var(--mint-100)`, `var(--paper-0)`, `var(--paper-50)`).
- Audit CalloutBox `warn` and `dont` variants specifically — historically prone to dark-on-dark.

### 5. Code blocks: hoisted const + `:code` binding, verified live

Declare code as a `const` in `<script setup>` at the top of the deck and bind via `:code`:

```vue
<script setup>
const requestCode_2_1 = `import anthropic
response = anthropic.Anthropic().messages.create(...)`
</script>

<CodeBlockSlide :code="requestCode_2_1" lang="python" title="..." />
```

Never embed raw triple-backtick fences inside component props. After creation, **verify the live render in the browser** — the `<pre>` panel may appear styled but empty due to markdown/Shiki interactions. If the code text isn't visible, the bug is real and must be fixed before moving on (typical remedy: `v-text="code"` instead of `{{ code }}`, or drop the `language-*` class that Shiki intercepts).

### 6. ASCII-safe characters in hoisted consts

Template literals that become code or prose must use ASCII where possible:

- Smart quotes `" " ' '` → straight `" ' `
- Em dash `—` → `--`
- En dash `–` → `-`
- Ellipsis `…` → `...`
- Right arrow `→` → `->`
- Left arrow `←` → `<-`

Validated Unicode (emoji, CJK, math symbols) is allowed when intentional, but audit any string that will be rendered inside a `<pre>` or `<code>` block. Mojibake during rendering traces back to this in 90% of cases.

---

## Per-section file layout (recording workflow)

**One deck file per section, NOT per lecture.** This replaces the older per-lecture pattern.

### Why

Recording a whole section in one browser is faster than launching 15 dev servers and juggling ports. Instructors record the full section as one stream, then cut per-lecture videos in post. Cross-lecture edits become a grep inside one file, not across 17.

### File naming + port mapping

```
slidev/section-1.md  → port 3030
slidev/section-2.md  → port 3040
slidev/section-3.md  → port 3050
slidev/section-4.md  → port 3060
slidev/section-5.md  → port 3070
slidev/section-6.md  → port 3080
slidev/section-7.md  → port 3090
```

### File structure

```markdown
---
theme: default
title: "Section N: <Section name>"
info: |
  <course title>
  Section N: <section name>
highlighter: shiki
transition: slide-left
mdc: true
canvasWidth: 1920
aspectRatio: 16/9
---

<style>
@import './design-system.css';
</style>

<script setup>
// Hoist EVERY const from every lecture, prefixed by lecture number to avoid collisions.
const requestCode_2_1 = `...`
const coreParams_2_1 = [...]
const batchWrongCode_2_5 = `...`
// ... one block per lecture, concatenated
</script>

---

<!-- LECTURE 2.1 — The Messages API -->

<!-- Cover slide for lecture 2.1 -->

---

<!-- SLIDE 2 — The Five Core Request Parameters -->

<BulletReveal :bullets="coreParams_2_1" ... />

---

<!-- SLIDE 3 -->

<CodeBlockSlide :code="requestCode_2_1" lang="python" ... />

---

<!-- LECTURE 2.2 — System Prompts -->

<!-- lecture 2.2 slides continue here ... -->
```

### Conventions

- **Lecture boundary markers**: `<!-- LECTURE N.X — <Title> -->` on the first slide of each lecture. Used during post-production cuts.
- **Slide markers inside a lecture**: `<!-- SLIDE N -->` optional but recommended for cross-reference with the narration script's `<!-- SLIDE: N -->` markers.
- **Const naming**: always suffix with `_<section>_<lecture>`, e.g. `requestCode_2_1`. Without prefixes, consts collide when lectures merge.
- **Speaker notes**: HTML `<!-- ... -->` comments after each slide's content, as always.
- **Optional final "Takeaways" slide per lecture**: using `<BulletReveal>`. Lets the instructor pause naturally before cutting the video.

---

## Creating New Slides from Lecture Scripts

When asked to build or create slides for a lecture:

### Step 1 — Locate the script

Scripts live in `<course-dir>/scripts/section-XX-<slug>/<lecture>.md`. Read the script fully.

### Step 2 — Determine output path

Slidev files go in `<course-dir>/slidev/` alongside the other presentations. **Use per-section files (one file per section, not per lecture)** — see the "Per-section file layout" section above for the full rationale.
```
<course-dir>/slidev/section-<N>.md
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
title: "Section N: <Section Name>"
info: |
  <Course Title>
  Section N: <Section Name>
highlighter: shiki
transition: slide-left
mdc: true
canvasWidth: 1920
aspectRatio: 16/9
---

<style>
@import './design-system.css';
</style>
```

(Use `design-system.css` on new courses. Older projects may still reference `style.css` — keep that legacy path working if the project already has it, but prefer `design-system.css` in new work.)

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

After creating a new section file, add `dev`, `build`, and `export` script entries to `package.json` (one set per section, not per lecture):
```json
"dev:N": "slidev section-N.md --port 30<N+2>0",
"build:N": "slidev build section-N.md --out dist/N",
"export:N": "slidev export section-N.md --output exports/section-N.pdf"
```

Port pattern: Section 1 → 3030, Section 2 → 3040, Section 3 → 3050, Section 4 → 3060, Section 5 → 3070, Section 6 → 3080, Section 7 → 3090.

Also update `start-all.sh` to include the new section file with its mapped port.

---

## Running Presentations

### Launch Dev Server (Preview)

1. Find the Slidev project directory. Look for a `package.json` with `@slidev/cli` in dependencies, or `.md` files with Slidev frontmatter.
2. Check if `node_modules` exists. If not, run `npm install`.
3. Start the dev server(s). If there's a single section, use `npx slidev <file>.md --open`. For multiple sections, use the section-N.md + 10-apart port scheme:
   ```bash
   npx slidev section-1.md --port 3030 &
   npx slidev section-2.md --port 3040 &
   npx slidev section-3.md --port 3050 &
   ```
4. Report the URLs to the user.

If the project has npm scripts (like `dev:1`, `dev:2`), prefer those over raw npx commands.

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
