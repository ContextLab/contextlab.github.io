#!/usr/bin/env python3
"""Build publications.html from spreadsheet data.

Reads data from data/publications.xlsx and generates publications.html
using the template in templates/publications.html.
"""
from pathlib import Path
from typing import List, Dict, Any
import openpyxl

from utils import inject_content


def load_publications(xlsx_path: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Load all publication data from Excel spreadsheet.

    Args:
        xlsx_path: Path to the publications.xlsx file

    Returns:
        Dictionary with keys for each section (papers, chapters, etc.)
        Each value is a list of publication dictionaries.
    """
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)

    data = {}
    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]

        # Get headers from first row
        headers = [cell.value for cell in sheet[1]]

        rows = []
        for row in sheet.iter_rows(min_row=2, values_only=True):
            # Skip empty rows
            if not any(cell is not None for cell in row):
                continue

            row_dict = {}
            for header, value in zip(headers, row):
                if value is None:
                    row_dict[header] = ''
                else:
                    row_dict[header] = value
            rows.append(row_dict)

        data[sheet_name] = rows

    wb.close()
    return data


def generate_publication_card(pub: Dict[str, Any]) -> str:
    """Generate HTML for a single publication card.

    Args:
        pub: Dictionary with publication data (image, title, title_url, citation, links_html)

    Returns:
        HTML string for the publication card
    """
    image = pub.get('image', '')
    title = pub.get('title', '')
    title_url = pub.get('title_url', '')
    citation = pub.get('citation', '')
    links_html = pub.get('links_html', '')

    # Build image path - prepend directory if not empty
    if image:
        image_src = f"images/publications/{image}"
    else:
        image_src = ""

    # Build title HTML
    if title_url:
        title_html = f'<a href="{title_url}" target="_blank">{title}</a>'
    else:
        title_html = title

    # Build links paragraph if we have links
    links_p = ''
    if links_html:
        links_p = f'\n                        <p class="publication-links">{links_html}</p>'

    # Build citation paragraph if we have citation
    citation_p = ''
    if citation:
        citation_p = f'\n                        <p>{citation}</p>'

    html = f'''                <div class="publication-card">
                    <img src="{image_src}" alt="Publication thumbnail">
                    <div>
                        <h4>{title_html}</h4>{citation_p}{links_p}
                    </div>
                </div>'''

    return html


def generate_section_content(publications: List[Dict[str, Any]]) -> str:
    """Generate HTML content for a publications section.

    Args:
        publications: List of publication dictionaries

    Returns:
        HTML string with all publication cards for the section
    """
    cards = [generate_publication_card(pub) for pub in publications]
    return '\n\n'.join(cards)


def build_publications(
    data_path: Path,
    template_path: Path,
    output_path: Path
) -> None:
    """Build publications.html from data and template.

    Args:
        data_path: Path to publications.xlsx
        template_path: Path to template HTML file
        output_path: Path for generated HTML file
    """
    # Load data
    data = load_publications(data_path)

    # Generate content for each section
    replacements = {
        'PAPERS_CONTENT': generate_section_content(data.get('papers', [])),
        'CHAPTERS_CONTENT': generate_section_content(data.get('chapters', [])),
        'DISSERTATIONS_CONTENT': generate_section_content(data.get('dissertations', [])),
        'TALKS_CONTENT': generate_section_content(data.get('talks', [])),
        'COURSES_CONTENT': generate_section_content(data.get('courses', [])),
        'POSTERS_CONTENT': generate_section_content(data.get('posters', [])),
    }

    # Inject into template
    inject_content(template_path, output_path, replacements)

    # Report
    total = sum(len(items) for items in data.values())
    print(f"Generated {output_path} with {total} publications")


def main():
    """Main entry point for CLI usage."""
    project_root = Path(__file__).parent.parent
    data_path = project_root / 'data' / 'publications.xlsx'
    template_path = project_root / 'templates' / 'publications.html'
    output_path = project_root / 'publications.html'

    build_publications(data_path, template_path, output_path)


if __name__ == '__main__':
    main()
