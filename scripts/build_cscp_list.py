"""Builds data/cscp_reportable_ingredients.json from CDPH's Reportable Ingredients List workbook
(sources/cdph_reportable_ingredients_list_2026-04.xlsx, "Reportable Ingredients List" sheet).

Needs openpyxl. Usage: python scripts/build_cscp_list.py [--dry-run] [--source PATH]
Without --source it uses the newest workbook under sources/cdph/ (what the monthly refresh downloads), else the committed one.

One record per CAS number (a row naming several CAS numbers becomes several records; a CAS in
several rows is merged). Rows with no CAS number go under "ingredients_without_cas": CDPH says
those must still be reported, so they are matched by name or synonym, not by CAS.

"when" is CDPH's column F: Any (report whatever the ingredient's function), FF (report if used as
a fragrance or flavor ingredient), FA (fragrance allergen: report at or above 0.001% leave-on /
0.01% rinse-off).
"""

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "sources" / "cdph_reportable_ingredients_list_2026-04.xlsx"  # fallback: the edition committed by hand
DOWNLOADS = ROOT / "sources" / "cdph"  # where scripts/refresh_sources.py saves CDPH files
OUT = ROOT / "src" / "mocra_otc_spl_builder" / "data" / "cscp_reportable_ingredients.json"
SHEET = "Reportable Ingredients List"
HEADER = ["Chemical Name", "CAS RN", "Synonyms", "Hazard Traits", "Authoritative List", "When to Report (Any, FF, FA)"]
WHEN = {"ANY": "Any", "FF": "FF", "FA": "FA"}

def cas_ok(cas: str) -> bool:
    digits = cas.replace("-", "")
    return sum(int(d) * w for w, d in enumerate(reversed(digits[:-1]), 1)) % 10 == int(digits[-1])


CAS_IN = re.compile(r"\b\d{2,7}-\d{2}-\d\b")


def split(cell, pattern=r"\s*;\s*|\n") -> list[str]:
    return [p.strip() for p in re.split(pattern, str(cell)) if p and p.strip()] if cell else []


def when_codes(cell) -> list[str]:
    parts = [c.strip().upper() for c in re.split(r"[,;/]", str(cell or "")) if c.strip()]
    if not parts or any(c not in WHEN for c in parts):
        raise ValueError(f"Unrecognized 'When to Report' value: {cell!r}")
    return [WHEN[c] for c in parts]


def merge_into(rec: dict, name: str, synonyms, traits, lists, when):
    if name != rec["name"] and name not in rec["synonyms"]:
        rec["synonyms"].append(name)
    for key, values in (("synonyms", synonyms), ("hazard_traits", traits), ("lists", lists), ("when", when)):
        rec[key] += [v for v in values if v not in rec[key]]


def build(path: Path) -> dict:
    import openpyxl

    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)[SHEET]
    rows = list(ws.iter_rows(values_only=True))
    if [str(c).strip() for c in rows[0][:6]] != HEADER:
        raise ValueError(f"Unexpected header row: {rows[0][:6]}")
    by_cas: dict[str, dict] = {}
    no_cas: list[dict] = []
    for row in rows[1:]:
        if not row[0]:
            continue
        name = str(row[0]).strip()
        synonyms, traits, lists, when = split(row[2]), split(row[3]), split(row[4]), when_codes(row[5])
        cas_numbers = list(dict.fromkeys(CAS_IN.findall(str(row[1] or ""))))  # cells may add notes: "50-00-0 (Formaldehyde)"
        unparsed = str(row[1]).strip() if row[1] and not cas_numbers else None  # CDPH typo: keep it visible, don't guess
        if not cas_numbers:
            rec = {"name": name, "synonyms": synonyms, "hazard_traits": traits, "lists": lists, "when": when}
            if unparsed:
                rec["unparsed_cas"] = unparsed
            no_cas.append(rec)
            continue
        for cas in cas_numbers:
            rec = by_cas.setdefault(cas, {"cas": cas, "name": name, "synonyms": [], "hazard_traits": [], "lists": [], "when": []})
            merge_into(rec, name, synonyms, traits, lists, when)
            if not cas_ok(cas):
                rec["source_cas_invalid"] = True  # CDPH publishes it with a bad check digit; kept as published
    for rec in [*by_cas.values(), *no_cas]:
        rec["when"].sort(key=["Any", "FF", "FA"].index)
    ingredients = sorted(by_cas.values(), key=lambda r: r["cas"])
    count = lambda code: sum(code in r["when"] for r in ingredients)  # noqa: E731
    return {
        "metadata": {
            "description": f"CSCP Reportable Ingredients List (CDPH Occupational Health Branch), {edition(path)} edition",
            "verified": True,
            "verification_note": (
                "Transcribed mechanically from CDPH's workbook (file name and hash below); not compared with the live CDPH page. "
                "CDPH updates the list twice a year (6 months to comply after each update), so check for a newer edition."
            ),
            "official_source": "https://www.cdph.ca.gov/Programs/CCDPHP/DEODC/OHB/CSCP/Pages/ReportingGuidance.aspx",
            "source_file": path.name,
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "legend": {
                "Any": "report regardless of the ingredient's function in the product",
                "FF": "report if used as a fragrance or flavor ingredient",
                "FA": "fragrance allergen: report if at or above 0.01% in a rinse-off or 0.001% in a leave-on product",
            },
            "counts": {
                "rows": sum(1 for r in rows[1:] if r[0]),
                "cas_records": len(ingredients), "Any": count("Any"), "FF": count("FF"), "FA": count("FA"),
                "without_cas": len(no_cas),
            },
            "record_format": {
                "cas": "78-70-6", "name": "...", "synonyms": ["..."], "hazard_traits": ["..."],
                "lists": ["authoritative list names"], "when": ["Any | FF | FA"],
            },
        },
        "ingredients": ingredients,
        "ingredients_without_cas": no_cas,
    }


def find_source() -> Path:
    """The newest Reportable Ingredients List workbook that refresh_sources.py downloaded, else SOURCE."""
    found = [p for p in DOWNLOADS.rglob("*.xlsx") if "reportable" in p.name.lower()] if DOWNLOADS.exists() else []
    return max(found, key=lambda p: p.stat().st_mtime) if found else SOURCE


def edition(path: Path) -> str:
    """'April 2026' from the workbook's Introduction sheet."""
    import openpyxl

    for row in openpyxl.load_workbook(path, read_only=True, data_only=True)["Introduction"].iter_rows(values_only=True):
        for cell in row:
            if cell and re.fullmatch(r"[A-Z][a-z]+\.? \d{4}", str(cell).strip()):
                return str(cell).strip()
    return "unknown edition"


def main(argv: list[str]) -> int:
    path = Path(argv[argv.index("--source") + 1]) if "--source" in argv else find_source()
    doc = build(path)
    print(json.dumps(doc["metadata"]["counts"]))
    if "--dry-run" not in argv:
        OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
