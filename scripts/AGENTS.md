# BUILD SYSTEM

Python build scripts that generate HTML pages from Excel spreadsheets.

## STRUCTURE

```
scripts/
├── build.py              # Master orchestrator - runs all builders
├── build_publications.py # publications.xlsx → publications.html
├── build_people.py       # people.xlsx → people.html  
├── build_software.py     # software.xlsx → software.html
├── build_news.py         # news.xlsx → news.html
├── build_cv.py           # JRM_CV.tex → .pdf + .html
├── extract_cv.py         # Custom LaTeX→HTML parser
├── validate_data.py      # Pre-build validation
├── pre_push_check.py     # Full validation suite
├── utils.py              # Shared: load_spreadsheet, inject_content
├── citation_utils.py     # Publication citation formatting
├── add_borders.py        # Image processing (hand-drawn borders)
├── onboard_member.py     # Add new lab members (with LLM bio generation)
└── offboard_member.py    # Move members from active to alumni
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add new content type | Create `build_*.py`, update `build.py` | Follow existing pattern |
| Fix spreadsheet loading | `utils.py` | `load_spreadsheet()`, `load_spreadsheet_all_sheets()` |
| Fix template injection | `utils.py` | `inject_content()` uses `<!-- MARKER -->` pattern |
| Fix validation | `validate_data.py` | Required fields, file existence checks |
| Fix CV parsing | `extract_cv.py` | LaTeX commands → HTML |
| Fix image borders | `add_borders.py` | Uses MediaPipe for face detection |
| Onboard lab member | `onboard_member.py` | Processes photo, generates bio, updates spreadsheet + CV |
| Offboard lab member | `offboard_member.py` | Moves member to alumni, updates CV |

## CONVENTIONS

### Build Pattern
Every `build_*.py` follows:
1. Load spreadsheet(s) with `utils.load_spreadsheet_all_sheets()`
2. Generate HTML for each section
3. Inject via `utils.inject_content(template, output, {"MARKER": html})`

### Template Markers
```html
<!-- PUBLICATIONS_PAPERS -->   <!-- in templates/publications.html -->
<!-- PEOPLE_MEMBERS -->        <!-- in templates/people.html -->
<!-- SOFTWARE_PYTHON -->       <!-- in templates/software.html -->
<!-- NEWS_ITEMS -->            <!-- in templates/news.html -->
```

### Spreadsheet Columns
- `publications.xlsx`: title, title_url, citation, image (sheets: papers, preprints, chapters, other)
- `people.xlsx`: name, name_url, role, bio, image (sheets: members, alumni_*)
- `software.xlsx`: name, description, links_html (sheets: python, javascript, matlab)
- `news.xlsx`: title, description, image, link, date

## ANTI-PATTERNS

- **NEVER edit root HTML files** - edit templates/ or data/ instead
- **NEVER skip validation** - always run `validate_data.py` before build
- **NEVER hardcode paths** - use `Path(__file__).parent.parent` for project root

## COMMANDS

```bash
# From scripts/ directory:
python validate_data.py   # Check data integrity
python build.py           # Build all pages
python build_cv.py        # Build CV only
python pre_push_check.py  # Full pre-commit validation

# From project root:
python -m pytest tests/ -v

# Onboard a new lab member:
python onboard_member.py "First Last"
python onboard_member.py "First Last" --rank "grad student"
python onboard_member.py "First Last" --photo headshot --bio "Bio text..."
python onboard_member.py "First Last" --website "https://example.com"
python onboard_member.py "First Last" --skip-llm  # Skip LLM processing

# Offboard a lab member (move to alumni):
python offboard_member.py "member name"
python offboard_member.py "name" --end-year 2025
python offboard_member.py --list-no-photo  # List undergrads without photos
```

## DEPENDENCIES

See `requirements-build.txt`:
- openpyxl (Excel reading)
- mediapipe (face detection for add_borders.py)
- Pillow/numpy (image processing)
- transformers/torch (for onboard_member.py LLM bio generation)
