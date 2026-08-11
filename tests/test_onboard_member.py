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
    invitation_login,
    member_exists_in_cv,
    reopen_cv_entry,
    stated_pronouns,
)


class TestStatedPronouns:
    """The check that decides whether an LLM edit may be published.

    Prompt wording alone did not hold: the model would satisfy "keep his
    pronouns" by rewriting the sentence so no pronoun was needed.
    """

    def test_finds_masculine_pronouns(self):
        assert stated_pronouns("His research interests lie in memory.") == {"he"}
        assert stated_pronouns("He studies memory.") == {"he"}
        assert stated_pronouns("The lab hired him in 2026.") == {"he"}

    def test_finds_feminine_pronouns(self):
        assert stated_pronouns("She enjoys running and baking.") == {"she"}
        assert stated_pronouns("Her work is on causal inference.") == {"she"}

    def test_a_pronoun_free_bio_reports_nothing(self):
        assert stated_pronouns("Sreshth studies causal inference.") == frozenset()

    def test_they_them_is_not_a_gendered_group(self):
        """they/them is the neutral default, not something to preserve."""
        assert stated_pronouns("They study memory and their work is on LLMs.") == (
            frozenset()
        )

    def test_substrings_do_not_count_as_pronouns(self):
        """The regex is word-based; "the", "here", "this" must not match."""
        assert stated_pronouns("The history of these theories is here.") == (
            frozenset()
        )
        assert stated_pronouns("Sheffield and Hershey are places.") == frozenset()

    def test_is_case_insensitive(self):
        assert stated_pronouns("HIS work. He studies memory.") == {"he"}

    def test_empty_and_missing_text(self):
        assert stated_pronouns("") == frozenset()
        assert stated_pronouns(None) == frozenset()

    def test_the_exact_regression_case(self):
        """Sreshth's submitted bio versus what onboarding published."""
        submitted = (
            "Sreshth is a Mathematics and Computer Science double major at "
            "Dartmouth College. His research interests lie in causal inference."
        )
        published = submitted.replace("His", "Their")
        reworded = (
            "Sreshth is a Mathematics and Computer Science double major at "
            "Dartmouth College with research interests in causal inference."
        )

        assert stated_pronouns(submitted) == {"he"}
        # Both failure modes must be visible to the guard.
        assert stated_pronouns(published) != stated_pronouns(submitted)
        assert stated_pronouns(reworded) != stated_pronouns(submitted)


class TestInvitationLogin:
    """Whose invitation is this?

    Onboarding re-sent Sreshth Tiwari's org invitation on every run because
    GitHub returned it with a null `login`, and reading only that field made
    the pending list come back empty.
    """

    def test_reads_the_login_when_github_supplies_one(self):
        assert invitation_login({"login": "octocat", "email": None}) == "octocat"

    def test_falls_back_to_a_noreply_address(self):
        """The exact payload that caused the duplicate invitations."""
        assert (
            invitation_login(
                {
                    "login": None,
                    "email": "SreshthTiwari@users.noreply.github.com",
                }
            )
            == "SreshthTiwari"
        )

    def test_strips_the_numeric_id_prefix(self):
        """Accounts created after mid-2017 use "<id>+<username>@..."."""
        assert (
            invitation_login(
                {"login": None, "email": "1234567+octocat@users.noreply.github.com"}
            )
            == "octocat"
        )

    def test_a_real_email_is_not_treated_as_a_username(self):
        """An invite sent to a personal address names nobody we can match."""
        assert invitation_login({"login": None, "email": "someone@gmail.com"}) == ""

    def test_missing_fields_do_not_raise(self):
        assert invitation_login({}) == ""
        assert invitation_login({"login": None, "email": None}) == ""

    def test_the_match_is_case_insensitive_at_the_call_site(self):
        """invite_to_github_org lowercases both sides, so casing must not
        decide whether someone gets a second invitation."""
        login = invitation_login(
            {"login": None, "email": "SreshthTiwari@users.noreply.github.com"}
        )
        assert login.lower() == "sreshthtiwari"


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


