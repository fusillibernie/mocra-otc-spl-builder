"""Cosmetic facility registration (IG chapter 35): checks, then builds the SPL XML.

One facility per document. Initial, amendment and biennial renewal carry the facility details
and the products made there; abbreviated renewal and cancellation carry neither.
"""

import re
from datetime import date

from . import codes as C
from .categories import category_findings
from .completeness import Finding
from .cosmetic_validation import GUID, LISTING_NUMBER, US_PHONE, _address, _phone_ok
from .models import ContactParty, FacilityRegistration, RegisteredFacility, RegistrationType
from .spl_xml import (
    SplFile,
    SplNotValid,
    addr,
    categories,
    contact_party,
    document,
    el,
    guid,
    product_section,
    serialize,
    signature,
    small_business,
)

DOC_TYPES = {
    RegistrationType.INITIAL: C.DOC_FACILITY_REGISTRATION,
    RegistrationType.AMENDMENT: C.DOC_FACILITY_AMENDMENT,
    RegistrationType.BIENNIAL_RENEWAL: C.DOC_FACILITY_BIENNIAL_RENEWAL,
    RegistrationType.ABBREVIATED_RENEWAL: C.DOC_FACILITY_ABBREVIATED_RENEWAL,
    RegistrationType.CANCELLATION: C.DOC_FACILITY_CANCELLATION,
}
WITHOUT_DETAILS = {RegistrationType.ABBREVIATED_RENEWAL, RegistrationType.CANCELLATION}
RENEWALS = {RegistrationType.BIENNIAL_RENEWAL, RegistrationType.ABBREVIATED_RENEWAL}
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_facility_registration(reg: FacilityRegistration, today: date | None = None) -> list[Finding]:
    today = today or date.today()
    findings: list[Finding] = []
    kind = reg.registration_type

    if kind is not RegistrationType.INITIAL:
        if not GUID.match(reg.set_id):
            findings.append(Finding("set_id", "reuse the earlier registration's set id, a lower-case GUID (IG 35.1.1.4)"))
        if reg.version < 2:
            findings.append(Finding("version", "the version number is higher than the earlier one (IG 2.1.3.16)"))
    if kind in RENEWALS:
        if reg.last_submitted is None:
            findings.append(Finding("last_submitted", "a renewal needs the date of the last registration document (IG 35.1.1.6)"))
        elif today.year - reg.last_submitted.year <= 1:
            findings.append(Finding("last_submitted", "renewals come every 2 years: more than one year after the last registration (IG 35.1.1.6)"))
    if reg.signer and not (reg.signer.full_name and reg.signer.signature):
        findings.append(Finding("signer", "a signature needs the signer's name and signature text (IG 35.1.3.4, 35.1.3.6)"))

    if kind in WITHOUT_DETAILS:
        if reg.facility or reg.products:
            findings.append(Finding("facility", "an abbreviated renewal or cancellation has no facility or product details (IG 35.1.4.2, 35.2.1.1)"))
        if reg.authorized_agent:
            findings.append(Finding("authorized_agent", "an abbreviated renewal or cancellation has no authorized agent (IG 35.1.2.1)"))
        return findings

    if reg.facility is None:
        findings.append(Finding("facility", "the registration has one facility (IG 35.1.4.1)"))
    else:
        findings += _facility(reg.facility)
    if not reg.products:
        findings.append(Finding("products", "list the products made or processed at the facility (IG 35.2.1.2 to 35.2.1.4)"))
    for i, p in enumerate(reg.products):
        where = f"products[{i}]"
        if not p.name.strip():
            findings.append(Finding(where, "the product has the brand name it is sold under (IG 35.2.2.1)"))
        if "®" in p.name or "™" in p.name:
            findings.append(Finding(where, "remove ® and ™ from the name (IG 35.2.2.2)"))
        if not p.categories:
            findings.append(Finding(where, "one or more categories (IG 35.2.2.3)"))
        findings += category_findings(where, p.categories)
        if not p.responsible_person.strip():
            findings.append(Finding(where, "the product's responsible person (organization name) (IG 35.2.3.1)"))
        if p.listing_number and not LISTING_NUMBER.match(p.listing_number):
            findings.append(Finding(where, f"'{p.listing_number}' is not 53-XXXXXX-XXXXXX (IG 36.2.2.3)"))
    agent = reg.authorized_agent
    if agent:
        if not agent.name:
            findings.append(Finding("authorized_agent", "the authorized agent has a name (IG 35.1.2)"))
        if agent.duns and not re.fullmatch(r"\d{9}", agent.duns):
            findings.append(Finding("authorized_agent", "a DUNS number has 9 digits (IG 2.1.5.2)"))
    return findings


