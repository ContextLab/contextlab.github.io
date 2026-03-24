# Tasks: People & Lab-Manual Synchronization

**Input**: Design documents from `specs/001-people-labmanual-sync/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, quickstart.md

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Add lab-manual submodule and establish infrastructure

- [x] T001 Add lab-manual as Git submodule at `lab-manual/` via `git submodule add https://github.com/ContextLab/lab-manual.git lab-manual`
- [x] T002 Verify `lab-manual/lab_manual.tex` is accessible and contains `\chapter{Lab members and alumni}`
- [x] T003 [P] Update `.github/workflows/build-content.yml` to init submodule before build steps (add `submodules: true` to checkout step)

**Checkpoint**: Submodule accessible locally and in CI

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Lab-manual parser that US1, US2, and US3 all depend on

**⚠️ CRITICAL**: No user story work can begin until the parser is complete

- [x] T004 Create `scripts/parse_lab_manual.py` with `parse_members_chapter()` function that extracts all member/alumni entries from `lab_manual.tex` chapter "Lab members and alumni"
- [x] T005 Implement `\newthought{Role}` heading detection to identify role categories (PI, Postdoctoral Researchers, Graduate Students, Undergraduate RAs, Lab Managers, Research Assistants)
- [x] T006 Implement `\item Name (YYYY -- YYYY)` entry parsing within `\begin{list}{\quad}{}` blocks, handling: open year ranges (active), closed ranges (alumni), single-year entries, and commented-out sections
- [x] T007 Implement section splitting between `\subsection{Current lab members}` and `\subsection{Lab alumni}` to determine active vs. alumni status
- [x] T008 Handle PI special case (no list wrapper, format: `\enskip Jeremy R. Manning (2015 -- )`)
- [x] T009 Return list of `SourceRecord` dicts with keys: name, role_category, start_year, end_year, is_active, raw_line
- [x] T009a Create shared helper `commit_and_push_lab_manual(submodule_path, message)` in `scripts/parse_lab_manual.py` that runs `git add`, `git commit`, `git push origin master` in the submodule directory (used by T019 and T024/T025)
- [x] T010 [P] Create `tests/test_parse_lab_manual.py` with tests for: basic parsing, empty sections, single-year entries, multi-role person, commented sections, PI special case, commit_and_push graceful failure when submodule not initialized

**Checkpoint**: Parser extracts all members/alumni from lab_manual.tex correctly

---

## Phase 3: User Story 1 — Initial Audit and Reconciliation (Priority: P1) 🎯 MVP

**Goal**: Reconcile member/alumni data across people.xlsx (source of truth), JRM_CV.tex, and lab_manual.tex

**Independent Test**: Run `python reconcile_people.py --dry-run` and verify it produces a correct discrepancy report

### Implementation for User Story 1

- [x] T011 [US1] Create `scripts/reconcile_people.py` with CLI interface supporting `--dry-run` flag
- [x] T012 [US1] Implement source loading: load people.xlsx via `utils.load_spreadsheet_all_sheets()`, parse JRM_CV.tex via `parse_cv_trainees.parse_trainees()`, parse lab_manual.tex via `parse_lab_manual.parse_members_chapter()`
- [x] T013 [US1] Implement name normalization: lowercase, strip whitespace, integrate nickname table from `scripts/sync_cv_people.py`
- [x] T014 [US1] Implement three-way matching using: (a) exact match (case-insensitive), (b) nickname table lookup, (c) fuzzy match via `difflib.SequenceMatcher` with 0.85 threshold
- [x] T015 [US1] Implement discrepancy categorization: (a) in people.xlsx but not CV → auto-add to CV, (b) in people.xlsx but not lab-manual → auto-add to lab-manual, (c) in lab-manual but not people.xlsx → add + FLAG, (d) in CV but not people.xlsx → add + FLAG, (e) near-matches → FLAG
- [x] T016 [US1] Implement auto-fix application (when not `--dry-run`): add missing entries to people.xlsx, add missing entries to JRM_CV.tex (import `add_to_cv()` from `scripts/onboard_member.py` or extract to shared module), add missing entries to lab_manual.tex (reuse writer from T017)
- [x] T017 [US1] Implement lab_manual.tex writer: add `\item Name (YYYY -- )` to correct `\newthought{Role}` section under correct subsection (Current/Alumni)
- [x] T018 [US1] Implement report output to stdout with sections: "Auto-resolved", "Flagged for review", "Conflicts requiring manual resolution"
- [ ] T019 [US1] After auto-fixes, rebuild people.html via `build_people` and commit/push lab-manual submodule changes (reuse `commit_and_push_lab_manual()` from T009a)
- [x] T020 [P] [US1] Create `tests/test_reconcile_people.py` with tests for: exact match, nickname match, fuzzy match (including 0.85 threshold boundary — verify 0.84 is rejected and 0.86 is accepted), fuzzy match against corpus of 20+ name variation pairs (nicknames, abbreviations, typos, hyphenated names), auto-add from people.xlsx, flag from lab-manual, dry-run mode, report formatting (verify output contains distinct "Auto-resolved", "Flagged for review", and "Conflicts" sections)

**Checkpoint**: Reconciliation tool correctly identifies and resolves discrepancies across all three sources

---

## Phase 4: User Story 2 — Website Onboarding/Offboarding Updates Lab-Manual (Priority: P2)

**Goal**: Extend onboard/offboard scripts to also update lab_manual.tex, commit, and push

