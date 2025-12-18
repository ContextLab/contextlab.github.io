#!/usr/bin/env python3
"""Master build script for the Context Lab website.

Generates all HTML pages from spreadsheet data and templates.
Run this script to regenerate all content pages.
"""
import sys
from pathlib import Path

from build_publications import build_publications
from build_people import build_people
from build_software import build_software
from build_news import build_news


def main():
    """Build all content pages."""
    project_root = Path(__file__).parent.parent

    data_dir = project_root / 'data'
    templates_dir = project_root / 'templates'

    # Track build results
    results = []

    # Build publications.html
    try:
        build_publications(
            data_dir / 'publications.xlsx',
            templates_dir / 'publications.html',
            project_root / 'publications.html'
        )
        results.append(('publications.html', 'OK'))
    except Exception as e:
        results.append(('publications.html', f'FAILED: {e}'))

    # Build people.html
    try:
        build_people(
            data_dir / 'people.xlsx',
            templates_dir / 'people.html',
            project_root / 'people.html'
        )
        results.append(('people.html', 'OK'))
    except Exception as e:
        results.append(('people.html', f'FAILED: {e}'))

    # Build software.html
    try:
        build_software(
            data_dir / 'software.xlsx',
            templates_dir / 'software.html',
            project_root / 'software.html'
        )
        results.append(('software.html', 'OK'))
    except Exception as e:
        results.append(('software.html', f'FAILED: {e}'))

    # Build news.html
    try:
        build_news(
            data_dir / 'news.xlsx',
            templates_dir / 'news.html',
            project_root / 'news.html'
        )
        results.append(('news.html', 'OK'))
    except Exception as e:
        results.append(('news.html', f'FAILED: {e}'))

    # Print summary
    print("\n" + "=" * 50)
    print("Build Summary")
    print("=" * 50)

    failed = 0
    for page, status in results:
        print(f"  {page}: {status}")
        if status != 'OK':
            failed += 1

    print("=" * 50)

    if failed > 0:
        print(f"Build completed with {failed} error(s)")
        sys.exit(1)
    else:
        print("Build completed successfully!")
        sys.exit(0)


if __name__ == '__main__':
    main()
