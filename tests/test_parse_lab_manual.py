"""Tests for parse_lab_manual.py."""
import tempfile
import textwrap
from pathlib import Path

import pytest

from parse_lab_manual import (
    parse_members_chapter,
    add_member_to_lab_manual,
    move_member_to_alumni,
    commit_and_push_lab_manual,
)


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
        with pytest.raises(ValueError, match="Could not find"):
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
        """The guard is per-role, so a role change still records a new entry."""
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

    def test_commented_out_heading_is_refused(self, quirky_tex_file):
        """Inserting into a commented list yields a 'Lonely \\item' LaTeX error."""
        before = quirky_tex_file.read_text(encoding='utf-8')

        with pytest.raises(ValueError, match="Could not find an active"):
            add_member_to_lab_manual(quirky_tex_file, 'New RA', 'research assistant', 2026)

        assert quirky_tex_file.read_text(encoding='utf-8') == before

    def test_alumni_only_role_is_refused(self, quirky_tex_file):
        """'Lab Managers' exists only under Lab alumni, so there is nowhere to add."""
        before = quirky_tex_file.read_text(encoding='utf-8')

        with pytest.raises(ValueError, match="Could not find an active"):
            add_member_to_lab_manual(quirky_tex_file, 'New Manager', 'lab manager', 2026)

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