class TestReopenQualifiedEntries:
    """Real graduate entries carry a qualifier and often a destination:

        \\item Kirsten Ziman (Doctoral student; 2017 -- 2022; current position:
        Postdoctoral researcher at Princeton University)

    The year-only patterns this replaces could not match those at all, so
    add_to_cv printed "reopening..." and then returned False, which
    onboard_member reports as an outright failure.
    """

    def test_reopens_a_qualified_range(self, cv_file):
        assert reopen_cv_entry(cv_file, 'Caroline Lee') is True
        assert entries_for(cv_file, 'Caroline Lee') == [
            r'\item Caroline Lee (Doctoral student; 2019 -- )']

    def test_add_to_cv_succeeds_for_a_returning_grad(self, cv_file):
        assert add_to_cv(cv_file, 'Caroline Lee', 'grad student', '2026') is True
        assert cv_entry_is_open(cv_file, 'Caroline Lee')

    def test_a_recorded_destination_is_dropped(self, tmp_path):
        p = tmp_path / 'JRM_CV.tex'
        p.write_text(MINIMAL_CV.replace(
            r'\item Caroline Lee (Doctoral student; 2019 -- 2021)',
            r'\item Kirsten Ziman (Doctoral student; 2017 -- 2022; '
            r'current position: Postdoctoral researcher at Princeton University)'
        ), encoding='utf-8')

        assert reopen_cv_entry(p, 'Kirsten Ziman') is True
        assert entries_for(p, 'Kirsten Ziman') == [
            r'\item Kirsten Ziman (Doctoral student; 2017 -- )']

    def test_already_open_entry_is_left_alone(self, cv_file):
        before = cv_file.read_text(encoding='utf-8')
        assert reopen_cv_entry(cv_file, 'Claudia Gonciulea') is False
        assert cv_file.read_text(encoding='utf-8') == before

    def test_single_year_entry_is_reopened(self, tmp_path):
        p = tmp_path / 'JRM_CV.tex'
        p.write_text(MINIMAL_CV.replace(
            r'\item Old Timer (2019 -- 2021)',
            r'\item Mark Taylor (Masters student, Quantitative Biomedical Sciences; 2021)'
        ), encoding='utf-8')

        assert reopen_cv_entry(p, 'Mark Taylor') is True
        assert entries_for(p, 'Mark Taylor') == [
            r'\item Mark Taylor (Masters student, Quantitative Biomedical Sciences; 2021 -- )']

    def test_real_cv_returning_graduate_advisee(self, real_cv):
        """Kirsten Ziman is a real closed graduate entry with a destination."""
        assert add_to_cv(real_cv, 'Kirsten Ziman', 'grad student', '2026') is True
        assert cv_entry_is_open(real_cv, 'Kirsten Ziman')
        assert 'current position' not in entries_for(real_cv, 'Kirsten Ziman')[0]

    def test_every_closed_graduate_advisee_can_be_reopened(self, real_cv):
        """Not one of them could be, before this."""
        content = real_cv.read_text(encoding='utf-8')
        grad_start = content.index(r'\textit{Graduate Advisees}:')
        grad_end = content.index(r'\textit{Undergraduate Advisees}:')
        names = re.findall(
            r'\\item\s+([^(]+?)\s*\([^)]*--\s*\d{4}[^)]*\)',
            content[grad_start:grad_end]
        )
        assert len(names) >= 5, "expected several closed graduate entries"

        for name in names:
            fresh = real_cv.parent / f"cv_{abs(hash(name))}.tex"
            fresh.write_text(content, encoding='utf-8')
            assert reopen_cv_entry(fresh, name.strip()) is True, (
                f"could not reopen {name.strip()!r}"
            )
            assert cv_entry_is_open(fresh, name.strip())


class TestCloseCvEntryBreadth:
    def test_closes_only_the_first_open_entry(self, tmp_path):
        p = tmp_path / 'JRM_CV.tex'
        p.write_text(MINIMAL_CV.replace(
            r'\item Old Timer (2019 -- 2021)',
            r'\item Rising Star (2018 -- )'
        ), encoding='utf-8')

        # Two open entries for one name is anomalous; closing a role change
        # must not sweep up the unrelated one.
        assert close_cv_entry(p, 'Rising Star', '2026') is True
        closed = [e for e in entries_for(p, 'Rising Star') if re.search(r'--\s*\d{4}\)', e)]
        assert len(closed) == 1
