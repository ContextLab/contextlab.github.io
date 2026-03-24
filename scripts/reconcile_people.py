#!/usr/bin/env python3
"""Reconcile member/alumni data across people.xlsx, JRM_CV.tex, and lab_manual.tex.

people.xlsx is the source of truth. Discrepancies are categorized as:
- Auto-resolved: people in people.xlsx missing from other sources (auto-added)
- Flagged for review: people in other sources missing from people.xlsx
- Conflicts: data mismatches requiring manual resolution
"""
import argparse
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple

from utils import load_spreadsheet_all_sheets
from parse_cv_trainees import parse_cv_trainees, get_active_trainees, get_alumni_trainees
from parse_lab_manual import parse_members_chapter
from sync_cv_people import normalize_name, NICKNAME_MAP, expand_nicknames, names_match

PROJECT_ROOT = Path(__file__).parent.parent
PEOPLE_XLSX = PROJECT_ROOT / 'data' / 'people.xlsx'
CV_TEX = PROJECT_ROOT / 'documents' / 'JRM_CV.tex'
LAB_MANUAL_TEX = PROJECT_ROOT / 'lab-manual' / 'lab_manual.tex'

FUZZY_THRESHOLD = 0.85


def load_people_xlsx() -> Dict[str, List[Dict]]:
    """Load all sheets from people.xlsx and return normalized data."""
    sheets = load_spreadsheet_all_sheets(PEOPLE_XLSX)
    return sheets


# Sheets in people.xlsx that contain actual lab members/alumni
PERSON_SHEETS = {
    'members', 'alumni_postdocs', 'alumni_grads',
    'alumni_managers', 'alumni_undergrads',
}


def get_all_people_names(sheets: Dict[str, List[Dict]]) -> Dict[str, Dict]:
    """Extract all people from people.xlsx with their sheet and data.

    Excludes non-person sheets like 'collaborators' and 'director'.

    Returns:
        Dict mapping normalized name -> {sheet, name_original, data}
    """
    people = {}
    for sheet_name, rows in sheets.items():
        if sheet_name not in PERSON_SHEETS:
            continue
        for row in rows:
            name = row.get('name', '').strip()
            if not name:
                continue
            norm = normalize_name(name)
            people[norm] = {
                'sheet': sheet_name,
                'name_original': name,
                'data': row,
            }
    return people


def get_cv_names() -> Dict[str, Dict]:
    """Extract all trainees from JRM_CV.tex.

    Returns:
        Dict mapping normalized name -> {category, is_active, trainee}
    """
    if not CV_TEX.exists():
        return {}
    trainees_by_cat = parse_cv_trainees(CV_TEX)
    result = {}
    for cat, trainees in trainees_by_cat.items():
        for t in trainees:
            norm = normalize_name(t.name)
            result[norm] = {
                'category': t.category,
                'is_active': t.is_active,
                'name_original': t.name,
                'trainee': t,
            }
    return result


def get_lab_manual_names() -> Dict[str, Dict]:
    """Extract all members from lab_manual.tex.

    Returns:
        Dict mapping normalized name -> {role_category, is_active, record}
    """
    if not LAB_MANUAL_TEX.exists():
        return {}
    records = parse_members_chapter(LAB_MANUAL_TEX)
    result = {}
    for r in records:
        norm = normalize_name(r['name'])
        # Same person may appear multiple times (multi-role); keep the most recent
        if norm in result:
            existing = result[norm]
            if r['is_active'] and not existing['is_active']:
                result[norm] = {
                    'role_category': r['role_category'],
                    'is_active': r['is_active'],
                    'name_original': r['name'],
                    'record': r,
                }
        else:
            result[norm] = {
                'role_category': r['role_category'],
                'is_active': r['is_active'],
                'name_original': r['name'],
                'record': r,
            }
    return result


def fuzzy_find(name: str, name_set: Set[str]) -> Optional[Tuple[str, float]]:
    """Find the best fuzzy match for a name in a set.

    Args:
        name: Normalized name to search for.
        name_set: Set of normalized names to search in.

    Returns:
        Tuple of (matched_name, score) if score >= FUZZY_THRESHOLD, else None.
    """
    best_match = None
    best_score = 0.0
    for candidate in name_set:
        score = SequenceMatcher(None, name, candidate).ratio()
        if score > best_score:
            best_score = score
            best_match = candidate
    if best_score >= FUZZY_THRESHOLD and best_match:
        return (best_match, best_score)
    return None


