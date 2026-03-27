# Skill Development Conventions

- Each skill lives in `.claude/skills/<skill-name>/SKILL.md`
- Skills may include supporting scripts in a `scripts/` subdirectory
- The `plugin.json` manifest lists all skills — keep it in sync when adding/removing skills
- Lecture scripts use markdown with `<!-- SLIDE: ... -->` markers for slide generation
- Quiz output must be Udemy-compatible: multiple choice, true/false, or multi-select
- Section quizzes have 10 questions; practice exams have 40 questions
- All generated .pptx files go in the course's `slides/` directory
