# udemy-resource-uploader — Playbook

Operating reference for `[data-purpose="lecture-add-content-btn"]` →
'Resources' upload flow. Confirmed selectors are inherited from the
`udemy-curriculum-populator` playbook (same dashboard, same
`data-purpose` strategy). Resource-flow-specific selectors are TBD until
the first `--apply` run captures them.

## Key insight: Udemy uses `data-purpose`

Same as `udemy-curriculum-populator` and `udemy-landing-populator`.
`data-purpose` attributes are stable across React re-renders and across UI
revs because they're semantic markers on Udemy's side, not generated class
names. **Prefer them over CSS class matches at every step.**

## URL

```
https://www.udemy.com/instructor/course/<numeric-id>/manage/curriculum/
```

The instructor URL format uses a numeric course id, NOT the public slug.
Read the id from the URL while viewing the course in the instructor
dashboard. The public `/course/<slug>/` URL is for students and will not
work here.

## Confirmed selectors

All selectors below were captured during the first real `--apply` run
against course id `7140821` Lecture 1.1 on 2026-04-27. They held across
multiple opens/closes of the Resources panel.

### Curriculum + lecture row (inherited from curriculum-populator)

| Purpose | Selector |
|---|---|
| Whole curriculum container | `[data-purpose="curriculum-list"]` |
| A lecture row | `[data-purpose="lecture-editor"]` |
| Title text inside a lecture row | `[data-purpose="item-full-title"]` (innerText starts with `"Lecture N:"` — strip prefix to get the bare title) |
| Order/index inside a lecture row | `[data-purpose="item-object-index"]` (innerText is literally `"Lecture N:"`) |
| Toggle the lecture's content panel | `[data-purpose="lecture-add-content-btn"]` (button labelled "Content") |
| Close the open panel | `[data-purpose="content-tab-close"]` (visible only when a panel is open) |

The content panel is a sticky inline expansion (NOT a popover). Escape
and outside-click do NOT close it. Two siblings live underneath
`[data-purpose="add-content-wrapper"]`:

- `[data-purpose="add-content"]` — visible when the lecture has no
  primary content type yet. Shows Video / Article / Mashup pickers.
- `[data-purpose="edit-content"]` — visible when the lecture HAS a
  primary content type. Shows Description / Resources / Lab buttons.

### add-content panel (when lecture has no main content)

| Purpose | Selector |
|---|---|
| Wrapper around the content-type picker | `[data-purpose="add-content"]` |
| Pick Video as main content type | `[data-purpose="select-video"]` |
| Pick Video Mashup | `[data-purpose="select-videomashup"]` |
| Pick Article as main content type | `[data-purpose="select-article"]` |

After clicking `select-article`, the inline article editor opens with a
WYSIWYG / HTML mode toggle. The body is a `[contenteditable="true"]`
`<div>` inside `[data-purpose="wysiwyg-mode"]`. To set placeholder body
programmatically: `el.focus(); el.innerHTML = '<p>...</p>';
el.dispatchEvent(new InputEvent('input', {bubbles:true, inputType:'insertText'}));
el.dispatchEvent(new Event('change', {bubbles:true}));` then click the
visible "Save" `<button>` (no `data-purpose` on it; find via text).
Save flips the panel from `add-content` → `edit-content` and exposes
`add-resources-btn`.

The article editor toolbar uses `data-purpose` markers:
`SET_PARAGRAPH`, `TOGGLE_BLOCKQUOTE`, `TOGGLE_HEADING`, `TOGGLE_STRONG`,
`TOGGLE_EM`, `TOGGLE_ORDERED_LIST`, `TOGGLE_BULLET_LIST`,
`PROMPT_ANCHOR`, `PROMPT_IMAGE_UPLOAD`, `TOGGLE_CODE`,
`TOGGLE_MONOSPACE`, `TOGGLE_HTML_MODE`, plus `wysiwyg-mode` /
`html-mode` panels.

### edit-content panel (when lecture HAS main content) — Resources flow

| Purpose | Selector |
|---|---|
| Wrapper around the edit-content panel | `[data-purpose="edit-content"]` |
| Open the Resources sub-panel | `[data-purpose="add-resources-btn"]` (text: "Resources") — **NOT `resource-content-btn` as v1 guessed** |
| Open the Description sub-panel | `[data-purpose="add-desc-btn"]` |
| Open the Lab sub-panel | `[data-purpose="add-lab-btn"]` |
| Replace primary content with Video | `[data-purpose="replace-with-video"]` (use sparingly — destructive on existing Article body) |
| Per-asset metadata under main content | `[data-purpose="selected-asset"]`, `[data-purpose="asset-info"]` |
| Lecture settings sub-panel | `[data-purpose="lecture-settings"]` |
| Article icon in the row header (after Article set) | `[data-purpose="article-icon"]` — useful as a "lecture has Article main content" indicator |

