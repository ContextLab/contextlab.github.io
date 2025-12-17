#!/usr/bin/env python3
"""Utilities for formatting citations and handling links.

Provides functions to:
- Convert markdown to HTML
- Format bibliographic citations from structured data
- Handle file paths (converting local paths to GitHub URLs)
- Build link HTML from URLs or local file paths
"""
import re
from typing import Optional, List, Tuple
from pathlib import Path

# GitHub repository URL for the project
GITHUB_REPO_URL = "https://github.com/ContextLab/contextlab.github.io/blob/main"
GITHUB_PAGES_URL = "https://contextlab.github.io"


def markdown_to_html(text: str) -> str:
    """Convert markdown formatting to HTML.

    Supports:
    - **bold** or __bold__ -> <strong>bold</strong>
    - *italic* or _italic_ -> <em>italic</em>
    - [text](url) -> <a href="url" target="_blank">text</a>

    Args:
        text: Markdown-formatted string

    Returns:
        HTML-formatted string
    """
    if not text:
        return ''

    # Convert **bold** or __bold__ to <strong> BEFORE processing links
    # This prevents issues with underscores in URLs
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__([^_]+)__', r'<strong>\1</strong>', text)

    # Convert *italic* or _italic_ to <em> BEFORE processing links
    # Only match when underscores/asterisks are at word boundaries (not inside URLs)
    # Be careful not to match ** or __
    text = re.sub(r'(?<!\*)\*(?!\*)([^*]+)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)
    # For underscores, require word boundary or whitespace to avoid matching URL patterns
    text = re.sub(r'(?<![a-zA-Z0-9])_([^_\s][^_]*)_(?![a-zA-Z0-9])', r'<em>\1</em>', text)

    # Convert markdown links [text](url) to HTML AFTER processing bold/italic
    text = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)',
        r'<a href="\2" target="_blank">\1</a>',
        text
    )

    return text


def resolve_link(link: str, base_path: str = "data/pdfs") -> str:
    """Resolve a link to a full URL.

    If the link is already a URL (http/https), return it as-is.
    If the link is a local path:
      - HTML files use GitHub Pages URL (so they render as webpages)
      - Other files use GitHub blob URL (for viewing/downloading)

    Args:
        link: URL or filename or path
        base_path: Base path for local files (default: data/pdfs)

    Returns:
        Full URL
    """
    if not link:
        return ''

    link = link.strip()

    # Already a full URL
    if link.startswith('http://') or link.startswith('https://'):
        return link

    # Remove leading slash if present
    link = link.lstrip('/')

    # Determine the full path
    if '/' in link:
        full_path = link
    else:
        full_path = f"{base_path}/{link}"

    # HTML files should use GitHub Pages URL so they render as webpages
    if full_path.endswith('.html'):
        return f"{GITHUB_PAGES_URL}/{full_path}"

    # Other files use GitHub blob URL
    return f"{GITHUB_REPO_URL}/{full_path}"


def build_links_html(links: List[Tuple[str, str]], base_path: str = "data/pdfs") -> str:
    """Build HTML for a list of links.

    Args:
        links: List of (label, url_or_path) tuples
        base_path: Base path for local files

    Returns:
        HTML string like '[<a href="...">PDF</a>] [<a href="...">CODE</a>]'
    """
    if not links:
        return ''

    parts = []
    for label, url_or_path in links:
        if not url_or_path:
            continue
        resolved_url = resolve_link(url_or_path, base_path)
        parts.append(f'[<a href="{resolved_url}" target="_blank">{label}</a>]')

    return ' '.join(parts)


def format_authors(authors: str) -> str:
    """Format author string, ensuring proper formatting.

    Args:
        authors: Author string (e.g., "Fitzpatrick PC, Heusser AC, Manning JR")

    Returns:
        Formatted author string (same format, but cleaned)
    """
    if not authors:
        return ''
    return authors.strip()


