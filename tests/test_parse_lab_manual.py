"""Tests for parse_lab_manual.py."""
import re
import tempfile
import textwrap
from pathlib import Path

import pytest

from parse_lab_manual import (
    _find_role_block,
    parse_members_chapter,
    add_member_to_lab_manual,
    move_member_to_alumni,
    commit_and_push_lab_manual,
    find_current_role,
    sync_member_role,
    ROLE_ORDER,
)


def headings_in(tex_path, subsection, next_subsection=None):
    """Uncommented \\newthought headings inside one \\subsection."""
    content = tex_path.read_text(encoding='utf-8')
    start = content.index(r'\subsection{' + subsection + '}')
    end = (content.index(r'\subsection{' + next_subsection + '}')
           if next_subsection else len(content))
    return re.findall(r'^[^%\n]*\\newthought\{(.*?)\}', content[start:end], re.MULTILINE)


def assert_no_empty_lists(tex_path):
    """An \\item-less list is a fatal LaTeX error, so one must never be written.

    Verified against real LaTeX: '\\begin{list}{\\quad}{}\\end{list}' aborts with
    "Something's wrong--perhaps a missing \\item" and produces no PDF at all.
    """
    content = tex_path.read_text(encoding='utf-8')
    empty = re.findall(
        r'\\begin\{list\}\{\\quad\}\{\}\s*\\end\{list\}', content
    )
    assert not empty, f"{len(empty)} empty list block(s) would break the LaTeX build"


MINIMAL_TEX = textwrap.dedent(r"""
    \chapter{Lab members and alumni}\label{ch:members}
    \begin{fullwidth}
    \subsection{Current lab members}\label{sec:curr_members}
    \newthought{PI}
    \bigskip

    \enskip Jeremy R. Manning (2015 -- )

    \newthought{Graduate Students}
    \begin{multicols}{2}\raggedcolumns
    \begin{list}{\quad}{}
    \item Alice Smith (2022 -- )
    \item Bob Jones (2023 -- )
    \end{list}
    \end{multicols}

    \newthought{Undergraduate RAs}
    \begin{multicols}{2}\raggedcolumns
    \begin{list}{\quad}{}
    \item Charlie Brown (2024 -- )
    \end{list}
    \end{multicols}

    \subsection{Lab alumni}
    \newthought{Graduate Students}
    \begin{multicols}{2}\raggedcolumns
    \begin{list}{\quad}{}
    \item Dana White (2018 -- 2022)
    \end{list}
    \end{multicols}

    \newthought{Undergraduate RAs}
    \begin{multicols}{2}\raggedcolumns
    \begin{list}{\quad}{}
    \item Eve Black (2020 -- 2021)
    \item Frank Green (2019)
    \end{list}
    \end{multicols}
    \end{fullwidth}
""").strip()


@pytest.fixture
def tex_file(tmp_path):
    """Create a temporary tex file with minimal member data."""
    p = tmp_path / "lab_manual.tex"
    p.write_text(MINIMAL_TEX, encoding='utf-8')
    return p


class TestParseBasic:
    def test_parses_all_entries(self, tex_file):
        records = parse_members_chapter(tex_file)
        assert len(records) == 7

    def test_parses_pi(self, tex_file):
        records = parse_members_chapter(tex_file)
        pi = [r for r in records if r['role_category'] == 'PI']
        assert len(pi) == 1
        assert pi[0]['name'] == 'Jeremy R. Manning'
        assert pi[0]['start_year'] == 2015
        assert pi[0]['end_year'] is None
        assert pi[0]['is_active'] is True

    def test_parses_active_members(self, tex_file):
        records = parse_members_chapter(tex_file)
        active = [r for r in records if r['is_active']]
        assert len(active) == 4
        names = {r['name'] for r in active}
        assert 'Alice Smith' in names
        assert 'Bob Jones' in names
        assert 'Charlie Brown' in names

    def test_parses_alumni(self, tex_file):
        records = parse_members_chapter(tex_file)
        alumni = [r for r in records if not r['is_active']]
        assert len(alumni) == 3
        dana = next(r for r in alumni if r['name'] == 'Dana White')
        assert dana['start_year'] == 2018
        assert dana['end_year'] == 2022
        assert dana['role_category'] == 'Graduate Students'

    def test_parses_single_year_entry(self, tex_file):
        records = parse_members_chapter(tex_file)
        frank = next(r for r in records if r['name'] == 'Frank Green')
        assert frank['start_year'] == 2019
        assert frank['end_year'] is None  # single year has no end
        assert frank['is_active'] is False  # in alumni section

    def test_role_categories(self, tex_file):
        records = parse_members_chapter(tex_file)
        roles = {r['role_category'] for r in records}
        assert 'PI' in roles
        assert 'Graduate Students' in roles
        assert 'Undergraduate RAs' in roles


