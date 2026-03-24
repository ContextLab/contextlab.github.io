# Data Model: People & Lab-Manual Synchronization

**Date**: 2026-03-23
**Branch**: `001-people-labmanual-sync`

## Entities

### Person (unified representation)

A person as represented across all three sources. Used internally by
the reconciliation tool to compare records.

| Field | Type | Source(s) | Notes |
|-|-|-|-|
| name | string | all three | Canonical full name |
| role | string | people.xlsx, CV | e.g., "grad student", "postdoc", "undergrad" |
| start_year | int | all three | Year joined the lab |
| end_year | int or None | all three | None = currently active |
| is_active | bool | derived | True if end_year is None |
| alumni_category | string | derived | "alumni_postdocs", "alumni_grads", etc. |
| bio | string | people.xlsx only | Not in CV or lab-manual |
| image | string | people.xlsx only | Photo filename |
| current_position | string | CV, people.xlsx | Post-lab position (alumni only) |

### SourceRecord

A person record as parsed from a single source.

| Field | Type | Notes |
|-|-|-|
| name | string | As written in that source |
| source | enum | "people_xlsx", "cv_tex", "lab_manual_tex" |
| role_category | string | Role heading under which they appear |
| start_year | int | Parsed from year range |
| end_year | int or None | Parsed from year range |
| is_active | bool | Derived from section (current vs alumni) |
| raw_line | string | Original text for debugging |

### Discrepancy

Result of comparing records across sources.

| Field | Type | Notes |
|-|-|-|
| person_name | string | Best-guess canonical name |
| type | enum | "missing", "conflict", "near_match" |
| present_in | list[str] | Which sources have this person |
| missing_from | list[str] | Which sources lack this person |
| details | string | Human-readable explanation |
| resolution | enum | "auto_add", "flag_for_review", "conflict" |
| confidence | float | Fuzzy match score (1.0 = exact) |

## Source-Specific Parsing

### people.xlsx

- **Sheets**: members, alumni_postdocs, alumni_grads, alumni_managers, alumni_undergrads
- **Key columns**: name, name_url, role, bio, image, years
- **Active vs alumni**: Determined by which sheet they're on
- **Parser**: Existing `utils.load_spreadsheet_all_sheets()`

### JRM_CV.tex

- **Sections**: Postdoctoral Advisees, Graduate Advisees, Undergraduate Advisees
- **Format**: `\item Name (metadata; YYYY -- YYYY; current position)`
- **Active vs alumni**: end_year present = alumni, open range = active
- **Parser**: Existing `parse_cv_trainees.py`

### lab_manual.tex

- **Sections**: Current lab members / Lab alumni, each with role subsections
- **Format**: `\item Name (YYYY -- YYYY)` inside `\begin{list}{\quad}{}`
- **Active vs alumni**: Determined by subsection (Current vs Alumni)
- **Parser**: New — needs to handle `\newthought{}` role headings
- **Note**: Same person can appear in multiple role sections

## State Transitions

```
New member joins lab:
  → Added to people.xlsx (members sheet)
  → Added to JRM_CV.tex (active, open year range)
  → Added to lab_manual.tex (Current lab members section)

Member leaves lab:
  → Moved in people.xlsx (members → alumni_* sheet)
  → Updated in JRM_CV.tex (year range closed)
  → Moved in lab_manual.tex (Current → Alumni section)
```

## Identity & Uniqueness

- **Primary key**: Person name (case-insensitive)
- **Fuzzy matching**: difflib.SequenceMatcher >= 0.85 threshold
- **Nickname table**: Reuse from sync_cv_people.py (Will↔William, etc.)
- **Duplicate handling**: Same person in multiple role sections of
  lab_manual.tex is normal (career progression), not a conflict
