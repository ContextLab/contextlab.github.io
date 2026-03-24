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
