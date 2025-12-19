#!/usr/bin/env python3
"""Build news.html from spreadsheet data.

Reads data from data/news.xlsx and generates news.html
using the template in templates/news.html.
"""
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import openpyxl

from utils import inject_content


def load_news(xlsx_path: Path) -> List[Dict[str, Any]]:
    """Load news items from Excel spreadsheet.

    Args:
        xlsx_path: Path to the news.xlsx file

    Returns:
        List of news item dictionaries, sorted by date (most recent first)
    """
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    sheet = wb.active

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

    wb.close()

    # Sort by date (most recent first)
    # Parse dates in YYYY-MM-DD format
    def parse_date(item):
        date_str = item.get('date', '')
        if not date_str:
            # Items without dates go to the end
            return datetime.min
        try:
            return datetime.strptime(str(date_str), '%Y-%m-%d')
        except (ValueError, TypeError):
            # If date parsing fails, put at end
            return datetime.min

    rows.sort(key=parse_date, reverse=True)

    return rows


def generate_news_item(item: Dict[str, Any]) -> str:
    """Generate HTML for a single news item.

    Args:
        item: Dictionary with news item data (image, title, title_url, content, links_html)

    Returns:
        HTML string for the news item
    """
    image = item.get('image', '')
    title = item.get('title', '')
    title_url = item.get('title_url', '')
    content = item.get('content', '')
    links_html = item.get('links_html', '')

    # Build image path
    image_src = f"images/news/{image}" if image else ""

    # Build title with optional link
    if title_url:
        title_display = f'<a href="{title_url}" target="_blank">{title}</a>'
    else:
        title_display = title

    # Build links paragraph if present
    links_p = ''
    if links_html:
        links_p = f'\n                        <p>{links_html}</p>'

    html = f'''                <div class="news-item">
                    <img src="{image_src}" alt="{title}" class="news-thumbnail">
                    <div class="news-content">
                        <h3>{title_display}</h3>
                        <p>{content}</p>{links_p}
                    </div>
                </div>'''

    return html


def generate_news_content(items: List[Dict[str, Any]]) -> str:
    """Generate HTML content for all news items.

    Args:
        items: List of news item dictionaries

    Returns:
        HTML string with all news items
    """
    if not items:
        return ''

    news_items = [generate_news_item(item) for item in items]
    return '\n\n'.join(news_items)


def build_news(
    data_path: Path,
    template_path: Path,
    output_path: Path
) -> None:
    """Build news.html from data and template.

    Args:
        data_path: Path to news.xlsx
        template_path: Path to template HTML file
        output_path: Path for generated HTML file
    """
    # Load data
    items = load_news(data_path)

    # Generate content
    replacements = {
        'NEWS_CONTENT': generate_news_content(items),
    }

    # Inject into template
    inject_content(template_path, output_path, replacements)

    # Report
    print(f"Generated {output_path} with {len(items)} news items")


def main():
    """Main entry point for CLI usage."""
    project_root = Path(__file__).parent.parent
    data_path = project_root / 'data' / 'news.xlsx'
    template_path = project_root / 'templates' / 'news.html'
    output_path = project_root / 'news.html'

    build_news(data_path, template_path, output_path)


if __name__ == '__main__':
    main()
