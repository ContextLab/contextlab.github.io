"""Tests for the CV writers in onboard_member.py.

Focused on the mentorship-section routing that issue #17 was about: which
roles land in which CV section, which roles are deliberately absent, and what
a role change does to an existing entry.
"""
import re
import textwrap
from pathlib import Path

import pytest

from onboard_member import (
    add_to_cv,
    close_cv_entry,
    cv_entry_is_open,
    cv_section_for_role,
    find_cv_section,
    member_exists_in_cv,
    reopen_cv_entry,
)


# Mirrors the three mentorship subsections of the real JRM_CV.tex, including
# the \blfootnote that sits between the undergraduate heading and its list.
MINIMAL_CV = textwrap.dedent(r"""
    \subsection*{Mentorship  (selected)}

    \textit{Postdoctoral Advisees}:
    \begin{etaremune}  \item Hung-Tu Chen (2024 -- 2025; current position: Meta)
    \end{etaremune}

    \textit{Graduate Advisees}:
    \begin{etaremune}
    \item Claudia Gonciulea (Doctoral student; 2025 -- )
    \item Caroline Lee (Doctoral student; 2019 -- 2021)
    \end{etaremune}

    \textit{Undergraduate Advisees}:
    \blfootnote{Senior thesis students are denoted by asterisks
      (*)}
    \begin{multicols}{2}
    \begin{etaremune}
      \item Neui Wadwalai (2026 -- )
      \item Rising Star (2024 -- )
      \item Old Timer (2019 -- 2021)
      \item Thesis Writer* (2020 -- 2022)
    \end{etaremune}
    \end{multicols}
""").strip()


@pytest.fixture
def cv_file(tmp_path):
    p = tmp_path / "JRM_CV.tex"
    p.write_text(MINIMAL_CV, encoding='utf-8')
    return p


@pytest.fixture
def real_cv(tmp_path):
    """A copy of the real JRM_CV.tex."""
    real = Path(__file__).parent.parent / 'documents' / 'JRM_CV.tex'
    if not real.exists():
        pytest.skip("JRM_CV.tex not found")
    target = tmp_path / "JRM_CV.tex"
    target.write_text(real.read_text(encoding='utf-8'), encoding='utf-8')
    return target


def entries_for(cv_path, name):
    content = cv_path.read_text(encoding='utf-8')
    return re.findall(
        r'\\item\s+' + re.escape(name) + r'\*?\s*\([^)]*\)', content
    )


class TestCvSectionForRole:
    """Routing rules confirmed by the lab director on issue #17."""

    def test_postdoc(self):
        assert cv_section_for_role('postdoc') == 'postdoc'

    def test_grad_student(self):
        assert cv_section_for_role('grad student') == 'grad'
        assert cv_section_for_role('graduate student') == 'grad'

    def test_undergrad(self):
        assert cv_section_for_role('undergrad') == 'undergrad'
        assert cv_section_for_role('undergraduate') == 'undergrad'

    def test_undergrad_is_not_mistaken_for_grad(self):
        """'undergrad' contains 'grad' -- the substring check must not trip."""
        assert cv_section_for_role('undergrad') != 'grad'

    def test_research_assistants_are_undergrads_on_purpose(self):
        """Not an accidental else-branch: this is the intended routing."""
        assert cv_section_for_role('research assistant') == 'undergrad'

    def test_lab_managers_get_no_cv_entry(self):
        """Lab managers are staff, not trainees, so they are absent entirely."""
        assert cv_section_for_role('lab manager') is None


class TestLabManagersAreNotWrittenToTheCv:
    """The one real defect in section 3 of issue #17."""

    def test_add_to_cv_writes_nothing(self, cv_file):
        before = cv_file.read_text(encoding='utf-8')
        assert add_to_cv(cv_file, 'New Manager', 'lab manager', '2026') is True
        assert cv_file.read_text(encoding='utf-8') == before

    def test_reports_success_so_onboarding_is_not_marked_failed(self, cv_file):
        """Returning False here would make onboard_member exit(1) spuriously."""
        assert add_to_cv(cv_file, 'New Manager', 'lab manager', '2026') is True

    def test_manager_does_not_appear_as_an_undergraduate(self, cv_file):
        add_to_cv(cv_file, 'New Manager', 'lab manager', '2026')
        assert not member_exists_in_cv(cv_file, 'New Manager')

    def test_still_absent_on_the_real_cv(self, real_cv):
        before = real_cv.read_text(encoding='utf-8')
        add_to_cv(real_cv, 'New Manager', 'lab manager', '2026')
        assert real_cv.read_text(encoding='utf-8') == before