class TestParseEdgeCases:
    def test_commented_section(self, tmp_path):
        tex = MINIMAL_TEX.replace(
            r'\newthought{Undergraduate RAs}' + '\n'
            r'\begin{multicols}{2}\raggedcolumns' + '\n'
            r'\begin{list}{\quad}{}' + '\n'
            r'\item Charlie Brown (2024 -- )' + '\n'
            r'\end{list}' + '\n'
            r'\end{multicols}' + '\n\n'
            r'\subsection{Lab alumni}',
            '% \\newthought{Undergraduate RAs}\n'
            '% \\begin{multicols}{2}\\raggedcolumns\n'
            '% \\begin{list}{\\quad}{}\n'
            '% \\end{list}\n'
            '% \\end{multicols}\n\n'
            '\\subsection{Lab alumni}'
        )
        p = tmp_path / "lab_manual.tex"
        p.write_text(tex, encoding='utf-8')
        records = parse_members_chapter(p)
        names = {r['name'] for r in records}
        assert 'Charlie Brown' not in names

    def test_missing_chapter_raises(self, tmp_path):
        p = tmp_path / "lab_manual.tex"
        p.write_text("\\chapter{Something else}", encoding='utf-8')
        with pytest.raises(ValueError, match="Could not find"):
            parse_members_chapter(p)

    def test_empty_list_section(self, tmp_path):
        tex = MINIMAL_TEX.replace(
            '\\item Charlie Brown (2024 -- )\n',
            ''
        )
        p = tmp_path / "lab_manual.tex"
        p.write_text(tex, encoding='utf-8')
        records = parse_members_chapter(p)
        names = {r['name'] for r in records}
        assert 'Charlie Brown' not in names


class TestParseRealData:
    def test_parses_real_lab_manual(self):
        real_path = Path(__file__).parent.parent / 'lab-manual' / 'lab_manual.tex'
        if not real_path.exists():
            pytest.skip("Lab-manual submodule not initialized")
        records = parse_members_chapter(real_path)
        assert len(records) > 50
        active = [r for r in records if r['is_active']]
        alumni = [r for r in records if not r['is_active']]
        assert len(active) > 5
        assert len(alumni) > 20
        # PI should always be present
        pi = [r for r in records if r['role_category'] == 'PI']
        assert len(pi) == 1
        assert 'Manning' in pi[0]['name']

    def test_multi_role_person_in_real_data(self):
        real_path = Path(__file__).parent.parent / 'lab-manual' / 'lab_manual.tex'
        if not real_path.exists():
            pytest.skip("Lab-manual submodule not initialized")
        records = parse_members_chapter(real_path)
        # Paxton Fitzpatrick appears as undergrad RA alumni, lab manager alumni, and grad student
        paxton_records = [r for r in records if 'Paxton' in r['name'] and 'Fitzpatrick' in r['name']]
        assert len(paxton_records) >= 2


class TestAddMember:
    def test_adds_grad_student(self, tex_file):
        add_member_to_lab_manual(tex_file, 'New Person', 'grad student', 2026)
        records = parse_members_chapter(tex_file)
        new = next(r for r in records if r['name'] == 'New Person')
        assert new['role_category'] == 'Graduate Students'
        assert new['start_year'] == 2026
        assert new['is_active'] is True

    def test_adds_undergrad(self, tex_file):
        add_member_to_lab_manual(tex_file, 'Test Undergrad', 'undergrad', 2026)
        records = parse_members_chapter(tex_file)
        new = next(r for r in records if r['name'] == 'Test Undergrad')
        assert new['role_category'] == 'Undergraduate RAs'
        assert new['is_active'] is True

    def test_invalid_role_raises(self, tex_file):
        with pytest.raises(ValueError, match="Unknown role"):
            add_member_to_lab_manual(tex_file, 'Test', 'wizard', 2026)

    def test_returns_true_when_added(self, tex_file):
        assert add_member_to_lab_manual(tex_file, 'Fresh Face', 'undergrad', 2026) is True

    def test_adding_twice_does_not_duplicate(self, tex_file):
        """Re-running onboarding must be a no-op (issue #15)."""
        assert add_member_to_lab_manual(tex_file, 'Repeat Person', 'undergrad', 2026) is True
        assert add_member_to_lab_manual(tex_file, 'Repeat Person', 'undergrad', 2026) is False
        assert add_member_to_lab_manual(tex_file, 'Repeat Person', 'undergrad', 2026) is False

        records = parse_members_chapter(tex_file)
        matches = [r for r in records if r['name'] == 'Repeat Person']
        assert len(matches) == 1, f"expected 1 entry, found {len(matches)}"

    def test_second_add_leaves_file_byte_identical(self, tex_file):
        add_member_to_lab_manual(tex_file, 'Byte Identical', 'grad student', 2026)
        after_first = tex_file.read_text(encoding='utf-8')

        add_member_to_lab_manual(tex_file, 'Byte Identical', 'grad student', 2026)

        assert tex_file.read_text(encoding='utf-8') == after_first

    def test_duplicate_guard_ignores_case(self, tex_file):
        """Matches member_exists_in_cv, which is case-insensitive."""
        assert add_member_to_lab_manual(tex_file, 'Casey Jones', 'undergrad', 2026) is True
        assert add_member_to_lab_manual(tex_file, 'casey jones', 'undergrad', 2026) is False

        records = parse_members_chapter(tex_file)
        matches = [r for r in records if r['name'].lower() == 'casey jones']
        assert len(matches) == 1

    def test_same_name_different_roles_is_not_blocked(self, tex_file):
        """add_member_to_lab_manual is the low-level primitive: its guard is
        per-role, so on its own it will happily record two open entries.

        Onboarding must NOT call it directly for this reason -- it goes through
        sync_member_role, which closes the old role out first. See
        TestSyncMemberRole.
        """
        assert add_member_to_lab_manual(tex_file, 'Role Changer', 'undergrad', 2024) is True
        assert add_member_to_lab_manual(tex_file, 'Role Changer', 'grad student', 2026) is True

        records = parse_members_chapter(tex_file)
        roles = {r['role_category'] for r in records if r['name'] == 'Role Changer'}
        assert roles == {'Undergraduate RAs', 'Graduate Students'}


