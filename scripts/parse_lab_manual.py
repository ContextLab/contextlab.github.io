"""Parse lab_manual.tex to extract member and alumni data.

Parses the 'Lab members and alumni' chapter from the ContextLab lab-manual
repository's lab_manual.tex file. Extracts names, roles, year ranges, and
active/alumni status.
"""
import re
import subprocess
from pathlib import Path


def parse_members_chapter(tex_path):
    """Extract all member/alumni entries from lab_manual.tex.

    Args:
        tex_path: Path to lab_manual.tex file.

    Returns:
        List of dicts with keys: name, role_category, start_year,
        end_year (None if active), is_active, raw_line.
    """
    tex_path = Path(tex_path)
    content = tex_path.read_text(encoding='utf-8')

    # Extract the members chapter
    chapter_match = re.search(
        r'\\chapter\{Lab members and alumni\}.*?\\begin\{fullwidth\}(.*?)\\end\{fullwidth\}',
        content, re.DOTALL
    )
    if not chapter_match:
        raise ValueError(f"Could not find 'Lab members and alumni' chapter in {tex_path}")

    chapter_text = chapter_match.group(1)

    # Split into Current and Alumni sections
    subsection_pattern = r'\\subsection\{(.*?)\}'
    subsection_splits = re.split(subsection_pattern, chapter_text)

    # subsection_splits: [before_first, title1, content1, title2, content2, ...]
    sections = {}
    for i in range(1, len(subsection_splits), 2):
        title = subsection_splits[i].strip()
        body = subsection_splits[i + 1] if i + 1 < len(subsection_splits) else ''
        sections[title] = body

    records = []

    for section_title, section_body in sections.items():
        is_active = 'current' in section_title.lower()
        _parse_section(section_body, is_active, records)

    return records


def _parse_section(section_body, is_active, records):
    """Parse a section (Current or Alumni) for role groups and entries."""
    # Split by \newthought{Role}
    thought_pattern = r'\\newthought\{(.*?)\}'
    parts = re.split(thought_pattern, section_body)

    # parts: [before_first, role1, content1, role2, content2, ...]
    for i in range(1, len(parts), 2):
        role_category = parts[i].strip()
        role_content = parts[i + 1] if i + 1 < len(parts) else ''

        # Skip commented-out sections (all lines start with %)
        uncommented_lines = [
            line for line in role_content.split('\n')
            if line.strip() and not line.strip().startswith('%')
        ]
        if not uncommented_lines:
            continue

        # Handle PI special case (no list wrapper)
        if role_category == 'PI':
            _parse_pi_entry(role_content, role_category, is_active, records)
            continue

        # Parse \item entries
        _parse_list_entries(role_content, role_category, is_active, records)


def _parse_pi_entry(content, role_category, is_active, records):
    """Parse PI entry which has no list wrapper."""
    # Format: \enskip Name (YYYY -- ) or just Name (YYYY -- )
    pattern = r'(?:\\enskip\s+)?([A-Z][\w\s.]+?)\s*\((\d{4})\s*--\s*(\d{4})?\s*\)?'
    for match in re.finditer(pattern, content):
        name = match.group(1).strip()
        start_year = int(match.group(2))
        end_year = int(match.group(3)) if match.group(3) else None
        records.append({
            'name': name,
            'role_category': role_category,
            'start_year': start_year,
            'end_year': end_year,
            'is_active': is_active and end_year is None,
            'raw_line': match.group(0).strip(),
        })


def _parse_list_entries(content, role_category, is_active, records):
    """Parse \\item entries from list blocks."""
    # Match \item Name (YYYY -- YYYY) or \item Name (YYYY) or \item Name (YYYY --)
    item_pattern = r'\\item\s+(.+?)\s*\((\d{4})(?:\s*--\s*(\d{4})?)?\s*\)'
    for line in content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('%'):
            continue
        match = re.search(item_pattern, stripped)
        if match:
            name = match.group(1).strip()
            start_year = int(match.group(2))
            end_str = match.group(3)
            end_year = int(end_str) if end_str else None
            records.append({
                'name': name,
                'role_category': role_category,
                'start_year': start_year,
                'end_year': end_year,
                'is_active': is_active and end_year is None,
                'raw_line': stripped,
            })