**Independent Test**: Run `onboard_member.py` for a test member and verify lab_manual.tex is updated, committed, and pushed

### Implementation for User Story 2

- [x] T021 [US2] Refactor T017's lab_manual.tex writer into shared helper `add_member_to_lab_manual(tex_path, name, role, start_year)` in `scripts/parse_lab_manual.py` (depends on T017). Inserts `\item Name (YYYY -- )` into correct `\newthought{Role}` section under `\subsection{Current lab members}`
- [x] T022 [US2] Create shared helper function in `scripts/parse_lab_manual.py`: `move_member_to_alumni(tex_path, name, end_year)` that moves entry from Current to Alumni section and closes the year range
- [x] T023 [US2] Update `scripts/onboard_member.py`: after existing people.xlsx + JRM_CV.tex updates, call `add_member_to_lab_manual()` and `commit_and_push_lab_manual()` (from T009a), wrapped in try/except with warning on failure
- [x] T024 [US2] Update `scripts/offboard_member.py`: after existing people.xlsx + JRM_CV.tex updates, call `move_member_to_alumni()` and `commit_and_push_lab_manual()` (from T009a), wrapped in try/except with warning on failure
- [x] T025 [P] [US2] Add tests to `tests/test_parse_lab_manual.py` for: add_member_to_lab_manual (correct section, correct format), move_member_to_alumni (removal + insertion)

**Checkpoint**: Onboard/offboard scripts update all three destinations; lab-manual failures warn but don't block

---

## Phase 5: User Story 3 — Lab-Manual as Submodule (Priority: P3)

**Goal**: Ensure submodule is properly documented and integrated into workflows

**Independent Test**: Fresh clone with `--recurse-submodules` gives working lab-manual access

### Implementation for User Story 3

- [ ] T026 [US3] Update `.github/workflows/build-cv.yml` to init submodule before build steps (if reconciliation or CV sync references lab-manual)
- [ ] T027 [US3] Add submodule initialization check to `scripts/pre_push_check.py`: warn if submodule is not initialized when running checks that depend on it
- [ ] T028 [US3] Test that GitHub Actions workflows succeed with the submodule (verify CI can access lab-manual/lab_manual.tex)

**Checkpoint**: Submodule works in local dev AND CI environments

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and final validation

- [ ] T029 [P] Update `CLAUDE.md`: add reconcile command, submodule setup instructions, note lab-manual submodule under architecture
- [ ] T030 [P] Update `AGENTS.md`: add `reconcile_people.py` and `parse_lab_manual.py` to structure and WHERE TO LOOK table
- [ ] T031 [P] Update `scripts/AGENTS.md`: add new scripts to structure, commands, and conventions sections
- [ ] T032 [P] Update `README.md`: add submodule setup instructions, reconciliation documentation, updated onboard/offboard examples
- [ ] T033 Run `python reconcile_people.py --dry-run` against real production data and review the discrepancy report
- [ ] T034 Run `python reconcile_people.py` to apply auto-fixes to real data (after T033 review)
- [ ] T035 Run full test suite: `python -m pytest tests/ -v` — all tests MUST pass
- [ ] T036 Run `cd scripts && python pre_push_check.py` for full pre-push validation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 (needs submodule access) — BLOCKS all user stories
- **US1 Reconciliation (Phase 3)**: Depends on Phase 2 (needs parser)
- **US2 Script Updates (Phase 4)**: Depends on Phase 2 (needs parser + writer helpers)
- **US3 Submodule Integration (Phase 5)**: Depends on Phase 1 only — can run in parallel with Phases 3-4
- **Polish (Phase 6)**: Depends on Phases 3, 4, 5

### User Story Dependencies

- **US1 (P1)**: Depends on parser (Phase 2). No dependencies on other stories.
- **US2 (P2)**: Depends on parser + writer helpers (Phase 2). Reuses T017's writer (refactored in T021) and T009a's git helper. Can start after Phase 2 but benefits from US1 being done first.
- **US3 (P3)**: Depends only on Phase 1 (submodule exists). Can run in parallel with US1/US2.

### Within Each User Story

- Source loading before matching
- Matching before categorization
- Categorization before auto-fix application
- Core implementation before tests
- Story complete before moving to next priority

### Parallel Opportunities

- T003 can run in parallel with T001/T002 (different files)
- T010 can run in parallel with T004-T009 (test file vs. implementation)
- T020 can run in parallel with T011-T019 (test file vs. implementation)
- T026 can run in parallel with T021-T025 (test file vs. implementation)
- T027, T028, T029 (US3) can run in parallel with US1/US2 phases
- T030, T031, T032, T033 (docs) can all run in parallel

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Submodule Setup
2. Complete Phase 2: Parser (CRITICAL — blocks everything)
3. Complete Phase 3: Reconciliation Tool (US1)
4. **STOP and VALIDATE**: Run reconciliation against real data
5. Review flagged items with lab director

### Incremental Delivery

1. Setup + Parser → Foundation ready
2. Add Reconciliation Tool → Run initial audit (MVP!)
3. Add Script Updates → Ongoing sync automated
4. Add CI Integration → Safety net in place
5. Documentation → Everything documented

### Parallel Opportunities Summary

With multiple developers or agents:
- Agent A: US1 (Reconciliation) after parser done
- Agent B: US2 (Script updates) after parser done
- Agent C: US3 (CI integration) after submodule setup

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- Each user story is independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate independently
- T034/T035 are the critical real-data validation — review carefully before applying
