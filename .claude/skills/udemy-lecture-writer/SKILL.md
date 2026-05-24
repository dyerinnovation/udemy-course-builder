---
name: udemy-lecture-writer
description: >
  Write complete, production-ready lecture scripts and slide content for Udemy courses.
  Generates fully narrated scripts with SLIDE sections, visual descriptions, speaker
  notes, and exam tips. Use when asked to write a lecture, fill in a script stub, or
  generate slide content for recording.
---

# Udemy Lecture Writer

## Overview

Produces fully written, recordable lecture scripts for Udemy certification prep courses.
Output is a completed lecture file in the established format — every SLIDE section has
narration, visual descriptions, and where relevant, code samples and exam tips.

Key conventions for this Udemy course:
- **7-10 minutes** per lecture (Udemy recommends shorter, but certification prep warrants depth)
- **Exam-anchored** — every lecture ends with an explicit exam tip
- **No Udacity branding** — clean, neutral presentation style
- **Claude/Anthropic API focus** — code examples use Python/TypeScript with the Anthropic SDK
- **No infrastructure** — no deploy scripts, no Cloud9, no lab environment in lecture scripts
- **SLIDE 1 is the cover slide; SLIDE 2 is often a dedicated "problem hook" slide.** Script SLIDE 1 narration plays over the slidev lecture-cover slide (Dyer Innovation branded title card) — keep it short and orientation-flavored (eg "You've probably called the Claude API before. But do you actually know what every field does?"), 30–60 seconds. If the slidev deck has a follow-up slide for the problem/antipattern/hook (very common pattern: ConceptHero, AntiPatternSlide, etc.) BEFORE the first content slide, give it its own script SLIDE 2 — don't fold the problem statement into SLIDE 1. The `udemy-lecture-video-renderer` skill maps script SLIDE N → slidev slide N with no offset, so the counts must match. Observed in 5 of 10 lectures in section 2: cover (SLIDE 1) + problem hook (SLIDE 2) is the dominant opening shape; only the very simplest lectures have just a cover + content.

## Click-aligned reveals (script + slidev)

The `udemy-lecture-video-renderer` skill respects `[click]` markers in script narration to add timed pauses (and, in a future version, per-click visual reveals). The contract:

- In the script narration, place `[click]` markers at the boundaries between code/content chunks. N `[click]` markers in a SLIDE's narration produce N+1 narration sub-chunks. The sub-chunk BEFORE the first `[click]` introduces the slide; each subsequent sub-chunk explains the newly-revealed content.
- In the slidev deck, the matching slide can use chunked reveals via `<CodeBlockSlide :code-chunks="[chunk1, chunk2, ...]" />` (chunk 0 initially visible; chunks 1..N reveal on slidev clicks in the live HTML preview). This makes the dev-server preview match the narration pacing, which is useful for visual review and live-presentation playback.

**Video render behavior:** the renderer drives a headless Chromium (Playwright) against the running Slidev dev server to capture one PNG per click state, emits one MP3 per narration sub-chunk, and muxes them in `(slide, click)` order. The video visually unfolds chunk-by-chunk as the narration explains each chunk. This bypasses a bug in Slidev v51's `--range` CLI (it accepts the arg but doesn't trim the PDF); using the runtime directly works perfectly. See `udemy-lecture-video-renderer/playbook.md` "Per-click visual capture via Playwright" for the full architecture.

