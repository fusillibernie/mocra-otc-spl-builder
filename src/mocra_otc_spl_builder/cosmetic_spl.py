"""Builds the SPL XML for a cosmetic product listing (IG chapter 36).

Element layout follows the guide's examples. Not yet checked against FDA's spl.xsd schema or
FDA's validator; see README "Open questions".
"""

import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date

from . import codes as C
from .cosmetic_validation import validate_cosmetic_listing
from .models import Address, CosmeticListing, CosmeticProduct, Facility, ListingType

ET.register_namespace("", C.HL7_NS)
ET.register_namespace("xsi", C.XSI_NS)
XSI_TYPE = f"{{{C.XSI_NS}}}type"


class ListingNotValid(ValueError):
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


def _el(parent, tag, text=None, **attrs):
    e = ET.SubElement(parent, f"{{{C.HL7_NS}}}{tag}", {k: v for k, v in attrs.items()})
    if text is not None:
        e.text = text
    return e


def _guid() -> str:
    return str(uuid.uuid4())  # lower case (IG 2.1.1.7)


def build_cosmetic_listing(listing: CosmeticListing, today: date | None = None) -> SplFile:
    findings = validate_cosmetic_listing(listing)
    if findings:
        raise ListingNotValid(findings)
    today = today or date.today()
    stamp = today.strftime("%Y%m%d")  # effective time year is the current year (IG 36.1.1.2)
    doc_id = _guid()
    set_id = listing.set_id or _guid()

    doc = ET.Element(f"{{{C.HL7_NS}}}document", {f"{{{C.XSI_NS}}}schemaLocation": C.SCHEMA_LOCATION})
    _el(doc, "id", root=doc_id)
    code, display = C.DOC_COSMETIC_UPDATE if listing.listing_type is ListingType.UPDATE else C.DOC_COSMETIC_LISTING
    _el(doc, "code", code=code, codeSystem=C.LOINC, displayName=display)
    # No title (IG 36.1.1.3)
    _el(doc, "effectiveTime", value=stamp)
    _el(doc, "setId", root=set_id)
    _el(doc, "versionNumber", value=str(listing.version))

    _author(doc, listing)
    if listing.signer:
        _signature(doc, listing, stamp)

    body = _el(_el(doc, "component"), "structuredBody")
    section = _el(_el(body, "component"), "section")
    _el(section, "id", root=_guid())
    _el(section, "code", code=C.SECTION_PRODUCT_DATA[0], codeSystem=C.LOINC, displayName=C.SECTION_PRODUCT_DATA[1])
    _el(section, "effectiveTime", value=stamp)
    for product in listing.products:
        _product(section, product)

    ET.indent(doc)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<?xml-stylesheet href="{C.STYLESHEET}" type="text/xsl"?>\n'
        + ET.tostring(doc, encoding="unicode")
        + "\n"
    )
    images = [img for p in listing.products for img in p.label_images]
    return SplFile(document_id=doc_id, set_id=set_id, version=listing.version, xml=xml, images=images)


def _author(doc, listing: CosmeticListing) -> None:
    rp = listing.responsible_person
    author = _el(doc, "author")
    _el(author, "time")
    labeler = _el(_el(author, "assignedEntity"), "representedOrganization")
    if rp.duns:
        _el(labeler, "id", extension=rp.duns, root=C.DUNS_ROOT)
    _el(labeler, "name", rp.name)
    _el(labeler, "telecom", value=f"tel:{rp.phone}")

    registrant = _el(_el(labeler, "assignedEntity"), "assignedOrganization")  # IG 36.1.3

    if rp.business_type or rp.small_business:  # IG 36.1.4: first entity, empty organization
        details = _el(registrant, "assignedEntity")
        _el(details, "assignedOrganization")
        if rp.small_business:
            _small_business(details)
        if rp.business_type:
            act = _el(_el(details, "performance"), "actDefinition")
            value = rp.business_type.value
            _el(act, "code", code=C.BUSINESS_TYPE_CODES[value], codeSystem=C.NCI_THESAURUS, displayName=value)

    for facility, products in _facilities(listing):
        _facility(registrant, facility, products)


def _facilities(listing: CosmeticListing) -> list[tuple[Facility, list[CosmeticProduct]]]:
    """Each distinct facility (one per FEI) with the products it is linked to (IG 36.1.5.5, 36.1.6)."""
    out: dict[object, tuple[Facility, list[CosmeticProduct]]] = {}
    for product in listing.products:
        for f in product.facilities:
            out.setdefault(f.fei or id(f), (f, []))[1].append(product)
    return list(out.values())


