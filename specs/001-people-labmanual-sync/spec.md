# Feature Specification: People & Lab-Manual Synchronization

**Feature Branch**: `001-people-labmanual-sync`
**Created**: 2026-03-23
**Status**: Draft
**Input**: Sync people page, JRM_CV, and lab-manual. people.xlsx is
source of truth for member/alumni lists.

## Clarifications

### Session 2026-03-23

- Q: How should lab-manual updates be delivered? → A: Commit and push directly to lab-manual's main branch (no PR).
- Q: Which file in the lab-manual contains member/alumni data? → A: `lab_manual.tex` under `\chapter{Lab members and alumni}\label{ch:members}` (repo: ContextLab/lab-manual, branch: master).
- Q: Should the spec adopt distinct terms for the overloaded "onboarding"? → A: Yes. Use "data collection" for gathering info (via lab-manual process or Slack bot) and "website onboarding" for the actual act of adding someone to people.xlsx/CV/accounts. The Slack bot is an alternative data collection channel, not a separate onboarding process.

## Terminology

To avoid confusion from overloaded naming:

- **Data collection**: The process of gathering information from a new
  lab member (name, photo, bio, role, etc.). Can happen via the
  lab-manual process or via the Slack bot — both are collection
  channels feeding into the same destination.
- **Website onboarding**: The act of adding a person to `people.xlsx`,
  `JRM_CV.tex`, GitHub org, and Google calendars. Performed by the lab
  director via `onboard_member.py`. This is the only process that
  creates the canonical member record.
- **Website offboarding**: Moving a person from active members to alumni
  across all destinations. Performed via `offboard_member.py`.
- **Reconciliation**: Comparing member/alumni lists across all sources
  and resolving discrepancies.

## Context: Current Onboarding Landscape

There are two phases to adding a new lab member:

1. **Data collection** (happens first): Gathering info from the new
   member. This can happen through the lab-manual process OR through
   the Slack bot (which lets new members self-initiate). Both are
   alternative channels for the same goal. The Slack bot is configured
   directly in Slack (not in any GitHub repo) and also updates
   `people.xlsx` and `JRM_CV.tex` via GitHub API PRs.
2. **Website onboarding** (happens second): The lab director runs
   `onboard_member.py` to add the person to the people page and invite
   them to accounts (GitHub org, Google calendars).

This feature focuses on ensuring the *data* stays consistent across
all sources (`people.xlsx`, `JRM_CV.tex`, `lab_manual.tex`), not on
unifying the data collection workflows.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Initial Audit and Reconciliation (Priority: P1)

The lab director needs to verify that the current member and alumni lists
are consistent across `people.xlsx` (source of truth for member/alumni
lists), `JRM_CV.tex`, and the lab-manual's `lab_manual.tex` (chapter:
"Lab members and alumni"). Any discrepancies MUST be identified and
resolved.

When sources conflict:
- `people.xlsx` wins over all other sources for member/alumni data.
- People found in `lab_manual.tex` but NOT in `people.xlsx` should be
  added to `people.xlsx` but flagged for the director's manual review.
- People found in `people.xlsx` but missing from `lab_manual.tex` or
  `JRM_CV.tex` should be auto-added to those destinations.

**Why this priority**: Without a correct baseline, all future sync is
built on incorrect data. This is foundational.

**Independent Test**: Run the reconciliation tool and verify it produces
a report listing all discrepancies. Manually confirm a sample of flagged
entries against the actual sources.

**Acceptance Scenarios**:

1. **Given** people.xlsx, JRM_CV.tex, and lab_manual.tex all exist,
   **When** the reconciliation tool runs, **Then** it produces a report
   listing every person present in one source but missing from another,
   grouped by category (members vs. alumni types).
2. **Given** lab_manual.tex has people not in people.xlsx, **When** the
   reconciliation runs, **Then** those people are added to people.xlsx
   AND flagged for manual review by the lab director.
3. **Given** people.xlsx has people not in JRM_CV.tex or lab_manual.tex,
   **When** the reconciliation runs, **Then** those people are
   auto-added to the missing destination(s).
4. **Given** a person's data conflicts between sources (e.g., different
   role or years), **When** the reconciliation runs, **Then**
   people.xlsx data wins and the other sources are updated accordingly.

---

### User Story 2 - Website Onboarding/Offboarding Updates Lab-Manual (Priority: P2)

When a lab member is onboarded or offboarded using the website scripts,
the lab-manual's `lab_manual.tex` MUST also be updated automatically.
Currently, `onboard_member.py` and `offboard_member.py` update
`people.xlsx` and `JRM_CV.tex` but do NOT touch the lab-manual.

Updates to the lab-manual MUST be committed and pushed directly to the
lab-manual's main branch (no PR required).

**Why this priority**: Once the baseline is correct (US1), ongoing
changes need to flow to all destinations to prevent future drift.

**Independent Test**: Run the onboard script for a test member and verify
that (a) people.xlsx is updated, (b) JRM_CV.tex is updated, and (c)
lab_manual.tex in the submodule is updated, committed, and pushed.

**Acceptance Scenarios**:

1. **Given** a new member is being onboarded, **When** `onboard_member.py`
   runs, **Then** lab_manual.tex is updated with the new member's info,
   committed, and pushed to the lab-manual repo.
2. **Given** a member is being offboarded, **When** `offboard_member.py`
   runs, **Then** lab_manual.tex is updated to reflect the move to
   alumni, committed, and pushed.
3. **Given** the lab-manual submodule is not initialized or the push
   fails, **When** website onboarding runs, **Then** the website and CV
   updates still succeed, and a warning is printed about the failed
   lab-manual update.

---

### User Story 3 - Lab-Manual as Submodule (Priority: P3)

