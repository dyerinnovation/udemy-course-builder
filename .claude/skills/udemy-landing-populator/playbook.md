# udemy-landing-populator — Playbook

Field-by-field operating instructions for the Playwright MCP. Selectors were
captured live from the Udemy instructor UI on 2026-04-17; if Udemy changes
attribute names the skill must re-capture via `browser_evaluate`.

## Key insight: Udemy uses `data-purpose`

Almost every interactive element on the instructor UI carries a stable
`data-purpose="..."` attribute. Prefer these over CSS class matches, which
Udemy rotates regularly via their build pipeline.

## URL map

Replace `<ID>` with the course ID.

| Section | URL | Done state |
|---|---|---|
| Intended learners | `/instructor/course/<ID>/manage/goals/` | sidebar checkmark `[data-purpose="react-nav-link-goals"]` ancestor shows green icon |
| Course landing page | `/instructor/course/<ID>/manage/basics/` | `[data-purpose="react-nav-link-basics"]` checkmark |
| Course messages | `/instructor/course/<ID>/manage/communications/messages/` | `[data-purpose="react-nav-link-communications"]` checkmark |

## Parsing — read markdown into structured fields

Use `Read` then `browser_evaluate` is not needed here — parse in plain
TypeScript/regex or inline in the agent turn. Structured schema:

```ts
interface CourseMetadata {
  landing: {
    title: string;              // recommended from landing-page.md
    subtitle: string;
    descriptionHTML: string;    // convert markdown bullets to <ul><li>, bold to <strong>
    level: "Beginner Level" | "Intermediate Level" | "Expert Level" | "All Levels";
    category: string;           // e.g. "Development"
    subcategory: string;        // e.g. "Software Engineering"
    primaryTopic: string;       // e.g. "Anthropic Claude"
  };
  learners: {
    objectives: string[];       // strip trailing " (NN)" or " (Domain X)"
    prerequisites: string[];
    audience: string[];
  };
  messages: {
    welcomeHTML: string;
    congratsHTML: string;
  };
}
```

### Markdown → field extraction rules

**landing-page.md**
- Title: first non-empty line under `## Title candidates` that starts with `**Recommended:`; extract the text between `**Recommended: ` and ` (NN chars)**`.
- Subtitle: first line under `## Subtitle`, strip trailing ` (NNN chars)`.
- Description: full block under `## Description` up to (but not including) `## Basic info picks`. Convert: `**…**` → `<strong>…</strong>`, lines starting with `- ` → `<li>`, grouped into `<ul>`.
- Level / Category / Subcategory / Primary topic: regex on the `## Basic info picks` bullets.

**intended-learners.md**
- Objectives: each bullet under `## What will students learn`, strip trailing ` (Domain X)` and ` (NNN)` counts.
- Prerequisites: each bullet under `## Prerequisites` — raw text.
- Audience: each bullet under `## Who is this course for`, strip trailing ` (NNN)`.

**course-messages.md**
- Welcome: body under `## Welcome Message` up to `(NNN chars)` footer, convert newlines to `<p>…</p>` paragraphs.
- Congratulations: same for `## Congratulations Message`. Preserve ordered list: lines `1.`, `2.`, etc → `<ol><li>`.

## Section 1 — Intended Learners (`/manage/goals`)

### Learning objectives (≥4 required, 160 char max each)

Selector pattern: `input[data-purpose^="learn-goal-input-answer-list--"]`.
At initial load there are 4 of these (with numeric suffixes — `--25`, `--26`, `--27`, `--28` in the captured DOM, but the suffixes are React render IDs and will drift). Resolve by order instead:

```js
document.querySelectorAll('input[data-purpose^="learn-goal-input-answer-list--"]')[i]
```

**Fill procedure:**
1. Read current values via `browser_evaluate` — if any input already has non-empty `.value`, stop and ask user (no overwrite).
2. For each objective `i` in parsed list:
   - If `i < 4`: fill the i-th existing input. Use Playwright's `locator.fill()` — native `<input type="text">` supports it.
   - If `i ≥ 4`: click `button[data-purpose="add-learn-goal"]` (labeled "Add more to your response") to spawn a new input, then fill the newest one.
3. Verify char count ≤ 160 before filling. If over, truncate and log a warning.

### Prerequisites (1+ inputs)

Same pattern — text inputs with `+ Add more` button.
- First input placeholder: `"Example: No programming experience needed. You will learn everything you need to know"`.
- Add more button: `button[data-purpose="add-requirements"]`.

**Fill procedure:**
1. For each prereq bullet, fill the next input (create via the add button after the first).

### Audience

- First input placeholder: `"Example: Beginner Python developers curious about data science"`.
- Add more button: `button[data-purpose="add-target-student"]`.
- Same fill pattern.

### Save

Click `button` whose visible text is `"Save"` in the page header (top-right next to the cogwheel). There is no stable `data-purpose` on this button — use Playwright's `getByRole('button', { name: 'Save' })`. After click, wait for a toast/indicator or simply wait for the `/manage/goals` sidebar item to show a check.

## Section 2 — Course Landing Page (`/manage/basics`)

