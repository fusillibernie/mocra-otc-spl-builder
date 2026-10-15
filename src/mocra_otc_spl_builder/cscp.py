"""California Safe Cosmetics Program (CSCP) reporting of fragrance and flavor ingredients (SB 312).

Two things are reportable to CDPH for a cosmetic sold in California:
  1. fragrance allergens at or above 0.001% (leave-on) or 0.01% (rinse-off), whatever their function;
  2. fragrance and flavor ingredients on CDPH's Reportable Ingredients List, at any concentration.

Reporting is through CDPH's web portal, so the output is a data pack for a person to enter, with
this package's field names, not a submission. Rules are in data/cscp_rules.json and are NOT yet
verified against CDPH's own pages; the ingredient list is not loaded (data/cscp_reportable_
ingredients.json awaits an importer), so a report is never "complete" until it is.

The allergen figures come from fragrance-reg-core (the optional `core` extra): the same supplier
declarations, naturals estimates and rounding checks as the US ingredient list.
"""

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import date
from importlib import resources

from .completeness import Finding

TOLERANCE = 1e-12  # floating-point noise: 0.01% of 10% is 0.0010000000000000002


def load_rules() -> dict:
    return json.loads((resources.files("mocra_otc_spl_builder") / "data" / "cscp_rules.json").read_text(encoding="utf-8"))


@dataclass
class ReportableList:
    """CDPH's Reportable Ingredients List, keyed by CAS number."""

    entries: dict[str, dict] = field(default_factory=dict)
    verified: bool = False

    @property
    def loaded(self) -> bool:
        return bool(self.entries)

    @classmethod
    def from_records(cls, records: list[dict], verified: bool = False) -> "ReportableList":
        return cls({r["cas"]: r for r in records}, verified)

    @classmethod
    def load(cls) -> "ReportableList":
        path = resources.files("mocra_otc_spl_builder") / "data" / "cscp_reportable_ingredients.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_records(doc.get("ingredients", []), bool(doc.get("metadata", {}).get("verified")))


@dataclass
class AllergenRow:
    name: str
    cas_number: str
    percentage: float  # % w/w in the finished product
    threshold: float
    estimated: bool  # estimated from reference data for a natural, not declared by the supplier
    sources: list[str]


@dataclass
class ListedIngredient:
    name: str
    cas_number: str
    lists: list[str]
    component: str
    max_percentage: float  # % in the finished product, upper bound from the supplier's figure