class TestAddToCv:
    def test_adds_undergrad(self, cv_file):
        assert add_to_cv(cv_file, 'Fresh Face', 'undergrad', '2026') is True
        assert find_cv_section(cv_file, 'Fresh Face') == 'undergrad'

    def test_adds_grad_with_doctoral_qualifier(self, cv_file):
        add_to_cv(cv_file, 'New Doc', 'grad student', '2026')
        assert entries_for(cv_file, 'New Doc') == [
            r'\item New Doc (Doctoral student; 2026 -- )']

    def test_adds_postdoc(self, cv_file):
        add_to_cv(cv_file, 'New Postdoc', 'postdoc', '2026')
        assert find_cv_section(cv_file, 'New Postdoc') == 'postdoc'

    def test_research_assistant_lands_with_the_undergrads(self, cv_file):
        add_to_cv(cv_file, 'New RA', 'research assistant', '2026')
        assert find_cv_section(cv_file, 'New RA') == 'undergrad'

    def test_rerun_is_a_no_op(self, cv_file):
        add_to_cv(cv_file, 'Fresh Face', 'undergrad', '2026')
        before = cv_file.read_text(encoding='utf-8')
        assert add_to_cv(cv_file, 'Fresh Face', 'undergrad', '2026') is True
        assert cv_file.read_text(encoding='utf-8') == before

    def test_closed_entry_in_the_same_section_is_reopened(self, cv_file):
        assert add_to_cv(cv_file, 'Old Timer', 'undergrad', '2026') is True
        assert entries_for(cv_file, 'Old Timer') == [r'\item Old Timer (2019 -- )']

    def test_adds_to_the_real_cv(self, real_cv):
        assert add_to_cv(real_cv, 'Brand New', 'undergrad', '2026') is True
        assert find_cv_section(real_cv, 'Brand New') == 'undergrad'


class TestFindCvSection:
    def test_locates_each_section(self, cv_file):
        assert find_cv_section(cv_file, 'Hung-Tu Chen') == 'postdoc'
        assert find_cv_section(cv_file, 'Claudia Gonciulea') == 'grad'
        assert find_cv_section(cv_file, 'Neui Wadwalai') == 'undergrad'

    def test_absent_name_is_none(self, cv_file):
        assert find_cv_section(cv_file, 'Nobody Here') is None

    def test_matches_a_starred_thesis_entry(self, cv_file):
        assert find_cv_section(cv_file, 'Thesis Writer') == 'undergrad'

    def test_prefers_the_open_entry_over_a_closed_one(self, real_cv):
        """Paxton Fitzpatrick is closed under undergrad AND open under grad.

        The real CV holds '\\item Paxton Fitzpatrick* (2017 -- 2019)' among the
        undergraduates and '\\item Paxton Fitzpatrick (Doctoral student;
        2021 -- )' among the graduates. His current role is the open one.
        """
        assert find_cv_section(real_cv, 'Paxton Fitzpatrick') == 'grad'


class TestCvEntryIsOpen:
    def test_open_range(self, cv_file):
        assert cv_entry_is_open(cv_file, 'Neui Wadwalai')

    def test_closed_range(self, cv_file):
        assert not cv_entry_is_open(cv_file, 'Old Timer')

    def test_open_range_with_a_qualifier(self, cv_file):
        assert cv_entry_is_open(cv_file, 'Claudia Gonciulea')

    def test_absent_name(self, cv_file):
        assert not cv_entry_is_open(cv_file, 'Nobody Here')

    def test_a_person_with_both_reads_as_open(self, real_cv):
        """The case that broke the old has-an-end-date question."""
        assert cv_entry_is_open(real_cv, 'Paxton Fitzpatrick')

    def test_reopening_paxton_is_not_attempted(self, real_cv):
        """Re-onboarding a current grad must not touch their closed undergrad
        range. The old cv_entry_has_end_date said True for Paxton and sent
        onboarding into reopen_cv_entry, which would reopen '(2017 -- 2019)'.
        """
        before = real_cv.read_text(encoding='utf-8')
        assert add_to_cv(real_cv, 'Paxton Fitzpatrick', 'grad student', '2026') is True
        assert real_cv.read_text(encoding='utf-8') == before