| Field | Selector | Input type | Notes |
|---|---|---|---|
| Course title | `input[data-purpose="edit-course-title"]` | text, 60 char max | Clear existing value first (may hold the old title) |
| Course subtitle | `input[data-purpose="course-headline"]` | text, 120 char max | |
| Course description | `div.ProseMirror[contenteditable="true"]` (there's only one on this page) | ProseMirror rich-text | See "ProseMirror fill" below — `fill()` does NOT work on contenteditable |
| Language | `select[name="locale"]` | native select | `selectOption("English (US)")` |
| Level | `select[name="instructional_level"]` | native select | Values: "Beginner Level", "Intermediate Level", "Expert Level", "All Levels" |
| Category | `select[name="category"]` | native select | "Development" etc. Must be set before subcategory (options depend on it). |
| Subcategory | `select[name="subcategory"]` | native select | Under Development: "Web Development", "Data Science", "Mobile Development", "Programming Languages", "Game Development", "Database Design & Development", "Software Testing", "Software Engineering", "Software Development Tools", "No-Code Development" |
| What is primarily taught | `input[data-purpose="autosuggest-input"]` | autocomplete text | Type the term, wait for dropdown, press ArrowDown+Enter to select |
| Course image | `input[type="file"][accept*="image"]` (via `#form-group--50` id, but ID is generated — use accept attribute + DOM order) | file upload | OUT OF SCOPE v1 — print the local path and prompt user |
| Promo video | `input[type="file"][accept*="video"]` | file upload | OUT OF SCOPE v1 |

### ProseMirror fill

Udemy's description and message fields use ProseMirror (`div.ProseMirror`, contenteditable). Playwright's `fill()` does NOT work on these. Recipe:

```js
// Via browser_evaluate
const el = document.querySelector('div.ProseMirror[contenteditable="true"]');
el.focus();
document.execCommand('selectAll', false, null);
document.execCommand('delete', false, null);
document.execCommand('insertHTML', false, parsedHTML); // e.g. "<p>…</p><ul><li>…</li></ul>"
el.dispatchEvent(new Event('input', { bubbles: true }));
```

Alternative using Playwright directly (preferred — keyboard path):
1. `locator('div.ProseMirror').click()`.
2. `page.keyboard.press('Meta+A')` then `'Backspace'` to clear.
3. `page.keyboard.type(plainText)` — works for plain paragraphs. For rich content, fall back to the `execCommand('insertHTML')` path above via `browser_evaluate`.

For the description: Udemy requires ≥200 words and will flag save errors otherwise — verify word count before submitting.

### Save

Same `getByRole('button', { name: 'Save' })` as on goals page.

## Section 3 — Course Messages (`/manage/communications/messages`)

Two ProseMirror editors on this page, distinguished by the heading above them:

```js
// browser_evaluate recipe to identify them
const editors = document.querySelectorAll('div.ProseMirror[contenteditable="true"]');
// editors[0] → Welcome Message, editors[1] → Congratulations Message (verified by DOM walk to nearest preceding h3)
```

Playwright selector:
- Welcome: `page.locator('h3:has-text("Welcome Message") ~ * div.ProseMirror').first()`
- Congratulations: `page.locator('h3:has-text("Congratulations Message") ~ * div.ProseMirror').first()`

If those sibling selectors are flaky, fall back to positional index (`nth(0)` / `nth(1)`).

Fill using the ProseMirror recipe above.

### Save

Same Save button at page header.

## Global: waiting for checkmarks

After each Save, verify persistence by:
1. Waiting for a toast or (more reliably) reloading the current page and re-reading field values.
2. Checking the sidebar nav item for this section — Udemy adds a green checkmark icon inside the link after all required fields are filled. The exact icon selector is inside `[data-purpose="react-nav-link-<section>"]`; inspect with `browser_evaluate` to find the class, but a simple check is:
   ```js
   document.querySelector('[data-purpose="react-nav-link-goals"] [data-checked="true"]')
   ```
   (The `data-checked` attribute may not exist — the reliable check is: the circle icon's parent svg has class including "checkmark" or the aria-label contains "complete".)

If the checkmark does not appear within 10s of Save:
- Screenshot the page
- Dump any `role="alert"` messages via `browser_evaluate`
- Stop and surface the error

## Save button caveats

- Udemy disables Save until at least one field has changed — if all form values already match the markdown, Save stays greyed out. Treat as success.
- Save also validates: if any single objective > 160 chars, Udemy shows a red caption under that input but does NOT show a top-level error. Iterate each input's sibling for validation state after a Save click.

## Known-good selectors (captured 2026-04-17)

```
# Nav
[data-purpose="react-nav-link-goals"]
[data-purpose="react-nav-link-basics"]
[data-purpose="react-nav-link-communications"]

# Goals page
input[data-purpose^="learn-goal-input-answer-list--"]     (4+ objective inputs)
button[data-purpose="add-learn-goal"]                     ("+ Add more" under objectives)
button[data-purpose="add-requirements"]                   ("+ Add more" under prereqs)
button[data-purpose="add-target-student"]                 ("+ Add more" under audience)

# Basics page
input[data-purpose="edit-course-title"]                   (60 char max)
input[data-purpose="course-headline"]                     (120 char max)
div.ProseMirror[contenteditable="true"]                   (description)
select[name="locale"]
select[name="instructional_level"]
select[name="category"]
select[name="subcategory"]
input[data-purpose="autosuggest-input"]                   (primary topic)

# Messages page
div.ProseMirror[contenteditable="true"]                   (x2 — disambiguate by heading)
```

## Re-capture recipe

If these selectors drift, re-capture with:

```js
// browser_evaluate on any of the 3 pages
[...new Set(Array.from(document.querySelectorAll('[data-purpose]')).map(el => el.getAttribute('data-purpose')))]
```

Then update the table above.