**Authoring guidance:**
- Use `[click]` reveals for **code blocks** and **comparison patterns** (DON'T/DO callouts) — anywhere the audience benefits from a narration beat between explanation chunks.
- Skip `[click]` reveals for **bullet lists** unless you want explicit pacing beats between bullets.
- Each narration sub-chunk should be ~30–60 seconds — enough to explain the conceptual unit without making the previous chunk feel stale.
- Narration immediately AFTER a `[click]` should reference what JUST APPEARED (or the next concept being introduced), not what was already on screen.

## Slide Design Guidelines

### Color Palette (apply when generating slides via pptx skill)

| Role | Hex | Usage |
|------|-----|-------|
| Primary Blue | #1A56DB | Title text on light backgrounds, CTAs, key term highlights |
| Near-black | #111928 | Dark slide backgrounds, titles on dark slides |
| Accent Green | #0E9F6E | Correct patterns, "Do this" callouts |
| Amber | #E3A008 | Exam tips, warnings, anti-patterns to avoid |
| Light Gray | #F9FAFB | Content slide backgrounds |
| White | #FFFFFF | Text on dark slides |

### Typography
- **Title**: Inter Bold or Arial Bold, 32-40pt
- **Body**: Inter Regular or Arial, 18-22pt
- **Code**: Courier New or Menlo, 16-18pt (dark background, light text)
- **Exam tip callouts**: amber background (#E3A008), near-black text, italic

### Slide Layouts

| Visual Description Contains | Layout |
|-----------------------------|--------|
| "Title slide", "course opener" | Full dark background, large centered title |
| "Two options", "comparison", "vs" | Two-column split |
| "Three concepts", "three pillars" | Three-column layout |
| "Flowchart", "decision tree", "loop" | Title + large diagram area |
| "Code example", "code block" | Title + code area (dark background panel) |
| "Bullet list", "key points" | Title + body bullets |
| "Exam tip" | Amber callout box, title "Exam Tip" |

## Lecture Script Format

Every lecture file follows this structure. Use `---` to separate slides.

```markdown
# Lecture N.N: [Full Title]

**Section**: [Section name] ([Domain weight if applicable])
**Duration**: ~[X] minutes
**Status**: Ready to record

---

## SLIDE 1: [Opening Hook or Concept Title]

**Visual**: [One-sentence description of the slide's visual elements — diagram, code,
comparison, title card, etc. Be specific enough that a designer can reproduce it.]

[Narration: Opening sentence — start with a question, surprising fact, or direct
statement of what this lecture answers. Keep it punchy.]

[Second narration sentence. One idea per sentence.]

[continue narration — one sentence per line for easy teleprompter reading]

---

## SLIDE 2: [Concept Title]

**Visual**: [Visual description]

[Narration for this slide]

[click]

[Progressive reveal text — narration that accompanies the next build on the same slide]

---

...additional slides...

---

## SLIDE N: Exam Tip

**Visual**: Amber callout box. Title: "Exam Tip". Icon: target/bullseye. Text: [one-line
summary of the trap or pattern.]

**Exam Trap**: [One sentence stating the wrong thing candidates often do]

**Correct Approach**: [One sentence stating the right approach]

[Optional: one-sentence scenario that illustrates the difference]

---

## SLIDE N+1: Key Takeaways

**Visual**: Clean bullet list on light background. Title: "What to Remember".

[3-4 bullet points — the most exam-critical things from this lecture]

- [Key takeaway 1]
- [Key takeaway 2]
- [Key takeaway 3]
```

## Writing Rules

### Content Quality
1. **Answer a specific question** — every lecture should answer one clear question stated in Slide 1 (e.g., "When should you escalate vs. resolve?")
2. **Conversational tone** — write as if speaking to a smart colleague, not reading documentation
3. **Short sentences** — each narration line should be speakable in one breath; split anything over 20 words
4. **One idea per slide** — never try to cover more than one core concept per slide
5. **Concrete examples** — abstract concepts need a concrete code snippet or scenario by Slide 3
6. **Exam tie-in** — every lecture ends with an explicit exam tip (what trap candidates fall into)

### Code Examples
- Use Python or TypeScript with the Anthropic SDK (student's choice)
- Show realistic snippets (not toy "hello world" examples)
- Highlight the specific line or parameter that matters with a comment
- Keep code blocks to 10-20 lines for slide readability
- For agentic loops, show the actual control flow pattern

```python
# Example: the agentic loop skeleton
while True:
    response = client.messages.create(...)

    if response.stop_reason == "end_turn":
        break  # ← This is the exit condition

    if response.stop_reason == "tool_use":
        # Extract tool use block and execute
        tool_result = execute_tool(response.content)
        messages.append({"role": "user", "content": tool_result})
```

### Slide Counts
- **Minimum**: 5 slides per lecture (including opening + takeaways)
- **Maximum**: 8 slides per lecture (7-10 minutes at ~1 min/slide)
- **Exam tip slide**: Always the penultimate slide
- **Takeaways**: Always the final slide

### Progressive Reveals
Use `[click]` markers when a single slide builds over multiple narration beats:
```
**Visual**: Diagram with three phases. Phase 2 and 3 start hidden.

The first phase is [narration for phase 1].

[click]

In the second phase, [narration for phase 2].

[click]

Finally, [narration for phase 3].
```

## Script Formatting for Narration

> These conventions are enforced by the slide-QA pass documented in
> `udemy-slide-creator/SKILL.md`. They were learned the hard way during
> lecture 2.1's first end-to-end render — when each one was violated, the
> resulting MP4 felt rough enough that the user pulled them out as
> universal rules.

### Rule 1 — Every lecture deck has 3 intro slides (Cover → Fits-in → What-you'll-learn)

Every lecture opens with three slides in this exact order:

1. **Cover** — eyebrow + title + subtitle. Narration is a **~50-word hook (~10 seconds)**: name the gap the lecture closes. Do NOT recite outcomes — outcomes belong on slide 3. The cover is on screen briefly; long narration over a static cover feels dead.
2. **How this lecture fits in** — a `<LectureContext>` slide (component in `slidev/components/`) showing this lecture's position in the section + course. Narration is **~15 seconds**: what came before, what comes after, why this lecture exists.
3. **What you'll learn** — a `<BulletReveal>` slide with **3-5 bullets, one per click reveal**. Narration walks each bullet as it appears. This sets explicit expectations the rest of the lecture cashes in.

**Why this rule exists:** lecture 2.1's first render parked the viewer on a static cover for ~40 seconds while narration recited the cover hook, the "fits in" context, AND the outcomes — all on one slide. Splitting them fixes pacing AND gives a clean checklist the takeaways slide can mirror.

### Rule 2 — Title-orientation clause opens every slide's narration

The first clause of each slide's narration must name what the slide is about — a ~1-second handoff that orients the viewer before detail lands.

GOOD examples:
- *"Let's look at a real, complete request."* (orients to SLIDE 3's title "A Complete Request, Annotated")
- *"Now let's look at what comes back."* (orients to SLIDE 4 "The Response Object")
- *"Here are the four things you'll walk away knowing."* (orients to the "What you'll learn" slide)

BAD examples (skip the orientation, drop the viewer mid-thought):
- *"We start by importing anthropic."* (drops the viewer into a code walkthrough with no title context)
- *"The content field is a list, not a string."* (jumps to a detail without naming the topic)

**Why this rule exists:** viewers landing on a new slide need ~1 second of orientation before detail lands. Skipping that clause makes click reveals feel jarring because the narration is mid-thought when the visual changes.

### Rule 3 — Identifier pronunciation: spell phonetically OR add to the PLS

Code identifiers with underscores, dots, brackets, or other punctuation must either be spelled out phonetically in the narration text OR added to the course's pronunciation dictionary at `course-metadata/pronunciation.pls`.

| Identifier | Treatment | Why |
|---|---|---|
| `stop_reason` | Add to PLS: `<lexeme><grapheme>stop_reason</grapheme><alias>stop reason</alias></lexeme>` | Used across 5+ slides. PLS keeps script readable; renderer handles pronunciation deterministically. |
| `response.content[0].text` | Spell out in script: *"response dot content, the first item, dot text"* | Too specific for a dict entry. Authoring effort, but the script reads naturally. |
| Bare `[0]`, `[1]` | Spell out: *"the first item"*, *"the second item"*, or *"index zero"* | Bare bracket-number combos trip the TTS rhythm — sounds like "zo" or gets skipped. |
| `maxTokens`, `topK` (mixed case) | PLS if used repeatedly; otherwise spell out: *"max tokens"*, *"top K"* | TTS may slur or split inconsistently across slides. |

**When to use PLS vs spell-out:**
- **PLS entry** — for identifiers used in 3+ slides or across multiple lectures. One entry, deterministic pronunciation everywhere.
- **Spell-out in script** — for one-off code references where the phonetic version is more readable than the symbol.

**Why this rule exists:** lecture 2.1's first render had ElevenLabs reading `stop_reason` as "Stop-R-reason" on some slides and "stop reason" on others (non-deterministic). Bare `response.content[0].text` tripped the TTS into "response dot content zo text".

#### Pre-render PLS audit (do this BEFORE running the renderer)

The renderer's `parse_lecture.py` now runs an auto-audit and warns if any underscored identifier in the narration is missing a PLS entry — but you can (and should) catch these BEFORE invoking the renderer using two grep recipes. This is the safety net for the scale to 90+ remaining lectures.

**Recipe 1 — underscored snake_case identifiers (the common case):**

```bash
# Lists every snake_case identifier appearing in the lecture narration
grep -oE '\b[a-z][a-z]+_[a-z][a-z_]*\b' \
  scripts/section-NN-*/X.Y-*.md \
  | sort -u
```

For each match: confirm it exists in `course-metadata/pronunciation.pls` OR `udemy-course-builder/.claude/skills/udemy-lecture-video-renderer/pronunciation.template.pls`. If missing, add:

```xml
<lexeme><grapheme>stop_sequence</grapheme><alias>stop sequence</alias></lexeme>
```

The alias is just the grapheme with underscores replaced by spaces (almost always the right answer). Renderer pre-flight auto-warns these too — but catching them at authoring time saves a round-trip.

**Recipe 2 — 2-letter common-word identifiers (the hidden case):**

```bash
# 2-letter identifiers that the TTS will read as English homophones
grep -nE '`(id|ip|ui|ai|ml|os|db|fs|io|fk|pk|cd|ls|rm)`' \
  scripts/section-NN-*/X.Y-*.md
```

For each match, force letter-reading mode via period-separated capitals:

```xml
<lexeme><grapheme>id</grapheme><alias>I. D.</alias></lexeme>
```

**Why a manual scan, not auto-detection:** the underscored case is regex-safe (snake_case is distinct). The 2-letter case has high false-positive risk — "ai" appears as "AI" (acronym, good), as "Hawaii" substring (bad), as English particle (rare). Manual scan is fast and stays accurate.

#### Ellipses in narration are stripped automatically

`parse_lecture.py` removes both `...` (three ASCII dots) and `…` (Unicode horizontal ellipsis) from narration text before TTS handoff. This handles cases where you want to show an elided value visually — e.g. quoting `{"content": "..."}` in a slide example — but don't want the TTS to insert a 1-2 second pause where the dots appear.

If you actually want a spoken pause effect, use SSML `<break time="0.8s"/>` or just write the word "pause" as a stage direction. Don't rely on `...` for pacing — it's stripped silently.

### Rule 4 — Code-heavy slides: one narration clause per revealed chunk

When a slide reveals code in chunks (via `[click]` markers + slidev's `codeChunks` prop), every revealed chunk needs at least a brief narration clause introducing it. Don't reveal a JSON block with 6 fields and only narrate 2 of them.

Either:
- **(a)** Narrate every chunk (group related fields into one clause if needed), OR
- **(b)** Shrink the visible code to match what you actually want to discuss (split the slide if it can't fit)

GOOD chunking example — SLIDE 4 (Response Object) with 4 chunks and matching narration:

| Chunk | Code revealed | Narration clause |
|---|---|---|
| 1 | `id`, `type`, `role` | *"Three quick metadata fields at the top..."* |
| 2 | `content` block | *"Then the content field — content is a LIST, not a string..."* |
| 3 | `model`, `stop_reason`, `stop_sequence` | *"Below content, three 'why did Claude stop' fields..."* |
| 4 | `usage` | *"And finally usage — input and output tokens..."* |

BAD chunking example — 2 chunks but 6 fields visible, narration covering only 2 of them. Viewers parse what they see; if 4 lines appear and narration only addresses 1, they assume they missed something.

### Rule 5 — Every slide narration ends with a brief preview of what's next

The closing clause of every slide's narration names what's coming next. For intra-lecture slides, name the next slide's topic. For the LAST slide of a lecture, name the next lecture's topic (look up via `course-outline.md`).

This is what makes a lecture feel like a continuous teaching session rather than a sequence of disconnected slides — viewers stay engaged through the click-pause if they know what's coming.

Examples (lecture 2.1):
- Slide 5 ("A Complete Request") → *"Now let's flip to the response side and dissect what comes back."* (orienting to slide 6 "Response Object")
- Slide 6 ("Response Object") → *"Up next, the four values of `stop_reason` in detail."*
- Slide 9 (Exam Tip, last content slide before takeaways) → *"Last up: the takeaways to lock in."*
- Slide 10 (Takeaways, last slide of lecture) → *"In the next lecture, we'll go deep on system prompts — where they live, what they do, and how to write them well."*

The preview clause should be one short sentence (~10 words). Don't restate the entire next-slide content — just plant the hook.

**Why this rule exists:** lecture 2.1 round-2 feedback flagged a continuity gap — viewers felt slide transitions were abrupt because each slide's narration ended on the current concept with no forward link. One sentence at the end fixes it.

### Exam Tips
Every lecture includes an exam tip callout. Good exam tips:
- Name a specific wrong answer pattern (distractor)
- Contrast the trap with the correct approach
- Are grounded in a concrete scenario

**Weak exam tip**: "Remember to understand stop_reason."
**Strong exam tip**: "The trap is checking the response text for the word 'done' instead of reading stop_reason. If stop_reason is end_turn, the loop stops — full stop. Never parse text to decide."

## Workflow

### Step 1: Load Context

Read before writing:
1. The lecture's stub file — get the Key Points section
2. `course-outline.md` — understand the lecture's position in the section
3. `study-guide.md` — pull relevant concept detail and sample questions
4. Relevant cheat sheet files in `resources/cheat-sheets/` (if they exist for this topic)

### Step 2: Identify the Core Question

Before writing a single slide, complete this sentence:
"By the end of this lecture, a student will know the answer to: ___"

That question becomes Slide 1's title or opening line.

### Step 3: Identify the Exam Tip

Before writing, identify:
- The most common wrong answer for exam questions about this topic
- The correct approach/pattern

This goes in the penultimate slide. Knowing it upfront helps you write toward it.

### Step 4: Design the Slide Sequence

Plan the slide sequence before writing narration:
```
Slide 1: Opening hook / question
Slide 2: Core concept definition
Slide 3: Visual model (diagram, code, comparison)
Slide 4: Example / deeper dive
Slide 5: [Additional concept if needed]
Slide N-1: Exam Tip
Slide N: Key Takeaways
```

### Step 5: Write Narration

Write slide by slide, one sentence per line. After completing all slides:
- Read each slide aloud — if it sounds like documentation, rewrite it
- Check that Slide 1 hooks the student within 15 seconds
- Verify the code example is realistic and explains the key line
- Confirm the exam tip names a specific trap (not vague advice)

### Step 6: Write Visual Descriptions

For each slide, write the **Visual** line — a designer should be able to reproduce it without
reading the narration. Include:
- Layout type (split, single column, full-bleed, code block)
- Key elements (diagram labels, icon descriptions, code highlights)
- Color cues if specific colors convey meaning (green = correct, amber = warning)

### Step 7: Final Review

- [ ] Lecture answers one clear question (stated in Slide 1)
- [ ] Slide count is 5-8
- [ ] Each slide has: title, Visual description, narration
- [ ] Code examples (if present) are realistic and annotated
- [ ] `[click]` markers on progressive reveal slides
- [ ] Exam tip is on penultimate slide, names a specific trap
- [ ] Key takeaways on final slide (3-4 bullets)
- [ ] Duration estimate is reasonable (count slides × ~1 min = rough total)
- [ ] Tone is conversational throughout — no documentation-style language
- [ ] Status updated to "Ready to record"

## Slide Generation (pptx skill)

When the user asks to generate actual slides (not just the script):

1. Read the completed lecture script
2. Use the `pptx` skill to create the presentation
3. Apply the color palette and typography above
4. For each SLIDE section:
   - Title = the SLIDE header text
   - Layout = determined by the **Visual** description
   - Body = extract key points from narration (3-5 bullets max — not full narration)
   - Speaker notes = full narration text from the script
5. Verify slide count matches the script

**Important**: Slides show bullet-point highlights, NOT the full narration. The full narration is in speaker notes. Students read the bullets; the instructor reads the notes.

## Domain-Specific Conventions (Claude Architect Course)

For the CCA-F exam prep course, every lecture should:

- **Anchor to the exam domain** — state the domain name and weight at least once early
- **Use correct API names** — `stop_reason`, `tool_choice`, `tool_use`, `end_turn` (exact case)
- **Reference real SDK patterns** — show actual `client.messages.create()` calls
- **Name specific exam traps** — the exam guide's sample questions reveal what Anthropic tests
- **Connect to scenarios** — reference which of the 6 exam scenarios this concept applies to

Domain weight order (for priority when time is short):
1. Domain 1: Agentic Architecture (27%) — cover deeply
2. Domain 3: Claude Code Config (20%) — cover deeply
3. Domain 4: Prompt Engineering (20%) — cover deeply
4. Domain 2: Tool Design & MCP (18%) — cover thoroughly
5. Domain 5: Context Management (15%) — cover thoroughly
