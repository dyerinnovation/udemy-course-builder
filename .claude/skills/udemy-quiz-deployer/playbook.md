# udemy-quiz-deployer — Playbook

Operating reference for the quiz-creation flow on `/manage/curriculum/`.
Sibling document to `udemy-curriculum-populator/playbook.md` and
`udemy-coding-exercise-deployer/SKILL.md`. Selectors marked **CONFIRMED**
were captured live on 2026-04-26 from
`https://www.udemy.com/instructor/course/7140821/manage/curriculum/`.
Selectors marked **TBD** must be captured on the first real `--apply` run
and pasted back into this file.

## Key insight: Udemy uses `data-purpose`

Same pattern as the curriculum-populator and exercise-deployer skills.
`data-purpose` is stable across React re-renders and UI rev-ups —
**prefer it over CSS class matches at every step.**

## URL

```
https://www.udemy.com/instructor/course/<numeric-id>/manage/curriculum/
```

Numeric course id from the instructor URL — NOT the public slug.

## Confirmed selectors (carried over from curriculum-populator)

| Purpose | Selector |
|---|---|
| Whole curriculum container | `[data-purpose="curriculum-list"]` |
| A section row | `[data-purpose="section-editor"]` |
| A lecture row (also wraps quizzes) | `[data-purpose="lecture-editor"]` |
| Title text inside a row | `[data-purpose="item-full-title"]` |
| Order/index inside a row | `[data-purpose="item-object-index"]` (innerText e.g. `"Section 2:"`, `"Lecture 1:"`, `"Quiz 1:"`) |
| Inline insert + (between every pair of items) | `[data-purpose="add-item-inline"]` |
| Choice after clicking + | `[data-purpose="add-item-inline-last"]` (innerText `"Curriculum item"` or `"Section"`) |
| Quiz picker | `[data-purpose="add-quiz-btn"]` (aria-label `"Add Quiz"`) |

## DOM model — rows are SIBLINGS under curriculum-list

Same correction as in the curriculum-populator playbook: section rows,
lecture rows, quiz rows, exercise rows are ALL direct children of
`[data-purpose="curriculum-list"]`, each wrapped in a
`div.js-curriculum-item-draggable.curriculum-list--list-item--xn0`.

To find items belonging to Section N:

1. Walk `curriculumList.children` in order.
2. Find the wrapper whose `[data-purpose="section-editor"]` has
   `item-object-index` matching `Section <N>:`.
3. Continue forward — every consecutive non-section wrapper belongs to
   that section.
4. Stop at the next wrapper containing a `[data-purpose="section-editor"]`.

Quizzes share the `lecture-editor` wrapper class (Udemy collapses all
non-section curriculum items into one editor type at the DOM level).
Differentiate via the `item-object-index` text, which reads `Quiz N:` for
quizzes vs. `Lecture N:` for lectures.

Reference enumeration (read-only):

```js
const list = document.querySelector('[data-purpose="curriculum-list"]');
const wrappers = list.querySelectorAll(
  ':scope > div.js-curriculum-item-draggable, :scope > div.curriculum-list--list-item--xn0'
);
const items = [];
let currentSection = null;
wrappers.forEach(w => {
  const sec = w.querySelector('[data-purpose="section-editor"]');
  const lec = w.querySelector('[data-purpose="lecture-editor"]');
  const idxEl = w.querySelector('[data-purpose="item-object-index"]');
  const titleEl = w.querySelector('[data-purpose="item-full-title"]');
  const idx = idxEl?.innerText?.trim() ?? '';
  if (sec) {
    const m = idx.match(/Section\s+(\d+):/);
    currentSection = { number: m ? Number(m[1]) : null, title: titleEl?.innerText.replace(/^Section\s+\d+:\s*/, '').trim(), items: [] };
    items.push(currentSection);
  } else if (lec && currentSection) {
    let kind = 'lecture';
    if (/^Quiz\s+\d+:/.test(idx)) kind = 'quiz';
    else if (/^Coding Exercise\s+\d+:/.test(idx)) kind = 'coding-exercise';
    currentSection.items.push({ kind, title: titleEl?.innerText.replace(/^(Lecture|Quiz|Coding Exercise)\s+\d+:\s*/, '').trim() });
  }
});
JSON.stringify(items, null, 2);
```

