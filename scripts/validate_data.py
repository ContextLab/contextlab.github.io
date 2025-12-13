#!/usr/bin/env python3
"""Validate spreadsheet data before building.

Checks for common issues like missing required fields,
invalid URLs, and missing image files.
"""
import sys
from pathlib import Path
from typing import List, Tuple

from utils import (
    load_spreadsheet_all_sheets,
    validate_url_format,
    check_file_exists,
)


def validate_publications(project_root: Path) -> List[str]:
    """Validate publications.xlsx data.

    Returns list of error messages (empty if valid).
    """
    errors = []
    xlsx_path = project_root / 'data' / 'publications.xlsx'

    if not xlsx_path.exists():
        errors.append(f"Missing file: {xlsx_path}")
        return errors

    try:
        data = load_spreadsheet_all_sheets(xlsx_path)
    except Exception as e:
        errors.append(f"Error loading {xlsx_path}: {e}")
        return errors

    required_fields = ['title', 'citation']
    image_dir = project_root / 'images' / 'publications'

    for sheet_name, items in data.items():
        for i, item in enumerate(items, 1):
            # Check required fields
            for field in required_fields:
                val = item.get(field, '')
                if not val or (isinstance(val, str) and not val.strip()):
                    errors.append(f"publications/{sheet_name} row {i}: missing {field}")

            # Check URL format (validate_url_format returns True if valid)
            url = item.get('title_url', '')
            if url and not validate_url_format(url):
                errors.append(f"publications/{sheet_name} row {i}: invalid URL '{url}'")

            # Check image file exists (check_file_exists returns error msg or None)
            if item.get('image'):
                file_error = check_file_exists(item['image'], image_dir)
                if file_error:
                    errors.append(f"publications/{sheet_name} row {i}: {file_error}")

    return errors


def validate_people(project_root: Path) -> List[str]:
    """Validate people.xlsx data.

    Returns list of error messages (empty if valid).
    """
    errors = []
    xlsx_path = project_root / 'data' / 'people.xlsx'

    if not xlsx_path.exists():
        errors.append(f"Missing file: {xlsx_path}")
        return errors

    try:
        data = load_spreadsheet_all_sheets(xlsx_path)
    except Exception as e:
        errors.append(f"Error loading {xlsx_path}: {e}")
        return errors

    image_dir = project_root / 'images' / 'people'

    # Validate director
    if 'director' in data:
        for i, item in enumerate(data['director'], 1):
            if not item.get('name'):
                errors.append(f"people/director row {i}: missing name")
            if item.get('image'):
                file_error = check_file_exists(item['image'], image_dir)
                if file_error:
                    errors.append(f"people/director row {i}: {file_error}")

    # Validate members
    if 'members' in data:
        for i, item in enumerate(data['members'], 1):
            if not item.get('name'):
                errors.append(f"people/members row {i}: missing name")
            if item.get('image'):
                file_error = check_file_exists(item['image'], image_dir)
                if file_error:
                    errors.append(f"people/members row {i}: {file_error}")
            url = item.get('name_url', '')
            if url and not validate_url_format(url):
                errors.append(f"people/members row {i}: invalid URL '{url}'")

    # Validate alumni sheets
    for sheet_name in ['alumni_postdocs', 'alumni_grads', 'alumni_managers']:
        if sheet_name in data:
            for i, item in enumerate(data[sheet_name], 1):
                if not item.get('name'):
                    errors.append(f"people/{sheet_name} row {i}: missing name")
                url = item.get('name_url', '')
                if url and not validate_url_format(url):
                    errors.append(f"people/{sheet_name} row {i}: invalid URL '{url}'")
                pos_url = item.get('current_position_url', '')
                if pos_url and not validate_url_format(pos_url):
                    errors.append(f"people/{sheet_name} row {i}: invalid position URL '{pos_url}'")

    # Validate undergrads
    if 'alumni_undergrads' in data:
        for i, item in enumerate(data['alumni_undergrads'], 1):
            if not item.get('name'):
                errors.append(f"people/alumni_undergrads row {i}: missing name")

    # Validate collaborators
    if 'collaborators' in data:
        for i, item in enumerate(data['collaborators'], 1):
            if not item.get('name'):
                errors.append(f"people/collaborators row {i}: missing name")
            url = item.get('url', '')
            if url and not validate_url_format(url):
                errors.append(f"people/collaborators row {i}: invalid URL '{url}'")

    return errors


def validate_software(project_root: Path) -> List[str]:
    """Validate software.xlsx data.

    Returns list of error messages (empty if valid).
    """
    errors = []
    xlsx_path = project_root / 'data' / 'software.xlsx'

    if not xlsx_path.exists():
        errors.append(f"Missing file: {xlsx_path}")
        return errors

    try:
        data = load_spreadsheet_all_sheets(xlsx_path)
    except Exception as e:
        errors.append(f"Error loading {xlsx_path}: {e}")
        return errors

    for sheet_name, items in data.items():
        for i, item in enumerate(items, 1):
            if not item.get('name'):
                errors.append(f"software/{sheet_name} row {i}: missing name")
            if not item.get('description'):
                errors.append(f"software/{sheet_name} row {i}: missing description")

    return errors


def validate_templates(project_root: Path) -> List[str]:
    """Validate that all required templates exist.

    Returns list of error messages (empty if valid).
    """
    errors = []
    templates_dir = project_root / 'templates'

    required_templates = [
        'publications.html',
        'people.html',
        'software.html'
    ]

    for template in required_templates:
        template_path = templates_dir / template
        if not template_path.exists():
            errors.append(f"Missing template: {template_path}")

    return errors


def main():
    """Run all validations and report results."""
    project_root = Path(__file__).parent.parent

    print("Validating data files...")
    print("=" * 50)

    all_errors = []

    # Validate templates first
    template_errors = validate_templates(project_root)
    if template_errors:
        print("\nTemplate errors:")
        for error in template_errors:
            print(f"  - {error}")
        all_errors.extend(template_errors)
    else:
        print("Templates: OK")

    # Validate publications
    pub_errors = validate_publications(project_root)
    if pub_errors:
        print("\nPublications errors:")
        for error in pub_errors:
            print(f"  - {error}")
        all_errors.extend(pub_errors)
    else:
        print("Publications: OK")

    # Validate people
    people_errors = validate_people(project_root)
    if people_errors:
        print("\nPeople errors:")
        for error in people_errors:
            print(f"  - {error}")
        all_errors.extend(people_errors)
    else:
        print("People: OK")

    # Validate software
    sw_errors = validate_software(project_root)
    if sw_errors:
        print("\nSoftware errors:")
        for error in sw_errors:
            print(f"  - {error}")
        all_errors.extend(sw_errors)
    else:
        print("Software: OK")

    # Summary
    print("\n" + "=" * 50)
    if all_errors:
        print(f"Validation completed with {len(all_errors)} error(s)")
        sys.exit(1)
    else:
        print("Validation completed successfully!")
        sys.exit(0)


if __name__ == '__main__':
    main()
