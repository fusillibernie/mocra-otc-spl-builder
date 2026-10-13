"""XML pieces shared by every SPL document we build (IG chapter 2)."""

import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from . import codes as C
from .models import Address, Category, ContactParty, Signer

ET.register_namespace("", C.HL7_NS)
ET.register_namespace("xsi", C.XSI_NS)
XSI_TYPE = f"{{{C.XSI_NS}}}type"


class SplNotValid(ValueError):
    def __init__(self, findings):
        self.findings = findings
        super().__init__("; ".join(f"{f.field}: {f.message}" for f in findings))


@dataclass
class SplFile:
    document_id: str
    set_id: str
    version: int
    xml: str
    images: list[str]  # .jpg files that must be submitted with the XML (IG 3.4.9.5)

    @property
    def filename(self) -> str:
        return f"{self.document_id}.xml"  # IG 2.1.2.6


def el(parent, tag, text=None, **attrs):
    e = ET.SubElement(parent, f"{{{C.HL7_NS}}}{tag}", attrs)
    if text is not None:
        e.text = text
    return e


def guid() -> str:
    return str(uuid.uuid4())  # lower case (IG 2.1.1.7)


def document(doc_id: str, code: tuple[str, str], stamp: str, set_id: str, version: int):
    """Document header without a title (IG 2.1.3; cosmetics have no title, IG 35.1.1.3, 36.1.1.3)."""
    doc = ET.Element(f"{{{C.HL7_NS}}}document", {f"{{{C.XSI_NS}}}schemaLocation": C.SCHEMA_LOCATION})
    el(doc, "id", root=doc_id)
    el(doc, "code", code=code[0], codeSystem=C.LOINC, displayName=code[1])
    el(doc, "effectiveTime", value=stamp)
    el(doc, "setId", root=set_id)
    el(doc, "versionNumber", value=str(version))
    return doc


def serialize(doc) -> str:
    """XML and stylesheet declarations, no other processing instructions or comments (IG 2.1.2)."""
    ET.indent(doc)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<?xml-stylesheet href="{C.STYLESHEET}" type="text/xsl"?>\n'
        + ET.tostring(doc, encoding="unicode")
        + "\n"
    )


def product_section(doc, stamp: str):
    body = el(el(doc, "component"), "structuredBody")
    section = el(el(body, "component"), "section")
    el(section, "id", root=guid())
    el(section, "code", code=C.SECTION_PRODUCT_DATA[0], codeSystem=C.LOINC, displayName=C.SECTION_PRODUCT_DATA[1])
    el(section, "effectiveTime", value=stamp)
    return section


def addr(parent, a: Address) -> None:
    node = el(parent, "addr")
    for line in a.street:
        el(node, "streetAddressLine", line)
    el(node, "city", a.city)
    if a.state:
        el(node, "state", a.state)
    if a.postal_code:
        el(node, "postalCode", a.postal_code)
    el(node, "country", a.country_name, code=a.country_code, codeSystem=C.ISO_COUNTRY)


def contact_party(parent, c: ContactParty) -> None:
    """IG 2.1.8: address, telephone, email, person, each optional for cosmetics."""
    node = el(parent, "contactParty")
    if c.address:
        addr(node, c.address)
    if c.phone:
        el(node, "telecom", value=f"tel:{c.phone}")
    if c.email:
        el(node, "telecom", value=f"mailto:{c.email}")
    if c.person_name:
        el(el(node, "contactPerson"), "name", c.person_name)


def small_business(entity) -> None:
    ch = el(el(entity, "subjectOf"), "characteristic", classCode="OBS")
    el(ch, "code", code=C.SMALL_BUSINESS, codeSystem=C.SPL_CHARACTERISTIC)
    el(ch, "value", **{XSI_TYPE: "BL", "value": "true"})


def categories(product, cats: list[Category]) -> None:
    for c in cats:
        kind = el(el(product, "asSpecializedKind", classCode="GEN"), "generalizedMaterialKind")
        el(kind, "code", code=c.code, codeSystem=C.COSMETIC_CATEGORY_SYSTEM, displayName=c.display_name)


def signature(doc, signer: Signer, statement: str, stamp: str) -> None:
    auth = el(doc, "legalAuthenticator")
    el(auth, "noteText", statement)
    el(auth, "time", value=stamp)
    el(auth, "signatureText", signer.signature, mediaType="text/plain")
    entity = el(auth, "assignedEntity")
    el(el(entity, "assignedPerson"), "name", signer.full_name)
    el(entity, "representedOrganization")  # signs for the responsible organization