class TestCloseCvEntry:
    def test_closes_a_plain_range(self, cv_file):
        assert close_cv_entry(cv_file, 'Rising Star', '2026') is True
        assert entries_for(cv_file, 'Rising Star') == [
            r'\item Rising Star (2024 -- 2026)']

    def test_preserves_a_qualifier(self, cv_file):
        close_cv_entry(cv_file, 'Claudia Gonciulea', '2026')
        assert entries_for(cv_file, 'Claudia Gonciulea') == [
            r'\item Claudia Gonciulea (Doctoral student; 2025 -- 2026)']

    def test_absent_name_returns_false(self, cv_file):
        before = cv_file.read_text(encoding='utf-8')
        assert close_cv_entry(cv_file, 'Nobody Here', '2026') is False
        assert cv_file.read_text(encoding='utf-8') == before

    def test_round_trips_with_reopen(self, cv_file):
        before = cv_file.read_text(encoding='utf-8')
        close_cv_entry(cv_file, 'Rising Star', '2026')
        reopen_cv_entry(cv_file, 'Rising Star')
        assert cv_file.read_text(encoding='utf-8') == before


class TestCvRoleChange:
    """A role change closes the old range and opens a new one -- the shape the
    real CV already records for Paxton Fitzpatrick.
    """

    def test_undergrad_to_grad_leaves_two_entries(self, cv_file):
        add_to_cv(cv_file, 'Rising Star', 'grad student', '2026')

        assert entries_for(cv_file, 'Rising Star') == [
            r'\item Rising Star (Doctoral student; 2026 -- )',
            r'\item Rising Star (2024 -- 2026)',
        ]

    def test_the_old_entry_is_closed(self, cv_file):
        add_to_cv(cv_file, 'Rising Star', 'grad student', '2026')
        content = cv_file.read_text(encoding='utf-8')
        assert r'\item Rising Star (2024 -- )' not in content

    def test_the_new_entry_is_the_current_one(self, cv_file):
        add_to_cv(cv_file, 'Rising Star', 'grad student', '2026')
        assert find_cv_section(cv_file, 'Rising Star') == 'grad'

    def test_exactly_one_open_entry_remains(self, cv_file):
        add_to_cv(cv_file, 'Rising Star', 'grad student', '2026')
        open_entries = [e for e in entries_for(cv_file, 'Rising Star')
                        if re.search(r'--\s*\)', e)]
        assert len(open_entries) == 1

    def test_undergrad_to_postdoc(self, cv_file):
        add_to_cv(cv_file, 'Rising Star', 'postdoc', '2026')
        assert find_cv_section(cv_file, 'Rising Star') == 'postdoc'
        assert r'\item Rising Star (2024 -- 2026)' in cv_file.read_text(encoding='utf-8')

    def test_promotion_to_lab_manager_writes_nothing_new(self, cv_file):
        """Lab managers are absent from the CV, so an undergrad promoted to lab
        manager keeps their existing undergraduate entry untouched.
        """
        before = cv_file.read_text(encoding='utf-8')
        assert add_to_cv(cv_file, 'Rising Star', 'lab manager', '2026') is True
        assert cv_file.read_text(encoding='utf-8') == before

    def test_role_change_on_the_real_cv(self, real_cv):
        add_to_cv(real_cv, 'Role Changer', 'undergrad', '2024')
        add_to_cv(real_cv, 'Role Changer', 'grad student', '2026')

        assert entries_for(real_cv, 'Role Changer') == [
            r'\item Role Changer (Doctoral student; 2026 -- )',
            r'\item Role Changer (2024 -- 2026)',
        ]