class TestMoveMember:
    def test_moves_to_alumni(self, tex_file):
        move_member_to_alumni(tex_file, 'Alice Smith', 2026)
        records = parse_members_chapter(tex_file)
        # Should no longer be active
        active_names = {r['name'] for r in records if r['is_active']}
        assert 'Alice Smith' not in active_names
        # Should be in alumni
        alice = next(r for r in records if r['name'] == 'Alice Smith' and not r['is_active'])
        assert alice['end_year'] == 2026
        assert alice['role_category'] == 'Graduate Students'

    def test_move_nonexistent_raises(self, tex_file):
        with pytest.raises(ValueError, match="Could not find"):
            move_member_to_alumni(tex_file, 'Nobody Here', 2026)


class TestCommitAndPush:
    def test_raises_when_not_initialized(self, tmp_path):
        with pytest.raises(RuntimeError, match="not initialized"):
            commit_and_push_lab_manual(tmp_path / 'nonexistent', 'test')


# Mirrors two quirks of the real lab_manual.tex: the Research Assistants
# heading under Current is commented out, and Lab Managers exists only under
# Lab alumni. Both used to make add_member_to_lab_manual write to the wrong
# place instead of refusing.
QUIRKY_TEX = textwrap.dedent(r"""
    \chapter{Lab members and alumni}\label{ch:members}
    \begin{fullwidth}
    \subsection{Current lab members}\label{sec:curr_members}
    \newthought{PI}
    \bigskip

    \enskip Jeremy R. Manning (2015 -- )

    % \newthought{Research Assistants}
    % \begin{multicols}{2}\raggedcolumns
    % \begin{list}{\quad}{}
    % \item Nobody Here (2020 -- )
    % \end{list}
    % \end{multicols}

    \newthought{Undergraduate RAs}
    \begin{multicols}{2}\raggedcolumns
    \begin{list}{\quad}{}
    \item Charlie Brown (2024 -- )
    \end{list}
    \end{multicols}

    \subsection{Lab alumni}
    \newthought{Lab Managers}
    \begin{multicols}{2}\raggedcolumns
    \begin{list}{\quad}{}
    \item Dana White (2018 -- 2022)
    \end{list}
    \end{multicols}

    \newthought{Undergraduate RAs}
    \begin{multicols}{2}\raggedcolumns
    \begin{list}{\quad}{}
    \item Eve Black (2020 -- 2021)
    \end{list}
    \end{multicols}
    \end{fullwidth}
""").strip()


@pytest.fixture
def quirky_tex_file(tmp_path):
    p = tmp_path / "lab_manual.tex"
    p.write_text(QUIRKY_TEX, encoding='utf-8')
    return p