The lab-manual repository MUST be available as a Git submodule of the
website repository, so scripts can read from and write to `lab_manual.tex`
locally without requiring API calls for every operation.

**Why this priority**: This is infrastructure that supports US1 and US2.
It could be implemented first chronologically, but its value is only
realized through the other stories.

**Independent Test**: Clone the website repo with `--recurse-submodules`
and verify the lab-manual appears at the expected path.

**Acceptance Scenarios**:

1. **Given** a fresh clone of the website repo, **When** submodules are
   initialized, **Then** the lab-manual repo appears at `lab-manual/`
   within the website repo.
2. **Given** the submodule is initialized, **When** scripts reference
   `lab-manual/lab_manual.tex`, **Then** they can read and write to it
   using local file paths.
3. **Given** the submodule is at a specific commit, **When** the
   lab-manual is updated upstream, **Then** the website repo can pull
   the latest by updating the submodule reference.

---

### Edge Cases

- What happens when a person's name is spelled differently across
  sources (e.g., "Rob" vs. "Robert")? The reconciliation tool MUST use
  fuzzy matching and flag near-matches for manual review.
- What happens when the Slack bot creates a PR on the website repo at
  the same time a website onboarding script runs locally? The system
  MUST handle merge conflicts gracefully by alerting the user.
- What happens when a person appears as both an active member and
  alumni in different sources? The reconciliation tool MUST flag this
  as a conflict requiring manual resolution.
- What happens when the submodule is not initialized and a script tries
  to update the lab-manual? The script MUST print a clear error message
  with instructions on how to initialize the submodule.
- What happens when the Slack bot updates people.xlsx via a PR but the
  local copy has diverged? The reconciliation tool MUST be safe to run
  after pulling the latest changes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST treat `data/people.xlsx` as the single
  source of truth for member and alumni list data. When data conflicts
  exist between sources, people.xlsx wins.
- **FR-002**: The system MUST provide a reconciliation tool that compares
  personnel across `people.xlsx`, `JRM_CV.tex`, and `lab_manual.tex`
  (specifically the "Lab members and alumni" chapter), and produces a
  human-readable discrepancy report.
- **FR-003**: People found in `lab_manual.tex` but not in people.xlsx
  MUST be added to people.xlsx AND flagged for the lab director's
  manual review.
- **FR-004**: People found in people.xlsx but missing from JRM_CV.tex or
  `lab_manual.tex` MUST be auto-added to those destinations.
- **FR-005**: `onboard_member.py` MUST update `lab_manual.tex` in the
  lab-manual submodule, commit, and push directly to the lab-manual's
  `master` branch.
- **FR-006**: `offboard_member.py` MUST update `lab_manual.tex` in the
  lab-manual submodule, commit, and push directly to the lab-manual's
  `master` branch.
- **FR-007**: Lab-manual update failures MUST NOT block website or CV
  updates; failures MUST be reported as warnings.
- **FR-008**: The lab-manual MUST be available as a Git submodule of the
  website repository at `lab-manual/`.
- **FR-009**: The reconciliation tool MUST use fuzzy name matching to
  catch spelling variations and flag near-matches for review.
- **FR-010**: All existing tests MUST continue to pass after these
  changes.
- **FR-011**: The reconciliation report MUST clearly distinguish between
  auto-resolved discrepancies and items requiring manual review.

### Key Entities

- **Person**: Name, role/rank, years active, alumni status, bio, photo,
  website URL. Exists across people.xlsx (authoritative for
  member/alumni lists), JRM_CV.tex (authoritative for career/publication
  data), and lab_manual.tex (chapter "Lab members and alumni").
- **Discrepancy**: A person present in one source but missing or
  different in another. Has a type (missing, conflicting, near-match)
  and a resolution (auto-resolved vs. flagged for review).
- **Lab-Manual Submodule**: The Git submodule at `lab-manual/` pointing
  to ContextLab/lab-manual (master branch), pinned to a specific commit.

## Assumptions

- The lab-manual's `lab_manual.tex` chapter "Lab members and alumni"
  can be parsed for names, roles, and years from its LaTeX structure.
- The Slack bot (`cdl_bot/services/website_service.py`) is a data
  collection channel — it reads and writes `people.xlsx` and
  `JRM_CV.tex` via GitHub API but does not maintain a separate member
  list.
- The lab-manual repo is accessible via the same GitHub credentials
  used for the website repo.
- The submodule path will be `lab-manual/` at the repository root.
- Fuzzy name matching with a reasonable similarity threshold (e.g., 85%)
  is sufficient to catch most spelling variations without excessive
  false positives.
- The two data collection channels (lab-manual process, Slack bot) and
  the website onboarding workflow will continue to coexist. This
  feature synchronizes their *outputs*, not the collection workflows.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After running the reconciliation tool, 100% of personnel
  in people.xlsx are also present in JRM_CV.tex and lab_manual.tex
  (zero discrepancies for spreadsheet-sourced entries).
- **SC-002**: People found in lab_manual.tex but not in people.xlsx are
  added and flagged, with zero silent additions (100% flagging rate).
- **SC-003**: Website onboarding updates all three destinations
  (people.xlsx, JRM_CV.tex, lab_manual.tex) in a single script
  invocation.
- **SC-004**: Website offboarding updates all three destinations in a
  single script invocation.
- **SC-005**: Lab-manual update failures do not prevent website or CV
  updates from completing (graceful degradation).
- **SC-006**: All discrepancies between sources are identified and
  categorized in under 30 seconds for a lab of up to 200 people.
- **SC-007**: Near-match detection catches name variations (e.g.,
  nicknames, typos) with at least 90% recall against a test corpus of
  20+ name variation pairs (nicknames, abbreviations, typos, hyphenated
  vs. non-hyphenated names).
