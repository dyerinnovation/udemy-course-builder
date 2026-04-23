---
name: udemy-coding-exercise-authoring
description: "Author a Udemy native coding exercise from a lecture reference and a one-line concept. Produces a complete 5-file exercise directory (exercise.md, learner.py, solution.py, evaluation.py, explanation.md) under the course repo's labs/coding-exercises/ tree, then runs a dogfood test to verify the solution passes its own evaluation. Trigger on: 'create a coding exercise', 'add a Udemy coding exercise for lecture X.Y', 'I need a practice challenge for [concept]', 'author an exercise on [pattern]'. Do not use for Udemy dashboard deployment (that's udemy-coding-exercise-deployer). Also do not use for assignment-style exercises or multi-file projects — this skill targets single-function, sandboxed, unittest-verified Python exercises only."
---

# Udemy Coding Exercise — Authoring

You author **Udemy native coding exercises** in the authoring repo's on-disk format. Each exercise is a directory with exactly 5 files, validated by a dogfood test before commit. A sibling skill (`udemy-coding-exercise-deployer`) handles pushing the exercise into Udemy's instructor dashboard.

## When to use

- The user asks you to create a Udemy coding exercise.
- The user points at a specific lecture (e.g. "add a practice challenge for lecture 3.5") and asks for an exercise.
- The user gives you a concept ("test them on the error response contract") and asks you to turn it into a coding exercise.

## When NOT to use

- **Deploying an existing exercise to Udemy** → use `udemy-coding-exercise-deployer`.
- **Authoring a quiz question** → use `udemy-quiz-creator`.
- **Authoring a full lecture script** → use `udemy-lecture-writer`.
- **Multi-file coding projects or local labs that need API keys / network** → not a Udemy native exercise candidate. Tell the user and redirect.

## Input format

Expected from the user:
- **Lecture reference** (e.g. `3.5`, `2.1`, `6.9`) — maps to `scripts/section-0N-*/N.Y-*.md` in the course repo.
- **Concept** — one sentence describing what the exercise tests.

Optional:
- **Difficulty** — `easy` / `medium` / `hard`. Default `easy`.
- **Estimated minutes** — integer, default 5-10 based on difficulty.
- **Exam scenarios** — which of the 6 official scenarios (1-6) this reinforces.

## Output process (walk through these steps)

1. **Read the target lecture's narration script** at `scripts/section-0N-*/N.Y-*.md` in the course repo. This grounds the exercise in what the lecture actually taught — you should not introduce concepts the lecture hasn't covered.

2. **Determine section + next sequence number.** List `labs/coding-exercises/section-N/` — pick the next `NN` prefix (e.g. if `01-*` and `02-*` exist, new exercise is `03-`). If the section directory doesn't exist yet, create it.

3. **Design a mock Claude API fixture** that exercises the concept. The fixture is a Python dict (or list of dicts) that matches the real API shape but is hardcoded — no network, no dependencies, no API keys. This is the constraint that shapes every exercise: Udemy's sandbox can't call Claude.

4. **Write all 5 files** into the new directory, following the seed exercise format exactly (see `labs/coding-exercises/README.md` in the course repo, and the live seed at `labs/coding-exercises/section-2/01-parse-stop-reason/`).

5. **Run the dogfood test** to prove the solution passes its own evaluation:
   ```bash
   cd labs/coding-exercises/section-N/NN-<slug>
   cp learner.py learner.py.bak
   cp solution.py learner.py
   python -m unittest evaluation.py
   # expect: OK
   mv learner.py.bak learner.py
   ```
   If tests fail, either `solution.py` or `evaluation.py` is wrong. Fix and re-test. Never ship a broken exercise.

6. **Commit** in the course repo with message `feat(labs): add coding exercise s<N>-<NN>-<slug>`.

7. **Report** the directory path + a 2-sentence summary of what the exercise tests + the dogfood pass line.

## Authoring heuristics (mandatory — every exercise must follow)

1. **Mock the API, don't call it.** Python dicts as fixtures. No `anthropic.Anthropic()` calls. No network. No API keys.
2. **One concept per exercise.** A stop_reason branch doesn't also test tool schema. Split when in doubt. If the problem statement exceeds 3 paragraphs, it's two exercises.
3. **5-10 minute solve time.** A student who watched the linked lecture should picture the solution within 90 seconds of reading the problem. If they can't, rescope.
4. **High-value only.** Target ~22 exercises total across Sections 2-7. Every exercise maps to at least one exam scenario via `exam_scenarios:` frontmatter. If it doesn't, don't write it.
5. **Evaluation uses only the Python standard library.** `unittest` or plain `assert`. No pytest, no external deps.
6. **Learner file is meaningful but incomplete.** Function signature + type hints + docstring + a `# TODO` or `pass`. Not blank. Not the solution with one line stripped.
7. **Problem statement shows example input + expected output.** At least TWO concrete examples. Concrete I/O beats abstract descriptions every time.
8. **Test coverage includes the "almost-right trap."** At least one test case catches the plausible-but-wrong answer — the distractor pattern the exam itself uses. This is the pedagogical payoff.

