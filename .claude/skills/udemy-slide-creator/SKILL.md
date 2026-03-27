---
name: udemy-slide-creator
description: >
  Generate Dyer Innovation branded PowerPoint slides for Udemy courses from lecture scripts.
  Takes udemy-lecture-writer markdown output and produces a fully branded .pptx using python-pptx.
  Use this skill whenever you need to create slide decks, generate PowerPoint files, or convert
  Udemy lecture scripts into presentation files. Trigger on: "create slides", "generate slides",
  "make a pptx", "build the deck", "turn this script into slides", or any request for a .pptx
  from a lecture script file. Also trigger when the user finishes writing a lecture and wants
  to record — slides are always the next step.
---

# Udemy Slide Creator

Converts `udemy-lecture-writer` markdown scripts into professionally branded `.pptx` slide decks
using the Dyer Innovation design system. Generates Python code using `python-pptx`, runs it,
and saves the file to the course's `slides/` directory.

## Dyer Innovation Design System

### Brand Colors

Extracted from the Dyer Innovation logo (`utils/dyer_innovation_logo.png` — 1024×1024 PNG,
green plant/leaf design with teal accents and dark navy text).

| Role | Hex | RGB | Usage |
|------|-----|-----|-------|
| Leaf Green (Primary) | `#3CAF50` | 60, 175, 80 | CTAs, highlights, key term callouts |
| Deep Green | `#1B8A5A` | 27, 138, 90 | Gradient partner, section dividers |
| Teal Accent | `#0D7377` | 13, 115, 119 | Code block accents, icons, secondary |
| Dark Navy | `#1A3A4A` | 26, 58, 74 | Title text, dark backgrounds, headings |
| Light Mint | `#E8F5EB` | 232, 245, 235 | Content slide backgrounds |
| Amber | `#E3A008` | 227, 160, 8 | Exam tips, warnings |
| White | `#FFFFFF` | 255, 255, 255 | Text on dark slides, body areas |
| Near Black | `#111928` | 17, 25, 40 | Body text on light backgrounds |
| Code Dark | `#1E2D3D` | 30, 45, 61 | Code block background |
| Code Light | `#A8D5C2` | 168, 213, 194 | Code text (mint-tinted for brand feel) |

### Typography

Use fonts that ship with PowerPoint — no custom font installs needed.

| Role | Font | Size | Weight |
|------|------|------|--------|
| Slide Title | Calibri | 36–44pt | Bold |
| Section / Subtitle | Calibri | 24–28pt | Bold |
| Body / Bullets | Calibri | 18–22pt | Regular |
| Code | Courier New | 14–16pt | Regular |
| Footer / Logo label | Calibri | 10pt | Regular |
| Speaker Notes | Calibri | 12pt | Regular |

### Logo Placement

- **Title slides**: logo centered at bottom, 1.5" wide, with padding above footer line
- **All other slides**: logo in bottom-right corner, 0.8" wide, 0.15" from right/bottom edges
- Logo path: `../../utils/dyer_innovation_logo.png` relative to the `udemy-courses/` directory
  (absolute: `/Users/jonathandyer/Documents/Dyer_Innovation/dev/utils/dyer_innovation_logo.png`)

### Slide Dimensions

Always use **16:9 widescreen**: 13.333" × 7.5" (standard Udemy/modern format).

---

## Slide Layout Templates

