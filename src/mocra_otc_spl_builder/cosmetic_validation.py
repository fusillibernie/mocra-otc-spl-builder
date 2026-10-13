"""Checks a cosmetic listing against the FDA SPL Implementation Guide before any XML is built.

Each Finding cites the guide's validation procedure (IG x.y.z). This catches what we can check
locally; FDA's validator also checks things we cannot see (for example, that a listing number
was assigned to us, or that a facility has an active registration).
"""

import re

from .codes import LEAVE_ON_RINSE_OFF_PAIRS
from .completeness import Finding
from .models import Address, CosmeticListing, CosmeticProduct, Facility, ListingType

US_PHONE = re.compile(r"^\+1-\d{3}-\d{3}-\d{4}(;ext=\d+)?$")
INTL_PHONE = re.compile(r"^\+\d{1,3}(-\d+)+(;ext=\d+)?$")
LISTING_NUMBER = re.compile(r"^53-\d{6}-\d{6}$")
FEI = re.compile(r"^(\d{7}|\d{10})$")
US_ZIP = re.compile(r"^\d{5}(-\d{4})?$")
GUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
FRAGRANCE_NAMES = {"fragrance", "fragrances"}


def validate_cosmetic_listing(listing: CosmeticListing) -> list[Finding]:
    findings: list[Finding] = []
    findings += _responsible_person(listing)
    if listing.listing_type is ListingType.UPDATE:
        if not GUID.match(listing.set_id):
            findings.append(Finding("set_id", "an update reuses the earlier listing's set id, a lower-case GUID (IG 36.1.1.4)"))
        if listing.version < 2:
            findings.append(Finding("version", "an update's version number is higher than the earlier one (IG 2.1.3.16)"))
    if listing.signer and not (listing.signer.full_name and listing.signer.signature):
        findings.append(Finding("signer", "a signature needs the signer's name and signature text (IG 36.1.7.4, 36.1.7.6)"))

    if not listing.products:
        findings.append(Finding("products", "a listing has at least one product (IG 36.2.1.3)"))
    names = [p.name.strip().lower() for p in listing.products]
    for name in {n for n in names if names.count(n) > 1}:
        findings.append(Finding("products", f"product name '{name}' is used twice; add distinguishing information (IG 36.2.2.6, 36.2.2.7)"))
    for i, product in enumerate(listing.products):
        findings += _product(f"products[{i}]", product)

    feis: dict[str, Facility] = {}
    for facility in (f for p in listing.products for f in p.facilities):
        if facility.fei and feis.setdefault(facility.fei, facility) is not facility and feis[facility.fei] != facility:
            findings.append(Finding("facilities", f"FEI {facility.fei} is given for two different facilities (IG 36.1.5.5)"))
    return findings


def _responsible_person(listing: CosmeticListing) -> list[Finding]:
    rp = listing.responsible_person
    findings = []
    if not rp.name:
        findings.append(Finding("responsible_person.name", "the responsible person has a name (IG 36.1.2.2)"))
    if not (US_PHONE.match(rp.phone) or (not rp.phone.startswith("+1-") and INTL_PHONE.match(rp.phone))):
        findings.append(Finding("responsible_person.phone", f"'{rp.phone}' is not +1-aaa-bbb-cccc or another +country format (IG 2.1.7.3 to 2.1.7.10)"))
    if rp.duns and not re.fullmatch(r"\d{9}", rp.duns):
        findings.append(Finding("responsible_person.duns", "a DUNS number has 9 digits (IG 2.1.5.2)"))
    return findings


