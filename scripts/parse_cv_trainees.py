#!/usr/bin/env python3
"""Parse mentored trainees from JRM_CV.tex LaTeX file.

Extracts trainee information from the Mentorship section of the CV,
including postdoctoral advisees, graduate advisees, and undergraduate advisees.
"""
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict


@dataclass
class Trainee:
    """Represents a trainee parsed from the CV."""
    name: str
    category: str  # 'postdoc', 'grad', 'undergrad'
    role: Optional[str]  # e.g., 'Doctoral student', 'Masters student, QBS'
    start_year: Optional[int]
    end_year: Optional[int]  # None means still active
    current_position: Optional[str]
    is_thesis_student: bool = False  # For undergrads with asterisk

    @property
    def is_active(self) -> bool:
        """Return True if trainee is still active (no end year)."""
        return self.end_year is None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        d = asdict(self)
        d['is_active'] = self.is_active
        return d


def extract_section(tex_content: str, section_start: str, section_end: str) -> str:
    """Extract content between section markers.

    Args:
        tex_content: Full LaTeX content
        section_start: Text marking start of section
        section_end: Text marking end of section (or next section)

    Returns:
        Content between markers
    """
    start_idx = tex_content.find(section_start)
    if start_idx == -1:
        return ""

    # Find the end marker after the start
    end_idx = tex_content.find(section_end, start_idx + len(section_start))
    if end_idx == -1:
        end_idx = len(tex_content)

    return tex_content[start_idx:end_idx]


def clean_latex_name(name: str) -> str:
    """Clean LaTeX formatting from a name.

    Args:
        name: Name possibly containing LaTeX commands

    Returns:
        Cleaned name
    """
    # Remove asterisk (thesis student marker)
    name = name.rstrip('*')

    # Remove common LaTeX formatting
    name = re.sub(r'\\textit\{([^}]*)\}', r'\1', name)
    name = re.sub(r'\\textbf\{([^}]*)\}', r'\1', name)
    name = re.sub(r'\\ul\{([^}]*)\}', r'\1', name)
    name = re.sub(r'\\emph\{([^}]*)\}', r'\1', name)

    # Handle special characters
    name = name.replace('\\"{a}', 'a')
    name = name.replace('\\"{o}', 'o')
    name = name.replace('\\"{u}', 'u')
    name = name.replace("\\'e", 'e')
    name = name.replace("\\&", '&')

    return name.strip()


def parse_year_range(year_str: str) -> Tuple[Optional[int], Optional[int]]:
    """Parse a year range string.

    Handles formats:
    - "2024 -- )" -> (2024, None) - active
    - "2024 -- " -> (2024, None) - active (paren may be stripped)
    - "2024 -- 2025" -> (2024, 2025) - alumni
    - "2024" -> (2024, 2024) - single year (alumni)

    Args:
        year_str: Year string to parse

    Returns:
        Tuple of (start_year, end_year), end_year is None if active
    """
    year_str = year_str.strip()

    # Check for active pattern: "YYYY -- )" or "YYYY --)" or "YYYY --" (paren stripped)
    active_match = re.search(r'(\d{4})\s*--\s*\)?$', year_str)
    if active_match:
        # Make sure there's no second year after the --
        after_dash = year_str[year_str.find('--') + 2:].strip().rstrip(')')
        if not re.search(r'\d{4}', after_dash):
            return int(active_match.group(1)), None

    # Check for range pattern: "YYYY -- YYYY" or "YYYY--YYYY"
    range_match = re.search(r'(\d{4})\s*--?\s*(\d{4})', year_str)
    if range_match:
        return int(range_match.group(1)), int(range_match.group(2))

    # Check for single year: "YYYY"
    single_match = re.search(r'(\d{4})', year_str)
    if single_match:
        year = int(single_match.group(1))
        return year, year

    return None, None


def parse_postdoc_entry(entry: str) -> Optional[Trainee]:
    """Parse a postdoctoral advisee entry.

    Format: \\item Name (YYYY -- YYYY; current position: Company)

    Args:
        entry: LaTeX item entry

    Returns:
        Trainee object or None if parsing fails
    """
    # Pattern: \item Name (year info; current position: ...)
    # or: \item Name (year info)
    match = re.match(r'\\item\s+(.+?)\s*\((.+)\)', entry.strip())
    if not match:
        return None

    name = clean_latex_name(match.group(1))
    paren_content = match.group(2)

    # Split on semicolon to separate year from current position
    parts = paren_content.split(';')
    year_part = parts[0].strip()

    start_year, end_year = parse_year_range(year_part)

    # Extract current position if present
    current_position = None
    for part in parts[1:]:
        if 'current position' in part.lower():
            pos_match = re.search(r'current position:\s*(.+)', part, re.IGNORECASE)
            if pos_match:
                current_position = pos_match.group(1).strip()

    return Trainee(
        name=name,
        category='postdoc',
        role='Postdoctoral Researcher',
        start_year=start_year,
        end_year=end_year,
        current_position=current_position
    )