def add_member_to_lab_manual(tex_path, name, role, start_year):
    """Add a new member to the Current lab members section.

    Args:
        tex_path: Path to lab_manual.tex.
        name: Full name of the member.
        role: Role category (e.g., 'Graduate Students', 'Undergraduate RAs').
        start_year: Start year as int.
    """
    tex_path = Path(tex_path)
    content = tex_path.read_text(encoding='utf-8')

    # Map common role names to lab-manual role headings
    role_map = {
        'postdoc': 'Postdoctoral Researchers',
        'grad student': 'Graduate Students',
        'graduate student': 'Graduate Students',
        'undergrad': 'Undergraduate RAs',
        'undergraduate': 'Undergraduate RAs',
        'lab manager': 'Lab Managers',
        'research assistant': 'Research Assistants',
    }
    role_heading = role_map.get(role.lower(), role)

    new_item = f'\\item {name} ({start_year} -- )'

    # Find the role section under Current lab members
    # Look for \newthought{Role} followed by a list block
    pattern = (
        r'(\\subsection\{Current lab members\}.*?'
        r'\\newthought\{' + re.escape(role_heading) + r'\}.*?'
        r'\\begin\{list\}\{\\quad\}\{\})'
        r'(.*?)'
        r'(\\end\{list\})'
    )
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        raise ValueError(
            f"Could not find '{role_heading}' section under "
            f"'Current lab members' in {tex_path}"
        )

    # Insert new item before \end{list}
    before = match.group(1) + match.group(2).rstrip()
    new_content = content[:match.start()] + before + '\n' + new_item + '\n' + match.group(3) + content[match.end():]
    tex_path.write_text(new_content, encoding='utf-8')


def move_member_to_alumni(tex_path, name, end_year):
    """Move a member from Current to Alumni section.

    Args:
        tex_path: Path to lab_manual.tex.
        name: Full name of the member.
        end_year: End year as int.
    """
    tex_path = Path(tex_path)
    content = tex_path.read_text(encoding='utf-8')

    # Find the member in Current section
    # Match the \item line with their name
    item_pattern = re.compile(
        r'^(\s*)\\item\s+' + re.escape(name) + r'\s*\((\d{4})\s*--\s*\)',
        re.MULTILINE
    )

    # Only match within Current lab members section
    current_section_match = re.search(
        r'\\subsection\{Current lab members\}(.*?)\\subsection\{Lab alumni\}',
        content, re.DOTALL
    )
    if not current_section_match:
        raise ValueError("Could not find Current lab members section")

    current_start = current_section_match.start(1)
    current_end = current_section_match.end(1)
    current_text = current_section_match.group(1)

    item_match = item_pattern.search(current_text)
    if not item_match:
        raise ValueError(f"Could not find '{name}' in Current lab members section")

    start_year = item_match.group(2)

    # Determine role category by finding the \newthought before this item
    item_pos = item_match.start()
    role_matches = list(re.finditer(r'\\newthought\{(.*?)\}', current_text[:item_pos]))
    if not role_matches:
        raise ValueError(f"Could not determine role for '{name}'")
    role_category = role_matches[-1].group(1)

    # Remove from current section
    abs_start = current_start + item_match.start()
    abs_end = current_start + item_match.end()
    # Remove the full line including newline
    line_start = content.rfind('\n', 0, abs_start) + 1
    line_end = content.find('\n', abs_end)
    if line_end == -1:
        line_end = len(content)
    else:
        line_end += 1  # include the newline

    content = content[:line_start] + content[line_end:]

    # Add to alumni section with closed year range
    alumni_item = f'\\item {name} ({start_year} -- {end_year})'

    # Find the role section under Lab alumni
    pattern = (
        r'(\\subsection\{Lab alumni\}.*?'
        r'\\newthought\{' + re.escape(role_category) + r'\}.*?'
        r'\\begin\{list\}\{\\quad\}\{\})'
        r'(.*?)'
        r'(\\end\{list\})'
    )
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        raise ValueError(
            f"Could not find '{role_category}' alumni section in {tex_path}"
        )

    before = match.group(1) + match.group(2).rstrip()
    content = content[:match.start()] + before + '\n' + alumni_item + '\n' + match.group(3) + content[match.end():]

    tex_path.write_text(content, encoding='utf-8')


def commit_and_push_lab_manual(submodule_path, message):
    """Commit and push changes in the lab-manual submodule.

    Args:
        submodule_path: Path to the lab-manual submodule directory.
        message: Commit message.

    Raises:
        RuntimeError: If git operations fail.
    """
    submodule_path = Path(submodule_path)
    if not (submodule_path / '.git').exists() and not (submodule_path / 'lab_manual.tex').exists():
        raise RuntimeError(
            f"Lab-manual submodule not initialized at {submodule_path}. "
            f"Run: git submodule update --init"
        )

    try:
        subprocess.run(
            ['git', 'add', 'lab_manual.tex'],
            cwd=submodule_path, check=True, capture_output=True, text=True
        )
        # Check if there are staged changes
        result = subprocess.run(
            ['git', 'diff', '--cached', '--quiet'],
            cwd=submodule_path, capture_output=True
        )
        if result.returncode == 0:
            return  # Nothing to commit

        subprocess.run(
            ['git', 'commit', '-m', message],
            cwd=submodule_path, check=True, capture_output=True, text=True
        )
        subprocess.run(
            ['git', 'push', 'origin', 'master'],
            cwd=submodule_path, check=True, capture_output=True, text=True
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Failed to commit/push lab-manual changes: {e.stderr or e.stdout}"
        ) from e
