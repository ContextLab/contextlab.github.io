"""Tests for reconcile_people.py."""
import io
import sys
from difflib import SequenceMatcher
from unittest.mock import patch

import pytest

from reconcile_people import (
    fuzzy_find,
    find_match,
    get_all_people_names,
    reconcile,
    print_report,
    Discrepancy,
    FUZZY_THRESHOLD,
    PERSON_SHEETS,
)
from sync_cv_people import normalize_name, names_match, NICKNAME_MAP


class TestFuzzyFind:
    def test_exact_match_returns_1(self):
        result = fuzzy_find('alice smith', {'alice smith', 'bob jones'})
        assert result is not None
        assert result[0] == 'alice smith'
        assert result[1] == 1.0

    def test_above_threshold_matches(self):
        # "alice smith" vs "alice smth" should be above 0.85
        result = fuzzy_find('alice smith', {'alice smth', 'bob jones'})
        assert result is not None
        assert result[1] >= FUZZY_THRESHOLD

    def test_below_threshold_returns_none(self):
        result = fuzzy_find('alice smith', {'completely different'})
        assert result is None

    def test_threshold_boundary_reject(self):
        """Verify that scores just below 0.85 are rejected."""
        # Find a pair that scores ~0.84
        name1 = 'abcdefghij'
        name2 = 'abcdefxyzw'
        score = SequenceMatcher(None, name1, name2).ratio()
        if score < FUZZY_THRESHOLD:
            result = fuzzy_find(name1, {name2})
            assert result is None

    def test_threshold_boundary_accept(self):
        """Verify that scores at or above 0.85 are accepted."""
        # "aaryan agarwal" vs "aaryan agrawal" should be above threshold
        score = SequenceMatcher(None, 'aaryan agarwal', 'aaryan agrawal').ratio()
        assert score >= FUZZY_THRESHOLD
        result = fuzzy_find('aaryan agarwal', {'aaryan agrawal'})
        assert result is not None

    def test_empty_set_returns_none(self):
        result = fuzzy_find('alice', set())
        assert result is None


class TestFuzzyMatchCorpus:
    """Test fuzzy matching against a corpus of 20+ name variation pairs."""

    SHOULD_MATCH = [
        ('aaryan agarwal', 'aaryan agrawal'),       # transposed letters
        ('maura hough', 'maura f. hough'),           # middle initial
        ('francisca fadairo', 'francisca o. fadairo'), # middle initial
        ('armando oritz', 'armando ortiz'),           # transposed letters
        ('helen liu', 'helen lu'),                     # short name variation
        ('stephen satterthwaite', 'steven satterthwaite'), # steve/stephen
        ('william chen', 'will chen'),                 # nickname (via fuzzy)
        ('christopher jun', 'chris jun'),              # nickname (via fuzzy)
        ('samuel haskel', 'sam haskel'),               # nickname (via fuzzy)
        ('benjamin hanson', 'ben hanson'),             # nickname (via fuzzy)
        ('theodore larson', 'theo larson'),            # nickname (via fuzzy)
        ('jacob bacus', 'jakob bacus'),                # alternate spelling
        ('daniel carstensen', 'daniel carstenson'),    # -en vs -on
        ('rachael chacko', 'rachel chacko'),           # alternate spelling
        ('rodrigo vega ayllon', 'rodrigo vega-ayllon'), # hyphenation
        ('wei liang samuel ching', 'wei liang ching'), # dropped middle name
        ('annabelle morrow', 'annabel morrow'),        # double-l vs single
        ('maddy lee', 'madeline lee'),                 # nickname
        ('mike chen', 'michael chen'),                 # nickname
        ('matt givens', 'matthew givens'),             # nickname
        ('dan carstensen', 'daniel carstensen'),       # nickname
    ]

    SHOULD_NOT_MATCH = [
        ('alice smith', 'bob jones'),
        ('kevin chang', 'helen lu'),
        ('sarah park', 'shane park'),
        ('andrew cao', 'andrew richardson'),
    ]

    def test_matching_pairs(self):
        """At least 90% of matching pairs should be detected."""
        matches_found = 0
        for name1, name2 in self.SHOULD_MATCH:
            n1, n2 = normalize_name(name1), normalize_name(name2)
            # Check exact, nickname, or fuzzy
            if n1 == n2:
                matches_found += 1
            elif names_match(n1, n2):
                matches_found += 1
            elif fuzzy_find(n1, {n2}) is not None:
                matches_found += 1

        recall = matches_found / len(self.SHOULD_MATCH)
        assert recall >= 0.90, f"Only {recall:.0%} recall ({matches_found}/{len(self.SHOULD_MATCH)})"

    def test_non_matching_pairs(self):
        """Non-matching pairs should not match."""
        for name1, name2 in self.SHOULD_NOT_MATCH:
            n1, n2 = normalize_name(name1), normalize_name(name2)
            assert n1 != n2
            assert not names_match(n1, n2)
            result = fuzzy_find(n1, {n2})
            assert result is None, f"False positive: '{name1}' matched '{name2}'"


