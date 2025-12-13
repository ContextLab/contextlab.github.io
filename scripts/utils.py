"""Shared utilities for build scripts.

This module provides common functions for loading spreadsheets,
validating data, and injecting content into HTML templates.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
import openpyxl


def load_spreadsheet(filepath: Path) -> List[Dict[str, Any]]:
    """Load Excel spreadsheet and return list of row dictionaries.

    Args:
        filepath: Path to the .xlsx file

    Returns:
        List of dictionaries, one per row, with column headers as keys.
        Empty cells are converted to empty strings.

    Raises:
        FileNotFoundError: If the spreadsheet doesn't exist
        openpyxl.utils.exceptions.InvalidFileException: If file is not valid xlsx
    """
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    sheet = wb.active

    # Get headers from first row
    headers = [cell.value for cell in sheet[1]]

    # Validate headers - no None values allowed
    if None in headers:
        raise ValueError(f"Spreadsheet has empty header cells: {headers}")

    rows = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        # Skip completely empty rows
        if not any(cell is not None for cell in row):
            continue

        # Create dict, converting None to empty string for consistency
        row_dict = {}
        for header, value in zip(headers, row):
            if value is None:
                row_dict[header] = ''
            else:
                row_dict[header] = value
        rows.append(row_dict)

    wb.close()
    return rows


def inject_content(template_path: Path, output_path: Path,
                   replacements: Dict[str, str]) -> None:
    """Inject generated content into template at marker locations.

    Markers in the template should be HTML comments like: <!-- MARKER_NAME -->

    Args:
        template_path: Path to the template HTML file
        output_path: Path where the generated HTML will be written
        replacements: Dictionary mapping marker names to HTML content

    Raises:
        FileNotFoundError: If template doesn't exist
        ValueError: If a marker is not found in the template
    """
    content = template_path.read_text(encoding='utf-8')

    for marker, html in replacements.items():
        pattern = f'<!-- {marker} -->'
        if pattern not in content:
            raise ValueError(
                f"Marker '{pattern}' not found in template {template_path}"
            )
        content = content.replace(pattern, html)

    output_path.write_text(content, encoding='utf-8')


def validate_required_fields(row: Dict[str, Any], required: List[str],
                             row_num: int) -> List[str]:
    """Validate that required fields are present and non-empty.

    Args:
        row: Dictionary of field values from a spreadsheet row
        required: List of required field names
        row_num: Row number (for error messages), 1-indexed from data rows

    Returns:
        List of error messages (empty if all fields valid)
    """
    errors = []
    for field in required:
        value = row.get(field)
        if value is None or (isinstance(value, str) and value.strip() == ''):
            errors.append(f"Row {row_num}: Missing required field '{field}'")
    return errors


def validate_url_format(url: str) -> bool:
    """Check if a string looks like a valid URL.

    Args:
        url: String to validate

    Returns:
        True if URL starts with http:// or https://, False otherwise
    """
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    return url.startswith('http://') or url.startswith('https://')


def check_file_exists(filepath: Path, base_dir: Path) -> Optional[str]:
    """Check if a referenced file exists.

    Args:
        filepath: Filename (not full path) referenced in spreadsheet
        base_dir: Directory where the file should exist

    Returns:
        Error message if file doesn't exist, None if it exists
    """
    if not filepath or not str(filepath).strip():
        return None  # Empty is OK for optional fields

    full_path = base_dir / str(filepath).strip()
    if not full_path.exists():
        return f"File not found: {full_path}"
    return None
