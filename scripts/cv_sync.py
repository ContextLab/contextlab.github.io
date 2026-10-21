#!/usr/bin/env python3
"""Generate the CV's publication and software lists from the spreadsheets.

The website and the CV list the same papers, chapters and software. The
spreadsheets are the source for both: build_publications.py and
build_software.py turn them into the website's pages, and this script turns
them into the lists in documents/JRM_CV.tex, between marker comments:

    % BEGIN GENERATED PUBLICATIONS ...
    % END GENERATED PUBLICATIONS

Everything between a pair of markers is rewritten on every run, so edit the
spreadsheet, never the block. Text outside the markers (section headings,
the commented-out history of preprints) is left alone.

Trainee annotations
-------------------
The CV marks lab trainees among each item's authors: undergraduates are
underlined, graduate students italicized, postdocs both. Each author's mark
comes from, in order:

1. the item's ``author_roles`` cell, e.g. ``Jolly E: postdoc; Zhu Z: none``,
   which overrides everything ("none" leaves an author unmarked); then
2. default_role(), applied to the years the CV's mentorship section gives
   for that person (the same lists the people page is reconciled against).

Overrides cover trainees from collaborators' labs, who are not in the
mentorship lists, and people whose role when the work was done differs from
what their years alone would suggest.

Usage (from scripts/):
    python cv_sync.py          # rewrite the generated blocks
    python cv_sync.py --check  # exit 1 if the blocks are out of date
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from build_publications import load_publications
from build_software import load_software, parse_extra_links
from citation_utils import markdown_to_html, paper_venue_detail
from parse_cv_trainees import parse_cv_trainees

PROJECT_ROOT = Path(__file__).parent.parent
CV_PATH = PROJECT_ROOT / 'documents' / 'JRM_CV.tex'
PUBLICATIONS_PATH = PROJECT_ROOT / 'data' / 'publications.xlsx'
SOFTWARE_PATH = PROJECT_ROOT / 'data' / 'software.xlsx'

LAB_DIRECTOR = 'Manning JR'

ROLES = ('undergrad', 'grad', 'postdoc')
NO_ROLE = 'none'
ROLE_MARKUP = {
    'undergrad': '\\ul{%s}',
    'grad': '\\textit{%s}',
    'postdoc': '\\ul{\\textit{%s}}',
}
# parse_cv_trainees() groups trainees under these keys
_TRAINEE_GROUPS = {'undergrads': 'undergrad', 'grads': 'grad', 'postdocs': 'postdoc'}

BLOCKS = {
    'PUBLICATIONS': 'data/publications.xlsx (papers and chapters)',
    'SOFTWARE': 'data/software.xlsx',
}


def begin_marker(block: str) -> str:
    return (f'% BEGIN GENERATED {block}: built from {BLOCKS[block]} by '
            f'scripts/cv_sync.py. Edit the spreadsheet, not this block.')


def end_marker(block: str) -> str:
    return f'% END GENERATED {block}'


# ---------------------------------------------------------------------------
# Trainee roles
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RoleSpan:
    """One stretch of time someone spent in the lab in one role."""
    role: str  # one of ROLES
    start: int
    end: Optional[int]  # None while still in that role


PersonKey = Tuple[str, str]  # (surname, first initial), casefolded


def author_key(author: str) -> PersonKey:
    """Key for a citation-style author: 'van der Meer MAA' -> ('van der meer', 'm')."""
    words = author.split()
    if len(words) < 2:
        return (author.casefold(), '')
    return (' '.join(words[:-1]).casefold(), words[-1][0].casefold())


def trainee_key(full_name: str) -> PersonKey:
    """Key for a mentorship-list name: 'Paxton Fitzpatrick' -> ('fitzpatrick', 'p')."""
    words = full_name.split()
    return (words[-1].casefold(), words[0][0].casefold())


def load_role_spans(cv_path: Path = CV_PATH) -> Dict[PersonKey, List[RoleSpan]]:
    """Every lab trainee's roles and years, from the CV's mentorship section."""
    spans: Dict[PersonKey, List[RoleSpan]] = {}
    for group, trainees in parse_cv_trainees(cv_path).items():
        role = _TRAINEE_GROUPS[group]
        for trainee in trainees:
            if trainee.start_year is None:
                continue
            spans.setdefault(trainee_key(trainee.name), []).append(
                RoleSpan(role, trainee.start_year, trainee.end_year))
    return spans


def default_role(spans: Sequence[RoleSpan], year: int) -> Optional[str]:
    """The role an author is marked with on an item from `year`, absent an override.

    spans lists every stretch the author spent in the lab (one per role; a
    person who was an undergrad and later a grad student has two). Return one
    of ROLES, or None to leave the author unmarked.

    The rule: the most recent role the author had started by `year`, so alumni
    keep their last role and someone who moved from undergrad to grad student
    is marked by whichever came last. Items from before they joined the lab
    stay unmarked.
    """
    started = [s for s in spans if s.start <= year]
    if not started:
        return None
    return max(started, key=lambda s: s.start).role


def parse_role_overrides(text: str) -> Dict[str, Optional[str]]:
    """Parse an author_roles cell: 'Jolly E: postdoc; Zhu Z: none'.

    Returns {author: role}, with None for "none".
    """
    overrides: Dict[str, Optional[str]] = {}
    for part in (text or '').split(';'):
        if not part.strip():
            continue
        if ':' not in part:
            raise ValueError(f"author_roles entry {part.strip()!r} needs the form 'Name AB: role'")
        name, role = (s.strip() for s in part.rsplit(':', 1))
        if role not in ROLES and role != NO_ROLE:
            raise ValueError(
                f"author_roles: unknown role {role!r} for {name!r} "
                f"(use one of {', '.join(ROLES + (NO_ROLE,))})")
        overrides[name] = None if role == NO_ROLE else role
    return overrides


def split_authors(authors: str) -> List[str]:
    return [a.strip() for a in (authors or '').split(',') if a.strip()]


def resolve_roles(
    authors: Sequence[str],
    year: int,
    overrides: Dict[str, Optional[str]],
    spans: Dict[PersonKey, List[RoleSpan]],
) -> List[Optional[str]]:
    """Each author's mark: their override if they have one, else default_role()."""
    unknown = set(overrides) - set(authors)
    if unknown:
        raise ValueError(
            f"author_roles names {sorted(unknown)} who are not among the authors {list(authors)}")
    roles: List[Optional[str]] = []
    for author in authors:
        if author in overrides:
            roles.append(overrides[author])
        elif author == LAB_DIRECTOR:
            roles.append(None)
        else:
            person = spans.get(author_key(author))
            roles.append(default_role(person, year) if person else None)
    return roles