class TestAddMemberSectionScoping:
    """The insert must land in an active Current-section list, or not at all."""

    def test_commented_out_heading_gets_a_live_block(self, quirky_tex_file):
        """A commented-out heading is not a place to write, so make a real one.

        Inserting into the commented list would yield a 'Lonely \\item' LaTeX
        error; refusing outright made research assistants un-onboardable
        (issue #17). The block is created live, below the commented one.
        """
        assert add_member_to_lab_manual(
            quirky_tex_file, 'New RA', 'research assistant', 2026) is True

        assert 'Research Assistants' in headings_in(
            quirky_tex_file, 'Current lab members', 'Lab alumni')
        records = parse_members_chapter(quirky_tex_file)
        new_ra = next(r for r in records if r['name'] == 'New RA')
        assert new_ra['role_category'] == 'Research Assistants'
        assert new_ra['is_active']
        assert_no_empty_lists(quirky_tex_file)

    def test_alumni_only_role_gets_a_current_block(self, quirky_tex_file):
        """'Lab Managers' exists only under Lab alumni, so create it under Current."""
        assert add_member_to_lab_manual(
            quirky_tex_file, 'New Manager', 'lab manager', 2026) is True

        assert 'Lab Managers' in headings_in(
            quirky_tex_file, 'Current lab members', 'Lab alumni')

        records = parse_members_chapter(quirky_tex_file)
        manager = next(r for r in records if r['name'] == 'New Manager')
        assert manager['role_category'] == 'Lab Managers'
        assert manager['is_active']

        # Dana White is the pre-existing Lab Managers ALUMNA; she must not have
        # been dragged into the Current section by the new block.
        dana = next(r for r in records if r['name'] == 'Dana White')
        assert not dana['is_active']

    def test_created_block_lands_at_its_seniority_position(self, quirky_tex_file):
        """Lab Managers outrank Undergraduate RAs, so the block goes above them."""
        add_member_to_lab_manual(quirky_tex_file, 'New Manager', 'lab manager', 2026)

        current = headings_in(quirky_tex_file, 'Current lab members', 'Lab alumni')
        assert current.index('Lab Managers') < current.index('Undergraduate RAs')
        assert current == sorted(current, key=ROLE_ORDER.index)

    def test_created_block_is_never_empty(self, quirky_tex_file):
        add_member_to_lab_manual(quirky_tex_file, 'New Manager', 'lab manager', 2026)
        assert_no_empty_lists(quirky_tex_file)

    def test_unknown_role_still_raises_rather_than_inventing_a_section(
            self, quirky_tex_file):
        """A typo'd --rank must be reported, not turned into a new heading."""
        before = quirky_tex_file.read_text(encoding='utf-8')

        with pytest.raises(ValueError, match="Unknown role"):
            add_member_to_lab_manual(quirky_tex_file, 'Typo Person', 'wizard', 2026)

        assert quirky_tex_file.read_text(encoding='utf-8') == before

    def test_insert_lands_before_the_alumni_section(self, quirky_tex_file):
        assert add_member_to_lab_manual(quirky_tex_file, 'Fresh RA', 'undergrad', 2026) is True

        content = quirky_tex_file.read_text(encoding='utf-8')
        assert content.index('Fresh RA') < content.index(r'\subsection{Lab alumni}')

    def test_alumnus_is_not_mistaken_for_a_current_member(self, quirky_tex_file):
        """Eve Black is an undergrad ALUMNA; re-onboarding her must still add her."""
        assert add_member_to_lab_manual(quirky_tex_file, 'Eve Black', 'undergrad', 2026) is True

        records = parse_members_chapter(quirky_tex_file)
        active = [r for r in records if r['name'] == 'Eve Black' and r['is_active']]
        assert len(active) == 1

    def test_commented_entries_are_not_counted_as_duplicates(self, quirky_tex_file):
        """'Nobody Here' is only inside a commented block, so it is not present."""
        content = quirky_tex_file.read_text(encoding='utf-8')
        assert 'Nobody Here' in content

        records = parse_members_chapter(quirky_tex_file)
        assert not [r for r in records if r['name'] == 'Nobody Here']


class TestEmptyBlockCleanup:
    """Offboarding the last member of a role must take the block with it."""

    def test_removing_last_member_removes_the_block(self, tex_file):
        add_member_to_lab_manual(tex_file, 'Only Manager', 'lab manager', 2026)
        assert 'Lab Managers' in headings_in(
            tex_file, 'Current lab members', 'Lab alumni')

        move_member_to_alumni(tex_file, 'Only Manager', 2027)

        assert 'Lab Managers' not in headings_in(
            tex_file, 'Current lab members', 'Lab alumni')
        assert_no_empty_lists(tex_file)

    def test_removing_one_of_several_keeps_the_block(self, tex_file):
        move_member_to_alumni(tex_file, 'Alice Smith', 2026)

        current = headings_in(tex_file, 'Current lab members', 'Lab alumni')
        assert 'Graduate Students' in current

        records = parse_members_chapter(tex_file)
        assert 'Bob Jones' in {r['name'] for r in records if r['is_active']}

    def test_alumni_block_is_created_when_missing(self, tex_file):
        """MINIMAL_TEX has no Lab Managers block under alumni either."""
        add_member_to_lab_manual(tex_file, 'Only Manager', 'lab manager', 2026)
        move_member_to_alumni(tex_file, 'Only Manager', 2027)

        assert 'Lab Managers' in headings_in(tex_file, 'Lab alumni')
        record = next(r for r in parse_members_chapter(tex_file)
                      if r['name'] == 'Only Manager')
        assert record['role_category'] == 'Lab Managers'
        assert record['end_year'] == 2027
        assert not record['is_active']

    def test_block_removal_does_not_disturb_neighbours(self, tex_file):
        add_member_to_lab_manual(tex_file, 'Only Manager', 'lab manager', 2026)
        move_member_to_alumni(tex_file, 'Only Manager', 2027)

        # The full roster either side of the removed block must survive intact.
        active = {r['name'] for r in parse_members_chapter(tex_file) if r['is_active']}
        assert {'Alice Smith', 'Bob Jones', 'Charlie Brown',
                'Jeremy R. Manning'} <= active


