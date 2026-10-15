#!/usr/bin/env python3
"""PostToolUse check for regulatory data packs. Silent when valid.

Validates structure and value ranges for the known pack files and reports only
problems (max 15 lines, exit 2 so Claude sees them). Files not listed in RULES
are ignored. Catches the errors that corrupt a calculation: a threshold that is
a string, a negative or >100 percent limit, a malformed CAS number, a duplicate
CAS, a missing required field.
"""
import json
import re
import sys

CAS = re.compile(r"^\d{2,7}-\d{2}-\d$")


def cas_ok(value):
    if not isinstance(value, str) or not CAS.match(value):
        return False
    digits = value.replace("-", "")
    total = sum(int(d) * w for w, d in enumerate(reversed(digits[:-1]), 1))
    return total % 10 == int(digits[-1])


def num(v, lo=0.0, hi=None):
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and v >= lo and (hi is None or v <= hi))


def records(doc, key):
    items = doc.get(key) if isinstance(doc, dict) else None
    return items if isinstance(items, list) else None


def check_list(doc, key, required, checks, unique_cas=True):
    errs = []
    items = records(doc, key)
    if items is None:
        return [f"'{key}' must be a list"]
    seen = {}
    for i, rec in enumerate(items):
        label = rec.get("name") or rec.get("cas_number") or rec.get("id") or rec.get("code") if isinstance(rec, dict) else None
        tag = f"{key}[{i}] {label}" if label else f"{key}[{i}]"
        if not isinstance(rec, dict):
            errs.append(f"{tag}: not an object")
            continue
        for field in required:
            if rec.get(field) in (None, ""):
                errs.append(f"{tag}: missing {field}")
        for field, test, msg in checks:
            if field in rec and rec[field] is not None and not test(rec[field]):
                errs.append(f"{tag}: {field}={rec[field]!r} {msg}")
        cas = rec.get("cas_number")
        if unique_cas and cas:
            if cas in seen:
                errs.append(f"{tag}: duplicate cas_number {cas} (also [{seen[cas]}])")
            seen[cas] = i
    return errs


CAS_CHECK = ("cas_number", cas_ok, "is not a valid CAS number (format or check digit)")

RULES = {
    "ifra_restrictions.json": lambda d: check_list(
        d, "restrictions", ["cas_number", "name"], [CAS_CHECK]) + [
        f"restrictions[{i}] {r.get('name')}: category_limits[{k!r}]={v!r} must be a number 0-100"
        for i, r in enumerate(records(d, "restrictions") or [])
        if isinstance(r, dict) and isinstance(r.get("category_limits"), dict)
        for k, v in r["category_limits"].items() if not num(v, 0, 100)],
    "allergens.json": lambda d: check_list(
        d, "allergens", ["cas_number", "name", "leave_on_threshold", "rinse_off_threshold"],
        [CAS_CHECK,
         ("leave_on_threshold", lambda v: num(v, 0, 100) and v > 0, "must be a percent in (0, 100]"),
         ("rinse_off_threshold", lambda v: num(v, 0, 100) and v > 0, "must be a percent in (0, 100]")]),
    "prop65.json": lambda d: check_list(
        d, "substances", ["cas_number", "name", "listing_mechanism"],
        [CAS_CHECK, ("nsrl_ug_day", lambda v: num(v), "must be a number >= 0 or null")]),
    "reach.json": lambda d: check_list(d, "substances", ["cas_number", "name"], [CAS_CHECK]),
    "canada_hotlist.json": lambda d: check_list(
        d, "substances", ["cas_number", "name", "restriction_type"], [CAS_CHECK]),
    "eu_prohibited_fragrance_substances.json": lambda d: check_list(
        d, "substances", ["cas_numbers", "name"],
        [("cas_numbers", lambda v: isinstance(v, list) and v and all(cas_ok(c) for c in v),
          "must be a non-empty list of valid CAS numbers")], unique_cas=False),
    "voc_ingredients.json": lambda d: check_list(
        d, "ingredients", ["cas_number", "name", "voc_percent"],
        [CAS_CHECK, ("voc_percent", lambda v: num(v, 0, 100), "must be a percent 0-100"),
         ("vapor_pressure_mmhg", lambda v: num(v), "must be a number >= 0")]),
    "voc_limits.json": lambda d: check_list(
        d, "limits", ["regulation", "product_category", "limit_percent"],
        [("limit_percent", lambda v: num(v, 0, 100), "must be a percent 0-100"),
         ("effective_date", lambda v: isinstance(v, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", v),
          "must be YYYY-MM-DD")], unique_cas=False),
    "cscp_rules.json": lambda d: (
        [] if isinstance(d.get("allergens"), dict) and num(d["allergens"].get("leave_on_percent"), 0, 100)
        and num(d["allergens"].get("rinse_off_percent"), 0, 100)
        and d["allergens"]["leave_on_percent"] <= d["allergens"]["rinse_off_percent"]
        else ["allergens: leave_on_percent and rinse_off_percent must be percents 0-100 with leave_on <= rinse_off"]),
    "cscp_reportable_ingredients.json": lambda d: check_list(
        d, "ingredients", ["name"], [("cas_number", cas_ok, "is not a valid CAS number")]),
    "otc_monographs.json": lambda d: check_list(
        d, "monographs", ["id", "title", "order"], [], unique_cas=False),
    "cosmetic_categories.json": lambda d: check_list(
        d, "categories", ["code", "name"], [], unique_cas=False),
}


def main():
    path = (json.load(sys.stdin).get("tool_input") or {}).get("file_path", "")
    name = path.rsplit("/", 1)[-1]
    rule = RULES.get(name)
    if not rule or "/data/" not in path:
        return 0
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"{name}: cannot parse: {exc}", file=sys.stderr)
        return 2
    errs = rule(doc)
    if not errs:
        return 0
    shown = errs[:14] if len(errs) > 15 else errs
    print(f"{name}: {len(errs)} problem(s)", file=sys.stderr)
    for e in shown:
        print("  " + e, file=sys.stderr)
    if len(errs) > len(shown):
        print(f"  ... +{len(errs) - len(shown)} more", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