### Resources sub-panel internals

When `add-resources-btn` is clicked, the panel re-opens with a tab strip:

| Purpose | Selector |
|---|---|
| Tab navigation strip | `[data-purpose="tab-nav-buttons"]` |
| Each tab panel container (multiple) | `[data-purpose="tab-container"]` — first 4 are tab containers; `tab-container[0]` = Downloadable File, `tab-container[3]` = Source Code (verified positions; URL/External are tab-container[1]/[2]) |
| Existing attachments table | `[data-purpose="asset-table"]` |
| Already-uploaded files row container | `[data-purpose="downloadable-files-section"]` (innerText lists each `<filename>.<ext> (NNN.N kB)` per attachment; `(Processing)` while server processes) |
| Delete button per attachment row | `[data-purpose="delete-supplementary-asset-btn"]` (additive-only safety: the skill MUST NOT click these) |
| Upload widget wrapper | `[data-purpose="asset-uploader-input"]` (occurs twice — Downloadable File + Source Code tabs) |
| File input (hidden) | `input[type="file"][name="asset"]` inside `[data-purpose="asset-uploader-input"]`. Class `ud-sr-only`, bounding rect ~1×1px. Two exist (Downloadable File + Source Code). Filter the Source Code one out by `accept=".rb,.py,.sh"` — the Downloadable File one has empty `accept`. |
| Helper note text under the uploader | `[data-purpose="safely-set-inner-html:asset-uploader:note"]` |
| External URL — title field (URL tab) | `[data-purpose="title-field"]` |
| External URL — link field (URL tab) | `[data-purpose="url-field"]` |

### Validation / errors

| Purpose | Selector |
|---|---|
| Generic validation banner | `[role="alert"]` (assumption — not yet observed in this flow) |

## HARD prerequisite: lecture must have a main content type set

Udemy hides `[data-purpose="add-resources-btn"]` until the target lecture
has Video or Article as its main content. A bare lecture stub created by
`udemy-curriculum-populator` shows the `add-content` panel on click of
`lecture-add-content-btn`, NOT the `edit-content` panel that contains
the Resources affordance.

**Pre-flight check (before clicking add-resources-btn):**
```js
const editContent = lectureWrapper.querySelector('[data-purpose="edit-content"]');
const addContent  = lectureWrapper.querySelector('[data-purpose="add-content"]');
if (!editContent || editContent.offsetParent === null) {
  // Lecture has no main content — the Resources path is blocked.
  // Either abort with a clear message, or apply the Article-placeholder
  // workaround below (after explicit user consent).
}
```

**Article-placeholder workaround (with user consent):**

1. Click `lecture-add-content-btn` to open the panel.
2. Click `[data-purpose="select-article"]`.
3. Set the WYSIWYG body to a brief placeholder via the contenteditable
   pattern documented above (innerHTML + InputEvent + change).
4. Click the visible "Save" button (find by text — no `data-purpose`).
5. After save, the panel auto-flips from `add-content` to `edit-content`
   and `add-resources-btn` is now visible. Resources flow can proceed.

The Article main-content does NOT block a later Video upload — clicking
`[data-purpose="replace-with-video"]` swaps Article for Video without
touching the attached resources. So "Article placeholder now, Video
later" is a safe sequence.

## File upload — UI buttons, NOT the file_upload primitive

`mcp__Claude_in_Chrome__file_upload` was rejected with `code: -32000,
message: "Not allowed"` on every attempt during the first real `--apply`
run, regardless of file path (`/tmp/`, `~/Downloads/`, repo absolute) or
element ref (`ref_85`, `ref_162`, etc.). The Chrome MCP extension's
file-upload primitive is sandboxed off in production sessions. Do NOT
silently retry it.

**Working approach: drive the page's UI directly.** Two options, in
order of automation preference:

### Option 1 — Playwright `setInputFiles` (preferred when available)

If the run is on the Playwright backend (Option B in SKILL.md), use
`mcp__playwright__browser_file_upload` with the absolute file path. This
hits Chrome's CDP `Page.setInterceptFileChooserDialog` /
`Page.handleFileChooser` and bypasses the OS picker. Works without
user interaction.

### Option 2 — Chrome MCP: JS-click input + native picker

When the run is on the Chrome MCP backend (Option A — most users):

1. Locate the file input via JS:
   ```js
   const inputs = lectureWrapper.querySelectorAll('input[type="file"][name="asset"]');
   const downloadable = Array.from(inputs).find(i => !i.accept || i.accept === '');
   ```
2. Call `downloadable.click()` from `javascript_tool`. The OS file picker
   opens.
3. Prompt the user to pick the planned file in the picker. The skill
   waits for a fresh row to appear in `downloadable-files-section`.