class TestFindCurrentRole:
    def test_finds_role(self, tex_file):
        assert find_current_role(tex_file, 'Alice Smith') == 'Graduate Students'
        assert find_current_role(tex_file, 'Charlie Brown') == 'Undergraduate RAs'

    def test_absent_member_is_none(self, tex_file):
        assert find_current_role(tex_file, 'Nobody Here') is None

    def test_alumni_only_member_is_none(self, tex_file):
        """Dana White is a Graduate Students ALUMNA, not a current member."""
        assert find_current_role(tex_file, 'Dana White') is None

    def test_is_case_insensitive(self, tex_file):
        assert find_current_role(tex_file, 'alice smith') == 'Graduate Students'


class TestSyncMemberRole:
    """The convention lab_manual.tex has actually been maintained with: a role
    change closes the old role out to Lab alumni and opens a new Current entry.

    Grounded in two real entries -- Xinming Xu is 'Research Assistants
    (2019 -- 2021)' under alumni and 'Graduate Students (2021 -- )' under
    current; Paxton Fitzpatrick is 'Lab Managers (2018 -- 2021)' and
    'Graduate Students (2021 -- )'. Both close in the year the new role opens.
    """

    def test_new_member_is_added(self, tex_file):
        assert sync_member_role(tex_file, 'Brand New', 'undergrad', 2026) == 'added'

    def test_rerun_is_unchanged(self, tex_file):
        sync_member_role(tex_file, 'Brand New', 'undergrad', 2026)
        assert sync_member_role(tex_file, 'Brand New', 'undergrad', 2026) == 'unchanged'

    def test_rerun_leaves_file_byte_identical(self, tex_file):
        sync_member_role(tex_file, 'Brand New', 'undergrad', 2026)
        before = tex_file.read_text(encoding='utf-8')
        sync_member_role(tex_file, 'Brand New', 'undergrad', 2026)
        assert tex_file.read_text(encoding='utf-8') == before

    def test_role_change_closes_the_old_role(self, tex_file):
        sync_member_role(tex_file, 'Role Changer', 'undergrad', 2024)
        assert sync_member_role(
            tex_file, 'Role Changer', 'grad student', 2026) == 'role-changed'

        records = [r for r in parse_members_chapter(tex_file)
                   if r['name'] == 'Role Changer']
        by_role = {r['role_category']: r for r in records}

        assert set(by_role) == {'Undergraduate RAs', 'Graduate Students'}

        old = by_role['Undergraduate RAs']
        assert old['start_year'] == 2024
        assert old['end_year'] == 2026, "old range closes in the year the new one opens"
        assert not old['is_active']

        new = by_role['Graduate Students']
        assert new['start_year'] == 2026
        assert new['end_year'] is None
        assert new['is_active']

    def test_role_change_leaves_exactly_one_active_entry(self, tex_file):
        """The bug in issue #17: two OPEN entries at once."""
        sync_member_role(tex_file, 'Role Changer', 'undergrad', 2024)
        sync_member_role(tex_file, 'Role Changer', 'grad student', 2026)

        active = [r for r in parse_members_chapter(tex_file)
                  if r['name'] == 'Role Changer' and r['is_active']]
        assert len(active) == 1

    def test_role_change_into_a_role_with_no_block(self, tex_file):
        """undergrad -> lab manager, where Lab Managers exists in neither section."""
        sync_member_role(tex_file, 'Promoted', 'undergrad', 2024)
        assert sync_member_role(
            tex_file, 'Promoted', 'lab manager', 2026) == 'role-changed'

        records = [r for r in parse_members_chapter(tex_file)
                   if r['name'] == 'Promoted']
        by_role = {r['role_category']: r for r in records}
        assert by_role['Lab Managers']['is_active']
        assert by_role['Undergraduate RAs']['end_year'] == 2026
        assert_no_empty_lists(tex_file)

    def test_role_change_back_again(self, tex_file):
        """Round-tripping must not accumulate open entries."""
        sync_member_role(tex_file, 'Waffler', 'undergrad', 2024)
        sync_member_role(tex_file, 'Waffler', 'grad student', 2025)
        sync_member_role(tex_file, 'Waffler', 'undergrad', 2026)

        active = [r for r in parse_members_chapter(tex_file)
                  if r['name'] == 'Waffler' and r['is_active']]
        assert len(active) == 1
        assert active[0]['role_category'] == 'Undergraduate RAs'


