# Research: People & Lab-Manual Synchronization

**Date**: 2026-03-23
**Branch**: `001-people-labmanual-sync`

## R1: Lab-Manual LaTeX Structure

**Decision**: Parse `lab_manual.tex` chapter "Lab members and alumni"
using a custom parser that understands the Tufte-style LaTeX structure.

**Rationale**: The lab-manual uses a different LaTeX structure than the
CV — `\newthought{}` headings, `\begin{list}{\quad}{}` items inside
`multicols`. Cannot reuse the CV parser directly, but the data model
is simpler (name + years only).

**Structure**:
```
\chapter{Lab members and alumni}
\begin{fullwidth}
  \subsection{Current lab members}
    \newthought{Role}
    \begin{multicols}{2}\raggedcolumns
    \begin{list}{\quad}{}
    \item Name (start_year -- )
    \end{list}
    \end{multicols}
  \subsection{Lab alumni}
    \newthought{Role}
    ... same pattern, closed year ranges ...
\end{fullwidth}
```

**Role categories**: PI, Postdoctoral Researchers, Graduate Students,
Research Assistants, Undergraduate RAs, Lab Managers.

**Data per person**: Name and year range only. No bio, photo, links.

**Key detail**: Same person can appear in multiple role sections (e.g.,
as undergrad RA alumni AND current grad student).

## R2: Existing CV Parser Infrastructure

**Decision**: Extend existing `parse_cv_trainees.py` and
`sync_cv_people.py` rather than building new infrastructure.

**Rationale**: These scripts already handle:
- Parsing CV trainees with `etaremune` lists and `\textit{}` headings
- Bidirectional comparison with `people.xlsx`
- Nickname/name variation handling
- Routing members to correct spreadsheet sheets

**Alternatives considered**:
- Building a new unified parser: Rejected — the two LaTeX formats are
  different enough that a single parser adds complexity without benefit.
- Using a LaTeX parsing library (e.g., pylatexenc): Rejected — the
  structure is simple enough for regex-based parsing, consistent with
  the existing approach.

## R3: Lab-Manual Update Mechanism

**Decision**: Use Git submodule + local file writes + commit/push.

**Rationale**: The lab-manual is a standard Git repo. Since updates
should push directly to main (per clarification), the simplest approach
is: modify `lab_manual.tex` in the submodule, commit, and push. No
GitHub API needed.

**Alternatives considered**:
- GitHub API (like the Slack bot uses): Rejected — adds complexity and
  a dependency on PyGithub when local Git operations suffice.
- PR-based workflow: Rejected per user clarification — direct push
  preferred.

## R4: Fuzzy Name Matching

**Decision**: Use Python's `difflib.SequenceMatcher` with an 85%
similarity threshold, supplemented by a nickname mapping table.

**Rationale**: `sync_cv_people.py` already has a nickname mapping
(Will↔William, Rob↔Robert, etc.). Combining this with fuzzy matching
covers both common nicknames and typos.

**Alternatives considered**:
- `fuzzywuzzy`/`thefuzz` library: Rejected — adds a dependency for
  marginal improvement over stdlib `difflib` + nickname table.
- Exact match only: Rejected — too many false negatives from name
  variations.

## R5: Reconciliation Tool Design

**Decision**: Create `scripts/reconcile_people.py` that compares all
three sources and produces a categorized report.

**Rationale**: Needs to be a standalone script (like validate_data.py)
that can be run independently or as part of pre-push checks. Output
should be both human-readable (terminal) and machine-actionable (can
auto-fix what's safe to auto-fix).

**Flow**:
1. Parse people.xlsx (source of truth)
2. Parse JRM_CV.tex trainees (reuse parse_cv_trainees.py)
3. Parse lab_manual.tex members chapter (new parser)
4. Compare all three using fuzzy matching
5. Auto-resolve: people.xlsx entries missing from CV or lab-manual
6. Flag for review: lab-manual entries missing from people.xlsx
7. Report conflicts and near-matches