@dataclass
class CscpReport:
    product_name: str
    leave_on: bool
    allergens: list[AllergenRow] = field(default_factory=list)
    listed_ingredients: list[ListedIngredient] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)  # block: the report is not complete
    warnings: list[str] = field(default_factory=list)  # a person should read these
    list_loaded: bool = False
    rules_verified: bool = False

    @property
    def complete(self) -> bool:
        return not self.findings

    def rows(self) -> list[dict]:
        base = {"product": self.product_name, "type": "leave-on" if self.leave_on else "rinse-off"}
        out = [
            {**base, "section": "fragrance allergen", "ingredient": a.name, "cas": a.cas_number,
             "percent": f"{a.percentage:.6f}", "threshold_percent": f"{a.threshold:g}",
             "estimated": "yes" if a.estimated else "", "from": "; ".join(a.sources), "lists": ""}
            for a in self.allergens
        ]
        out += [
            {**base, "section": "reportable list ingredient", "ingredient": i.name, "cas": i.cas_number,
             "percent": f"<= {i.max_percentage:.6f}", "threshold_percent": "any", "estimated": "",
             "from": i.component, "lists": "; ".join(i.lists)}
            for i in self.listed_ingredients
        ]
        return out

    def to_csv(self) -> str:
        columns = ["product", "type", "section", "ingredient", "cas", "percent", "threshold_percent", "estimated", "from", "lists"]
        buf = io.StringIO()
        writer = csv.DictWriter(buf, columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(self.rows())
        return buf.getvalue()


def _at_or_above(value: float, threshold: float) -> bool:
    return value - threshold >= -TOLERANCE


def _allergen_totals(service, product, as_of: date, core_findings: list):
    """Allergen totals per name across every component, from fragrance-reg-core.

    This calls LabelingService._allergen_contributions, which is private in core v0.6.0. Ask core to
    expose it (planned for the next release) and switch to that; the tests in tests/test_cscp.py
    exercise this call so a change in core fails loudly.
    """
    from fragrance_reg_core.models.regulatory import Market

    return service._allergen_contributions(product, Market.US, core_findings, as_of)


def cscp_report(product, as_of: date | None = None, labeling_service=None, reportable_list: ReportableList | None = None) -> CscpReport:
    """What to report to CSCP for a fragrance_reg_core FinishedProduct."""
    from fragrance_reg_core.models.findings import Severity
    from fragrance_reg_core.models.product import ComponentRole
    from fragrance_reg_core.services.labeling_service import LabelingService, title_inci

    as_of = as_of or date.today()
    rules = load_rules()
    allergen_rules = rules["allergens"]
    service = labeling_service or LabelingService()
    reportable_list = reportable_list or ReportableList.load()
    report = CscpReport(
        product_name=product.name, leave_on=product.is_leave_on,
        list_loaded=reportable_list.loaded, rules_verified=bool(rules["metadata"]["verified"]),
    )
    threshold = allergen_rules["leave_on_percent"] if product.is_leave_on else allergen_rules["rinse_off_percent"]

    # 1. Fragrance allergens
    core_findings: list = []
    totals = _allergen_totals(service, product, as_of, core_findings)
    for t in totals.values():
        if not any(getattr(t.allergen, flag, False) for flag in allergen_rules["list_flags"]):
            continue
        if _at_or_above(t.percentage, threshold):
            report.allergens.append(AllergenRow(
                title_inci(t.allergen.inci_name or t.allergen.name), t.allergen.cas_number,
                t.percentage, threshold, t.estimated, list(t.sources)))
        elif _at_or_above(t.percentage + t.uncertainty, threshold):
            report.warnings.append(
                f"{title_inci(t.allergen.inci_name or t.allergen.name)} works out at {t.percentage:.5f}%, under the "
                f"{threshold:g}% threshold, but the supplier's rounding allows up to {t.percentage + t.uncertainty:.5f}%. "
                f"Ask for the unrounded value.")
    report.allergens.sort(key=lambda a: (-a.percentage, a.name))

    for f in core_findings:
        text = f"{f.message}" + (f" ({f.component})" if f.component else "")
        if f.code == "label.no_allergen_declaration" or f.severity == Severity.ERROR:
            report.findings.append(Finding("allergens", text))
        elif f.severity == Severity.WARNING:
            report.warnings.append(text)

    accepted = set(allergen_rules["accepted_declaration_basis"])
    for c in product.components:
        if c.role != ComponentRole.FRAGRANCE or c.full_composition:
            continue
        if c.allergen_list_basis is None:
            report.warnings.append(f"{c.name}: the allergen declaration doesn't say which list it covers; confirm it covers the expanded (82) list.")
        elif c.allergen_list_basis not in accepted:
            report.findings.append(Finding(
                "allergens",
                f"{c.name}: the allergen declaration covers the '{c.allergen_list_basis}' list only. CDPH's list appears to "
                f"track the expanded EU list, so allergens may be missing; request a current declaration."))

    # 2. Fragrance and flavor ingredients on CDPH's Reportable Ingredients List (any concentration)
    if not reportable_list.loaded:
        report.findings.append(Finding(
            "reportable_ingredients_list",
            "CDPH's Reportable Ingredients List isn't loaded, so fragrance and flavor ingredients that are "
            "reportable at any concentration can't be checked."))
    else:
        for c in product.components:
            if c.role == ComponentRole.FRAGRANCE and not c.full_composition:
                report.findings.append(Finding(
                    "reportable_ingredients_list",
                    f"{c.name}: no full composition, so list ingredients below allergen level can't be ruled out. "
                    f"Ask the supplier to state which Reportable Ingredients List substances it contains."))
            for s in (c.full_composition or []):
                for cas in s.all_cas:
                    if cas in reportable_list.entries:
                        entry = reportable_list.entries[cas]
                        report.listed_ingredients.append(ListedIngredient(
                            entry.get("name") or s.name, cas, list(entry.get("lists", [])), c.name,
                            s.percentage * c.percentage / 100.0))
                        break
    return report
