"""Builds data/cosmetic_categories.json from Appendix A of FDA's cosmetics registration and
listing guidance (sources/fda_guidance_cosmetics_registration_listing_2024-12.pdf).

Needs `pdftotext` (poppler). Usage: python scripts/build_cosmetic_categories.py [--dry-run]
"""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "sources" / "fda_guidance_cosmetics_registration_listing_2024-12.pdf"
OUT = ROOT / "src" / "mocra_otc_spl_builder" / "data" / "cosmetic_categories.json"


def appendix_a(text: str) -> list[str]:
    start = text.index("Cosmetic Product Categories and Codes")
    end = text.index("APPENDIX B", start)
    lines = []
    for raw in text[start:end].splitlines()[1:]:
        line = raw.strip()
        if not line or line == "Contains Nonbinding Recommendations" or line.isdigit():
            continue
        lines.append(line)
    return lines


def parse(lines: list[str]) -> list[dict]:
    entries, group, sub = [], None, None
    for line in lines:
        if m := re.fullmatch(r"\((\d{2})\) (.+?)\.?", line):
            group = {"code": m[1], "name": m[2], "group": m[2], "parent": None}
            entries.append(group)
            sub = None
        elif m := re.fullmatch(r"\(([a-z])\) (.+?)\.?", line):
            sub = {"code": group["code"] + m[1].upper(), "name": m[2], "group": group["name"], "parent": group["code"]}
            entries.append(sub)
        elif m := re.fullmatch(r"(\d)\. (.+?)\.?", line):
            entries.append({"code": sub["code"] + m[1], "name": m[2], "group": group["name"], "parent": sub["code"]})
        else:
            raise ValueError(f"Unrecognized Appendix A line: {line!r}")
    parents = {e["parent"] for e in entries}
    for e in entries:
        e["selectable"] = e["code"] not in parents  # only the most specific code is listed
    return entries


def display_name(e: dict, by_code: dict) -> str:
    """Guess in the style of IG 3.4.3.5: 'Other baby products, leave-on [Baby products]'."""
    if e["parent"] is None:
        return e["name"]
    if len(e["code"]) == 4:
        sub = by_code[e["parent"]]
        return f"{sub['name']}, {e['name'][0].lower()}{e['name'][1:]} [{e['group']}]"
    return f"{e['name']} [{e['group']}]"


def main() -> None:
    text = subprocess.run(["pdftotext", "-layout", str(SOURCE), "-"], capture_output=True, text=True, check=True).stdout
    entries = parse(appendix_a(text))
    by_code = {e["code"]: e for e in entries}
    for e in entries:
        e["display_name"] = display_name(e, by_code)
    doc = {
        "metadata": {
            "source": "FDA, Guidance for Industry: Registration and Listing of Cosmetic Product Facilities and Products, Appendix A",
            "source_file": SOURCE.name,
            "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            "codes_verified": True,
            "codes_note": "Codes follow the appendix numbering (group 2 digits + letter + leave-on/rinse-off or application digit), the same pattern as the SPL IG's own examples (01B, 01D1, 14D1).",
            "display_names_verified": False,
            "display_names_note": "SPL needs FDA's exact display name (IG 3.4.3.4). The guide shows three different styles, so these are a best guess in the style of IG 3.4.3.5 until FDA's terminology file is checked.",
            "code_17_note": "Group 17 (Other preparations) has no subcategories; '17' is used as its code, unconfirmed.",
        },
        "categories": entries,
    }
    if "--dry-run" in sys.argv:
        print(f"{len(entries)} entries, {sum(e['selectable'] for e in entries)} selectable")
        return
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(entries)} entries)")


if __name__ == "__main__":
    main()