class TestRealLabManualRoundTrip:
    """Exercise the writers against the REAL lab_manual.tex, on a copy."""

    @pytest.fixture
    def real_copy(self, tmp_path):
        real = Path(__file__).parent.parent / 'lab-manual' / 'lab_manual.tex'
        if not real.exists():
            pytest.skip("lab-manual submodule not initialized")
        target = tmp_path / 'lab_manual.tex'
        target.write_text(real.read_text(encoding='utf-8'), encoding='utf-8')
        return target

    def test_real_manual_has_no_empty_lists_to_begin_with(self, real_copy):
        assert_no_empty_lists(real_copy)

    def test_onboarding_a_lab_manager_works_on_real_data(self, real_copy):
        assert sync_member_role(real_copy, 'Test Manager', 'lab manager', 2026) == 'added'
        assert find_current_role(real_copy, 'Test Manager') == 'Lab Managers'
        assert_no_empty_lists(real_copy)

    def test_onboarding_a_research_assistant_works_on_real_data(self, real_copy):
        assert sync_member_role(real_copy, 'Test RA', 'research assistant', 2026) == 'added'
        assert find_current_role(real_copy, 'Test RA') == 'Research Assistants'
        assert_no_empty_lists(real_copy)

    def test_real_current_headings_stay_in_seniority_order(self, real_copy):
        sync_member_role(real_copy, 'Test Manager', 'lab manager', 2026)
        sync_member_role(real_copy, 'Test RA', 'research assistant', 2026)

        current = headings_in(real_copy, 'Current lab members', 'Lab alumni')
        assert current == sorted(current, key=ROLE_ORDER.index)

    def test_real_role_change_matches_the_xinming_xu_shape(self, real_copy):
        """Research Assistant -> Graduate Student, the transition Xinming Xu made."""
        sync_member_role(real_copy, 'Test RA', 'research assistant', 2024)
        assert sync_member_role(
            real_copy, 'Test RA', 'grad student', 2026) == 'role-changed'

        by_role = {r['role_category']: r for r in parse_members_chapter(real_copy)
                   if r['name'] == 'Test RA'}
        assert by_role['Research Assistants']['end_year'] == 2026
        assert by_role['Graduate Students']['is_active']
        # The RA block held only this person, so it must be gone from Current.
        assert 'Research Assistants' not in headings_in(
            real_copy, 'Current lab members', 'Lab alumni')
        assert_no_empty_lists(real_copy)

    def test_existing_members_are_untouched_by_a_new_block(self, real_copy):
        before = {(r['name'], r['role_category'], r['is_active'])
                  for r in parse_members_chapter(real_copy)}

        sync_member_role(real_copy, 'Test Manager', 'lab manager', 2026)

        after = {(r['name'], r['role_category'], r['is_active'])
                 for r in parse_members_chapter(real_copy)}
        assert after - before == {('Test Manager', 'Lab Managers', True)}
        assert before - after == set()


# The real lab_manual.tex writes some entries with the list terminator riding
# on the same line as the last \item, e.g.
#   \item Caroline Lee (2019 -- 2021)\end{list}
# There are three such lines in the live file.
CRAMPED_TEX = textwrap.dedent(r"""
    \chapter{Lab members and alumni}\label{ch:members}
    \begin{fullwidth}
    \subsection{Current lab members}\label{sec:curr_members}
    \newthought{PI}
    \bigskip

    \enskip Jeremy R. Manning (2015 -- )

    \newthought{Graduate Students}
    \begin{multicols}{2}\raggedcolumns
    \begin{list}{\quad}{}
    \item Alice Smith (2022 -- )
    \item Bob Jones (2023 -- )\end{list}
    \end{multicols}

    \newthought{Undergraduate RAs}
    \begin{multicols}{2}\raggedcolumns
    \begin{list}{\quad}{}
    \item Charlie Brown (2024 -- )
    \end{list}
    \end{multicols}

    \newpage

    \subsection{Lab alumni}
    \newthought{Graduate Students}
    \begin{multicols}{2}\raggedcolumns
    \begin{list}{\quad}{}
    \item Dana White (2018 -- 2022)\end{list}
    \end{multicols}
    \end{fullwidth}
""").strip()


def assert_environments_balanced(tex_path):
    """\\begin and \\end counts must match for every environment we touch."""
    content = tex_path.read_text(encoding='utf-8')
    uncommented = '\n'.join(
        line for line in content.split('\n') if not line.strip().startswith('%')
    )
    for env in ('list', 'multicols', 'fullwidth'):
        opens = len(re.findall(r'\\begin\{' + env + r'\}', uncommented))
        closes = len(re.findall(r'\\end\{' + env + r'\}', uncommented))
        assert opens == closes, (
            f"{env}: {opens} begin vs {closes} end -- LaTeX would not build"
        )