# ---------------------------------------------------------------------------
# LaTeX formatting
# ---------------------------------------------------------------------------

_LATEX_SPECIALS = {
    '\\': '\\textbackslash{}', '&': '\\&', '%': '\\%', '$': '\\$', '#': '\\#',
    '_': '\\_', '{': '\\{', '}': '\\}', '~': '\\textasciitilde{}', '^': '\\^{}',
}


def latex_escape(text: str) -> str:
    """Escape text for LaTeX, with typographic quotes and dashes."""
    text = ''.join(_LATEX_SPECIALS.get(ch, ch) for ch in str(text))
    text = re.sub(r'"([^"]*)"', r"``\1''", text)
    text = text.replace('“', '``').replace('”', "''")
    return text.replace('—', '--').replace('–', '--')


def html_to_latex(text: str) -> str:
    """Convert a spreadsheet description (markdown or simple HTML) to LaTeX."""
    html = markdown_to_html(text or '')
    out: List[str] = []
    stack: List[str] = []
    for token in re.split(r'(<[^>]+>)', html):
        tag = re.match(r'<(/?)(\w+)([^>]*)>', token)
        if not tag:
            out.append(latex_escape(token))
            continue
        closing, name, attrs = tag.group(1), tag.group(2).lower(), tag.group(3)
        if closing:
            if stack and stack[-1] == name:
                stack.pop()
                out.append('}')
            continue
        if name == 'a':
            href = re.search(r'href="([^"]*)"', attrs)
            out.append('\\href{%s}{' % (href.group(1).replace('%', '\\%').replace('#', '\\#')
                                         if href else ''))
        elif name in ('em', 'i'):
            out.append('\\textit{')
        elif name in ('strong', 'b'):
            out.append('\\textbf{')
        elif name == 'sup':
            out.append('\\textsuperscript{')
        else:
            continue  # drop tags with no LaTeX counterpart, keep their text
        stack.append(name)
    return ''.join(out) + '}' * len(stack)