4. Repeat per file (the input has `multiple="false"` so one file per
   click).

### Option 3 — Drag-and-drop (multi-file friendly)

Udemy's Resources panel accepts file drops onto the upload zone (Uppy
widget convention). The skill prompts the user to drag the planned
files from Finder onto the panel. Udemy uploads them in parallel and
each one shows up in `downloadable-files-section`. One user gesture
covers N files. Watch for accidental duplicates if the user drops the
same file twice — the skill should re-read the section after the drop
and report any duplicates so the user can remove them via the
`delete-supplementary-asset-btn` (manually, since the skill is
additive-only).

### Verification regardless of upload method

After any upload, poll `[data-purpose="downloadable-files-section"]`:

```js
const section = lectureWrapper.querySelector('[data-purpose="downloadable-files-section"]');
const lines = section.innerText.split(/\n+/).filter(l => /\.[a-z0-9]+\s*\(/i.test(l));
// Each line: "filename.ext (NNN.N kB)" or "filename.ext (Processing)"
// Wait until every planned filename appears with a kB suffix (not Processing).
// Hard timeout: 120s per file.
```

## DOM model — sections and lectures are SIBLINGS, not nested

Inherited from `udemy-curriculum-populator` playbook. Every curriculum
item (section row OR lecture row) is a direct child of
`[data-purpose="curriculum-list"]`, each wrapped in a
`div.js-curriculum-item-draggable.curriculum-list--list-item--xn0`.

To find a specific lecture (e.g. Section 2 / Lecture 2.1 = the 1st
`lecture-editor` after the Section 2 row):

1. Walk `curriculumList.children` in order.
2. Find the wrapper containing the matching
   `[data-purpose="section-editor"]` (use `item-object-index` text or the
   title to match).
3. Continue forward, counting `lecture-editor` wrappers until you reach
   the M-th one.
4. Stop when you hit the next wrapper containing a `section-editor`.

Reference enumeration (read-only) — same JS as the curriculum-populator
playbook:

```js
const list = document.querySelector('[data-purpose="curriculum-list"]');
const wrappers = list.querySelectorAll(':scope > div.js-curriculum-item-draggable, :scope > div.curriculum-list--list-item--xn0');
const result = [];
let currentSection = null;
wrappers.forEach(w => {
  const sec = w.querySelector('[data-purpose="section-editor"]');
  const lec = w.querySelector('[data-purpose="lecture-editor"]');
  const idxEl = w.querySelector('[data-purpose="item-object-index"]');
  const titleEl = w.querySelector('[data-purpose="item-full-title"]');
  if (sec) {
    const m = idxEl?.innerText.match(/Section\s+(\d+):/);
    currentSection = {
      number: m ? Number(m[1]) : null,
      title: titleEl?.innerText.replace(/^Section\s+\d+:\s*/, '').trim(),
      lectures: [],
      wrapper: w
    };
    result.push(currentSection);
  } else if (lec && currentSection) {
    const m = idxEl?.innerText.match(/Lecture\s+(\d+):/);
    currentSection.lectures.push({
      number: m ? `${currentSection.number}.${m[1]}` : null,
      title: titleEl?.innerText.replace(/^Lecture\s+\d+:\s*/, '').trim(),
      wrapper: w
    });
  }
});
JSON.stringify(result.map(s => ({...s, wrapper: undefined, lectures: s.lectures.map(l => ({...l, wrapper: undefined}))})), null, 2);
```

For the skill, keep the `wrapper` references (don't strip them as the
JSON dump above does) so subsequent steps can scope queries to the
chosen lecture.

## Idempotency check (per lecture, before upload)

```js
function existingAttachmentFilenames(lectureWrapper) {
  const section = lectureWrapper.querySelector('[data-purpose="downloadable-files-section"]');
  if (!section) return [];
  // Each attached file appears as a line in the section's text content:
  // "filename.ext (NNN.N kB)" or "filename.ext (Processing)"
  const lines = section.innerText.split(/\n+/);
  return lines
    .map(l => l.match(/^(.+?\.[a-z0-9]+)\s*\(/i)?.[1].trim())
    .filter(Boolean);
}
```

Decision: if the planned file's basename (e.g. `CCA-CI-Study-Guide.pdf`)
appears in the returned list, SKIP unless `--force`. Match is exact,
case-sensitive — Udemy preserves the uploaded filename verbatim.

## Upload flow (per file)

1. **Locate the lecture wrapper** using the enumeration JS above. Keep
   the wrapper reference for scoping.

2. **Pre-flight: confirm `edit-content` panel is reachable.** If the
   lecture lacks a main content type, the `add-content` panel will open
   instead (no Resources affordance). Either abort with a clear message
   or apply the Article-placeholder workaround (with explicit user
   consent) — see the prerequisite section above.

