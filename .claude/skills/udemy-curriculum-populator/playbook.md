# udemy-curriculum-populator — Playbook

Operating reference for `/manage/curriculum/`. Selectors captured live on
2026-04-26 from `https://www.udemy.com/instructor/course/7140821/manage/curriculum/`.
If Udemy rotates `data-purpose` attributes, the skill must re-capture via a
read pass before any clicks.

## Key insight: Udemy uses `data-purpose`

Same as `udemy-landing-populator`. `data-purpose` attributes are stable
across React re-renders and across UI revs because they're semantic markers
on Udemy's side, not generated class names. **Prefer them over CSS class
matches at every step.**

## URL

```
https://www.udemy.com/instructor/course/<numeric-id>/manage/curriculum/
```

The instructor URL format uses a numeric course id, NOT the public slug. Read
the id from the URL while viewing the course in the instructor dashboard. The
public `/course/<slug>/` URL is for students and will not work here.

## Confirmed selectors (2026-04-26 recon)

| Purpose | Selector |
|---|---|
| Whole curriculum container | `[data-purpose="curriculum-list"]` |
| A section row | `[data-purpose="section-editor"]` |
| Section edit button | `[data-purpose="section-edit-btn"]` |
| Section delete button (DO NOT auto-click) | `[data-purpose="section-delete-btn"]` |
| Inline insert + (between every pair of items, always visible — no hover) | `[data-purpose="add-item-inline"]` |
| Choice that appears after clicking + | `[data-purpose="add-item-inline-last"]` (innerText is `"Curriculum item"` OR `"Section"`) |
| Coding Exercise picker | `[data-purpose="add-coding-exercise-btn"]` (aria-label `"Add Coding Exercise"`) |
| Lecture picker | `[data-purpose="add-lecture-btn"]` (aria-label `"Add Lecture"`) |
| Quiz picker | `[data-purpose="add-quiz-btn"]` |
| Practice Test picker | `[data-purpose="add-practice-test-btn"]` |
| Assignment picker | `[data-purpose="add-assignment-btn"]` |
| Inside a lecture row: pick content type (Video/Article/etc) — NOT used by this skill | `[data-purpose="lecture-add-content-btn"]` |

## Menu behaviour notes

- The `+` picker is **inline-expanded** (sticky), NOT a popover. Clicking the
  same `+` button again toggles it closed. Escape and outside-click do NOT
  close it.
- The `+` is always visible — there is no hover-to-reveal behaviour to
  emulate.
- Clicking `+` always shows TWO choices: `Curriculum item` and `Section`.
  Picking `Curriculum item` reveals the 5-button sub-picker (Lecture / Quiz /
  Coding Exercise / Practice Test / Assignment).

## Parsing — `course-outline.md` → planned tree

The outline file uses these markdown conventions:

```
## Section N: <Section title>

[free-text paragraph(s)]

**Estimated Duration**: ~XX minutes

### Lectures
N.1 <Lecture 1 title>
N.2 <Lecture 2 title>
...

### Quiz: <quiz title>
...

### Downloadable Resources
...
```

Extraction rules:

- **Sections.** Every line matching `/^## Section (\d+): (.+)$/`. `number` is
  group 1; `title` is group 2.
- **Lectures.** Within a section block (between this `##` and the next),
  every line matching `/^(\d+)\.(\d+)\s+(.+?)$/` under the `### Lectures`
  heading. `number` is `${maj}.${min}`; `title` is the rest.
- **Skip headings:** `### Quiz:`, `### Downloadable Resources`, `### Labs`,
  etc. — these are NOT lectures.
- **Lecture title hygiene:** trim trailing whitespace, strip any trailing
  `(NN min)` time hints.

### Per-section objective (optional)

If the file `scripts/section-NN-<slug>/section-overview.md` exists in the
course repo, extract the Learning Objectives bullet list:

```
## Learning Objectives

By the end of this section, students will be able to:
- <objective 1>
- <objective 2>
...
```

Concatenate the bullets into a single paragraph (separator: `". "`) for use
as the section description in Udemy. If the file is missing, leave the
section description empty (user can fill in later).

## Reading existing curriculum (idempotency baseline)

```js
const sections = Array.from(document.querySelectorAll('[data-purpose="section-editor"]')).map(s => {
  // First text-bearing block holds "Section N:Title" then the title repeated; we want the section number + title
  const text = s.innerText.trim();
  const match = text.match(/^Section\s+(\d+):\s*(.+?)\n/);
  return {
    number: match ? Number(match[1]) : null,
    title: match ? match[2].trim() : null,
    // Lecture rows are nested; selector still TBD — capture during first run
    rawText: text.slice(0, 200)
  };
});
JSON.stringify(sections, null, 2);
```

For lecture rows inside a section: this selector is NOT yet captured. First
real run will surface it. Look for `[data-purpose*="lecture"]` or
`[data-purpose*="curriculum-item"]` within the section's subtree.

## Section creation flow

For each `CREATE` section in the plan:

1. Find the LAST `[data-purpose="add-item-inline"]` on the page — this is the
   "add new section at the end" insertion point:
   ```js
   const adds = document.querySelectorAll('[data-purpose="add-item-inline"]');
   adds[adds.length - 1].click();
   ```
   For inserting a section in the MIDDLE (rare — outline order should match
   creation order), use the `add-item-inline` immediately above the section
   that should come after it.

