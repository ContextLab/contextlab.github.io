# Implementation Plan: People & Lab-Manual Synchronization

**Branch**: `001-people-labmanual-sync` | **Date**: 2026-03-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/001-people-labmanual-sync/spec.md`

## Summary

Synchronize member and alumni data across three sources: `data/people.xlsx`
(source of truth), `documents/JRM_CV.tex`, and the lab-manual's
`lab_manual.tex`. Build a reconciliation tool to audit and fix drift, extend
onboard/offboard scripts to update all three destinations, and add the
lab-manual as a Git submodule.

## Technical Context

**Language/Version**: Python 3.9+ (matches existing build system)
**Primary Dependencies**: openpyxl (spreadsheet), difflib (fuzzy matching), subprocess/git (submodule operations)
**Storage**: Excel spreadsheet (people.xlsx), LaTeX files (JRM_CV.tex, lab_manual.tex)
**Testing**: pytest (existing suite in tests/)
**Target Platform**: macOS/Linux (developer machines + GitHub Actions)
**Project Type**: CLI build tools (extending existing scripts)
**Performance Goals**: Reconciliation completes in <30 seconds for 200 people
**Constraints**: No new pip dependencies; reuse stdlib and existing deps
**Scale/Scope**: ~163 people entries across 3 sources

## Constitution Check

*GATE: Must pass before implementation. Re-checked after design.*

| Principle | Status | Notes |
|-|-|-|
| I. User Experience | PASS | Reconciliation report is clear and actionable; scripts give feedback |
| II. Attention to Detail | PASS | Full test coverage planned; existing tests must continue to pass |
| III. Living Documentation | PASS | CLAUDE.md, AGENTS.md, README.md updates included in plan |
| IV. Repository Cleanliness | PASS | Submodule is clean; no temp files; no secrets |
| V. Cross-Repository Consistency | PASS | This feature IS the consistency enforcement mechanism |

## Project Structure

### Documentation (this feature)

```text
specs/001-people-labmanual-sync/
├── spec.md
├── plan.md              # This file
├── research.md
├── data-model.md
├── quickstart.md
└── checklists/
    └── requirements.md
```

### Source Code (changes to existing repo)

```text
# New files
scripts/
├── reconcile_people.py       # Reconciliation tool (new)
├── parse_lab_manual.py       # Lab-manual LaTeX parser (new)
tests/
├── test_reconcile_people.py  # Reconciliation tests (new)
├── test_parse_lab_manual.py  # Parser tests (new)

# Modified files
scripts/
├── onboard_member.py         # Add lab-manual update step
├── offboard_member.py        # Add lab-manual update step
.gitmodules                   # New file for submodule config
lab-manual/                   # Submodule (ContextLab/lab-manual)

# Documentation updates
CLAUDE.md
AGENTS.md
README.md
scripts/AGENTS.md
```

**Structure Decision**: Extending the existing `scripts/` directory with
two new scripts (parser + reconciliation tool) and modifying two existing
scripts. Follows the established pattern of one script per concern.

## Implementation Phases

### Phase 1: Submodule Setup (US3 — infrastructure first)

Add the lab-manual as a Git submodule. This unblocks all other work.

1. Run `git submodule add https://github.com/ContextLab/lab-manual.git lab-manual`
2. Verify `.gitmodules` is created correctly
3. Ensure `lab-manual/lab_manual.tex` is accessible
4. Update `.github/workflows/build-content.yml` to init submodule if needed

### Phase 2: Lab-Manual Parser (supports US1)

Create `scripts/parse_lab_manual.py` to extract member/alumni data from
`lab_manual.tex`.

**Parser approach**:
- Find `\chapter{Lab members and alumni}` as entry point
- Split into `\subsection{Current lab members}` and `\subsection{Lab alumni}`
- Within each subsection, find `\newthought{Role}` headings
- Extract `\item Name (YYYY -- YYYY)` entries from `\begin{list}` blocks
- Return list of `SourceRecord` objects (name, role, years, active/alumni)