def parse_grad_entry(entry: str) -> Optional[Trainee]:
    """Parse a graduate advisee entry.

    Formats:
    - \\item Name (Doctoral student; YYYY -- )
    - \\item Name (Masters student, Program; YYYY -- YYYY; current position: ...)

    Args:
        entry: LaTeX item entry

    Returns:
        Trainee object or None if parsing fails
    """
    match = re.match(r'\\item\s+(.+?)\s*\((.+)\)', entry.strip(), re.DOTALL)
    if not match:
        return None

    name = clean_latex_name(match.group(1))
    paren_content = match.group(2).replace('\n', ' ')

    # Split on semicolons
    parts = [p.strip() for p in paren_content.split(';')]

    role = None
    year_part = None
    current_position = None

    for part in parts:
        part_lower = part.lower()
        if 'student' in part_lower:
            role = part
        elif 'current position' in part_lower:
            pos_match = re.search(r'current position:\s*(.+)', part, re.IGNORECASE)
            if pos_match:
                current_position = pos_match.group(1).strip()
        elif re.search(r'\d{4}', part):
            year_part = part

    start_year, end_year = None, None
    if year_part:
        start_year, end_year = parse_year_range(year_part)

    return Trainee(
        name=name,
        category='grad',
        role=role,
        start_year=start_year,
        end_year=end_year,
        current_position=current_position
    )


def parse_undergrad_entry(entry: str) -> Optional[Trainee]:
    """Parse an undergraduate advisee entry.

    Formats:
    - \\item Name (YYYY -- )
    - \\item Name* (YYYY -- YYYY)
    - \\item Name (YYYY)

    Args:
        entry: LaTeX item entry

    Returns:
        Trainee object or None if parsing fails
    """
    match = re.match(r'\\item\s+(.+?)\s*\((.+)\)', entry.strip())
    if not match:
        return None

    raw_name = match.group(1).strip()
    is_thesis = raw_name.endswith('*')
    name = clean_latex_name(raw_name)

    year_part = match.group(2)
    start_year, end_year = parse_year_range(year_part)

    return Trainee(
        name=name,
        category='undergrad',
        role='Undergraduate Researcher',
        start_year=start_year,
        end_year=end_year,
        current_position=None,
        is_thesis_student=is_thesis
    )


def parse_cv_trainees(cv_path: Path) -> Dict[str, List[Trainee]]:
    """Parse all trainees from the CV.

    Args:
        cv_path: Path to JRM_CV.tex

    Returns:
        Dictionary with keys 'postdocs', 'grads', 'undergrads',
        each containing a list of Trainee objects
    """
    with open(cv_path, 'r', encoding='utf-8') as f:
        content = f.read()

    trainees = {
        'postdocs': [],
        'grads': [],
        'undergrads': []
    }

    # Extract postdoctoral section
    postdoc_section = extract_section(
        content,
        r'\textit{Postdoctoral Advisees}',
        r'\textit{Graduate Advisees}'
    )

    # Find all \item entries in postdoc section
    postdoc_items = re.findall(r'\\item\s+[^\\]+\([^)]+\)', postdoc_section)
    for item in postdoc_items:
        trainee = parse_postdoc_entry(item)
        if trainee:
            trainees['postdocs'].append(trainee)

    # Extract graduate section
    grad_section = extract_section(
        content,
        r'\textit{Graduate Advisees}',
        r'\textit{Thesis Committees}'
    )

    # Find all \item entries in grad section - handle multi-line entries
    grad_items = re.findall(r'\\item\s+.+?\([^)]+\)', grad_section, re.DOTALL)
    for item in grad_items:
        trainee = parse_grad_entry(item)
        if trainee:
            trainees['grads'].append(trainee)

    # Extract undergraduate section
    undergrad_section = extract_section(
        content,
        r'\textit{Undergraduate Advisees}',
        r'\section*{Service}'
    )

    # Find all \item entries in undergrad section
    undergrad_items = re.findall(r'\\item\s+[^\\]+?\([^)]+\)', undergrad_section)
    for item in undergrad_items:
        trainee = parse_undergrad_entry(item)
        if trainee:
            trainees['undergrads'].append(trainee)

    return trainees


def get_active_trainees(trainees: Dict[str, List[Trainee]]) -> List[Trainee]:
    """Get all active trainees across categories.

    Args:
        trainees: Dictionary of trainees by category

    Returns:
        List of active trainees
    """
    active = []
    for category_trainees in trainees.values():
        active.extend([t for t in category_trainees if t.is_active])
    return active


def get_alumni_trainees(trainees: Dict[str, List[Trainee]]) -> Dict[str, List[Trainee]]:
    """Get all alumni trainees by category.

    Args:
        trainees: Dictionary of trainees by category

    Returns:
        Dictionary of alumni trainees by category
    """
    return {
        category: [t for t in category_trainees if not t.is_active]
        for category, category_trainees in trainees.items()
    }


def main():
    """Main entry point - print summary of parsed trainees."""
    project_root = Path(__file__).parent.parent
    cv_path = project_root / 'documents' / 'JRM_CV.tex'

    trainees = parse_cv_trainees(cv_path)

    print("=== CV Trainee Summary ===\n")

    for category, category_trainees in trainees.items():
        active = [t for t in category_trainees if t.is_active]
        alumni = [t for t in category_trainees if not t.is_active]

        print(f"{category.upper()}: {len(category_trainees)} total ({len(active)} active, {len(alumni)} alumni)")

        if active:
            print(f"  Active: {', '.join(t.name for t in active)}")
        print()

    # Print detailed active members
    print("=== Active Members ===")
    for trainee in get_active_trainees(trainees):
        print(f"  {trainee.name} ({trainee.category}, {trainee.start_year} -- )")


if __name__ == '__main__':
    main()