## File format

See `labs/coding-exercises/README.md` in the course repo for the authoritative spec. Do not duplicate it here — link and rely on the live version. Summary:

- `exercise.md` — YAML frontmatter (id, title, section, lecture_ref, language, difficulty, learning_objective, exam_scenarios, related_lectures, estimated_minutes, hints) + markdown problem statement + 2+ examples
- `learner.py` — starter: function signature + type hints + docstring + `# TODO` or `pass`
- `solution.py` — full correct implementation, under 40 LOC
- `evaluation.py` — `unittest.TestCase` with `from learner import <fn>`, at least 5 test cases including happy-path + edge + almost-right-trap
- `explanation.md` — Why this matters / The trap / The solution line by line / Exam relevance

## Worked examples (reference these when authoring)

### Example A — Domain 1 (control-loop)

- **Lecture:** 3.1 — The Agentic Loop: stop_reason Is Everything
- **Concept:** "Given a list of Claude API responses from a multi-turn loop, count how many turns involved tool calls."
- **Target function:** `def count_tool_turns(responses: list[dict]) -> int`
- **Mock fixture:** `[{"stop_reason": "tool_use"}, {"stop_reason": "tool_use"}, {"stop_reason": "end_turn"}]` → expected `2`
- **Solution:** `return sum(1 for r in responses if r.get("stop_reason") == "tool_use")`
- **Almost-right trap case in tests:** responses where `content[0].type == "tool_use"` but `stop_reason != "tool_use"` — a lazy implementer who branches on content type counts wrong.

### Example B — Domain 2 (tool schema)

- **Lecture:** 4.2 — Tool Description Anatomy
- **Concept:** "Given a tool schema dict, validate that it has all required top-level fields (name, description, input_schema) AND that input_schema has type, properties, required."
- **Target function:** `def validate_tool_schema(tool: dict) -> tuple[bool, list[str]]`
- **Mock fixture:** a correct tool dict + several malformed variants (missing name, empty description, input_schema missing `required`, etc.)
- **Solution:** series of `if "field" not in d: errors.append("missing field X")` checks, return `(not errors, errors)`.
- **Almost-right trap case in tests:** a tool with all 3 top-level fields but an empty `input_schema.properties` — passes a shallow check but fails the spec.

### Example C — Domain 4 (structured output validation)

- **Lecture:** 6.9 — Validation-Retry Loops (When They Work and When They Don't)
- **Concept:** "Given a string that should contain JSON matching a schema, return `(valid: bool, parsed_or_error_msg)`."
- **Target function:** `def validate_structured(raw: str, required_fields: list[str]) -> tuple[bool, object]`
- **Mock fixture:** well-formed JSON with all fields; malformed JSON (missing brace); JSON missing a required field.
- **Solution:** `try: data = json.loads(raw); except ... return (False, "parse error: ...")`; then check for missing fields; return `(True, data)` only if both pass.
- **Almost-right trap case in tests:** JSON that parses cleanly but is missing a required field — a lazy implementer who only catches the parse error returns `(True, parsed_object)` instead of `(False, "missing field: X")`.

## Dogfood test protocol

Before reporting done, run this in the exercise directory:

```bash
cp learner.py learner.py.bak
cp solution.py learner.py
python -m unittest evaluation.py
mv learner.py.bak learner.py
```

Expected last line: `OK`. If you see `FAILED`, either the solution or the evaluation is wrong — fix and retry. This test MUST pass before you commit.

## Cross-references

- **Format spec (authoritative):** `labs/coding-exercises/README.md` in the course repo
- **Authoring rules:** `.claude/rules/coding-exercises.md` in the course repo
- **Seed exercise (canonical template):** `labs/coding-exercises/section-2/01-parse-stop-reason/` in the course repo
- **Sibling skill (deployment):** `udemy-coding-exercise-deployer`
- **Udemy docs:** https://support.udemy.com/hc/en-us/articles/115002883587-How-to-Create-a-Coding-Exercise