def format_authors_tex(authors: Sequence[str], roles: Sequence[Optional[str]]) -> str:
    """Authors with the lab director in bold and trainees marked by role."""
    parts = []
    for author, role in zip(authors, roles):
        name = latex_escape(author)
        if author == LAB_DIRECTOR:
            name = '\\textbf{%s}' % name
        elif role:
            name = ROLE_MARKUP[role] % name
        parts.append(name)
    return ', '.join(parts)


def join_names(names: Sequence[str]) -> str:
    """'A', 'A and B', 'A, B, and C'."""
    if len(names) <= 2:
        return ' and '.join(names)
    return ', '.join(names[:-1]) + ', and ' + names[-1]


def end_sentence(text: str) -> str:
    """Text followed by a period, unless it already ends a sentence."""
    text = text.rstrip()
    ended = text.rstrip(')"\'').endswith(('.', '?', '!'))
    return text if ended else text + '.'


# Capitalized names a description may start with, which sentence_fragment
# would otherwise lowercase
PROPER_NOUNS = {'Android', 'Blender', 'Gmail', 'Google', 'Jupyter', 'Python', 'Thunderbird'}


def sentence_fragment(text: str, name: str = '') -> str:
    """Lowercase a description's first word so it can follow 'Name:'.

    Words written in capitals or with inner capitals (LLM, BrainIAK, MATLAB)
    are names and keep their case, as do the item's own name ('Clustrix is
    a Python package...') and the proper nouns in PROPER_NOUNS.
    """
    first = text.split(' ', 1)[0]
    if name and first.strip('.,:;').casefold() == name.split(' ', 1)[0].casefold():
        return text
    if first.strip('.,:;') in PROPER_NOUNS:
        return text
    if first[:1].isupper() and first[1:] == first[1:].lower():
        return text[0].lower() + text[1:]
    return text


def _year(item: Dict[str, str]) -> int:
    try:
        return int(float(item.get('year') or 0))
    except ValueError:
        raise ValueError(f"{item.get('title') or item.get('name')!r}: year {item.get('year')!r} is not a year")


def _authors_tex(item: Dict[str, str], spans: Dict[PersonKey, List[RoleSpan]]) -> str:
    authors = split_authors(item.get('authors', ''))
    try:
        overrides = parse_role_overrides(item.get('author_roles', ''))
        roles = resolve_roles(authors, _year(item), overrides, spans)
    except ValueError as e:
        raise ValueError(f"{item.get('title') or item.get('name')!r}: {e}") from None
    return format_authors_tex(authors, roles)


def _with_note(entry: str, item: Dict[str, str]) -> str:
    note = (item.get('cv_note') or '').strip()
    return f'{entry} {latex_escape(note)}' if note else entry


def paper_item(pub: Dict[str, str], spans: Dict[PersonKey, List[RoleSpan]]) -> str:
    """One \\item for a journal article, preprint or proceedings paper."""
    detail = paper_venue_detail(
        pub.get('journal', ''), pub.get('volume', ''), pub.get('issue', ''),
        pub.get('pages', ''), pub.get('status', ''))
    entry = (f"\\item {_authors_tex(pub, spans)} ({_year(pub)}) "
             f"{end_sentence(latex_escape(pub['title']))} "
             f"\\textit{{{latex_escape(pub.get('journal', ''))}}}{latex_escape(detail)}.")
    return _with_note(entry, pub)


def chapter_item(pub: Dict[str, str], spans: Dict[PersonKey, List[RoleSpan]]) -> str:
    """One \\item for a book chapter."""
    parts = [f"\\item {_authors_tex(pub, spans)} ({_year(pub)}) "
             f"{end_sentence(latex_escape(pub['title']))}"]
    editors = split_authors(pub.get('editors', ''))
    if editors:
        parts.append(f"In {latex_escape(join_names(editors))}, Ed.")
    parts.append(f"\\textit{{{latex_escape(pub.get('book_title', ''))}}}.")
    location, publisher = pub.get('publisher_location', ''), pub.get('publisher', '')
    if publisher:
        parts.append(latex_escape(f"{location}: {publisher}." if location else f"{publisher}."))
    if pub.get('chapter'):
        parts.append(f"Chapter {latex_escape(pub['chapter'])}.")
    elif pub.get('pages'):
        parts.append(f"pp. {latex_escape(pub['pages'])}.")
    return _with_note(' '.join(parts), pub)


