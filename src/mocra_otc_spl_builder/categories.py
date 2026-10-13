"""FDA cosmetic product categories (guidance Appendix A), built by scripts/build_cosmetic_categories.py."""

import json
from functools import cache
from importlib import resources

from .completeness import Finding
from .models import Category


@cache
def _data() -> dict:
    path = resources.files("mocra_otc_spl_builder") / "data" / "cosmetic_categories.json"
    return json.loads(path.read_text(encoding="utf-8"))


@cache
def _by_code() -> dict[str, dict]:
    return {e["code"]: e for e in _data()["categories"]}


def category(code: str) -> Category:
    """The Category for an Appendix A code, e.g. category("05B") for perfumes."""
    entry = _by_code().get(code)
    if entry is None:
        raise KeyError(f"{code} is not an FDA cosmetic category code")
    if not entry["selectable"]:
        options = ", ".join(e["code"] for e in _data()["categories"] if e["parent"] == code)
        raise ValueError(f"{code} has subcategories; use one of {options}")
    return Category(code, entry["display_name"])


def category_findings(where: str, categories: list[Category]) -> list[Finding]:
    findings = []
    for c in categories:
        entry = _by_code().get(c.code)
        if entry is None:
            findings.append(Finding(where, f"{c.code} is not in FDA's category list (guidance Appendix A; IG 3.4.3.3)"))
        elif not entry["selectable"]:
            findings.append(Finding(where, f"{c.code} has subcategories; list the specific one (guidance Appendix A)"))
        elif c.display_name.casefold() != entry["display_name"].casefold():
            findings.append(Finding(where, f"{c.code}: display name should be '{entry['display_name']}' (IG 3.4.3.4)"))
    return findings