## Menu behaviour notes

- The `+` picker is **inline-expanded** (sticky), NOT a popover. Clicking
  the same `+` again toggles it closed. Escape and outside-click do NOT
  close it.
- The `+` is always visible — no hover-to-reveal needed.
- Clicking `+` shows TWO choices: `Curriculum item` and `Section`. Pick
  `Curriculum item` to reveal the 5-button sub-picker (Lecture / Quiz /
  Coding Exercise / Practice Test / Assignment).

## Quiz markdown parsing — JS/regex stub

The skill should parse markdown in Python (preferred — same env as
`Bash` tool already running) using a small per-format dispatcher.
Pseudocode:

```python
import re
from pathlib import Path

def parse_quiz(md_path: Path) -> dict:
    text = md_path.read_text()
    title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if not title_match:
        raise ValueError(f"No H1 title in {md_path}")
    title = title_match.group(1).strip()

    section_num = parse_section_from_filename(md_path.name)
    blockquote = re.search(r"^>\s*Section:\s*(\d+)", text, re.MULTILINE)
    if blockquote:
        section_num = int(blockquote.group(1))

    # PRIMARY format: split on `^## Q\d+`
    q_blocks = re.split(r"(?=^##\s+Q\d+\s+\()", text, flags=re.MULTILINE)[1:]
    if q_blocks:
        questions = [parse_primary_q(b) for b in q_blocks]
    else:
        # ALTERNATE format: split on `^## Question \d+`
        q_blocks = re.split(r"(?=^##\s+Question\s+\d+)", text, flags=re.MULTILINE)[1:]
        questions = [parse_alternate_q(b) for b in q_blocks]

    if not questions:
        raise ValueError(f"No questions parsed in {md_path}")
    return {"title": title, "section": section_num, "questions": questions}

def parse_primary_q(block: str) -> dict:
    head = re.search(r"^##\s+Q(\d+)\s+\((multiple choice|true/false|multi-select)\)", block, re.MULTILINE)
    qtype_map = {"multiple choice": "multiple_choice", "true/false": "true_false", "multi-select": "multi_select"}
    qtype = qtype_map[head.group(2)]
    stem_match = re.search(r"\*\*Stem:\*\*\s*\n(.+?)\n\nA\)", block, re.DOTALL)
    stem = stem_match.group(1).strip() if stem_match else ""
    options = [(m.group(1), m.group(2).strip()) for m in re.finditer(r"^([A-D])\)\s+(.+)$", block, re.MULTILINE)]
    correct_match = re.search(r"\*\*Correct Answers?:\*\*\s+([A-D](?:,\s*[A-D])*)", block)
    if not correct_match:
        raise ValueError(f"No Correct Answer line in question block:\n{block[:200]}")
    correct_letters = {c.strip() for c in correct_match.group(1).split(",")}
    explanation_match = re.search(r"###\s+Explanation\s*\n(.+?)(?=\n---|\n##\s|\Z)", block, re.DOTALL)
    explanation = explanation_match.group(1).strip() if explanation_match else None
    return {
        "type": qtype,
        "stem": stem,
        "options": [{"text": text, "correct": letter in correct_letters} for letter, text in options],
        "explanation": explanation,
    }

def parse_alternate_q(block: str) -> dict:
    stem_match = re.search(r"^##\s+Question\s+\d+\s*\n(.+?)\n\n-\s+\[", block, re.DOTALL)
    stem = stem_match.group(1).strip() if stem_match else ""
    options = []
    for m in re.finditer(r"^-\s+\[([ x])\]\s+(.+)$", block, re.MULTILINE):
        options.append({"text": m.group(2).strip(), "correct": m.group(1) == "x"})
    if not any(o["correct"] for o in options):
        raise ValueError(f"No [x] correct marker in question block:\n{block[:200]}")
    n_correct = sum(1 for o in options if o["correct"])
    is_tf = (
        len(options) == 2
        and {o["text"].lower() for o in options} == {"true", "false"}
    )
    qtype = "true_false" if is_tf else ("multi_select" if n_correct > 1 else "multiple_choice")
    explanation_match = re.search(r"\*\*Explanation:\*\*\s+(.+?)(?=\n##|\Z)", block, re.DOTALL)
    explanation = explanation_match.group(1).strip() if explanation_match else None
    return {"type": qtype, "stem": stem, "options": options, "explanation": explanation}