class TestSameLineListTerminator:
    """Removing an \\item must not take a trailing \\end{list} with it."""

    @pytest.fixture
    def cramped(self, tmp_path):
        p = tmp_path / 'lab_manual.tex'
        p.write_text(CRAMPED_TEX, encoding='utf-8')
        return p

    def test_removing_it_keeps_the_terminator(self, cramped):
        move_member_to_alumni(cramped, 'Bob Jones', 2026)

        content = cramped.read_text(encoding='utf-8')
        current = content[content.index(r'\subsection{Current lab members}'):
                          content.index(r'\subsection{Lab alumni}')]
        assert 'Bob Jones' not in current
        # The \end{list} that shared his line must still be there.
        assert content.count(r'\end{list}') == content.count(r'\begin{list}')
        assert_environments_balanced(cramped)

    def test_the_role_block_survives(self, cramped):
        move_member_to_alumni(cramped, 'Bob Jones', 2026)

        assert 'Graduate Students' in headings_in(
            cramped, 'Current lab members', 'Lab alumni')
        active = {r['name'] for r in parse_members_chapter(cramped) if r['is_active']}
        assert 'Alice Smith' in active

    def test_removing_the_last_one_still_balances(self, cramped):
        move_member_to_alumni(cramped, 'Bob Jones', 2026)
        move_member_to_alumni(cramped, 'Alice Smith', 2026)

        assert_environments_balanced(cramped)
        assert 'Graduate Students' not in headings_in(
            cramped, 'Current lab members', 'Lab alumni')

    def test_alumni_entry_lands_beside_a_cramped_one(self, cramped):
        move_member_to_alumni(cramped, 'Bob Jones', 2026)

        record = next(r for r in parse_members_chapter(cramped)
                      if r['name'] == 'Bob Jones')
        assert record['end_year'] == 2026
        assert not record['is_active']
        assert_environments_balanced(cramped)


class TestRoleBlockScoping:
    """A role heading must never capture a different role's list."""

    def test_pi_does_not_capture_the_next_role(self, tex_file):
        """'PI' is bare text with no list, so a greedy match ran into the
        Graduate Students list and filed the new entry there.
        """
        with pytest.raises(ValueError, match="Unknown role"):
            add_member_to_lab_manual(tex_file, 'Fake Person', 'PI', 2026)

        assert 'Fake Person' not in tex_file.read_text(encoding='utf-8')

    def test_find_role_block_returns_none_for_a_listless_heading(self, tex_file):
        content = tex_file.read_text(encoding='utf-8')
        section = content[content.index(r'\subsection{Current lab members}'):
                          content.index(r'\subsection{Lab alumni}')]
        assert _find_role_block(section, 'PI') is None

    def test_commented_out_list_under_a_live_heading_is_not_used(self, tmp_path):
        """A live heading over a commented list must not receive a live \\item."""
        tex = MINIMAL_TEX.replace(
            '\\newthought{Undergraduate RAs}\n'
            '\\begin{multicols}{2}\\raggedcolumns\n'
            '\\begin{list}{\\quad}{}\n'
            '\\item Charlie Brown (2024 -- )\n'
            '\\end{list}\n'
            '\\end{multicols}',
            '\\newthought{Undergraduate RAs}\n'
            '% \\begin{multicols}{2}\\raggedcolumns\n'
            '% \\begin{list}{\\quad}{}\n'
            '% \\end{list}\n'
            '% \\end{multicols}'
        )
        p = tmp_path / 'lab_manual.tex'
        p.write_text(tex, encoding='utf-8')

        add_member_to_lab_manual(p, 'New Undergrad', 'undergrad', 2026)

        content = p.read_text(encoding='utf-8')
        for line in content.split('\n'):
            if 'New Undergrad' in line:
                assert not line.strip().startswith('%'), (
                    "the entry was written inside a commented-out block"
                )
        assert_environments_balanced(p)