3. **Idempotency check.** Open the `edit-content` panel by clicking
   `[data-purpose="lecture-add-content-btn"]` (if not already open).
   Run `existingAttachmentFilenames(lectureWrapper)`. Skip if match +
   no `--force`. Close the panel via `content-tab-close` if you want a
   clean slate before re-opening for upload (not required — the panel
   tolerates re-clicks).

4. **Open the Resources sub-panel.** Click
   `[data-purpose="add-resources-btn"]`. The Resources panel renders
   with a tab strip; the Downloadable File tab is selected by default.

5. **Locate the file input.** In the lecture wrapper, find the
   Downloadable File `<input>`:
   ```js
   const inputs = Array.from(lectureWrapper.querySelectorAll('input[type="file"][name="asset"]'));
   const downloadable = inputs.find(i => !i.accept || i.accept === '');
   const sourceCode = inputs.find(i => i.accept === '.rb,.py,.sh');
   ```

6. **Attach the file.** Pick ONE of these by backend:
   - **Playwright:** `mcp__playwright__browser_file_upload` with
     absolute path and the input's snapshot ref.
   - **Chrome MCP:** do NOT call `mcp__Claude_in_Chrome__file_upload` —
     it is denied. Either:
     - Call `downloadable.click()` via `javascript_tool` → user picks
       the file in the OS dialog, OR
     - Prompt the user to drag-drop the file(s) from Finder onto the
       upload zone (multi-file friendly, single gesture for N files).
   See the "File upload — UI buttons, NOT the file_upload primitive"
   section above for the full explanation.

7. **Wait for upload completion.** Poll
   `[data-purpose="downloadable-files-section"]`'s text for the new
   filename to appear with a `(NNN.N kB)` suffix (not `(Processing)`).
   Hard timeout: 120s per file.

8. **Display name.** Udemy does NOT expose an inline rename for
   Downloadable File assets at v1. The uploaded filename renders
   verbatim in the dashboard. If `display_name` is provided in the YAML,
   record it in the run report but take no dashboard action. Workaround:
   rename the source file on disk to the desired display name BEFORE
   upload (Udemy preserves the filename verbatim).

9. **Verify.** Re-read the lecture's attachment list; confirm the new
   filename is present. If not after timeout, screenshot + abort.

## Closing the picker without committing

The picker is sticky (same as `add-item-inline`). To dismiss it without
picking anything, click the SAME `lecture-add-content-btn` again
(toggles it closed). Do NOT rely on Escape or outside-click — neither
works.

## Worked example — `--preview` output

Input file `course-metadata/resources.yaml`:

```yaml
attachments:
  - section: 1
    lecture: 1.1
    files:
      - path: Claude-Created-Exam-Section-guides/CCA-CI-Study-Guide.pdf
        display_name: "Scenario 5: CI/CD Study Guide"
      - path: Claude-Created-Exam-Section-guides/CCA-Structured-Output-Study-Guide.pdf
        display_name: "Domain 4: Structured Output Study Guide"
```

Invocation:

```
udemy-resource-uploader \
  --course-id 7140821 \
  --course-repo ~/Documents/dev/udemy-courses/claude-architect-udemy-course \
  --preview
```

Expected text output:

```
DRY RUN — udemy-resource-uploader
Target: https://www.udemy.com/instructor/course/7140821/manage/curriculum/
Course repo: ~/Documents/dev/udemy-courses/claude-architect-udemy-course
Source: course-metadata/resources.yaml

Parsed plan (2 attachments across 1 lecture):
  Section 1 / Lecture 1.1 — "Welcome and What You'll Learn"
    + CCA-CI-Study-Guide.pdf (482 KB)
        display_name: "Scenario 5: CI/CD Study Guide"
    + CCA-Structured-Output-Study-Guide.pdf (1.1 MB)
        display_name: "Domain 4: Structured Output Study Guide"

File checks:
  ✓ All 2 source files exist
  ✓ No file exceeds 50MB threshold

Per-attachment dashboard flow (repeated for each file):
  [a] Read existing attachments on Lecture 1.1 (idempotency)
  [b] Click [data-purpose="lecture-add-content-btn"] on Lecture 1.1
  [c] Click "Resources" sub-option (selector TBD — first run captures)
  [d] Locate hidden file input (TBD)
  [e] setInputFiles(<absolute path to the PDF>)
  [f] Wait for upload-complete indicator (TBD), 120s timeout
  [g] Set display_name via rename input (TBD), save
  [h] Verify new attachment row present

Total to upload: 2 files (1.6 MB)
Lectures touched: 1
Existing attachments that would be SKIPPED: 0 (full read happens at apply time)

To apply: re-run without --preview AND with --apply
```