def parse_section_from_filename(name: str) -> int:
    m = re.match(r"section-(\d+)", name)
    if not m:
        raise ValueError(f"Filename {name} doesn't match section-NN-*.md")
    return int(m.group(1))
```

The skill should call this once per quiz file BEFORE touching the
browser. A failed parse aborts the run cleanly.

## Quiz creation flow

For each `CREATE` quiz in the plan:

1. **Locate Section N's last wrapper.** Walk the flat-DOM enumeration
   above; find the section wrapper for `Section N:`; track the index of
   the LAST wrapper belonging to that section.

2. **Click the `+` immediately after that last wrapper.** That's the
   `[data-purpose="add-item-inline"]` whose position in the document
   matches the count of wrappers before it being equal to the section's
   end-index.

3. **Wait ~400ms.** Click the `add-item-inline-last` button with
   `innerText === "Curriculum item"`.

4. **Wait for the 5-button sub-picker.** Click
   `[data-purpose="add-quiz-btn"]` (aria-label `"Add Quiz"`).

5. **Fill the title.** The inline quiz title form appears in place of the
   new row. Selector for title input is **TBD** (likely
   `[data-purpose="quiz-title"]` based on Udemy's `<entity>-title`
   pattern). Use the React-aware value setter:

   ```js
   const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
   setter.call(input, newValue);
   input.dispatchEvent(new Event('input', { bubbles: true }));
   input.dispatchEvent(new Event('change', { bubbles: true }));
   ```

6. **Submit.** Click the primary submit button (**TBD** — likely
   `[data-purpose="submit-quiz-form"]` with label `"Add Quiz"`). Poll for
   the form to disappear.

7. **Open the editor.** Quiz creation typically auto-opens the question
   editor. If not, click the new quiz row's edit affordance (**TBD** —
   likely `[data-purpose="quiz-edit-btn"]`).

8. **Per question, in markdown order:**
   1. Click "Add question" (**TBD** selector — likely
      `[data-purpose="add-question-btn"]`).
   2. Select the question-type picker option matching the parsed `type`
      (**TBD** selector — likely a button group with one of
      `[data-purpose="question-type-multiple-choice"]`,
      `[data-purpose="question-type-true-false"]`,
      `[data-purpose="question-type-multi-select"]`).
   3. Fill the question-text input (**TBD** — typically a Quill or
      contenteditable rich-text field).
      - If it's a plain `<input>` or `<textarea>`: use the React value
        setter above.
      - If it's a `[contenteditable="true"]`: focus + use
        `document.execCommand('insertText', false, value)` (works for
        Quill/Slate/ProseMirror in current browsers).
   4. For each option: fill the option text input (**TBD**), then click
      the correct-answer toggle (**TBD**) if the option is marked
      correct. For `multi_select`, multiple toggles will be active.
   5. If `explanation` is non-null: fill the explanation field (**TBD**)
      using the same pattern as the question-text field.

9. **Save the quiz.** Click the save button (**TBD** — likely
   `[data-purpose="submit-quiz-form"]` or a per-quiz "Save" button).
   Wait for a success indicator (**TBD** — toast / state change / editor
   closes).

10. **Verify.** Re-run the FLAT-DOM enumeration. Confirm a row matching
    `Quiz <M>: <title>` is present in Section N's wrapper range. Take a
    screenshot.

## Closing a picker without committing

The picker is sticky. To dismiss without picking, click the ORIGINAL `+`
button again (toggles it closed). Escape and outside-click do NOT work.

## TBD selectors — capture on first `--apply` run

These selectors are pending live capture. When you run `--apply` for the
first time, capture each one (use `mcp__claude-in-chrome__find` or
`mcp__claude-in-chrome__read_page` to inspect the DOM after the relevant
step) and paste the confirmed selector back into this file.

| TBD purpose | Hypothesized selector | Verified? |
|---|---|---|
| Quiz title input | `[data-purpose="quiz-title"]` | ☐ |
| Quiz title submit / "Add Quiz" button | `[data-purpose="submit-quiz-form"]` | ☐ |
| Quiz row edit affordance | `[data-purpose="quiz-edit-btn"]` | ☐ |
| Add-question button (in editor) | `[data-purpose="add-question-btn"]` | ☐ |
| Question-type picker — multiple choice | `[data-purpose="question-type-multiple-choice"]` | ☐ |
| Question-type picker — true/false | `[data-purpose="question-type-true-false"]` | ☐ |
| Question-type picker — multi-select | `[data-purpose="question-type-multi-select"]` | ☐ |
| Question text input (rich-text or contenteditable) | `[data-purpose="question-text"]` (likely contenteditable) | ☐ |
| Answer-option text input | `[data-purpose="answer-text"]` (per-row) | ☐ |
| Correct-answer toggle | `[data-purpose="answer-correct-toggle"]` (per-row) | ☐ |
| Explanation field | `[data-purpose="answer-explanation"]` | ☐ |
| Save quiz button (final) | `[data-purpose="submit-quiz-form"]` (may be reused) | ☐ |
| Save success indicator | `[role="alert"]` (toast) OR editor-close transition | ☐ |
| Validation-error banner | `[role="alert"]` (assumption — verify) | ☐ |

If any TBD selector returns zero matches on the first capture attempt,
ABORT and screenshot. Do not invent CSS selector substitutes — Udemy's
class names rotate and silent fallbacks lead to wrong-button clicks.

## Worked example — `--preview` output

For `quizzes/section-02-api-bootcamp.md` against course id `7140821`,
running:

```
udemy-quiz-deployer \
  --course-id 7140821 \
  --course-repo ~/Documents/dev/udemy-courses/claude-architect-udemy-course \
  --quiz quizzes/section-02-api-bootcamp.md \
  --preview