def format_paper_citation(
    authors: str,
    year: str,
    title: str,
    journal: str,
    volume: str = '',
    issue: str = '',
    pages: str = '',
    doi: str = '',
    article_number: str = '',
    status: str = '',  # e.g., "In press", "Preprint"
    preprint_id: str = ''  # e.g., "2510.21958" for arXiv
) -> str:
    """Format a journal paper citation.

    Format: Authors (Year). Title. <em>Journal</em>, Volume(Issue): Pages.

    Args:
        authors: Author string
        year: Publication year
        title: Paper title
        journal: Journal name (will be italicized)
        volume: Volume number
        issue: Issue number
        pages: Page range
        doi: DOI (optional)
        article_number: Article number for online journals
        status: Publication status (e.g., "In press")
        preprint_id: Preprint identifier (e.g., "2510.21958" for arXiv)

    Returns:
        Formatted citation HTML
    """
    parts = []

    # Authors (Year).
    if authors:
        parts.append(f"{format_authors(authors)} ({year}).")

    # Title.
    if title:
        parts.append(f"{title}.")

    # Journal with formatting
    journal_part = f"<em>{journal}</em>"

    # Handle preprint IDs specially (arXiv, bioRxiv, etc.)
    if preprint_id:
        journal_part += f": {preprint_id}"
    elif volume:
        journal_part += f", {volume}"
        if issue:
            journal_part += f"({issue})"
        if pages:
            journal_part += f": {pages}"
        elif article_number:
            journal_part += f": {article_number}"
    elif status:
        journal_part += f": {status}"

    journal_part += "."
    parts.append(journal_part)

    return ' '.join(parts)


def format_preprint_citation(
    authors: str,
    year: str,
    title: str,
    archive: str,  # e.g., "arXiv", "bioRxiv", "PsyArXiv"
    archive_id: str  # e.g., "2510.21958"
) -> str:
    """Format a preprint citation.

    Format: Authors (Year). Title. <em>Archive</em>: ID.

    Args:
        authors: Author string
        year: Year
        title: Paper title
        archive: Archive name (arXiv, bioRxiv, etc.)
        archive_id: Archive identifier

    Returns:
        Formatted citation HTML
    """
    return f"{format_authors(authors)} ({year}). {title}. <em>{archive}</em>: {archive_id}."


def format_chapter_citation(
    authors: str,
    year: str,
    title: str,
    editors: str,
    book_title: str,
    publisher_location: str,
    publisher: str
) -> str:
    """Format a book chapter citation.

    Format: Authors (Year) Title. Appears in Editors, Ed. <em>Book Title.</em> Location: Publisher.

    Args:
        authors: Author string
        year: Publication year
        title: Chapter title
        editors: Editor(s) string (e.g., "Kahana MJ and Wagner AD")
        book_title: Book title (will be italicized)
        publisher_location: Publisher location (e.g., "Oxford, UK")
        publisher: Publisher name

    Returns:
        Formatted citation HTML
    """
    parts = [f"{format_authors(authors)} ({year}) {title}."]

    if editors:
        parts.append(f"Appears in {editors}, Ed.")

    parts.append(f"<em>{book_title}.</em>")

    if publisher_location and publisher:
        parts.append(f"{publisher_location}: {publisher}.")
    elif publisher:
        parts.append(f"{publisher}.")

    return ' '.join(parts)


def format_dissertation_citation(
    authors: str,
    year: str,
    title: str,
    degree_type: str,  # "Doctoral dissertation" or "Senior thesis"
    institution: str,
    location: str
) -> str:
    """Format a dissertation/thesis citation.

    Format: Authors (Year) Title. <em>Degree type: Institution</em>, Location.

    Args:
        authors: Author string
        year: Year
        title: Dissertation title
        degree_type: Type of degree (e.g., "Doctoral dissertation", "Senior thesis")
        institution: Institution name
        location: Location (city, state)

    Returns:
        Formatted citation HTML
    """
    return f"{format_authors(authors)} ({year}) {title}. <em>{degree_type}: {institution}</em>, {location}."