def _facility(f: RegisteredFacility) -> list[Finding]:
    findings = []
    if not f.name:
        findings.append(Finding("facility.name", "the facility has a name (IG 35.1.4.3)"))
    if not re.fullmatch(r"\d{7}|\d{10}", f.fei):
        findings.append(Finding("facility.fei", f"FEI '{f.fei}' is not 7 or 10 digits (IG 35.1.4.4)"))
    if f.duns and not re.fullmatch(r"\d{9}", f.duns):
        findings.append(Finding("facility.duns", "a DUNS number has 9 digits (IG 2.1.5.2)"))
    findings += _address("facility.address", f.address)
    findings += _contact("facility.contact", f.contact)

    us = f.address.country_code == "USA"
    if us and f.us_agent:
        findings.append(Finding("facility.us_agent", "a facility in the US has no US agent (IG 35.1.5.3)"))
    if not us and not f.us_agent:
        findings.append(Finding("facility.us_agent", "a facility outside the US needs a US agent (IG 35.1.5.1)"))
    if f.us_agent:
        a = f.us_agent
        if not a.name:
            findings.append(Finding("facility.us_agent", "the US agent has a name (IG 35.1.5)"))
        if not US_PHONE.match(a.phone):
            findings.append(Finding("facility.us_agent", "the US agent has a US phone number, +1-aaa-bbb-cccc (IG 35.1.5.4)"))
        if a.email != "N/A" and not EMAIL.match(a.email):
            findings.append(Finding("facility.us_agent", "the US agent has an email, or 'N/A' if none (IG 35.1.5.5)"))
    return findings


def _contact(where: str, c: ContactParty) -> list[Finding]:
    findings = []
    if not _phone_ok(c.phone):
        findings.append(Finding(where, f"facility contact phone '{c.phone}' is required, in +country format (IG 2.1.7.1 to 2.1.7.10)"))
    if not EMAIL.match(c.email):
        findings.append(Finding(where, "facility contact email is required (IG 2.1.7.1, 2.1.7.12)"))
    if c.address:
        findings += _address(where, c.address)
    return findings


def build_facility_registration(reg: FacilityRegistration, today: date | None = None) -> SplFile:
    today = today or date.today()
    findings = validate_facility_registration(reg, today)
    if findings:
        raise SplNotValid(findings)
    stamp = today.strftime("%Y%m%d")  # year is the current year (IG 35.1.1.2)
    doc_id, set_id = guid(), reg.set_id or guid()
    doc = document(doc_id, DOC_TYPES[reg.registration_type], stamp, set_id, reg.version)

    author = el(doc, "author")
    el(author, "time")
    top = el(el(author, "assignedEntity"), "representedOrganization")  # pass-through, no labeler (IG 35.1.2.7)
    if reg.facility:
        registrant = el(el(top, "assignedEntity"), "assignedOrganization")
        if reg.authorized_agent:  # IG 35.1.2
            a = reg.authorized_agent
            if a.duns:
                el(registrant, "id", root=C.DUNS_ROOT, extension=a.duns)
            el(registrant, "name", a.name)
            if a.contact:
                contact_party(registrant, a.contact)
        _facility_xml(registrant, reg.facility)

    if reg.signer:
        signature(doc, reg.signer, C.SIGNING_STATEMENT_REGISTRATION, stamp)

    if reg.registration_type in WITHOUT_DETAILS:
        el(el(doc, "component"), "structuredBody")  # empty body (IG 35.2, 35.2.1.1)
    else:
        section = product_section(doc, stamp)
        for p in reg.products:
            outer = el(el(section, "subject"), "manufacturedProduct")
            inner = el(outer, "manufacturedProduct")
            if p.listing_number:
                el(inner, "code", code=p.listing_number, codeSystem=C.COSMETIC_LISTING_NUMBER)
            el(inner, "name", p.name)
            categories(inner, p.categories)  # nothing else on the product (IG 35.2.2.4)
            el(el(outer, "manufacturerOrganization"), "name", p.responsible_person)  # IG 35.2.3

    return SplFile(document_id=doc_id, set_id=set_id, version=reg.version, xml=serialize(doc), images=[])


def _facility_xml(registrant, f: RegisteredFacility) -> None:
    entity = el(registrant, "assignedEntity")
    org = el(entity, "assignedOrganization")
    if f.duns:  # DUNS first, then FEI (IG 35.1.4.3, 35.1.4.4)
        el(org, "id", extension=f.duns, root=C.DUNS_ROOT)
    el(org, "id", extension=f.fei, root=C.FEI_ROOT)
    el(org, "name", f.name)
    addr(org, f.address)
    contact_party(org, f.contact)
    if f.us_agent:  # IG 35.1.5
        agent = el(org, "assignedEntity")
        agent_org = el(agent, "assignedOrganization")
        el(agent_org, "name", f.us_agent.name)
        el(agent_org, "telecom", value=f"tel:{f.us_agent.phone}")
        el(agent_org, "telecom", value=f"mailto:{f.us_agent.email}")
        el(el(el(agent, "performance"), "actDefinition"), "code",
           code=C.US_AGENT[0], codeSystem=C.NCI_THESAURUS, displayName=C.US_AGENT[1])
    if f.parent_company:  # IG 35.1.6
        el(el(el(org, "assignedEntity1"), "representedOrganization"), "name", f.parent_company)
    if f.small_business:  # IG 35.1.7
        small_business(entity)