**Key considerations**:
- Handle same person appearing in multiple role sections
- Handle commented-out sections (e.g., Research Assistants)
- Handle single-year entries (e.g., `Jessica Tin (2016)`)
- Handle PI special case (no list wrapper)

**Tests**: Parse known structure, edge cases (empty sections, single-year,
multi-role person, commented sections).

### Phase 3: Reconciliation Tool (US1)

Create `scripts/reconcile_people.py` that compares all three sources.

**Flow**:
1. Load people.xlsx via `utils.load_spreadsheet_all_sheets()`
2. Parse JRM_CV.tex via `parse_cv_trainees.py`
3. Parse lab_manual.tex via `parse_lab_manual.py`
4. Normalize names (lowercase, strip whitespace)
5. Match across sources using:
   a. Exact match (case-insensitive)
   b. Nickname table (from sync_cv_people.py)
   c. Fuzzy match (difflib >= 0.85 threshold)
6. Categorize discrepancies:
   - In people.xlsx but not CV → auto-add to CV
   - In people.xlsx but not lab-manual → auto-add to lab-manual
   - In lab-manual but not people.xlsx → add to people.xlsx + FLAG
   - In CV but not people.xlsx → add to people.xlsx + FLAG
   - Near-matches → FLAG for manual review
7. Generate report (stdout) with clear sections:
   - Auto-resolved items
   - Items flagged for review
   - Conflicts requiring manual resolution
8. Apply auto-fixes (unless `--dry-run`)

**CLI interface**:
```
python reconcile_people.py           # Reconcile and apply auto-fixes
python reconcile_people.py --dry-run # Report only, no changes
```

**Tests**: Mock sources with known discrepancies, verify correct
categorization and resolution.

### Phase 4: Update Onboard/Offboard Scripts (US2)

Extend both scripts to also update `lab_manual.tex`.

**onboard_member.py changes**:
- After updating people.xlsx and JRM_CV.tex, also:
  1. Find the correct `\newthought{Role}` section in lab_manual.tex
     under `\subsection{Current lab members}`
  2. Add `\item Name (YYYY -- )` entry
  3. Commit and push the lab-manual submodule
- Wrap in try/except: warn on failure, don't block

**offboard_member.py changes**:
- After updating people.xlsx and JRM_CV.tex, also:
  1. Find the member in `\subsection{Current lab members}`
  2. Remove from current section
  3. Add to `\subsection{Lab alumni}` under the correct role
  4. Close the year range
  5. Commit and push the lab-manual submodule
- Wrap in try/except: warn on failure, don't block

**Lab-manual Git operations** (shared helper):
```
cd lab-manual/
git add lab_manual.tex
git commit -m "Update: onboard/offboard <name>"
git push origin master
cd ..
```

**Tests**: Verify lab-manual updates happen; verify graceful failure
when submodule is not initialized.

### Phase 5: Documentation & Polish

- Update CLAUDE.md: Add reconcile command, submodule setup instructions
- Update AGENTS.md: Add reconcile_people.py and parse_lab_manual.py
- Update scripts/AGENTS.md: Add new scripts to structure and commands
- Update README.md: Add submodule instructions, reconciliation docs
- Run full test suite
- Run reconciliation tool against real data for initial audit

## Dependencies & Execution Order

```
Phase 1 (Submodule) ──→ Phase 2 (Parser) ──→ Phase 3 (Reconciliation)
                    └──→ Phase 4 (Scripts)  ──→ Phase 5 (Docs)
```

- Phase 1 MUST be first (everything else depends on submodule access)
- Phases 2 and 4 can be partially parallelized (parser needed for
  reconciliation but not for the write-side of onboard/offboard)
- Phase 3 depends on Phase 2 (needs the parser)
- Phase 5 is last (documents everything)

## Complexity Tracking

No constitution violations. All changes follow existing patterns:
- New scripts follow the `scripts/*.py` convention
- New tests follow the `tests/test_*.py` convention
- Parser follows the same regex approach as `parse_cv_trainees.py`
- No new dependencies beyond stdlib