def format_talk_citation(
    authors: str,
    year: str,
    title: str,
    venue_name: str,
    venue_url: str = ''
) -> str:
    """Format a talk/presentation citation.

    Format: Authors (Year) Title. Talk given at <em>Venue</em>.

    Args:
        authors: Author string
        year: Year
        title: Talk title
        venue_name: Name of venue/event
        venue_url: URL for venue (optional)

    Returns:
        Formatted citation HTML
    """
    if venue_url:
        venue_html = f'<a href="{venue_url}" target="_blank"><em>{venue_name}</em></a>'
    else:
        venue_html = f'<em>{venue_name}</em>'

    return f"{format_authors(authors)} ({year}) {title}. Talk given at the {venue_html}."


def format_poster_citation(
    authors: str,
    year: str,
    title: str,
    conference: str,
    location: str,
    session_number: str = ''
) -> str:
    """Format a poster/abstract citation.

    Format: Authors (Year) Title. <em>Conference.</em> Location. Session#.

    Args:
        authors: Author string
        year: Year
        title: Poster title
        conference: Conference name
        location: Conference location
        session_number: Session/poster number (optional)

    Returns:
        Formatted citation HTML
    """
    parts = [f"{format_authors(authors)} ({year}) {title}. <em>{conference}.</em> {location}."]

    if session_number:
        parts.append(session_number + ".")

    return ' '.join(parts)


def format_course_citation(description: str) -> str:
    """Format a course description.

    Converts markdown to HTML.

    Args:
        description: Course description (may include markdown)

    Returns:
        HTML-formatted description
    """
    return markdown_to_html(description)