2. Wait for the picker to render (~400ms), then click the "Section" choice:
   ```js
   const choices = document.querySelectorAll('[data-purpose="add-item-inline-last"]');
   const sectionBtn = Array.from(choices).find(b => b.innerText.trim() === 'Section');
   sectionBtn.click();
   ```

3. A dialog appears asking for the section title and learning objective. The
   exact selectors are TBD — first real run will capture. Likely
   `[data-purpose="section-title-input"]` and
   `[data-purpose="section-objective-input"]` based on Udemy's naming
   convention. Abort cleanly on selector drift.

4. Type the title (`Section N: <title>` — Udemy's preview shows it with the
   "Section N:" prefix automatically when you provide just the title; verify
   on first run whether to include the prefix or not).

5. Type the objective (single paragraph from `section-overview.md` — see
   parsing rules above).

6. Click the submit button. TBD selector — likely
   `[data-purpose="save-section"]` or "Add Section" submit text.

7. Wait for a new `[data-purpose="section-editor"]` to appear matching the
   title.

## Lecture creation flow

For each `CREATE` lecture in the plan:

1. Find the parent section by matching `[data-purpose="section-editor"]`
   against the planned section title.

2. Find the `[data-purpose="add-item-inline"]` immediately AFTER the
   section's last existing item (this places the new lecture at the bottom of
   the section). For a brand-new section just created, that's the first +
   that appears below it.

3. Click the +. Wait ~400ms. Click the `add-item-inline-last` button with
   `innerText === "Curriculum item"`.

4. Wait for the 5-button sub-picker. Click `[data-purpose="add-lecture-btn"]`
   (aria-label `"Add Lecture"`).

5. A dialog appears asking for the lecture title. TBD selector — first run
   captures.

6. Type the lecture title. Submit.

7. Wait for the new lecture row to appear inside the parent section.

## Closing the picker without committing

The picker is sticky. To dismiss it without picking anything, click the
ORIGINAL `+` again (toggles it closed). Do NOT rely on Escape or
outside-click — neither works.

```js
// Reopen the same + that opened the picker → it collapses
document.querySelector('[data-purpose="add-item-inline"]:not([aria-expanded="false"])')?.click();
```

(Note: `aria-expanded` on `add-item-inline` was not verified during recon.
If it doesn't exist, track the originally-clicked `+` button reference in
the skill state and re-click it.)

## TBD — captured during first real run

These selectors were intentionally NOT captured during the 2026-04-26 recon
(no test exercises were committed). The skill must abort cleanly on first
encounter and surface the missing selector to the user, who will update this
playbook:

- Section title input field
- Section learning objective input/textarea field
- Section dialog submit button
- Lecture title input field
- Lecture dialog submit button
- Lecture row → child of `[data-purpose="section-editor"]` (selector for
  enumerating existing lectures within a section)
- Validation error banner (`[role="alert"]` is the assumption — verify)

## Worked example — `--preview` output

For a course with `course-outline.md` listing 7 sections, where Section 1
already exists in Udemy with 1 lecture, and the user runs:

```
udemy-curriculum-populator \
  --course-id 7140821 \
  --course-repo ~/Documents/dev/udemy-courses/claude-architect-udemy-course \
  --preview
```

Expected text output:

```
DRY RUN — udemy-curriculum-populator
Target: https://www.udemy.com/instructor/course/7140821/manage/curriculum/
Course repo: ~/Documents/dev/udemy-courses/claude-architect-udemy-course

Parsed plan from course-outline.md:
  Section 1: Course Introduction & Exam Strategy (1 lecture)
  Section 2: Claude API Fundamentals Bootcamp (14 lectures)
  Section 3: Domain 1 — Agentic Architecture (12 lectures)
  Section 4: Domain 2 — Tool Design & MCP (16 lectures)
  Section 5: Domain 3 — Claude Code (15 lectures)
  Section 6: Domain 4 — Prompt Eng & Structured Output (12 lectures)
  Section 7: Domain 5 — Context Mgmt & Reliability (17 lectures)

Existing curriculum (read from dashboard):
  Section 1: Introduction (1 lecture: "Introduction")

Diff:
  Section 1 — TITLE MISMATCH: plan="Course Introduction & Exam Strategy", dashboard="Introduction"
              → would NOT modify (skill is additive only). Manual fix needed.
  Section 1 — LECTURE TITLE MISMATCH: plan="1.1 Welcome, Exam Format, ...", dashboard="Introduction"
              → would NOT modify. Manual fix needed.
  Section 2 — CREATE
    + Lecture 2.1 The Agentic Loop
    + Lecture 2.2 Prefilling
    ... (12 more)
  Section 3 — CREATE (12 lectures)
  Section 4 — CREATE (16 lectures)
  Section 5 — CREATE (15 lectures)
  Section 6 — CREATE (12 lectures)
  Section 7 — CREATE (17 lectures)

Total to create: 6 sections + 86 lectures
Manual fixes needed: 2 (Section 1 title + lecture rename)

To apply: re-run without --preview AND with --apply
To skip Section 1 mismatch warnings: use --sections=2,3,4,5,6,7
```
