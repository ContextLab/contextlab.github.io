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


# Common role names (as passed to --rank) mapped to lab-manual headings.
ROLE_MAP = {
    'postdoc': 'Postdoctoral Researchers',
    'grad student': 'Graduate Students',
    'graduate student': 'Graduate Students',
    'undergrad': 'Undergraduate RAs',
    'undergraduate': 'Undergraduate RAs',
    'lab manager': 'Lab Managers',
    'research assistant': 'Research Assistants',
}

# The seniority order both \subsection blocks in lab_manual.tex are kept in.
# A role block created on demand is inserted at its position here so the file
# keeps reading the way a human maintained it.
ROLE_ORDER = [
    'PI',
    'Postdoctoral Researchers',
    'Graduate Students',
    'Lab Managers',
    'Research Assistants',
    'Undergraduate RAs',
]

# A \newthought heading that is NOT commented out. '[^%\n]*' after '^' lets
# leading whitespace through but stops at a '%', so the commented-out
# '% \newthought{Research Assistants}' never matches.
_HEADING_RE = re.compile(r'^[^%\n]*\\newthought\{(.*?)\}', re.MULTILINE)


def resolve_role_heading(role):
    """Map an onboarding --rank value to a lab-manual role heading."""
    return ROLE_MAP.get(role.lower(), role)


def _role_rank(heading):
    """Sort key for ROLE_ORDER; unknown roles sort last."""
    try:
        return ROLE_ORDER.index(heading)
    except ValueError:
        return len(ROLE_ORDER)


def _section_bounds(content, tex_path, subsection, *terminators):
    """Return (start, end) offsets of a \\subsection block's text.

    Every mutation below is restricted to one subsection. Unbounded, the
    DOTALL patterns run straight past \\subsection{Lab alumni} and append a
    current member to an alumni list. `terminators` are literal strings that
    end the section; the earliest one found wins, so a section that is created
    on demand can never be appended past the end of the chapter.
    """
    start = content.find(r'\subsection{' + subsection + '}')
    if start == -1:
        raise ValueError(f"Could not find '{subsection}' in {tex_path}")

    end = len(content)
    for terminator in terminators:
        found = content.find(terminator, start + 1)
        if found != -1:
            end = min(end, found)
    return start, end


# Terminators for the two subsections we mutate. Alumni is the last subsection
# in the chapter, so it ends at \end{fullwidth}.
_CURRENT_BOUNDS = (r'\subsection{Lab alumni}', r'\end{fullwidth}')
_ALUMNI_BOUNDS = (r'\end{fullwidth}',)


def _find_role_block(section, role_heading):
    """Match an uncommented '\\newthought{Role} ... \\begin{list} ... \\end{list}'.

    Groups: (1) heading through \\begin{list}, (2) the items, (3) \\end{list}.
    The heading must not be commented out -- inserting a live \\item into a
    commented-out list produces a LaTeX "Lonely \\item" error.
    """
    pattern = (
        r'(^[^%\n]*\\newthought\{' + re.escape(role_heading) + r'\}.*?'
        r'\\begin\{list\}\{\\quad\}\{\})'
        r'(.*?)'
        r'(\\end\{list\})'
    )
    return re.search(pattern, section, re.DOTALL | re.MULTILINE)


def _has_item(items_text, name):
    """Is `name` already listed in this block?

    Mirrors member_exists_in_cv(). The \\*? mirrors the CV's senior-thesis
    marker so a starred entry is recognized as the same person.
    """
    return bool(re.search(
        r'^[^%\n]*\\item\s+' + re.escape(name) + r'\*?\s*\(',
        items_text, re.IGNORECASE | re.MULTILINE
    ))


def _insert_role_block(section, role_heading, item_line):
    """Create a role block containing one item, at its ROLE_ORDER position.

    A role block is only ever created WITH a member in it. An empty
    '\\begin{list}{\\quad}{}\\end{list}' is a fatal LaTeX error --
    "Something's wrong--perhaps a missing \\item" -- and produces no PDF at
    all, which is why the Research Assistants block was commented out rather
    than left empty.
    """
    block = (
        f'\\newthought{{{role_heading}}}\n'
        '\\begin{multicols}{2}\\raggedcolumns\n'
        '\\begin{list}{\\quad}{}\n'
        f'{item_line}\n'
        '\\end{list}\n'
        '\\end{multicols}\n\n'
    )

    rank = _role_rank(role_heading)
    for heading in _HEADING_RE.finditer(section):
        if _role_rank(heading.group(1).strip()) > rank:
            # finditer starts each match at the line start, so this inserts
            # the block immediately above the more-junior role.
            return section[:heading.start()] + block + section[heading.start():]

    # More senior than everything present: append, but stay above a trailing
    # \newpage so the page break keeps separating Current from Alumni.
    newpage = section.rfind('\\newpage')
    if newpage != -1:
        return section[:newpage] + block + section[newpage:]
    return section.rstrip('\n') + '\n\n' + block


def _remove_role_block(section, match):
    """Delete a whole role block, including its \\end{multicols} wrapper."""
    end = match.end()
    trailer = re.match(
        r'[^\n]*\n(?:[^\n]*\\end\{multicols\}[^\n]*\n)?\s*?\n?',
        section[end:]
    )
    if trailer:
        end += trailer.end()
    return section[:match.start()] + section[end:]


def find_current_role(tex_path, name):
    """Return the role heading `name` is listed under in Current, or None."""
    tex_path = Path(tex_path)
    content = tex_path.read_text(encoding='utf-8')
    start, end = _section_bounds(
        content, tex_path, 'Current lab members', *_CURRENT_BOUNDS
    )
    section = content[start:end]

    item = re.search(
        r'^[^%\n]*\\item\s+' + re.escape(name) + r'\*?\s*\(',
        section, re.IGNORECASE | re.MULTILINE
    )
    if not item:
        return None

    headings = [h for h in _HEADING_RE.finditer(section) if h.start() < item.start()]
    if not headings:
        return None
    return headings[-1].group(1).strip()


