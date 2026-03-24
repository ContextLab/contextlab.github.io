# CONTEXTUAL DYNAMICS LAB WEBSITE

**Generated:** 2026-01-08
**Commit:** 4f62f4b
**Branch:** main

## OVERVIEW

Static website for Contextual Dynamics Lab (Dartmouth). Content pages auto-generated from Excel spreadsheets via Python build system. GitHub Pages hosting.

## STRUCTURE

```
contextlab.github.io/
├── *.html              # 7 pages (index, research, people, publications, software, news, contact)
├── css/style.css       # Single stylesheet, 1897 lines, CSS variables
├── js/main.js          # All interactive components (359 lines)
├── data/*.xlsx         # Content source: publications, people, software, news
├── templates/*.html    # HTML templates with <!-- MARKER --> injection points
├── scripts/            # Python build system (see scripts/AGENTS.md)
├── images/             # Assets: people/, publications/, software/, research/, news/
├── documents/          # CV files (JRM_CV.tex → .pdf, .html)
├── lab-manual/         # Git submodule (ContextLab/lab-manual)
└── tests/              # pytest suite for build system
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add publication | `data/publications.xlsx` | Auto-builds via GitHub Actions |
| Add team member | `scripts/onboard_member.py` | Processes photo, generates bio, updates CV |
| Offboard member | `scripts/offboard_member.py` | Moves to alumni, updates CV + lab-manual |
| Reconcile people | `scripts/reconcile_people.py` | Three-way sync: people.xlsx ↔ CV ↔ lab-manual |
| Add software | `data/software.xlsx` | |
| Add news | `data/news.xlsx` | Thumbnail in `images/news/` |
| Update CV | `documents/JRM_CV.tex` | Auto-compiles to PDF+HTML |
| Fix styling | `css/style.css` | See CSS variables at top |
| Fix JS behavior | `js/main.js` | 9 init functions |
| Modify page structure | `templates/*.html` | NOT root *.html (auto-generated) |
| Build system | `scripts/` | See scripts/AGENTS.md |

## CONVENTIONS

### Color Theme (CSS Variables)
```css
--primary-green: rgb(0, 112, 60);
--bg-green: rgba(0, 112, 60, 0.2);
--dark-text: rgba(0, 0, 0, 0.7);
```

### Typography
- All headings: lowercase (`text-transform: lowercase`)
- Font: Nunito Sans (300 weight body, 300-700 headings)
- Base: 14px, 1.7 line-height

### Images
- Publication thumbnails: 500x500px with hand-drawn green border
- People photos: Use `scripts/add_borders.py --face` for consistent styling
- Border templates in `images/templates/WebsiteDoodles_Posters_v1.svg`

### Template System
- Templates use `<!-- MARKER_NAME -->` for content injection
- Markers replaced by build scripts with generated HTML
- DO NOT edit root `publications.html`, `people.html`, `software.html`, `news.html` directly

## ANTI-PATTERNS

- **NEVER edit auto-generated HTML** (publications, people, software, news) - changes will be overwritten
- **NEVER use `!important`** in CSS without explicit justification
- **NEVER add inline styles** to templates - use CSS classes
- **NEVER commit without running tests** - `python -m pytest tests/ -v`

## COMMANDS

```bash
# Local development server
python3 -m http.server 8000

# Validate spreadsheet data
cd scripts && python validate_data.py

# Build all content pages
cd scripts && python build.py

# Build CV only
cd scripts && python build_cv.py

# Run full test suite
python -m pytest tests/ -v

# Pre-push validation
cd scripts && python pre_push_check.py

# Add borders to images
python scripts/add_borders.py image.png images/publications/
python scripts/add_borders.py photo.jpg images/people/ --face

# Onboard a new lab member
cd scripts && python onboard_member.py "First Last"
cd scripts && python onboard_member.py "First Last" --rank "grad student"
cd scripts && python onboard_member.py "First Last" --photo headshot --bio "Bio text..."
cd scripts && python onboard_member.py "First Last" --skip-llm
cd scripts && python onboard_member.py "First Last" --github username --teams "supereeg"
cd scripts && python onboard_member.py "First Last" --gmail user@gmail.com

# Offboard a lab member (move to alumni)
cd scripts && python offboard_member.py "member name"
cd scripts && python offboard_member.py "name" --end-year 2025
cd scripts && python offboard_member.py --list-no-photo
```

## GITHUB ACTIONS

| Workflow | Trigger | Action |
|----------|---------|--------|
| `build-content.yml` | Push to data/, templates/, scripts/ | Validate + build + commit HTML |
| `build-cv.yml` | Push to documents/JRM_CV.tex | Compile LaTeX to PDF+HTML |

## JS COMPONENTS

| Function | Purpose |
|----------|---------|
| `initDropdowns()` | Footer nav dropdown menus |
| `initStickyNav()` | Show/hide footer nav on scroll |
| `initSlideshow()` | Image carousel with autoplay |
| `initModal()` | Modal open/close (join-us form) |
| `initSmoothScroll()` | Anchor link scrolling |
| `initInfoPanel()` | Homepage "i" button toggle |
| `initContactForms()` | Formspree AJAX submission |
| `initMobileMenu()` | Hamburger menu toggle |
| `initCustomValidation()` | Green-themed validation tooltips |

## NOTES

- Forms use Formspree backend - endpoint in form `action` attribute
- Homepage brain animation: static PNG, CSS transforms on toggle
- Footer nav always visible (no scroll threshold on homepage)
- Bluesky feed integration on news page (see `news.html`)
- CV uses Dartmouth Ruzicka fonts (`data/DartmouthRuzicka-*.ttf`)