def parse_existing_citation(citation: str, pub_type: str) -> dict:
    """Parse an existing HTML citation into component fields.

    This is used for migrating existing data to the new format.

    Args:
        citation: Existing HTML citation string
        pub_type: Type of publication ('paper', 'chapter', 'dissertation', 'talk', 'poster', 'course')

    Returns:
        Dictionary of parsed fields
    """
    result = {
        'authors': '',
        'year': '',
        'title': '',
        'original_citation': citation
    }

    if not citation:
        return result

    # Common pattern: "Authors (Year) Title. Rest..."
    # or "Authors (Year). Title. Rest..."
    match = re.match(r'^([^(]+)\s*\((\d{4})\)\.?\s*(.+)$', citation, re.DOTALL)
    if match:
        result['authors'] = match.group(1).strip()
        result['year'] = match.group(2)
        rest = match.group(3)

        # For papers, the title ends at the first period before <em>
        if pub_type == 'paper':
            # Find title - everything before first ". <em>" or ".<em>"
            title_match = re.match(r'^([^.]+(?:\.[^.]+)*?)\.?\s*<em>', rest)
            if title_match:
                result['title'] = title_match.group(1).strip()
                journal_rest = rest[title_match.end()-4:]  # Include the <em>

                # Parse journal info
                journal_match = re.match(r'<em>([^<]+)</em>', journal_rest)
                if journal_match:
                    result['journal'] = journal_match.group(1).strip(':,. ')

                    # Try to parse volume, issue, pages
                    after_journal = journal_rest[journal_match.end():]
                    vol_match = re.match(r'[,:]\s*(\d+)(?:\((\d+)\))?(?:[,:]?\s*(.+?))?\.?$', after_journal.strip())
                    if vol_match:
                        result['volume'] = vol_match.group(1) or ''
                        result['issue'] = vol_match.group(2) or ''
                        result['pages'] = vol_match.group(3).strip(' .') if vol_match.group(3) else ''
                    else:
                        # Check for status like "In press" or article number
                        status_match = re.search(r':\s*(.+?)\.?$', after_journal.strip())
                        if status_match:
                            result['status'] = status_match.group(1).strip()

        elif pub_type == 'poster':
            # Title ends before <em>
            title_match = re.match(r'^(.+?)\.\s*<em>', rest)
            if title_match:
                result['title'] = title_match.group(1).strip()

                # Parse conference and location
                conf_match = re.search(r'<em>([^<]+)</em>\.?\s*([^.]+(?:\.[^.0-9][^.]*)?)', rest)
                if conf_match:
                    result['conference'] = conf_match.group(1).strip(' .')
                    location_part = conf_match.group(2).strip(' .')
                    # Check for session number at end
                    session_match = re.search(r'(\d+\.\d+(?:/[A-Z]+\d+)?)\s*\.?\s*$', rest)
                    if session_match:
                        result['session_number'] = session_match.group(1)
                        location_part = re.sub(r'\s*\d+\.\d+(?:/[A-Z]+\d+)?\s*\.?\s*$', '', rest)
                        # Re-extract location
                        conf_match = re.search(r'<em>[^<]+</em>\.?\s*([^.]+)', location_part)
                        if conf_match:
                            result['location'] = conf_match.group(1).strip(' .')
                    else:
                        result['location'] = location_part

        elif pub_type == 'dissertation':
            # Title ends before <em>
            title_match = re.match(r'^(.+?)\.\s*<em>', rest)
            if title_match:
                result['title'] = title_match.group(1).strip()

                # Parse degree type and institution
                diss_match = re.search(r'<em>([^:]+):\s*([^<]+)</em>[,.]?\s*(.+?)\.?$', rest)
                if diss_match:
                    result['degree_type'] = diss_match.group(1).strip()
                    result['institution'] = diss_match.group(2).strip()
                    result['location'] = diss_match.group(3).strip(' .')

        elif pub_type == 'chapter':
            # Title ends before "Appears in"
            title_match = re.match(r'^(.+?)\.\s*Appears in', rest)
            if title_match:
                result['title'] = title_match.group(1).strip()

                # Parse editors
                editors_match = re.search(r'Appears in\s+([^,]+,?\s*(?:and\s+[^,]+)?),?\s*Ed(?:s)?\.', rest)
                if editors_match:
                    result['editors'] = editors_match.group(1).strip()

                # Parse book title
                book_match = re.search(r'<em>([^<]+)</em>', rest)
                if book_match:
                    result['book_title'] = book_match.group(1).strip(' .')

                # Parse publisher info
                pub_match = re.search(r'</em>\.?\s*([^:]+):\s*([^.]+)', rest)
                if pub_match:
                    result['publisher_location'] = pub_match.group(1).strip()
                    result['publisher'] = pub_match.group(2).strip(' .')

        elif pub_type == 'talk':
            # Title ends before "Talk given at"
            title_match = re.match(r'^(.+?)\.\s*Talk given at', rest)
            if title_match:
                result['title'] = title_match.group(1).strip()

                # Parse venue (may have link)
                venue_link_match = re.search(r'<a href="([^"]+)"[^>]*><em>([^<]+)</em></a>', rest)
                if venue_link_match:
                    result['venue_url'] = venue_link_match.group(1)
                    result['venue_name'] = venue_link_match.group(2).strip()
                else:
                    venue_match = re.search(r'<em>([^<]+)</em>', rest)
                    if venue_match:
                        result['venue_name'] = venue_match.group(1).strip()

    return result


def parse_links_html(links_html: str) -> List[Tuple[str, str]]:
    """Parse existing links HTML into a list of (label, url) tuples.

    Args:
        links_html: HTML string like '[<a href="...">PDF</a>] [<a href="...">CODE</a>]'

    Returns:
        List of (label, url) tuples
    """
    if not links_html:
        return []

    links = []
    for match in re.finditer(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', links_html):
        url = match.group(1)
        label = match.group(2)
        links.append((label, url))

    return links