```

Expected text output:

```
DRY RUN — udemy-quiz-deployer
Target: https://www.udemy.com/instructor/course/7140821/manage/curriculum/
Course repo: ~/Documents/dev/udemy-courses/claude-architect-udemy-course

Parsed quiz:
  File: quizzes/section-02-api-bootcamp.md
  Title: "Quiz: Section 2 — Claude API Fundamentals Bootcamp"
  Section: 2 (from filename)
  Questions: 10
    Q1  multiple_choice  4 opts  correct=B   "A junior engineer on your team..."
    Q2  multiple_choice  4 opts  correct=C   "You're extracting structured JSON..."
    Q3  multiple_choice  4 opts  correct=C   "Your team needs a guarantee..."
    Q4  multiple_choice  4 opts  correct=C   "Your agent's loop reads response.stop_reason..."
    Q5  true_false       2 opts  correct=B   "True or False: temperature = 0..."
    Q6  multiple_choice  4 opts  correct=C   "You're building a customer-facing chatbot..."
    Q7  multiple_choice  4 opts  correct=B   "You have a prompt that bundles..."
    Q8  multi_select     4 opts  correct=A,B "Select ALL of the following..."
    Q9  multiple_choice  4 opts  correct=C   "A user sends a screenshot..."
    Q10 multiple_choice  4 opts  correct=A   "Your agent calls a lookup_order tool..."

Existing curriculum (read from dashboard):
  Section 2: Claude API Fundamentals Bootcamp — 14 lectures, 0 quizzes

Plan:
  Section 2 — CREATE quiz "Quiz: Section 2 — Claude API Fundamentals Bootcamp"
    + 10 questions (7 multiple_choice, 2 true_false, 1 multi_select)

Total to deploy: 1 quiz, 10 questions
TBD-selector risk: 11 selectors will be captured on first apply run.
To apply: re-run without --preview.
```
