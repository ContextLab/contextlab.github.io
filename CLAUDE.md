# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Static website for the Contextual Dynamics Lab at Dartmouth College. Hosted on GitHub Pages at [context-lab.com](https://context-lab.com). Content pages (publications, people, software, news) are **auto-generated** from Excel spreadsheets via a Python build system — never edit the root HTML for those pages directly.

## Commands

```bash
# Install dependencies
pip install -r requirements-build.txt

# Validate spreadsheet data
cd scripts && python validate_data.py

# Build all content pages (publications, people, software, news)
cd scripts && python build.py

# Build CV (requires XeLaTeX + Dartmouth Ruzicka fonts)
cd scripts && python build_cv.py

# Run full test suite
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_build_publications.py -v

# Pre-push validation (validation + build + tests)
cd scripts && python pre_push_check.py

# Local dev server
python3 -m http.server 8000

# Add hand-drawn borders to images
python scripts/add_borders.py image.png images/publications/
python scripts/add_borders.py photo.jpg images/people/ --face

# Onboard new member (from scripts/ dir)
python onboard_member.py "First Last" --rank "grad student" --photo headshot --skip-llm

# Offboard member to alumni (from scripts/ dir)
python offboard_member.py "member name" --end-year 2025

# Reconcile people across website, CV, and lab-manual
cd scripts && python reconcile_people.py --dry-run  # report only
cd scripts && python reconcile_people.py             # apply auto-fixes

# Initialize lab-manual submodule (required for reconciliation)
git submodule update --init
```

## Architecture

### Content Pipeline

```
data/*.xlsx  →  scripts/build_*.py  →  root *.html (auto-generated)
                    ↑
            templates/*.html (markers like <!-- PUBLICATIONS_PAPERS -->)
```

Each `build_*.py` follows the same pattern:
1. Load spreadsheet with `utils.load_spreadsheet_all_sheets()`
2. Generate HTML fragments
3. Inject into template via `utils.inject_content(template, output, {"MARKER": html})`

### Key Directories

| Directory | Purpose |
|-|-|
| `data/` | Source spreadsheets (publications.xlsx, people.xlsx, software.xlsx, news.xlsx) + Dartmouth fonts |
| `templates/` | HTML templates with `<!-- MARKER -->` injection points |
| `scripts/` | Python build system, validation, onboarding/offboarding tools |
| `tests/` | pytest suite — conftest.py adds `scripts/` to sys.path |
| `documents/` | CV source (JRM_CV.tex) and generated outputs (PDF, HTML) |
| `css/style.css` | Single stylesheet with CSS variables at top |
| `js/main.js` | All JS components (9 init functions) |
| `lab-manual/` | Git submodule — [ContextLab/lab-manual](https://github.com/ContextLab/lab-manual) (init with `git submodule update --init`) |

### CV Pipeline

`documents/JRM_CV.tex` → `scripts/build_cv.py` + `scripts/extract_cv.py` (custom LaTeX→HTML parser) → `documents/JRM_CV.pdf` + `documents/JRM_CV.html`

### GitHub Actions

- **build-content.yml**: Triggers on changes to `data/`, `templates/`, `scripts/`. Validates, builds, runs tests, auto-commits regenerated HTML.
- **build-cv.yml**: Triggers on changes to `documents/JRM_CV.tex`, CV scripts, or `css/cv.css`. Compiles LaTeX, runs tests, auto-commits PDF+HTML.

## Critical Rules

- **Never edit auto-generated root HTML** (`publications.html`, `people.html`, `software.html`, `news.html`) — edit `data/*.xlsx` or `templates/*.html` instead
- **Never use `!important`** in CSS without explicit justification
- **Never add inline styles** to templates — use CSS classes
- **Always run tests before pushing**: `python -m pytest tests/ -v`
- **All headings are lowercase** via `text-transform: lowercase` in CSS

## Design System

- **Colors**: `--primary-green: rgb(0, 112, 60)`, `--bg-green: rgba(0, 112, 60, 0.2)`, `--dark-text: rgba(0, 0, 0, 0.7)`
- **Font**: Nunito Sans, 300 weight body, 14px base, 1.7 line-height
- **Images**: 500x500px with hand-drawn green borders (use `scripts/add_borders.py`), face-detect cropping for people photos (`--face`)
- **Forms**: Formspree backend — endpoint in form `action` attribute
