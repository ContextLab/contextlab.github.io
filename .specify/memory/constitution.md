<!--
Sync Impact Report
===================
Version change: N/A (initial) → 1.0.0
Modified principles: N/A (all new)
Added sections:
  - I. User Experience Excellence
  - II. Attention to Detail
  - III. Living Documentation
  - IV. Repository Cleanliness
  - V. Cross-Repository Consistency
  - Cross-Repository Coordination (Section 2)
  - Development Workflow (Section 3)
  - Governance
Removed sections: None
Templates requiring updates:
  - .specify/templates/plan-template.md: ✅ No updates needed (Constitution Check
    section is dynamically filled from this file)
  - .specify/templates/spec-template.md: ✅ No updates needed (user stories and
    acceptance scenarios already support visual-check and documentation requirements)
  - .specify/templates/tasks-template.md: ✅ No updates needed (Polish phase already
    includes documentation updates; visual checks can be added per-feature)
Follow-up TODOs: None
-->

# Context Lab Website Constitution

## Core Principles

### I. User Experience Excellence

Every page MUST deliver a delightful, engaging, and visually cohesive
experience. This is a public-facing academic lab site — first impressions
shape how prospective students, collaborators, and funders perceive the lab.

- All text MUST be clear, brief, and free of jargon unless the audience
  is explicitly technical.
- Theming MUST remain cohesive: Dartmouth green palette, Nunito Sans
  typography, hand-drawn border aesthetic, lowercase headings.
- All pages MUST render correctly on desktop, tablet (768px), and mobile
  (480px) breakpoints. Test on Chrome, Firefox, Safari, and Edge.
- Interactive elements (modals, dropdowns, carousels, info panel) MUST
  feel responsive and smooth — no layout shifts, no broken animations.
- New UI features MUST be evaluated for whether they genuinely improve
  the visitor experience, not just add complexity.

### II. Attention to Detail

Every substantive change MUST be verified through comprehensive testing,
including visual checks. Bugs on a live academic website erode credibility.

- All changes MUST pass `python -m pytest tests/ -v` before pushing.
- Visual changes MUST be verified by screenshot or manual inspection on
  at least desktop and mobile viewports.
- The full pre-push validation (`scripts/pre_push_check.py`) MUST pass
  before any push to `main`.
- Build output MUST be inspected: auto-generated HTML pages should be
  spot-checked after spreadsheet or template changes.
- Link integrity MUST be maintained: no broken internal links, no dead
  external URLs in publications or software listings.

### III. Living Documentation

Documentation MUST stay synchronized with the codebase at all times.
Stale docs are worse than no docs — they actively mislead.

- Any functional change MUST include corresponding updates to relevant
  documentation (CLAUDE.md, AGENTS.md, README.md, inline comments).
- Changes to the build system, scripts, or templates MUST update
  `scripts/AGENTS.md` and the root `AGENTS.md`.
- New scripts or commands MUST be documented in CLAUDE.md under Commands.
- Spreadsheet schema changes (new columns, renamed fields) MUST update
  the field reference in README.md and relevant AGENTS.md files.
- GitHub Actions workflow changes MUST be reflected in documentation.

### IV. Repository Cleanliness

The repository MUST remain clean and free of private, temporary, or
extraneous files. This is a public GitHub Pages repo — everything
committed is visible to the world.

- Passwords, API keys, tokens, and personal information MUST NEVER be
  committed. Credentials belong in `~/.config/cdl/` or environment
  variables, never in the repo.
- Temporary files (screenshots, scratch scripts, debug output) MUST be
  deleted after use or moved to `scripts/` if reusable.
- `.gitignore` MUST be maintained to exclude OS artifacts, editor files,
  Python caches, and any generated files not needed for the live site.
- Auto-generated root HTML files (`publications.html`, `people.html`,
  `software.html`, `news.html`) MUST NOT be hand-edited — changes will
  be overwritten by the build system.
- No `!important` in CSS without explicit written justification.
- No inline styles in templates — use CSS classes.

### V. Cross-Repository Consistency

This website MUST remain consistent with the
[lab-manual](https://github.com/ContextLab/lab-manual) repository.
These two repos together define the lab's public and internal identity.

- Personnel information (current members, alumni, roles) MUST match
  across both repositories. When someone is onboarded or offboarded
  here, the lab-manual MUST be updated accordingly (and vice versa).
- Lab policies, descriptions, and research summaries that appear on
  both the website and the lab manual MUST NOT contradict each other.
- The lab-manual repository includes a Slack bot that may programmatically
  update this site. Changes made by the bot MUST follow the same build
  pipeline (edit data/templates, rebuild, test) rather than directly
  editing auto-generated HTML.
- When reviewing PRs that touch shared content (people, lab description,
  research areas), cross-check the other repository for drift.

## Cross-Repository Coordination

The website and lab-manual share overlapping content. To prevent drift:

- **People data**: The source of truth for the website is `data/people.xlsx`.
  The lab-manual maintains its own member records. After onboarding or
  offboarding, both repos MUST be updated in the same session or PR.
- **Slack bot integration**: The lab-manual Slack bot has write access to
  trigger updates on this site. Bot-initiated changes MUST go through
  the standard `data/*.xlsx` → `scripts/build.py` → test pipeline.
  Direct HTML edits by the bot are prohibited.
- **Conflict resolution**: If information conflicts between repos, resolve
  by checking the authoritative source (e.g., `people.xlsx` for member
  data, the lab-manual for policies) and updating the stale copy.

## Development Workflow

All changes to the website MUST follow this workflow:

1. **Edit sources, not outputs**: Modify `data/*.xlsx`, `templates/*.html`,
   `css/style.css`, `js/main.js`, or `documents/JRM_CV.tex` — never
   auto-generated root HTML or `documents/JRM_CV.html`.
2. **Validate**: Run `cd scripts && python validate_data.py`.
3. **Build**: Run `cd scripts && python build.py` (and `build_cv.py` if
   CV was changed).
4. **Test**: Run `python -m pytest tests/ -v` — all tests MUST pass.
5. **Visual verify**: For UI changes, serve locally (`python3 -m http.server 8000`)
   and check desktop + mobile viewports.
6. **Document**: Update CLAUDE.md, AGENTS.md, and/or README.md if the
   change affects commands, architecture, or conventions.
7. **Push**: Only after all above steps pass.

GitHub Actions (`build-content.yml`, `build-cv.yml`) provide a safety
net but are not a substitute for local validation.

## Governance

This constitution defines the non-negotiable standards for the Context Lab
website. All contributors (human and automated) MUST comply.

- **Precedence**: This constitution supersedes ad-hoc practices. When in
  doubt, follow the principles above.
- **Amendments**: Changes to this constitution require updating this file,
  incrementing the version (MAJOR for principle removals/redefinitions,
  MINOR for additions/expansions, PATCH for clarifications), and updating
  dependent artifacts if affected.
- **Compliance review**: PRs SHOULD be checked against these principles
  before merging. The pre-push check script enforces the testable subset.
- **Runtime guidance**: See `CLAUDE.md` for day-to-day development commands
  and conventions. This constitution governs *why*; CLAUDE.md governs *how*.

**Version**: 1.0.0 | **Ratified**: 2026-03-23 | **Last Amended**: 2026-03-23
