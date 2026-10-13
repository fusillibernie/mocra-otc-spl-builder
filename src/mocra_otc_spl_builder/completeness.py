"""Gaps that would stop a submission. Every gap is a Finding; nothing is filled in by guessing."""

import json
from dataclasses import dataclass
from importlib import resources

from .models import CosmeticProduct, Facility, OtcProduct


@dataclass(frozen=True)
class Finding:
    field: str
    message: str


def load_monographs() -> dict:
    path = resources.files("mocra_otc_spl_builder") / "data" / "otc_monographs.json"
    return json.loads(path.read_text())


def _facility_findings(facilities: list[Facility]) -> list[Finding]:
    if not facilities:
        return [Finding("facilities", "at least one facility is required")]
    return [
        Finding(f"facilities[{i}]", f"{f.name}: no FEI or DUNS number")
        for i, f in enumerate(facilities)
        if not (f.fei or f.duns)
    ]


def check_cosmetic_product(product: CosmeticProduct) -> list[Finding]:
    findings = _facility_findings(product.facilities)
    rp = product.responsible_person
    if not (rp.name and rp.address):
        findings.append(Finding("responsible_person", "name and address are required"))
    if not product.category_codes:
        findings.append(Finding("category_codes", "no cosmetic product category"))
    if not product.ingredients:
        findings.append(Finding("ingredients", "no ingredient list"))
    if not product.label_files:
        findings.append(Finding("label_files", "no label attached"))
    return findings


def check_otc_product(product: OtcProduct, monographs: dict | None = None) -> list[Finding]:
    monographs = monographs if monographs is not None else load_monographs()
    findings = _facility_findings(product.facilities)
    if not product.labeler_code:
        findings.append(Finding("labeler_code", "no NDC labeler code; request one first"))
    if not product.active_ingredients:
        findings.append(Finding("active_ingredients", "an OTC drug needs an active ingredient"))
    for i, a in enumerate(product.active_ingredients):
        if not (a.unii and a.strength):
            findings.append(Finding(f"active_ingredients[{i}]", f"{a.name}: UNII and strength are required"))
    if not product.drug_facts_file:
        findings.append(Finding("drug_facts_file", "no Drug Facts label attached"))

    known = {m["id"]: m for m in monographs.get("monographs", [])}
    if product.monograph_id not in known:
        findings.append(Finding("monograph_id", f"{product.monograph_id or '(none)'} is not in otc_monographs.json"))
    elif not monographs.get("metadata", {}).get("verified") and not known[product.monograph_id].get("verified"):
        findings.append(Finding("monograph_id", f"{product.monograph_id} limits not yet verified against the order"))
    return findings