def add_member_to_lab_manual(tex_path, name, role, start_year):
    """Add a new member to the Current lab members section.

    Args:
        tex_path: Path to lab_manual.tex.
        name: Full name of the member.
        role: Role category (e.g., 'grad student', 'Undergraduate RAs').
        start_year: Start year as int.

    Returns:
        True if the member was added, False if they were already listed under
        that role (in which case the file is left untouched).
    """
    tex_path = Path(tex_path)
    content = tex_path.read_text(encoding='utf-8')
    role_heading = resolve_role_heading(role)
    new_item = f'\\item {name} ({start_year} -- )'

    current_start, alumni_start = _section_bounds(
        content, tex_path, 'Current lab members', *_CURRENT_BOUNDS
    )
    section = content[current_start:alumni_start]

    match = _find_role_block(section, role_heading)
    if not match:
        # No active block for this role. 'Lab Managers' has no heading under
        # Current and 'Research Assistants' is commented out, so refusing here
        # made those two roles impossible to onboard (issue #17). Only known
        # roles get a block created -- otherwise a typo'd --rank would invent
        # a new section rather than being reported.
        if role_heading not in ROLE_ORDER:
            raise ValueError(
                f"Unknown role '{role}' -- expected one of "
                f"{sorted(set(ROLE_MAP.values()))}"
            )
        new_section = _insert_role_block(section, role_heading, new_item)
    else:
        # Don't add someone already listed under this role. The spreadsheet and
        # CV writers both check before appending; without the same guard here,
        # re-running onboarding leaves the three sources of truth disagreeing.
        if _has_item(match.group(2), name):
            return False

        before = match.group(1) + match.group(2).rstrip()
        new_section = (
            section[:match.start()] + before + '\n' + new_item + '\n'
            + match.group(3) + section[match.end():]
        )

    content = content[:current_start] + new_section + content[alumni_start:]
    tex_path.write_text(content, encoding='utf-8')
    return True


def move_member_to_alumni(tex_path, name, end_year):
    """Move a member from Current to Alumni, closing their year range.

    Args:
        tex_path: Path to lab_manual.tex.
        name: Full name of the member.
        end_year: End year as int.

    Returns:
        The role heading they were moved out of.
    """
    tex_path = Path(tex_path)
    content = tex_path.read_text(encoding='utf-8')

    current_start, alumni_start = _section_bounds(
        content, tex_path, 'Current lab members', *_CURRENT_BOUNDS
    )
    section = content[current_start:alumni_start]

    item_match = re.search(
        r'^[^%\n]*\\item\s+' + re.escape(name) + r'\*?\s*\((\d{4})\s*--\s*\)[^\n]*\n?',
        section, re.IGNORECASE | re.MULTILINE
    )
    if not item_match:
        raise ValueError(f"Could not find '{name}' in Current lab members section")

    start_year = item_match.group(1)

    headings = [h for h in _HEADING_RE.finditer(section) if h.start() < item_match.start()]
    if not headings:
        raise ValueError(f"Could not determine role for '{name}'")
    role_category = headings[-1].group(1).strip()

    section = section[:item_match.start()] + section[item_match.end():]

    # Removing the last member leaves an empty list, which is a fatal LaTeX
    # error, so the whole block goes with it.
    block = _find_role_block(section, role_category)
    if block and not re.search(r'^[^%\n]*\\item', block.group(2), re.MULTILINE):
        section = _remove_role_block(section, block)

    content = content[:current_start] + section + content[alumni_start:]

    # Recompute: removing the item above shifted every offset after it.
    alumni_start, alumni_end = _section_bounds(
        content, tex_path, 'Lab alumni', *_ALUMNI_BOUNDS
    )
    alumni_section = content[alumni_start:alumni_end]

    alumni_item = f'\\item {name} ({start_year} -- {end_year})'
    alumni_block = _find_role_block(alumni_section, role_category)
    if not alumni_block:
        new_alumni = _insert_role_block(alumni_section, role_category, alumni_item)
    else:
        before = alumni_block.group(1) + alumni_block.group(2).rstrip()
        new_alumni = (
            alumni_section[:alumni_block.start()] + before + '\n' + alumni_item
            + '\n' + alumni_block.group(3) + alumni_section[alumni_block.end():]
        )

    content = content[:alumni_start] + new_alumni + content[alumni_end:]
    tex_path.write_text(content, encoding='utf-8')
    return role_category


def sync_member_role(tex_path, name, role, year):
    """Record `name` under `role`, handling a role change the way the file does.

    lab_manual.tex has been maintained with one convention for a decade: a role
    change CLOSES OUT the old role into Lab alumni and opens a new entry under
    Current. Both Xinming Xu (Research Assistants 2019 -- 2021, then Graduate
    Students 2021 -- ) and Paxton Fitzpatrick (Lab Managers 2018 -- 2021, then
    Graduate Students 2021 -- ) are recorded exactly that way, with the old
    range closing in the year the new one opens.

    Returns:
        'unchanged' if they were already listed under this role,
        'role-changed' if an older role was closed out first,
        'added' otherwise.
    """
    role_heading = resolve_role_heading(role)
    existing = find_current_role(tex_path, name)

    if existing == role_heading:
        return 'unchanged'

    if existing is not None:
        move_member_to_alumni(tex_path, name, year)
        add_member_to_lab_manual(tex_path, name, role, year)
        return 'role-changed'

    return 'added' if add_member_to_lab_manual(tex_path, name, role, year) else 'unchanged'


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
