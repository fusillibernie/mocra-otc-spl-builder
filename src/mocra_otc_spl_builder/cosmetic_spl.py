"""Builds the SPL XML for a cosmetic product listing (IG chapter 36).

Element layout follows the guide's examples. Not yet checked against FDA's spl.xsd schema or
FDA's validator; see README "Open questions".
"""

from datetime import date

from . import codes as C
from .cosmetic_validation import validate_cosmetic_listing
from .models import CosmeticListing, CosmeticProduct, Facility, ListingType
from .spl_xml import (
    XSI_TYPE,
    SplFile,
    SplNotValid,
    addr,
    categories,
    document,
    el,
    guid,
    product_section,
    serialize,
    signature,
    small_business,
)

ListingNotValid = SplNotValid  # kept for callers of the first version


def build_cosmetic_listing(listing: CosmeticListing, today: date | None = None) -> SplFile:
    findings = validate_cosmetic_listing(listing)
    if findings:
        raise SplNotValid(findings)
    stamp = (today or date.today()).strftime("%Y%m%d")  # year is the current year (IG 36.1.1.2)
    code = C.DOC_COSMETIC_UPDATE if listing.listing_type is ListingType.UPDATE else C.DOC_COSMETIC_LISTING
    doc_id, set_id = guid(), listing.set_id or guid()
    doc = document(doc_id, code, stamp, set_id, listing.version)
    _author(doc, listing)
    if listing.signer:
        signature(doc, listing.signer, C.SIGNING_STATEMENT, stamp)
    section = product_section(doc, stamp)
    for product in listing.products:
        _product(section, product)
    images = [img for p in listing.products for img in p.label_images]
    return SplFile(document_id=doc_id, set_id=set_id, version=listing.version, xml=serialize(doc), images=images)


def _author(doc, listing: CosmeticListing) -> None:
    rp = listing.responsible_person
    author = el(doc, "author")
    el(author, "time")
    labeler = el(el(author, "assignedEntity"), "representedOrganization")
    if rp.duns:
        el(labeler, "id", extension=rp.duns, root=C.DUNS_ROOT)
    el(labeler, "name", rp.name)
    el(labeler, "telecom", value=f"tel:{rp.phone}")

    registrant = el(el(labeler, "assignedEntity"), "assignedOrganization")  # IG 36.1.3

    if rp.business_type or rp.small_business:  # IG 36.1.4: first entity, empty organization
        details = el(registrant, "assignedEntity")
        el(details, "assignedOrganization")
        if rp.small_business:
            small_business(details)
        if rp.business_type:
            act = el(el(details, "performance"), "actDefinition")
            value = rp.business_type.value
            el(act, "code", code=C.BUSINESS_TYPE_CODES[value], codeSystem=C.NCI_THESAURUS, displayName=value)

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
    entity = el(registrant, "assignedEntity")
    org = el(entity, "assignedOrganization")
    if f.fei:
        el(org, "id", extension=f.fei, root=C.FEI_ROOT)
    elif f.small_business:  # name/address only for an unregistered small business (IG 36.1.5.9)
        el(org, "name", f.name)
        addr(org, f.address)
    if f.small_business:
        small_business(entity)
    for product in products:
        made = el(el(el(el(entity, "performance"), "actDefinition"), "product"), "manufacturedProduct", classCode="MANU")
        kind = el(made, "manufacturedMaterialKind")
        if product.listing_number:  # number or name, not both (IG 36.1.6.3)
            el(kind, "code", code=product.listing_number, codeSystem=C.COSMETIC_LISTING_NUMBER)
        else:
            el(kind, "code")  # the schema needs the empty code (IG 36.1.6)
            el(kind, "name", product.name)


def _product(section, p: CosmeticProduct) -> None:
    outer = el(el(section, "subject"), "manufacturedProduct")
    inner = el(outer, "manufacturedProduct")
    if p.listing_number:  # included once assigned (IG 36.2.2.1)
        el(inner, "code", code=p.listing_number, codeSystem=C.COSMETIC_LISTING_NUMBER)
    el(inner, "name", p.name)
    categories(inner, p.categories)
    for i in p.ingredients:  # label order, no quantity (IG 3.4.4, 3.4.4.8)
        substance = el(el(inner, "ingredient", classCode="COLR" if i.color_additive else "INGR"), "ingredientSubstance")
        if i.unii:
            el(substance, "code", code=i.unii, codeSystem=C.UNII)
        el(substance, "name", i.name)

    if p.web_page:
        text = el(el(el(outer, "subjectOf"), "document"), "text")
        el(text, "reference", value=p.web_page)
    if p.professional_use:
        ch = el(el(outer, "subjectOf"), "characteristic", classCode="OBS")
        el(ch, "code", code=C.PROFESSIONAL_USE, codeSystem=C.SPL_CHARACTERISTIC)
        el(ch, "value", **{XSI_TYPE: "BL", "value": "true"})
    for image in p.label_images:
        ch = el(el(outer, "subjectOf"), "characteristic")
        el(ch, "code", code=C.LABEL_IMAGE, codeSystem=C.SPL_CHARACTERISTIC)
        value = el(ch, "value", **{XSI_TYPE: "ED", "mediaType": "image/jpeg"})
        el(value, "reference", value=image)