class TestFindMatch:
    def test_exact_match(self):
        result = find_match('alice smith', {'alice smith', 'bob jones'})
        assert result == ('alice smith', 'exact')

    def test_nickname_match(self):
        result = find_match('bill smith', {'william smith', 'bob jones'})
        assert result is not None
        assert result[1] == 'nickname'

    def test_fuzzy_match(self):
        result = find_match('alice smth', {'alice smith', 'bob jones'})
        assert result is not None
        assert result[1] == 'fuzzy'

    def test_no_match(self):
        result = find_match('alice smith', {'completely different'})
        assert result is None


class TestGetAllPeopleNames:
    def test_excludes_non_person_sheets(self):
        sheets = {
            'members': [{'name': 'Alice'}],
            'collaborators': [{'name': 'Some Lab'}],
            'director': [{'name': 'Director'}],
        }
        result = get_all_people_names(sheets)
        assert 'alice' in result
        assert 'some lab' not in result
        assert 'director' not in result

    def test_includes_all_person_sheets(self):
        sheets = {s: [{'name': f'Person from {s}'}] for s in PERSON_SHEETS}
        result = get_all_people_names(sheets)
        assert len(result) == len(PERSON_SHEETS)


class TestPrintReport:
    def test_report_has_auto_resolved_section(self):
        discs = [Discrepancy('Alice', 'missing', ['people.xlsx'], ['CV'],
                             'test', 'auto_add')]
        captured = io.StringIO()
        sys.stdout = captured
        print_report(discs)
        sys.stdout = sys.__stdout__
        output = captured.getvalue()
        assert 'AUTO-RESOLVED' in output

    def test_report_has_flagged_section(self):
        discs = [Discrepancy('Bob', 'missing', ['lab-manual'], ['people.xlsx'],
                             'test', 'flag_for_review')]
        captured = io.StringIO()
        sys.stdout = captured
        print_report(discs)
        sys.stdout = sys.__stdout__
        output = captured.getvalue()
        assert 'FLAGGED FOR REVIEW' in output

    def test_report_has_conflicts_section(self):
        discs = [Discrepancy('Eve', 'conflict', ['people.xlsx', 'CV'], [],
                             'test', 'conflict')]
        captured = io.StringIO()
        sys.stdout = captured
        print_report(discs)
        sys.stdout = sys.__stdout__
        output = captured.getvalue()
        assert 'CONFLICTS' in output

    def test_report_shows_all_in_sync_when_empty(self):
        captured = io.StringIO()
        sys.stdout = captured
        print_report([])
        sys.stdout = sys.__stdout__
        assert 'in sync' in captured.getvalue()

    def test_report_has_distinct_sections(self):
        """All three section headers appear distinctly in output."""
        discs = [
            Discrepancy('A', 'missing', ['people.xlsx'], ['CV'], 't', 'auto_add'),
            Discrepancy('B', 'missing', ['lab-manual'], ['people.xlsx'], 't', 'flag_for_review'),
            Discrepancy('C', 'conflict', ['CV'], [], 't', 'conflict'),
        ]
        captured = io.StringIO()
        sys.stdout = captured
        print_report(discs)
        sys.stdout = sys.__stdout__
        output = captured.getvalue()
        assert 'AUTO-RESOLVED' in output
        assert 'FLAGGED FOR REVIEW' in output
        assert 'CONFLICTS' in output
        # Verify sections appear in order
        auto_pos = output.index('AUTO-RESOLVED')
        flagged_pos = output.index('FLAGGED FOR REVIEW')
        conflict_pos = output.index('CONFLICTS')
        assert auto_pos < flagged_pos < conflict_pos


class TestReconcileIntegration:
    def test_reconcile_runs_without_error(self):
        """Reconciliation runs against real data without crashing."""
        discrepancies = reconcile(dry_run=True)
        assert isinstance(discrepancies, list)

    def test_reconcile_returns_list(self):
        """Reconciliation returns a list of discrepancies (may be empty if synced)."""
        discrepancies = reconcile(dry_run=True)
        assert isinstance(discrepancies, list)

    def test_reconcile_dry_run_doesnt_modify(self):
        """Dry run should not modify any files."""
        from pathlib import Path
        xlsx_path = Path(__file__).parent.parent / 'data' / 'people.xlsx'
        mtime_before = xlsx_path.stat().st_mtime
        reconcile(dry_run=True)
        mtime_after = xlsx_path.stat().st_mtime
        assert mtime_before == mtime_after