def find_match(name: str, target_names: Set[str]) -> Optional[Tuple[str, str]]:
    """Try to find a name in a set using exact, nickname, and fuzzy matching.

    Returns:
        Tuple of (matched_name, match_type) or None.
        match_type is 'exact', 'nickname', or 'fuzzy'.
    """
    # Exact match
    if name in target_names:
        return (name, 'exact')

    # Nickname match
    if names_match(name, name) is False:
        pass  # names_match compares two names
    for target in target_names:
        if names_match(name, target):
            return (target, 'nickname')

    # Fuzzy match
    result = fuzzy_find(name, target_names)
    if result:
        return (result[0], 'fuzzy')

    return None


class Discrepancy:
    """A discrepancy found during reconciliation."""

    def __init__(self, name, disc_type, present_in, missing_from,
                 details, resolution, confidence=1.0):
        self.name = name
        self.type = disc_type  # 'missing', 'conflict', 'near_match'
        self.present_in = present_in  # list of source names
        self.missing_from = missing_from  # list of source names
        self.details = details
        self.resolution = resolution  # 'auto_add', 'flag_for_review', 'conflict'
        self.confidence = confidence


def reconcile(dry_run=False) -> List[Discrepancy]:
    """Run three-way reconciliation.

    Args:
        dry_run: If True, report only; don't modify files.

    Returns:
        List of Discrepancy objects.
    """
    xlsx_people = get_all_people_names(load_people_xlsx())
    cv_people = get_cv_names()
    lm_people = get_lab_manual_names()

    xlsx_names = set(xlsx_people.keys())
    cv_names = set(cv_people.keys())
    lm_names = set(lm_people.keys())

    # Exclude PI from comparisons (PI is not in people.xlsx)
    pi_names = {normalize_name(r['name_original']) for r in lm_people.values()
                if r['role_category'] == 'PI'}
    lm_names_no_pi = lm_names - pi_names

    discrepancies = []

    # 1. People in people.xlsx but not in CV
    for name in xlsx_names:
        if name not in cv_names:
            match = find_match(name, cv_names)
            if match:
                matched, match_type = match
                if match_type == 'fuzzy':
                    discrepancies.append(Discrepancy(
                        name=xlsx_people[name]['name_original'],
                        disc_type='near_match',
                        present_in=['people.xlsx', 'CV (as ' + cv_people[matched]['name_original'] + ')'],
                        missing_from=[],
                        details=f"Fuzzy match: '{xlsx_people[name]['name_original']}' ≈ '{cv_people[matched]['name_original']}'",
                        resolution='flag_for_review',
                        confidence=SequenceMatcher(None, name, matched).ratio(),
                    ))
            else:
                discrepancies.append(Discrepancy(
                    name=xlsx_people[name]['name_original'],
                    disc_type='missing',
                    present_in=['people.xlsx'],
                    missing_from=['CV'],
                    details=f"'{xlsx_people[name]['name_original']}' is in people.xlsx ({xlsx_people[name]['sheet']}) but not in CV",
                    resolution='auto_add',
                ))

    # 2. People in people.xlsx but not in lab-manual
    for name in xlsx_names:
        if name not in lm_names_no_pi:
            match = find_match(name, lm_names_no_pi)
            if match:
                matched, match_type = match
                if match_type == 'fuzzy':
                    discrepancies.append(Discrepancy(
                        name=xlsx_people[name]['name_original'],
                        disc_type='near_match',
                        present_in=['people.xlsx', 'lab-manual (as ' + lm_people[matched]['name_original'] + ')'],
                        missing_from=[],
                        details=f"Fuzzy match: '{xlsx_people[name]['name_original']}' ≈ '{lm_people[matched]['name_original']}'",
                        resolution='flag_for_review',
                        confidence=SequenceMatcher(None, name, matched).ratio(),
                    ))
            else:
                discrepancies.append(Discrepancy(
                    name=xlsx_people[name]['name_original'],
                    disc_type='missing',
                    present_in=['people.xlsx'],
                    missing_from=['lab-manual'],
                    details=f"'{xlsx_people[name]['name_original']}' is in people.xlsx ({xlsx_people[name]['sheet']}) but not in lab-manual",
                    resolution='auto_add',
                ))

    # 3. People in lab-manual but not in people.xlsx (FLAG)
    for name in lm_names_no_pi:
        if name not in xlsx_names:
            match = find_match(name, xlsx_names)
            if match:
                matched, match_type = match
                if match_type in ('exact', 'nickname'):
                    continue  # Already matched
                discrepancies.append(Discrepancy(
                    name=lm_people[name]['name_original'],
                    disc_type='near_match',
                    present_in=['lab-manual'],
                    missing_from=['people.xlsx'],
                    details=f"Fuzzy match: '{lm_people[name]['name_original']}' ≈ '{xlsx_people[matched]['name_original']}'",
                    resolution='flag_for_review',
                    confidence=SequenceMatcher(None, name, matched).ratio(),
                ))
            else:
                discrepancies.append(Discrepancy(
                    name=lm_people[name]['name_original'],
                    disc_type='missing',
                    present_in=['lab-manual'],
                    missing_from=['people.xlsx'],
                    details=f"'{lm_people[name]['name_original']}' is in lab-manual ({lm_people[name]['role_category']}) but not in people.xlsx",
                    resolution='flag_for_review',
                ))

    # 4. People in CV but not in people.xlsx (FLAG)
    for name in cv_names:
        if name not in xlsx_names:
            match = find_match(name, xlsx_names)
            if match:
                matched, match_type = match
                if match_type in ('exact', 'nickname'):
                    continue
                discrepancies.append(Discrepancy(
                    name=cv_people[name]['name_original'],
                    disc_type='near_match',
                    present_in=['CV'],
                    missing_from=['people.xlsx'],
                    details=f"Fuzzy match: '{cv_people[name]['name_original']}' ≈ '{xlsx_people[matched]['name_original']}'",
                    resolution='flag_for_review',
                    confidence=SequenceMatcher(None, name, matched).ratio(),
                ))
            else:
                discrepancies.append(Discrepancy(
                    name=cv_people[name]['name_original'],
                    disc_type='missing',
                    present_in=['CV'],
                    missing_from=['people.xlsx'],
                    details=f"'{cv_people[name]['name_original']}' is in CV ({cv_people[name]['category']}) but not in people.xlsx",
                    resolution='flag_for_review',
                ))

    return discrepancies


