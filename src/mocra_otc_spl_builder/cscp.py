"""California Safe Cosmetics Program (CSCP) reporting of fragrance and flavor ingredients (SB 312).

Reportable to CDPH for a cosmetic sold in California, per the "When to Report" column of CDPH's
Reportable Ingredients List (data/cscp_reportable_ingredients.json, built by scripts/build_cscp_list.py):
  FA   fragrance allergens at or above 0.001% (leave-on) or 0.01% (rinse-off), whatever their function;
  FF   ingredients used as a fragrance or flavor ingredient, at any concentration;
  Any  ingredients on the list, at any concentration, whatever their function.

Reporting is through CDPH's web portal, so the output is a data pack for a person to enter, with
this package's field names, not a submission. Rules are in data/cscp_rules.json and are NOT yet
verified against CDPH's own pages. When the list is loaded, CDPH's FA entries decide which
allergens are reportable (core's EU-82 flags are only the fallback: they include substances that
are not on CDPH's list).

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
    without_cas: list[dict] = field(default_factory=list)  # CDPH rows with no CAS number: match by name

    @property
    def loaded(self) -> bool:
        return bool(self.entries)

    @property
    def allergen_cas(self) -> frozenset[str]:
        """CAS numbers CDPH lists as fragrance allergens (When to Report includes FA)."""
        return frozenset(c for c, r in self.entries.items() if "FA" in r.get("when", []))

    def group(self, cas: str) -> str:
        """Key shared by the CAS numbers of one CDPH row (isomers, oil variants); the CAS itself if unlisted."""
        entry = self.entries.get(cas)
        return _norm(entry["name"]) if entry else cas

    def name_matches(self, name: str) -> list[dict]:
        """Rows without a CAS number whose name or a synonym equals `name` (case-insensitive)."""
        key = _norm(name)
        return [r for r in self.without_cas if key in {_norm(n) for n in [r["name"], *r.get("synonyms", [])]}]

    @classmethod
    def from_records(cls, records: list[dict], verified: bool = False, without_cas: list[dict] | None = None) -> "ReportableList":
        return cls({r["cas"]: r for r in records}, verified, list(without_cas or []))

    @classmethod
    def load(cls) -> "ReportableList":
        path = resources.files("mocra_otc_spl_builder") / "data" / "cscp_reportable_ingredients.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_records(
            doc.get("ingredients", []), bool(doc.get("metadata", {}).get("verified")), doc.get("ingredients_without_cas", []))


def _norm(name: str) -> str:
    return " ".join(str(name).lower().split())


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
    when: list[str] = field(default_factory=list)  # CDPH "When to Report": Any / FF / FA


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


def _substances(product):
    """(component, substance name, CAS numbers, % of the finished product) for everything the product states.

    Reads the full composition, else the allergen declaration, and the component's own CAS number
    (a single-substance component, or a botanical oil that is itself listed).
    """
    for c in product.components:
        for s in (c.full_composition or c.allergen_declaration or []):
            yield c, s.name, list(s.all_cas), s.percentage * c.percentage / 100.0
        if c.cas_number:
            yield c, c.inci_name or c.name, [c.cas_number], c.percentage


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
    fa_cas = reportable_list.allergen_cas
    for t in totals.values():
        if fa_cas:
            if t.allergen.cas_number not in fa_cas:
                continue
        elif not any(getattr(t.allergen, flag, False) for flag in allergen_rules["list_flags"]):
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
    if not fa_cas:
        report.warnings.append(
            "Allergens were chosen with core's EU flags because CDPH's list isn't loaded; CDPH's own allergen list differs.")
    if fa_cas:
        # core resolves a declared name to one of its own records, which may not be the CAS CDPH lists
        # (spearmint oil 8008-79-5 vs core's 8022-56-8) or may not exist in core at all (isomer variants),
        # so also total what the product states under CDPH's own CAS numbers.
        covered = {reportable_list.group(a.cas_number) for a in report.allergens} | {
            reportable_list.group(t.allergen.cas_number) for t in totals.values() if t.allergen.cas_number in fa_cas}
        direct: dict[str, dict] = {}
        for c, name, cas_numbers, pct in _substances(product):
            cas = next((k for k in cas_numbers if k in fa_cas), None)
            if cas is None or reportable_list.group(cas) in covered:
                continue
            row = direct.setdefault(reportable_list.group(cas), {"cas": cas, "name": reportable_list.entries[cas]["name"], "pct": 0.0, "from": []})
            row["pct"] += pct
            if c.name not in row["from"]:
                row["from"].append(c.name)
        for row in direct.values():
            if _at_or_above(row["pct"], threshold):
                report.allergens.append(AllergenRow(row["name"], row["cas"], row["pct"], threshold, False, row["from"]))
                report.warnings.append(
                    f"{row['name']} ({row['cas']}) is on CDPH's allergen list but core's allergen data doesn't match it, so "
                    f"its {row['pct']:.5f}% is a plain sum of the declared figures, with no rounding check or naturals estimate.")
        report.allergens.sort(key=lambda a: (-a.percentage, a.name))
    reported = {reportable_list.group(a.cas_number) for a in report.allergens}

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

    # 2. Everything else on CDPH's list: Any (whatever its function) and FF (used as a fragrance or flavor)
    if not reportable_list.loaded:
        report.findings.append(Finding(
            "reportable_ingredients_list",
            "CDPH's Reportable Ingredients List isn't loaded, so ingredients reportable at any concentration "
            "can't be checked."))
        return report
    unchecked = []
    for c in product.components:
        if c.role == ComponentRole.FRAGRANCE and not c.full_composition:
            report.findings.append(Finding(
                "reportable_ingredients_list",
                f"{c.name}: no full composition, so list ingredients below allergen level can't be ruled out. "
                f"Ask the supplier to state which Reportable Ingredients List substances it contains."))
        elif not (c.full_composition or c.cas_number):
            unchecked.append(c.name)
    found: dict[str, ListedIngredient] = {}
    flavor_unsure: set[tuple[str, str]] = set()
    for c, name, cas_numbers, pct in _substances(product):
        entries = [(k, reportable_list.entries[k]) for k in cas_numbers if k in reportable_list.entries]
        if not entries:
            for row in reportable_list.name_matches(name):
                report.warnings.append(
                    f"{c.name}: '{name}' matches CDPH list entry '{row['name']}', which has no CAS number "
                    f"({'/'.join(row['when'])}). Confirm and report it if it applies.")
            continue
        is_fragrance = c.role == ComponentRole.FRAGRANCE
        for cas, entry in entries:
            when = entry.get("when") or ["Any"]  # a record without "when" is treated as reportable at any concentration
            if "Any" in when or ("FF" in when and is_fragrance):
                if reportable_list.group(cas) in reported:
                    break  # already an allergen row
                hit = found.get(cas)
                if hit is None:
                    found[cas] = ListedIngredient(entry.get("name") or name, cas, list(entry.get("lists", [])), c.name, pct, list(when))
                else:
                    hit.max_percentage += pct
                    hit.component = hit.component if c.name in hit.component.split("; ") else f"{hit.component}; {c.name}"
                break
            if "FF" in when and (c.name, cas) not in flavor_unsure:
                flavor_unsure.add((c.name, cas))
                report.warnings.append(
                    f"{c.name}: {entry.get('name') or name} ({cas}) is reportable if used as a fragrance or flavor ingredient. "
                    f"core has no flavor role, so confirm whether this component is one.")
    report.listed_ingredients = sorted(found.values(), key=lambda i: (-i.max_percentage, i.name))
    if unchecked:
        report.warnings.append(
            "No composition for " + ", ".join(unchecked) + ": ingredients CDPH lists as reportable whatever their "
            "function ('Any') can't be checked in them. Add their constituents with CAS numbers.")
    return report
