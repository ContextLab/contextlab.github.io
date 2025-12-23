#!/usr/bin/env python3
"""
Custom LaTeX to HTML converter for JRM_CV.tex.

This parser handles the specific LaTeX constructs used in the CV
and produces HTML that matches the PDF formatting exactly.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class CVSection:
    """Represents a section of the CV."""
    title: str
    content: str
    subsections: List['CVSection'] = field(default_factory=list)


def read_latex_file(filepath: Path) -> str:
    """Read and return the content of a LaTeX file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def extract_document_body(latex: str) -> str:
    """Extract content between begin document and end document."""
    match = re.search(r'\\begin\{document\}(.+?)\\end\{document\}', latex, re.DOTALL)
    if match:
        return match.group(1)
    return latex


def balanced_braces_extract(text: str, start: int) -> tuple:
    """Extract content within balanced braces starting at position start.
    Returns (content, end_position) or (None, -1) if not found."""
    if start >= len(text) or text[start] != '{':
        return None, -1

    depth = 0
    content_start = start + 1

    for i in range(start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return text[content_start:i], i + 1

    return None, -1


def convert_command(text: str, cmd: str, html_start: str, html_end: str) -> str:
    """Convert a LaTeX command to HTML tags."""
    pattern = '\\' + cmd + '{'
    result = []
    i = 0

    while i < len(text):
        pos = text.find(pattern, i)
        if pos == -1:
            result.append(text[i:])
            break

        result.append(text[i:pos])
        content, end_pos = balanced_braces_extract(text, pos + len(pattern) - 1)

        if content is not None:
            result.append(html_start)
            result.append(content)
            result.append(html_end)
            i = end_pos
        else:
            result.append(text[pos:pos + len(pattern)])
            i = pos + len(pattern)

    return ''.join(result)


def convert_href(text: str) -> str:
    """Convert href commands to HTML links."""
    result = []
    i = 0

    while i < len(text):
        match = re.search(r'\\href\{', text[i:])
        if not match:
            result.append(text[i:])
            break

        pos = i + match.start()
        result.append(text[i:pos])

        # \href{ is 6 chars, { is at position 5 from match start
        brace_pos = pos + 5

        # Extract URL
        url, url_end = balanced_braces_extract(text, brace_pos)
        if url is None:
            result.append(text[pos:pos + 6])
            i = pos + 6
            continue

        # Extract link text
        link_text, text_end = balanced_braces_extract(text, url_end)
        if link_text is None:
            result.append(text[pos:url_end])
            i = url_end
            continue

        result.append(f'<a href="{url}" target="_blank">{link_text}</a>')
        i = text_end

    return ''.join(result)


def remove_command_with_braces(text: str, cmd: str) -> str:
    """Remove a LaTeX command and its braced argument, handling nested braces."""
    pattern = '\\' + cmd + '{'
    result = []
    i = 0

    while i < len(text):
        pos = text.find(pattern, i)
        if pos == -1:
            result.append(text[i:])
            break

        result.append(text[i:pos])
        brace_pos = pos + len(pattern) - 1
        _, end_pos = balanced_braces_extract(text, brace_pos)

        if end_pos > 0:
            i = end_pos
        else:
            result.append(text[pos:pos + len(pattern)])
            i = pos + len(pattern)

    return ''.join(result)


def convert_latex_formatting(text: str) -> str:
    """Convert LaTeX formatting commands to HTML."""
    # Remove LaTeX comments (lines starting with %)
    text = re.sub(r'^%.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'(?<!\\)%.*$', '', text, flags=re.MULTILINE)

    # Remove commands with nested braces FIRST (before other processing)
    text = remove_command_with_braces(text, 'blfootnote')
    text = remove_command_with_braces(text, 'vspace')
    text = remove_command_with_braces(text, 'hspace')

    # Handle href first (two arguments)
    text = convert_href(text)

    # Single argument commands
    text = convert_command(text, 'textbf', '<strong>', '</strong>')
    text = convert_command(text, 'textit', '<em>', '</em>')
    text = convert_command(text, 'emph', '<em>', '</em>')
    text = convert_command(text, 'textsc', '<span class="small-caps">', '</span>')
    text = convert_command(text, 'ul', '<span class="underline">', '</span>')
    text = convert_command(text, 'texttt', '<code>', '</code>')
    text = convert_command(text, 'textsuperscript', '<sup>', '</sup>')

    # Handle {\bf text} style (old LaTeX)
    text = re.sub(r'\{\\bf\s+([^}]+)\}', r'<strong>\1</strong>', text)
    text = re.sub(r'\{\\it\s+([^}]+)\}', r'<em>\1</em>', text)
    text = re.sub(r'\{\\sc\s+([^}]+)\}', r'<span class="small-caps">\1</span>', text)

    # Handle special characters
    replacements = [
        (r'\&', '&amp;'),
        (r'\_', '_'),
        (r'\%', '%'),
        (r'\$', '$'),
        (r'\#', '#'),
        (r'\-', ''),  # discretionary hyphen
        ('``', '"'),
        ("''", '"'),
        ('`', "'"),
        ("'", "'"),
        ('---', '—'),  # em-dash (check before en-dash)
        ('--', '–'),   # en-dash
        ('~', ' '),    # non-breaking space
        (r'\,', ' '),  # thin space
        (r'\"a', 'ä'),
        (r'\"o', 'ö'),
        (r'\"u', 'ü'),
        (r'\"{a}', 'ä'),
        (r'\"{o}', 'ö'),
        (r'\"{u}', 'ü'),
    ]

    for old, new in replacements:
        text = text.replace(old, new)

    # Line breaks with spacing - \\[.1cm] etc adds extra space between blocks
    text = re.sub(r'\\\\\[[\d.]+cm\]', '<br><span class="block-spacer"></span>\n', text)
    text = text.replace(r'\\', '<br>\n')

    # Remove remaining LaTeX commands we don't need
    text = re.sub(r'\\noindent\s*', '', text)

    # Math mode: $...$ - simple handling
    text = re.sub(r'\$([^$]+)\$', r'<span class="math">\1</span>', text)

    # Superscripts in math
    text = re.sub(r'\^\\mathrm\{([^}]+)\}', r'<sup>\1</sup>', text)
    text = re.sub(r'\^\{([^}]+)\}', r'<sup>\1</sup>', text)

    # Remove any remaining raw LaTeX commands that shouldn't appear
    text = re.sub(r'\\begin\{center\}', '', text)
    text = re.sub(r'\\end\{center\}', '', text)
    text = re.sub(r'\{\\scriptsize\s+', '', text)
    text = re.sub(r'\\today\}?\s*', '', text)

    return text


def parse_single_etaremune(list_content: str) -> List[str]:
    """Parse a single etaremune list content and return items."""
    items = []
    # Split by item
    parts = re.split(r'\\item\s*', list_content)

    for part in parts:
        part = part.strip()
        if part:
            items.append(convert_latex_formatting(part))

    return items


def parse_etaremune(content: str) -> List[str]:
    """Parse etaremune environment (reverse-numbered list) and return items."""
    items = []

    # Find ALL etaremune lists
    for match in re.finditer(r'\\begin\{etaremune\}(.+?)\\end\{etaremune\}', content, re.DOTALL):
        list_content = match.group(1)
        items.extend(parse_single_etaremune(list_content))

    return items


def parse_multicol_etaremune(content: str) -> List[str]:
    """Parse multicol environment containing etaremune."""
    # Remove multicol wrapper
    content = re.sub(r'\\begin\{multicols\}\{\d+\}', '', content)
    content = re.sub(r'\\end\{multicols\}', '', content)

    return parse_etaremune(content)


def parse_labeled_lists(content: str) -> List[tuple]:
    """Parse content with labeled lists like:
    \\textit{Label}:
    \\begin{etaremune}...\\end{etaremune}

    Returns list of (label, items) tuples.
    """
    labeled_lists = []

    # Pattern to find labeled lists: \textit{Label}: followed by etaremune
    # Also handle multicols wrapper
    pattern = r'\\textit\{([^}]+)\}:\s*(?:\\begin\{multicols\}\{\d+\})?\s*\\begin\{etaremune\}(.+?)\\end\{etaremune\}\s*(?:\\end\{multicols\})?'

    for match in re.finditer(pattern, content, re.DOTALL):
        label = match.group(1).strip()
        list_content = match.group(2)
        items = parse_single_etaremune(list_content)
        labeled_lists.append((label, items))

    return labeled_lists


def extract_header_info(body: str) -> Dict[str, str]:
    """Extract header information (name, title, contact)."""
    info = {}

    # Find header section (before first section)
    header_match = re.search(r'^(.+?)\\section\*', body, re.DOTALL)
    if header_match:
        header = header_match.group(1)

        # Name - find the LARGE block and extract everything until the line break
        name_match = re.search(r'\{\\LARGE\s*(.+?)\}\\\\', header, re.DOTALL)
        if name_match:
            name_raw = name_match.group(1).strip()
            info['name'] = convert_latex_formatting(name_raw)

        # Find the position after the LARGE block (handles nested braces)
        large_match = re.search(r'\{\\LARGE', header)
        if large_match:
            # Find the matching closing brace
            start_pos = large_match.start()
            _, end_pos = balanced_braces_extract(header, start_pos)
            if end_pos > 0:
                # Skip past the \\ after the closing brace
                if header[end_pos:end_pos+2] == '\\\\':
                    end_pos += 2
                    # Skip any spacing like [0.25cm]
                    spacing_match = re.match(r'\[[\d.]+cm\]', header[end_pos:])
                    if spacing_match:
                        end_pos += spacing_match.end()
                rest_of_header = header[end_pos:]
            else:
                rest_of_header = header
        else:
            rest_of_header = header

        # Split by line breaks, but track which ones have spacing
        # Use a pattern that captures the spacing indicator
        lines = []
        # Find all parts and their spacing
        parts_with_spacing = re.split(r'(\\\\(?:\[[\d.]+cm\])?)', rest_of_header)

        current_text = ''
        for i, part in enumerate(parts_with_spacing):
            if re.match(r'\\\\(?:\[[\d.]+cm\])?', part):
                # This is a line break - check if it has spacing
                has_spacing = '[' in part and 'cm]' in part
                if current_text.strip():
                    # Remove LaTeX comments
                    text = re.sub(r'%.*$', '', current_text, flags=re.MULTILINE).strip()
                    if text and text not in ['}', '{', '']:
                        converted = convert_latex_formatting(text).strip()
                        if converted and converted not in ['}', '{', '']:
                            lines.append({'text': converted, 'space_after': has_spacing})
                current_text = ''
            else:
                current_text += part

        # Handle last part
        if current_text.strip():
            text = re.sub(r'%.*$', '', current_text, flags=re.MULTILINE).strip()
            if text and text not in ['}', '{', '']:
                converted = convert_latex_formatting(text).strip()
                if converted and converted not in ['}', '{', '']:
                    lines.append({'text': converted, 'space_after': False})

        info['header_lines'] = lines

    return info


def remove_latex_comments(text: str) -> str:
    """Remove LaTeX comments from text."""
    # Remove full-line comments
    text = re.sub(r'^%.*$', '', text, flags=re.MULTILINE)
    # Remove inline comments (but not escaped \%)
    text = re.sub(r'(?<!\\)%.*$', '', text, flags=re.MULTILINE)
    return text


def extract_sections(body: str) -> List[CVSection]:
    """Extract all sections from the CV."""
    sections = []

    # Remove comments BEFORE splitting to avoid commented-out subsections
    body = remove_latex_comments(body)

    # Split by section* or section
    section_pattern = r'\\section\*?\{([^}]+)\}'
    parts = re.split(section_pattern, body)

    # parts[0] is header, parts[1] is first section title, parts[2] is content, etc.
    if len(parts) > 1:
        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                title = parts[i].strip()
                content = parts[i + 1].strip()

                # Check for subsections
                subsection_pattern = r'\\subsection\*?\{([^}]+)\}'
                sub_parts = re.split(subsection_pattern, content)

                if len(sub_parts) > 1:
                    section = CVSection(title=title, content=sub_parts[0].strip())
                    for j in range(1, len(sub_parts), 2):
                        if j + 1 < len(sub_parts):
                            sub_title = sub_parts[j].strip()
                            sub_content = sub_parts[j + 1].strip()
                            section.subsections.append(CVSection(title=sub_title, content=sub_content))
                    sections.append(section)
                else:
                    sections.append(CVSection(title=title, content=content))

    return sections


def render_list_items(items: List[str], reversed_numbering: bool = True) -> str:
    """Render a list of items as HTML ordered list."""
    if not items:
        return ''

    if reversed_numbering:
        html = f'<ol reversed start="{len(items)}">\n'
    else:
        html = '<ol>\n'

    for item in items:
        item = item.strip()
        # Clean up leading/trailing breaks
        item = re.sub(r'^<br>\s*', '', item)
        item = re.sub(r'\s*<br>\s*$', '', item)
        html += f'  <li>{item}</li>\n'

    html += '</ol>\n'
    return html


def render_labeled_lists(labeled_lists: List[tuple], use_two_column: bool = False) -> str:
    """Render labeled lists (like Mentorship section) to HTML."""
    html = ''
    for label, items in labeled_lists:
        html += f'<h4>{label}</h4>\n'
        # Apply 2-column layout for Undergraduate Advisees or when explicitly requested
        is_undergrad = 'undergraduate' in label.lower()
        if (use_two_column or is_undergrad) and len(items) > 10:
            html += f'<div class="two-column-list">{render_list_items(items)}</div>\n'
        else:
            html += render_list_items(items)
    return html


def extract_footnote(content: str) -> tuple:
    """Extract blfootnote content from text. Returns (footnote_text, cleaned_content)."""
    pattern = r'\\blfootnote\{'
    match = re.search(pattern, content)
    if not match:
        return None, content

    brace_pos = match.end() - 1
    footnote_content, end_pos = balanced_braces_extract(content, brace_pos)
    if footnote_content:
        # Convert LaTeX formatting in footnote
        footnote_html = convert_latex_formatting(footnote_content)
        # Remove the footnote from content
        cleaned = content[:match.start()] + content[end_pos:]
        return footnote_html, cleaned
    return None, content


def preprocess_content(content: str, extract_footnotes: bool = False) -> tuple:
    """Preprocess content to handle problematic LaTeX commands before parsing.

    If extract_footnotes is True, returns (footnote, cleaned_content).
    Otherwise returns just cleaned_content for backwards compatibility.
    """
    # Remove comments first
    content = re.sub(r'^%.*$', '', content, flags=re.MULTILINE)
    content = re.sub(r'(?<!\\)%.*$', '', content, flags=re.MULTILINE)

    footnote = None
    if extract_footnotes:
        footnote, content = extract_footnote(content)
    else:
        # Remove blfootnote (with nested braces)
        content = remove_command_with_braces(content, 'blfootnote')

    # Remove vspace
    content = remove_command_with_braces(content, 'vspace')

    # Remove "Last updated: \today" line (handled in footer)
    content = re.sub(r'\{\\scriptsize\s*Last updated:.*?\\today\s*\}', '', content, flags=re.DOTALL)
    content = re.sub(r'Last updated:\s*$', '', content, flags=re.MULTILINE)

    if extract_footnotes:
        return footnote, content
    return content


def render_section_content(content: str, section_title: str) -> str:
    """Render section content to HTML based on section type."""

    # Extract footnote first (for display as note under section header)
    footnote, content = preprocess_content(content, extract_footnotes=True)

    # Build HTML with optional footnote note
    html_prefix = ''
    if footnote:
        html_prefix = f'<p class="section-note"><em>{footnote}</em></p>\n'

    # Check for labeled lists (like in Mentorship section)
    labeled_lists = parse_labeled_lists(content)
    if labeled_lists:
        # Check if this is the undergraduate advisees (use two-column)
        use_two_col = 'undergraduate' in section_title.lower()
        return html_prefix + render_labeled_lists(labeled_lists, use_two_column=use_two_col)

    # Check for etaremune lists
    if r'\begin{etaremune}' in content:
        if r'\begin{multicols}' in content:
            items = parse_multicol_etaremune(content)
            if 'talks' in section_title.lower() or 'undergraduate' in section_title.lower():
                return html_prefix + f'<div class="two-column-list">{render_list_items(items)}</div>'
            else:
                return html_prefix + render_list_items(items)
        else:
            items = parse_etaremune(content)
            # Check if should be 2 columns based on section
            if 'undergraduate' in section_title.lower():
                return html_prefix + f'<div class="two-column-list">{render_list_items(items)}</div>'
            return html_prefix + render_list_items(items)

    # For regular content, convert formatting
    content = convert_latex_formatting(content)

    # Split into paragraphs
    paragraphs = re.split(r'\n\s*\n', content)

    html = html_prefix
    for para in paragraphs:
        para = para.strip()
        if para:
            # Skip empty-looking content or raw LaTeX remnants
            if para in ['}', '{', ''] or para.startswith('\\'):
                continue
            if not para.startswith('<'):
                html += f'<p>{para}</p>\n'
            else:
                html += f'{para}\n'

    return html


def generate_html(tex_content: str) -> str:
    """Generate complete HTML from LaTeX content."""
    body = extract_document_body(tex_content)
    header_info = extract_header_info(body)
    sections = extract_sections(body)

    html_parts = []

    # Build sidebar navigation from sections
    sidebar_links = []
    for section in sections:
        section_id = section.title.lower()
        section_id = re.sub(r'[^a-z0-9]+', '-', section_id).strip('-')
        # Shorten some section titles for sidebar display
        display_title = section.title
        if len(display_title) > 25:
            # Truncate long titles
            display_title = display_title[:22] + '...'
        sidebar_links.append(f'            <a href="#{section_id}">{display_title}</a>\n')

    # HTML header
    html_parts.append('''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jeremy R. Manning, Ph.D. - Curriculum Vitae</title>
    <link rel="stylesheet" href="../css/cv.css">
</head>
<body>
    <div class="cv-download-bar">
        <div class="bar-content">
            <span class="cv-title">Curriculum Vitae</span>
            <a href="JRM_CV.pdf" class="download-btn" download>Download PDF</a>
        </div>
    </div>

    <aside class="cv-sidebar">
        <div class="cv-sidebar-title">Sections</div>
        <nav>
''')
    html_parts.extend(sidebar_links)
    html_parts.append('''        </nav>
    </aside>

    <div class="cv-content">
''')

    # Header section
    html_parts.append('        <header class="cv-header">\n')
    if 'name' in header_info:
        html_parts.append(f'            <h1>{header_info["name"]}</h1>\n')
    if 'header_lines' in header_info:
        html_parts.append('            <div class="contact-info">\n')
        for line_info in header_info['header_lines']:
            if isinstance(line_info, dict):
                text = line_info['text']
                space_class = ' class="space-after"' if line_info.get('space_after') else ''
                if text.strip():
                    html_parts.append(f'                <p{space_class}>{text}</p>\n')
            elif line_info.strip():  # Backwards compatibility
                html_parts.append(f'                <p>{line_info}</p>\n')
        html_parts.append('            </div>\n')
    html_parts.append('        </header>\n\n')

    # Sections
    for section in sections:
        section_id = section.title.lower()
        section_id = re.sub(r'[^a-z0-9]+', '-', section_id).strip('-')
        html_parts.append(f'        <section id="{section_id}">\n')
        html_parts.append(f'            <h2>{section.title}</h2>\n')

        if section.subsections:
            if section.content.strip():
                rendered = render_section_content(section.content, section.title)
                html_parts.append(f'            {rendered}\n')

            for subsection in section.subsections:
                rendered = render_section_content(subsection.content, subsection.title)
                # Skip empty subsections
                if not rendered.strip():
                    continue
                sub_id = re.sub(r'[^a-z0-9]+', '-', subsection.title.lower()).strip('-')
                html_parts.append(f'            <div class="subsection" id="{sub_id}">\n')
                html_parts.append(f'                <h3>{subsection.title}</h3>\n')
                html_parts.append(f'                {rendered}\n')
                html_parts.append('            </div>\n')
        else:
            rendered = render_section_content(section.content, section.title)
            html_parts.append(f'            {rendered}\n')

        html_parts.append('        </section>\n\n')

    # Footer
    html_parts.append('''        <footer class="cv-footer">
            <p>Last updated: <span id="last-updated"></span></p>
            <script>
                document.getElementById('last-updated').textContent = new Date().toLocaleDateString('en-US', {year: 'numeric', month: 'long', day: 'numeric'});
            </script>
        </footer>
    </div>
</body>
</html>
''')

    return ''.join(html_parts)


def extract_cv(input_path: Path, output_path: Path) -> bool:
    """Main extraction function."""
    try:
        tex_content = read_latex_file(input_path)
        html_content = generate_html(tex_content)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return True
    except Exception as e:
        print(f"Error extracting CV: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    project_root = Path(__file__).parent.parent
    input_file = project_root / 'documents' / 'JRM_CV.tex'
    output_file = project_root / 'documents' / 'JRM_CV.html'

    if extract_cv(input_file, output_file):
        print(f"Successfully generated {output_file}")
    else:
        print("Failed to generate HTML")