def print_report(discrepancies: List[Discrepancy]) -> None:
    """Print a categorized reconciliation report."""
    auto_resolved = [d for d in discrepancies if d.resolution == 'auto_add']
    flagged = [d for d in discrepancies if d.resolution == 'flag_for_review']
    conflicts = [d for d in discrepancies if d.resolution == 'conflict']

    print("=" * 60)
    print("RECONCILIATION REPORT")
    print("=" * 60)
    print(f"\nTotal discrepancies: {len(discrepancies)}")
    print(f"  Auto-resolved: {len(auto_resolved)}")
    print(f"  Flagged for review: {len(flagged)}")
    print(f"  Conflicts: {len(conflicts)}")

    if auto_resolved:
        print("\n" + "-" * 60)
        print("AUTO-RESOLVED (people.xlsx → other sources)")
        print("-" * 60)
        for d in auto_resolved:
            print(f"  + {d.name}")
            print(f"    Present in: {', '.join(d.present_in)}")
            print(f"    Missing from: {', '.join(d.missing_from)}")
            print(f"    Action: Auto-add to {', '.join(d.missing_from)}")

    if flagged:
        print("\n" + "-" * 60)
        print("FLAGGED FOR REVIEW")
        print("-" * 60)
        for d in flagged:
            flag = "~" if d.type == 'near_match' else "?"
            print(f"  {flag} {d.name}")
            print(f"    {d.details}")
            if d.type == 'near_match':
                print(f"    Confidence: {d.confidence:.0%}")

    if conflicts:
        print("\n" + "-" * 60)
        print("CONFLICTS REQUIRING MANUAL RESOLUTION")
        print("-" * 60)
        for d in conflicts:
            print(f"  ! {d.name}")
            print(f"    {d.details}")

    if not discrepancies:
        print("\nAll sources are in sync!")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Reconcile member/alumni data across people.xlsx, CV, and lab-manual.'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Report discrepancies without making changes.'
    )
    args = parser.parse_args()

    # Verify sources exist
    if not PEOPLE_XLSX.exists():
        print(f"ERROR: {PEOPLE_XLSX} not found", file=sys.stderr)
        sys.exit(1)

    if not LAB_MANUAL_TEX.exists():
        print(f"WARNING: {LAB_MANUAL_TEX} not found (submodule not initialized?)", file=sys.stderr)
        print("Run: git submodule update --init", file=sys.stderr)

    discrepancies = reconcile(dry_run=args.dry_run)
    print_report(discrepancies)

    if args.dry_run:
        print("\n(Dry run — no changes made)")
    else:
        # TODO: Apply auto-fixes in Phase 3 implementation
        print("\n(Report only — auto-fix not yet implemented)")

    # Exit with non-zero if there are flagged items
    flagged = [d for d in discrepancies if d.resolution == 'flag_for_review']
    if flagged:
        sys.exit(1)


if __name__ == '__main__':
    main()
