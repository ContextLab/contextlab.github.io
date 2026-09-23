"""The one order people are listed in, everywhere they are listed.

people.xlsx, JRM_CV.tex and the lab manual all list people newest first by
start year, then alphabetically by name -- the CV's order, which build_people
also uses for the people page. Onboarding and offboarding insert entries with
insert_item_sorted() so every list stays in that order instead of drifting
(new entries used to go at the top of a list, or at the bottom).
"""

import re
from typing import Tuple

# An \item, its name, and the first year inside its parentheses. The
# parentheses may hold a qualifier before the years, possibly across a line
# break: '(Masters student, Quantitative Biomedical\nSciences; 2018 -- 2020)'.
_ITEM_RE = re.compile(r"\\item\s+([^(\n]+?)\*?\s*\(([^)]*)\)")
_YEAR_RE = re.compile(r"\d{4}")


def order_key(name: str, start_year) -> Tuple[int, str]:
    """Sort key: newest start year first, then name, case-insensitively."""
    return (-int(start_year), name.strip().casefold())


def insert_item_sorted(items_text: str, item_line: str, name: str, start_year) -> str:
    """Insert item_line into the \\item lines of one list at its sorted position.

    items_text is everything between a list's \\begin and \\end. The new item
    goes before the first existing item that sorts after it, taking that line's
    indentation; if none does, it goes after the last item.
    """
    key = order_key(name, start_year)
    items = [m for m in _ITEM_RE.finditer(items_text) if _YEAR_RE.search(m.group(2))]

    for m in items:
        year = _YEAR_RE.search(m.group(2))
        assert year is not None
        if order_key(m.group(1), year.group(0)) > key:
            line_start = items_text.rfind("\n", 0, m.start()) + 1
            lead = items_text[line_start:m.start()]
            # An item that starts its line keeps its indentation for the new
            # line; one that shares a line ('\begin{etaremune}  \item ...')
            # gets the two-space indent the CV uses.
            indent = lead if lead.strip() == "" else "  "
            return items_text[:m.start()] + item_line + "\n" + indent + items_text[m.start():]

    if items:
        last = items[-1]
        line_start = items_text.rfind("\n", 0, last.start()) + 1
        lead = items_text[line_start:last.start()]
        indent = lead if lead.strip() == "" else "  "
        return items_text[:last.end()] + "\n" + indent + item_line + items_text[last.end():]

    return items_text.rstrip("\n") + "\n" + item_line + "\n"