def _product(where: str, p: CosmeticProduct) -> list[Finding]:
    findings = []
    if not p.name.strip():
        findings.append(Finding(f"{where}.name", "the product has a name as on the label (IG 3.4.2.1)"))
    if "®" in p.name or "™" in p.name:
        findings.append(Finding(f"{where}.name", "remove ® and ™ from the name (IG 3.4.2.2)"))
    if p.listing_number and not LISTING_NUMBER.match(p.listing_number):
        findings.append(Finding(f"{where}.listing_number", f"'{p.listing_number}' is not 53-XXXXXX-XXXXXX (IG 36.2.2.3)"))

    if not p.categories:
        findings.append(Finding(f"{where}.categories", "at least one cosmetic product category (IG 36.2.2.11)"))
    for c in p.categories:
        if not (c.code and c.display_name):
            findings.append(Finding(f"{where}.categories", "each category has a code and its display name (IG 3.4.3.3, 3.4.3.4)"))
    codes = {c.code for c in p.categories}
    for a, b in LEAVE_ON_RINSE_OFF_PAIRS:
        if a in codes and b in codes:
            findings.append(Finding(f"{where}.categories", f"{a} (leave-on) and {b} (rinse-off) cannot both apply (IG 3.4.3.5 to 3.4.3.30)"))

    if not p.ingredients:
        findings.append(Finding(f"{where}.ingredients", "at least one ingredient (IG 36.2.2.14)"))
    fragrance = [i for i in p.ingredients if i.name.strip().lower() in FRAGRANCE_NAMES]
    if len(fragrance) > 1:
        findings.append(Finding(f"{where}.ingredients", "only one 'fragrance' entry (IG 3.4.4.7)"))
    if any(i.unii for i in fragrance):
        findings.append(Finding(f"{where}.ingredients", "'fragrance' is listed without a UNII (IG 3.4.4.7)"))
    if any(not i.name.strip() for i in p.ingredients):
        findings.append(Finding(f"{where}.ingredients", "every ingredient has a name (IG 3.4.4)"))

    if not p.facilities:
        findings.append(Finding(f"{where}.facilities", "each product is linked from at least one facility (IG 36.1.6.6)"))
    for j, f in enumerate(p.facilities):
        findings += _facility(f"{where}.facilities[{j}]", f)

    for image in p.label_images:
        if not image.lower().endswith(".jpg"):
            findings.append(Finding(f"{where}.label_images", f"{image}: label images are .jpg files (IG 2.1.2.7, 3.4.9.3)"))
    if p.web_page and not re.match(r"^https?://\S+$", p.web_page):
        findings.append(Finding(f"{where}.web_page", "the web page is an absolute http:// or https:// URL (IG 3.4.7.2)"))
    return findings


def _facility(where: str, f: Facility) -> list[Finding]:
    findings = []
    if f.fei and not FEI.match(f.fei):
        findings.append(Finding(where, f"FEI '{f.fei}' is not 7 or 10 digits (IG 36.1.5.4)"))
    if not f.fei and not f.small_business:
        findings.append(Finding(where, "a facility that is not a small business needs its FEI (IG 36.1.5.6)"))
    if not f.fei and f.small_business and not (f.name and f.address):
        findings.append(Finding(where, "a small business facility without an FEI is identified by name and address (IG 36.1.5.9)"))
    if f.address:
        findings += _address(where, f.address)
    return findings


def _address(where: str, a: Address) -> list[Finding]:
    findings = []
    if not (1 <= len(a.street) <= 2 and a.city and a.country_code):
        findings.append(Finding(where, "an address has one or two street lines, a city and a country (IG 2.1.6.1)"))
    if not re.fullmatch(r"[A-Z]{3}", a.country_code):
        findings.append(Finding(where, "country code is ISO 3-letter, e.g. USA (IG 2.1.6.2)"))
    if a.country_code == "USA":
        if not re.fullmatch(r"[A-Z]{2}", a.state):
            findings.append(Finding(where, "a US address has a 2-letter state (IG 2.1.6.4)"))
        if not US_ZIP.match(a.postal_code):
            findings.append(Finding(where, "a US postal code is 5 digits, optionally -4 more (IG 2.1.6.5)"))
    return findings