class TestRemoveRoleBlockPrecision:
    """_remove_role_block must take exactly its own block."""

    def test_it_takes_the_end_multicols_too(self, tex_file):
        add_member_to_lab_manual(tex_file, 'Only Manager', 'lab manager', 2026)
        move_member_to_alumni(tex_file, 'Only Manager', 2027)
        assert_environments_balanced(tex_file)

    def test_it_leaves_the_following_heading_intact(self, tex_file):
        add_member_to_lab_manual(tex_file, 'Only Manager', 'lab manager', 2026)
        before = headings_in(tex_file, 'Current lab members', 'Lab alumni')
        move_member_to_alumni(tex_file, 'Only Manager', 2027)
        after = headings_in(tex_file, 'Current lab members', 'Lab alumni')

        assert set(before) - set(after) == {'Lab Managers'}

    def test_it_does_not_eat_the_newpage(self, tmp_path):
        p = tmp_path / 'lab_manual.tex'
        p.write_text(CRAMPED_TEX, encoding='utf-8')

        add_member_to_lab_manual(p, 'Only Manager', 'lab manager', 2026)
        move_member_to_alumni(p, 'Only Manager', 2027)

        content = p.read_text(encoding='utf-8')
        current = content[content.index(r'\subsection{Current lab members}'):
                          content.index(r'\subsection{Lab alumni}')]
        assert r'\newpage' in current

    def test_a_block_with_no_multicols_wrapper_is_removed_cleanly(self, tmp_path):
        tex = MINIMAL_TEX.replace(
            '\\newthought{Undergraduate RAs}\n'
            '\\begin{multicols}{2}\\raggedcolumns\n'
            '\\begin{list}{\\quad}{}\n'
            '\\item Charlie Brown (2024 -- )\n'
            '\\end{list}\n'
            '\\end{multicols}',
            '\\newthought{Undergraduate RAs}\n'
            '\\begin{list}{\\quad}{}\n'
            '\\item Charlie Brown (2024 -- )\n'
            '\\end{list}'
        )
        p = tmp_path / 'lab_manual.tex'
        p.write_text(tex, encoding='utf-8')

        move_member_to_alumni(p, 'Charlie Brown', 2026)
        assert_environments_balanced(p)


class TestStaleClosedCurrentEntry:
    """A Current entry closed in place must not crash sync_member_role."""

    @pytest.fixture
    def stale(self, tmp_path):
        p = tmp_path / 'lab_manual.tex'
        p.write_text(
            MINIMAL_TEX.replace(
                r'\item Charlie Brown (2024 -- )',
                r'\item Charlie Brown (2024 -- 2025)'
            ),
            encoding='utf-8'
        )
        return p

    def test_find_current_role_ignores_a_closed_entry(self, stale):
        assert find_current_role(stale, 'Charlie Brown') is None

    def test_sync_does_not_raise(self, stale):
        # Must reach a decision rather than blowing up inside
        # move_member_to_alumni, which can only close an OPEN range.
        outcome = sync_member_role(stale, 'Charlie Brown', 'grad student', 2026)
        assert outcome in {'added', 'unchanged', 'role-changed'}
        assert_environments_balanced(stale)


class TestStarredEntries:
    """The real CV marks senior-thesis students with '*', and the lab manual
    guard mirrors that so a starred entry is the same person.
    """

    def test_a_starred_open_entry_blocks_a_duplicate(self, tmp_path):
        p = tmp_path / 'lab_manual.tex'
        p.write_text(
            MINIMAL_TEX.replace(
                r'\item Charlie Brown (2024 -- )',
                r'\item Charlie Brown* (2024 -- )'
            ),
            encoding='utf-8'
        )
        assert add_member_to_lab_manual(p, 'Charlie Brown', 'undergrad', 2026) is False

    def test_a_starred_entry_is_found_by_find_current_role(self, tmp_path):
        p = tmp_path / 'lab_manual.tex'
        p.write_text(
            MINIMAL_TEX.replace(
                r'\item Charlie Brown (2024 -- )',
                r'\item Charlie Brown* (2024 -- )'
            ),
            encoding='utf-8'
        )
        assert find_current_role(p, 'Charlie Brown') == 'Undergraduate RAs'


class TestRealManualStaysBuildable:
    """Every mutation of the real file must leave balanced environments."""

    @pytest.fixture
    def real_copy(self, tmp_path):
        real = Path(__file__).parent.parent / 'lab-manual' / 'lab_manual.tex'
        if not real.exists():
            pytest.skip("lab-manual submodule not initialized")
        target = tmp_path / 'lab_manual.tex'
        target.write_text(real.read_text(encoding='utf-8'), encoding='utf-8')
        return target

    def test_starting_point_is_balanced(self, real_copy):
        assert_environments_balanced(real_copy)

    def test_offboarding_a_real_member_keeps_it_balanced(self, real_copy):
        move_member_to_alumni(real_copy, 'Ansh Patel', 2026)
        assert_environments_balanced(real_copy)

    def test_a_full_round_trip_keeps_it_balanced(self, real_copy):
        sync_member_role(real_copy, 'Test Manager', 'lab manager', 2026)
        sync_member_role(real_copy, 'Test RA', 'research assistant', 2026)
        sync_member_role(real_copy, 'Test RA', 'grad student', 2027)
        move_member_to_alumni(real_copy, 'Test Manager', 2027)
        move_member_to_alumni(real_copy, 'Test RA', 2028)
        assert_environments_balanced(real_copy)
        assert_no_empty_lists(real_copy)