def _facility(registrant, f: Facility, products: list[CosmeticProduct]) -> None:
    entity = _el(registrant, "assignedEntity")
    org = _el(entity, "assignedOrganization")
    if f.fei:
        _el(org, "id", extension=f.fei, root=C.FEI_ROOT)
    elif f.small_business:  # name/address only for an unregistered small business (IG 36.1.5.9)
        _el(org, "name", f.name)
        _addr(org, f.address)
    if f.small_business:
        _small_business(entity)
    for product in products:
        made = _el(_el(_el(_el(entity, "performance"), "actDefinition"), "product"), "manufacturedProduct", classCode="MANU")
        kind = _el(made, "manufacturedMaterialKind")
        if product.listing_number:  # number or name, not both (IG 36.1.6.3)
            _el(kind, "code", code=product.listing_number, codeSystem=C.COSMETIC_LISTING_NUMBER)
        else:
            _el(kind, "code")  # the schema needs the empty code (IG 36.1.6)
            _el(kind, "name", product.name)


def _addr(parent, a: Address) -> None:
    addr = _el(parent, "addr")
    for line in a.street:
        _el(addr, "streetAddressLine", line)
    _el(addr, "city", a.city)
    if a.state:
        _el(addr, "state", a.state)
    if a.postal_code:
        _el(addr, "postalCode", a.postal_code)
    _el(addr, "country", a.country_name, code=a.country_code, codeSystem=C.ISO_COUNTRY)


def _small_business(entity) -> None:
    ch = _el(_el(entity, "subjectOf"), "characteristic", classCode="OBS")
    _el(ch, "code", code=C.SMALL_BUSINESS, codeSystem=C.SPL_CHARACTERISTIC)
    _el(ch, "value", **{XSI_TYPE: "BL", "value": "true"})


def _signature(doc, listing: CosmeticListing, stamp: str) -> None:
    auth = _el(doc, "legalAuthenticator")
    _el(auth, "noteText", C.SIGNING_STATEMENT)
    _el(auth, "time", value=stamp)
    _el(auth, "signatureText", listing.signer.signature, mediaType="text/plain")
    entity = _el(auth, "assignedEntity")
    _el(_el(entity, "assignedPerson"), "name", listing.signer.full_name)
    _el(entity, "representedOrganization")  # signs for the responsible person (IG 36.1.7.8)


def _product(section, p: CosmeticProduct) -> None:
    outer = _el(_el(section, "subject"), "manufacturedProduct")
    inner = _el(outer, "manufacturedProduct")
    if p.listing_number:  # included once assigned (IG 36.2.2.1)
        _el(inner, "code", code=p.listing_number, codeSystem=C.COSMETIC_LISTING_NUMBER)
    _el(inner, "name", p.name)
    for c in p.categories:
        kind = _el(_el(inner, "asSpecializedKind", classCode="GEN"), "generalizedMaterialKind")
        _el(kind, "code", code=c.code, codeSystem=C.COSMETIC_CATEGORY_SYSTEM, displayName=c.display_name)
    for i in p.ingredients:  # label order, no quantity (IG 3.4.4, 3.4.4.8)
        substance = _el(_el(inner, "ingredient", classCode="COLR" if i.color_additive else "INGR"), "ingredientSubstance")
        if i.unii:
            _el(substance, "code", code=i.unii, codeSystem=C.UNII)
        _el(substance, "name", i.name)

    if p.web_page:
        text = _el(_el(_el(outer, "subjectOf"), "document"), "text")
        _el(text, "reference", value=p.web_page)
    if p.professional_use:
        ch = _el(_el(outer, "subjectOf"), "characteristic", classCode="OBS")
        _el(ch, "code", code=C.PROFESSIONAL_USE, codeSystem=C.SPL_CHARACTERISTIC)
        _el(ch, "value", **{XSI_TYPE: "BL", "value": "true"})
    for image in p.label_images:
        ch = _el(_el(outer, "subjectOf"), "characteristic")
        _el(ch, "code", code=C.LABEL_IMAGE, codeSystem=C.SPL_CHARACTERISTIC)
        value = _el(ch, "value", **{XSI_TYPE: "ED", "mediaType": "image/jpeg"})
        _el(value, "reference", value=image)
