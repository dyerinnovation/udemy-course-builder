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
