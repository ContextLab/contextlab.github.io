"""Tests for people_order.py: the shared newest-first, then-by-name order."""

import re
from pathlib import Path

from people_order import insert_item_sorted, order_key

REPO = Path(__file__).parent.parent


def names(text):
    return re.findall(r"\\item\s+([^(\n]+?)\*?\s*\(", text)


class TestOrderKey:
    def test_newer_start_sorts_first(self):
        assert order_key("Zed", 2026) < order_key("Amy", 2025)

    def test_same_year_sorts_by_name_ignoring_case(self):
        assert order_key("amy", 2025) < order_key("Bob", 2025)


class TestInsertItemSorted:
    BLOCK = (
        "\n  \\item Carl Doe (2026 -- )"
        "\n  \\item Amy Roe (2025 -- 2026)"
        "\n  \\item Zoe Poe (2025)"
        "\n  \\item Bea Loe (2023 -- 2024)"
    )

    def test_lands_inside_its_year_in_name_order(self):
        out = insert_item_sorted(self.BLOCK, "\\item Mia Hoe (2025 -- )", "Mia Hoe", 2025)
        assert names(out) == ["Carl Doe", "Amy Roe", "Mia Hoe", "Zoe Poe", "Bea Loe"]
        assert "\n  \\item Mia Hoe (2025 -- )\n  \\item Zoe Poe" in out

    def test_newest_goes_first_with_the_lists_indent(self):
        out = insert_item_sorted(self.BLOCK, "\\item Ann Coe (2026 -- )", "Ann Coe", 2026)
        assert names(out)[:2] == ["Ann Coe", "Carl Doe"]
        assert out.startswith("\n  \\item Ann Coe (2026 -- )\n  \\item Carl Doe")

    def test_oldest_goes_last(self):
        out = insert_item_sorted(self.BLOCK, "\\item Old Timer (2016)", "Old Timer", 2016)
        assert names(out)[-1] == "Old Timer"
        assert out.endswith("\n  \\item Old Timer (2016)")

    def test_trailing_end_stays_after_the_new_last_item(self):
        # The CV writes some lists as '...PyMC Labs)\end{etaremune}'.
        block = "  \\item Gina Notaro (2017 -- 2018; current position: HRL)"
        out = insert_item_sorted(block, "\\item New Postdoc (2010 -- )", "New Postdoc", 2010)
        assert names(out) == ["Gina Notaro", "New Postdoc"]

    def test_qualified_grad_entries_sort_by_their_year(self):
        block = (
            "\n\\item Claudia Gonciulea (Doctoral student; 2025 -- )"
            "\n\\item Max Bluestone (Masters student, Quantitative Biomedical\nSciences; 2018 -- 2020)"
        )
        out = insert_item_sorted(
            block, "\\item New Grad (Doctoral student; 2021 -- )", "New Grad", 2021
        )
        assert names(out) == ["Claudia Gonciulea", "New Grad", "Max Bluestone"]

    def test_empty_list_gets_the_item(self):
        out = insert_item_sorted("\n", "\\item Solo (2026 -- )", "Solo", 2026)
        assert names(out) == ["Solo"]


class TestRealListsAreAlreadySorted:
    """The real CV lists this helper maintains must already be in its order."""

    def cv_block(self, label):
        text = (REPO / "documents" / "JRM_CV.tex").read_text(encoding="utf-8")
        head = text.index(r"\textit{" + label + "}")
        beg = text.index(r"\begin{etaremune}", head) + len(r"\begin{etaremune}")
        return text[beg:text.index(r"\end{etaremune}", beg)]

    def keys(self, block):
        out = []
        for m in re.finditer(r"\\item\s+([^(\n]+?)\*?\s*\(([^)]*)\)", block):
            out.append(order_key(m.group(1), re.search(r"\d{4}", m.group(2)).group(0)))
        return out

    def test_undergrad_advisees_sorted(self):
        k = self.keys(self.cv_block("Undergraduate Advisees"))
        assert k == sorted(k)

    def test_graduate_advisees_sorted(self):
        k = self.keys(self.cv_block("Graduate Advisees"))
        assert k == sorted(k)

    def test_postdoctoral_advisees_sorted(self):
        k = self.keys(self.cv_block("Postdoctoral Advisees"))
        assert k == sorted(k)