def _fileexchange_label(url: str) -> str:
    number = re.search(r'(\d+)/?$', url)
    return f"MATLAB Central File Exchange: {number.group(1)}" if number else 'MATLAB Central File Exchange'


def software_item(item: Dict[str, str], spans: Dict[PersonKey, List[RoleSpan]]) -> str:
    """One \\item for a software package, with the website's links."""
    links = []
    for column, label in (('github_link', 'GitHub'), ('pypi_link', 'PyPI'), ('docs_link', 'Docs')):
        if item.get(column):
            links.append((label, item[column]))
    if item.get('fileexchange_link'):
        links.append((_fileexchange_label(item['fileexchange_link']), item['fileexchange_link']))
    links.extend(parse_extra_links(item.get('extra_links', '')))

    description = end_sentence(sentence_fragment(html_to_latex(item.get('description', '')), item['name']))
    parts = [f"\\item {_authors_tex(item, spans)} ({_year(item)}) "
             f"{latex_escape(item['name'])}: {description}"]
    for label, url in links:
        parts.append(f"\\href{{{url}}}{{{latex_escape(label)}}}.")
    return ' '.join(parts)


# ---------------------------------------------------------------------------
# Lists and blocks
# ---------------------------------------------------------------------------

def _newest_first(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    # sorted() is stable, so items from the same year keep spreadsheet order
    return sorted(items, key=lambda item: -_year(item))


def publications_block(pubs: Dict[str, List[Dict[str, str]]],
                       spans: Dict[PersonKey, List[RoleSpan]]) -> str:
    """The CV's publication list: papers and chapters, newest first."""
    tagged = [dict(item, _kind='papers') for item in pubs.get('papers', [])]
    tagged += [dict(item, _kind='chapters') for item in pubs.get('chapters', [])]
    entries = []
    for item in _newest_first(tagged):
        make = paper_item if item['_kind'] == 'papers' else chapter_item
        entries.append(make(item, spans))
    return '\n\n'.join(entries)


def software_block(software: Dict[str, List[Dict[str, str]]],
                   spans: Dict[PersonKey, List[RoleSpan]]) -> str:
    """The CV's software list: every package on the software page, newest first."""
    items = [item for sheet in software.values() for item in sheet]
    return '\n'.join(software_item(item, spans) for item in _newest_first(items))


def replace_block(tex: str, block: str, body: str) -> str:
    """Put body between a block's markers. Missing markers are an error."""
    begin, end = begin_marker(block), end_marker(block)
    pattern = re.compile(
        r'^% BEGIN GENERATED ' + block + r'\b[^\n]*\n.*?^' + re.escape(end) + r'$',
        re.DOTALL | re.MULTILINE)
    matches = pattern.findall(tex)
    if len(matches) != 1:
        raise ValueError(
            f"expected one '% BEGIN GENERATED {block}' ... '{end}' pair in the CV, found {len(matches)}")
    return pattern.sub(lambda _: f'{begin}\n{body}\n{end}', tex)


def generate_cv_tex(
    tex: str,
    cv_path: Path = CV_PATH,
    publications_path: Path = PUBLICATIONS_PATH,
    software_path: Path = SOFTWARE_PATH,
) -> str:
    """The CV source with its generated blocks rebuilt from the spreadsheets."""
    spans = load_role_spans(cv_path)
    tex = replace_block(tex, 'PUBLICATIONS',
                        publications_block(load_publications(publications_path), spans))
    return replace_block(tex, 'SOFTWARE', software_block(load_software(software_path), spans))


def sync_cv(
    cv_path: Path = CV_PATH,
    publications_path: Path = PUBLICATIONS_PATH,
    software_path: Path = SOFTWARE_PATH,
    check: bool = False,
) -> bool:
    """Rebuild the CV's generated blocks. Returns True if they were out of date.

    With check=True nothing is written.
    """
    tex = cv_path.read_text(encoding='utf-8')
    new_tex = generate_cv_tex(tex, cv_path, publications_path, software_path)
    if new_tex == tex:
        return False
    if not check:
        cv_path.write_text(new_tex, encoding='utf-8')
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--check', action='store_true',
                        help='exit 1 if the CV is out of date with the spreadsheets; write nothing')
    args = parser.parse_args()
    stale = sync_cv(check=args.check)
    if args.check:
        print(f"{CV_PATH.name}: {'out of date' if stale else 'up to date'}")
        return 1 if stale else 0
    print(f"{CV_PATH.name}: {'updated' if stale else 'already up to date'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
