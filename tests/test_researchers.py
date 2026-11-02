"""Researcher records stay distinct from student records across the build."""
from pathlib import Path
import shutil

import openpyxl

from build_people import build_people
from onboard_member import add_to_spreadsheet, get_existing_bio, cv_section_for_role
from parse_cv_trainees import parse_cv_trainees
from sync_cv_people import get_target_sheet, get_role_for_spreadsheet

ROOT = Path(__file__).resolve().parents[1]


def test_researcher_sheet_is_rendered_between_grads_and_undergrads(tmp_path):
    output = tmp_path / 'people.html'
    build_people(ROOT / 'data/people.xlsx', ROOT / 'templates/people.html',
                 output, ROOT / 'documents/JRM_CV.tex')
    html = output.read_text()
    assert html.index('claudia gonciulea') < html.index('alishba tahir')
    assert html.index('alishba tahir') < html.index('sarah kerns')
    assert html.index('sarah kerns') < html.index('alexandra wingo')
    assert html.count('alishba tahir | researcher') == 1


def test_researchers_are_not_parsed_as_graduate_or_undergraduate_trainees():
    trainees = parse_cv_trainees(ROOT / 'documents/JRM_CV.tex')
    assert {t.name for t in trainees['researchers']} == {'Sarah Kerns', 'Alishba Tahir'}
    for key in ('grads', 'undergrads'):
        assert not {'Sarah Kerns', 'Alishba Tahir'} & {t.name for t in trainees[key]}
    for trainee in trainees['researchers']:
        assert get_target_sheet(trainee) == 'researchers'
        assert get_role_for_spreadsheet(trainee) == 'researcher'
    assert cv_section_for_role('researcher') == 'researcher'


def test_onboarding_researcher_updates_correct_sheet_without_duplicate(tmp_path):
    path = tmp_path / 'people.xlsx'
    shutil.copy(ROOT / 'data/people.xlsx', path)
    add_to_spreadsheet(path, 'sarah kerns', 'researcher', 'Updated bio for Sarah.', '', '')
    assert get_existing_bio(path, 'Sarah Kerns') == 'Updated bio for Sarah.'
    wb = openpyxl.load_workbook(path)
    assert sum(row[1] == 'sarah kerns' for row in wb['researchers'].values) == 1
    assert all(row[1] != 'sarah kerns' for row in wb['members'].values)
    wb.close()