### TITLE — Lecture opener
- Background: dark navy (`#1A3A4A`) full bleed
- Large centered title: white, Calibri Bold 44pt
- Subtitle (lecture number + section): white, 22pt, lighter opacity
- Logo: centered bottom, 1.5" wide
- Optional: thin green accent bar at top (0.05" tall, full width, `#3CAF50`)

### CONTENT — Standard bullet slide
- Background: light mint (`#E8F5EB`)
- Title bar: dark navy strip across top (~1.2" tall), white title text Calibri Bold 36pt
- Body: bullets in Near Black, Calibri 20pt, left-aligned with indent
- Logo: bottom-right, 0.8" wide
- Optional left accent bar: 0.08" wide, Leaf Green, full height

### CODE — Code example slide
- Background: Code Dark (`#1E2D3D`) full bleed
- Title: white, Calibri Bold 32pt, top-left with left padding
- Code block: Courier New 15pt, Code Light (`#A8D5C2`) text, slightly inset box with
  darker fill (`#152535`), rounded corners via fill
- Logo: bottom-right, 0.8" wide (white version — use white-tinted positioning)
- Thin teal accent line below title: `#0D7377`, 0.04" tall

### COMPARISON — Two-column split
- Background: white
- Title bar: dark navy, white title text
- Left column (60% width): label in Leaf Green bold, content in Near Black
- Right column (40% width): label in Teal Accent bold, content in Near Black
- Vertical divider: Leaf Green, 0.03" wide
- Logo: bottom-right

### EXAM_TIP — Exam tip callout
- Background: white
- Full-width amber banner at top: `#E3A008`, "EXAM TIP" in white Calibri Bold 28pt, centered
- Title/trap text: Dark Navy bold, 22pt, centered below banner
- Two-box layout:
  - Left box (red-tinted `#FFF0F0`): "The Trap" label in red, trap description
  - Right box (green-tinted `#F0FFF4`): "Correct Approach" label in green, correct text
- Logo: bottom-right

### TAKEAWAY — Key takeaways / summary
- Background: dark navy gradient (`#1A3A4A` → `#0D7377`)
- Title: "What to Remember" in white Calibri Bold 36pt
- Bullets: white text, Calibri 20pt, each with a Leaf Green dot marker
- Logo: bottom-right (white visible on dark)

### SECTION — Section divider
- Background: gradient — Leaf Green (`#3CAF50`) to Deep Green (`#1B8A5A`)
- Large centered section title: white, Calibri Bold 40pt
- Subtitle (section number / domain): white, 20pt, italic
- Logo: centered bottom, 1.2" wide

### QUIZ — Knowledge check
- Background: light mint
- Title bar: Teal Accent (`#0D7377`), white "Knowledge Check" text
- Question text: Dark Navy, Calibri 22pt
- Answer options: A–D as styled boxes with Light Mint fill, Dark Navy border
- Logo: bottom-right

---

## Workflow

### Step 1: Locate and read the lecture script

The input is a lecture markdown file written by `udemy-lecture-writer`. It lives in the
course's `scripts/` directory (e.g., `claude-architect-udemy-course/scripts/lecture-2.3.md`).

If the user passes a file path, read it. If they say "generate slides for this lecture" with
the script in context, use the current context.

### Step 2: Parse the lecture

Run the parse script to extract structured slide data:

```bash
python3 .claude/skills/udemy-slide-creator/scripts/parse_lecture.py \
  <lecture_script_path> \
  --output /tmp/lecture_parsed.json
```

Review the output to confirm slide count and types look right before proceeding.

### Step 3: Determine output path

Save the `.pptx` to the course's `slides/` directory:
```
<course-dir>/slides/lecture-<N.N>-<slug>.pptx
```

Create the `slides/` directory if it doesn't exist.

### Step 4: Generate the slides

Write a Python script (or adapt `scripts/generate_slides.py`) and run it to produce the `.pptx`.
See `scripts/generate_slides.py` for the full template with all layout implementations.

The generation script takes:
- The parsed JSON from Step 2
- The logo path
- The output `.pptx` path

Run it:
```bash
python3 /tmp/generate_slides_<lecture>.py
```

### Step 5: Verify

After generation, confirm:
- [ ] File exists at expected output path
- [ ] Slide count matches the script
- [ ] Title slide has logo
- [ ] Code slides have dark background
- [ ] Exam tip slide has amber treatment
- [ ] Speaker notes populated on all slides
- [ ] Report the output path to the user

---

## Key python-pptx Patterns

See `scripts/generate_slides.py` for the full working template. Key patterns used throughout:

```python
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

# 16:9 presentation
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

# Blank slide (use layout index 6 for blank)
slide = prs.slides.add_slide(prs.slide_layouts[6])

# Solid background color
bg = slide.background.fill
bg.solid()
bg.fore_color.rgb = RGBColor(0x1A, 0x3A, 0x4A)

# Add a rectangle shape
from pptx.enum.shapes import MSO_SHAPE_TYPE
rect = slide.shapes.add_shape(
    1,  # MSO_SHAPE_TYPE.RECTANGLE
    Inches(0), Inches(0), Inches(13.333), Inches(1.2)
)
rect.fill.solid()
rect.fill.fore_color.rgb = RGBColor(0x1A, 0x3A, 0x4A)
rect.line.fill.background()  # no border

# Add text box
txBox = slide.shapes.add_textbox(Inches(0.5), Inches(0.15), Inches(12), Inches(0.9))
tf = txBox.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = "Slide Title"
p.font.name = "Calibri"
p.font.bold = True
p.font.size = Pt(36)
p.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
p.alignment = PP_ALIGN.LEFT

# Add bullet paragraph
p2 = tf.add_paragraph()
p2.text = "Bullet point text"
p2.font.name = "Calibri"
p2.font.size = Pt(20)
p2.font.color.rgb = RGBColor(0x11, 0x19, 0x28)
p2.level = 0

# Add image (logo)
slide.shapes.add_picture(
    logo_path,
    left=Inches(12.333),   # 13.333 - 0.8 - 0.2
    top=Inches(6.85),      # 7.5 - 0.5 - 0.15
    width=Inches(0.8)
)

# Speaker notes
notes_slide = slide.notes_slide
notes_slide.notes_text_frame.text = "Full narration text goes here."

# Save
prs.save("output.pptx")
```

---

## Handling [click] Progressive Reveals

PowerPoint animations via python-pptx are complex and limited. The practical approach:

1. **Detect** slides with `has_clicks: true` in the parsed JSON
2. **Split content**: each `[click]` segment becomes either:
   - A **separate slide** with "(continued)" in the title — simplest, always works
   - Or noted in speaker notes as "CLICK: [narration for next reveal]"
3. **Default behavior**: use the "separate slide" approach unless the user explicitly requests
   animation builds. It's cleaner for recording anyway.

When splitting into multiple slides, number them as: "3a", "3b", "3c" or "3 (1 of 3)", etc.

---

## Dependency Check

Before running generation scripts, verify python-pptx is installed:

```bash
python3 -c "import pptx; print('python-pptx OK')" 2>/dev/null || pip3 install python-pptx
```

If pip3 install fails due to permissions, try: `pip3 install --user python-pptx`

---

## File Naming Convention

```
lecture-{N}.{M}-{kebab-slug}.pptx
```

Examples:
- `lecture-2.3-agentic-loops.pptx`
- `lecture-1.1-course-overview.pptx`
- `lecture-4.2-tool-use-patterns.pptx`

The kebab slug comes from the lecture title: lowercase, spaces → hyphens, drop special chars.

---

## Full generation script

Read `scripts/generate_slides.py` for the complete working Python template. It implements
all 8 layout types with the Dyer Innovation brand system and handles logo placement,
speaker notes, and [click] splits automatically.
