import re
import xml.etree.ElementTree as ET
from datetime import date

import pytest

from mocra_otc_spl_builder import Facility, ListingNotValid, ListingType, build_cosmetic_listing
from mocra_otc_spl_builder import codes as C

from .cosmetic_fixtures import FILLER, SMALL_STUDIO, edp, listing

NS = {"v3": C.HL7_NS}
TODAY = date(2026, 10, 13)


def parse(spl):
    return ET.fromstring(spl.xml.split("?>", 2)[2])


def test_header_and_file_name():
    spl = build_cosmetic_listing(listing(), today=TODAY)
    assert spl.xml.startswith('<?xml version="1.0" encoding="UTF-8"?>\n<?xml-stylesheet href="https://www.accessdata.fda.gov/spl/stylesheet/spl.xsl"')
    assert spl.filename == f"{spl.document_id}.xml"
    assert re.fullmatch(r"[0-9a-f-]{36}", spl.document_id) and spl.document_id != spl.set_id
    doc = parse(spl)
    assert doc.find("v3:code", NS).attrib == {"code": "103572-4", "codeSystem": C.LOINC, "displayName": "Cosmetic Product Listing"}
    assert doc.find("v3:effectiveTime", NS).get("value") == "20261013"
    assert doc.find("v3:title", NS) is None
    assert "<!--" not in spl.xml  # no comments (IG 2.1.2.5)


def test_labeler_registrant_and_facility_link_by_name():
    doc = parse(build_cosmetic_listing(listing(), today=TODAY))
    labeler = doc.find("v3:author/v3:assignedEntity/v3:representedOrganization", NS)
    assert labeler.find("v3:name", NS).text == "Our Brand LLC"
    assert labeler.find("v3:telecom", NS).get("value") == "tel:+1-212-555-0100"
    entities = labeler.findall("v3:assignedEntity/v3:assignedOrganization/v3:assignedEntity", NS)
    details, facility = entities
    assert len(details.find("v3:assignedOrganization", NS)) == 0
    assert details.find(".//v3:actDefinition/v3:code", NS).get("code") == "C201565"
    assert facility.find("v3:assignedOrganization/v3:id", NS).attrib == {"extension": "1234567", "root": C.FEI_ROOT}
    kind = facility.find("v3:performance/v3:actDefinition/v3:product/v3:manufacturedProduct/v3:manufacturedMaterialKind", NS)
    assert len(kind.find("v3:code", NS).attrib) == 0
    assert kind.find("v3:name", NS).text == "Moon Dust Eau de Parfum"


def test_link_by_listing_number_once_assigned():
    lst = listing(products=[edp(listing_number="53-000000-000001")])
    doc = parse(build_cosmetic_listing(lst, today=TODAY))
    kind = doc.find(".//v3:performance/v3:actDefinition/v3:product/v3:manufacturedProduct/v3:manufacturedMaterialKind", NS)
    assert kind.find("v3:code", NS).get("code") == "53-000000-000001"
    assert kind.find("v3:name", NS) is None
    product = doc.find(".//v3:section/v3:subject/v3:manufacturedProduct/v3:manufacturedProduct", NS)
    assert product.find("v3:code", NS).get("codeSystem") == C.COSMETIC_LISTING_NUMBER


def test_one_facility_entry_per_fei_with_one_link_per_product():
    lst = listing(products=[edp(), edp(name="Dusk Eau de Parfum", facilities=[Facility(fei="1234567"), SMALL_STUDIO])])
    doc = parse(build_cosmetic_listing(lst, today=TODAY))
    registrant = doc.find(".//v3:representedOrganization/v3:assignedEntity/v3:assignedOrganization", NS)
    facilities = registrant.findall("v3:assignedEntity", NS)[1:]
    assert len(facilities) == 2
    assert len(facilities[0].findall("v3:performance", NS)) == 2
    studio = facilities[1]
    assert studio.find("v3:assignedOrganization/v3:name", NS).text == "Small Pour Studio"
    assert studio.find("v3:subjectOf/v3:characteristic/v3:code", NS).get("code") == "SPLSMALLBUSINESS"


def test_product_section_ingredients_in_label_order():
    doc = parse(build_cosmetic_listing(listing(), today=TODAY))
    section = doc.find("v3:component/v3:structuredBody/v3:component/v3:section", NS)
    assert section.find("v3:code", NS).get("code") == "48780-1"
    product = section.find("v3:subject/v3:manufacturedProduct/v3:manufacturedProduct", NS)
    assert product.find("v3:code", NS) is None  # no listing number yet
    names = [n.text for n in product.findall("v3:ingredient/v3:ingredientSubstance/v3:name", NS)]
    assert names == ["Alcohol Denat.", "Fragrance", "Water", "Linalool"]
    assert {i.get("classCode") for i in product.findall("v3:ingredient", NS)} == {"INGR"}
    assert product.find("v3:ingredient//v3:quantity", NS) is None  # IG 3.4.4.8


def test_signature_statement_is_word_for_word():
    doc = parse(build_cosmetic_listing(listing(), today=TODAY))
    auth = doc.find("v3:legalAuthenticator", NS)
    assert auth.find("v3:noteText", NS).text == C.SIGNING_STATEMENT
    assert auth.find("v3:signatureText", NS).attrib == {"mediaType": "text/plain"}
    assert len(auth.find("v3:assignedEntity/v3:representedOrganization", NS)) == 0


def test_label_image_and_web_page():
    lst = listing(products=[edp(label_images=["front.jpg"], web_page="https://example.com/moon-dust")])
    spl = build_cosmetic_listing(lst, today=TODAY)
    assert spl.images == ["front.jpg"]
    assert 'xsi:type="ED" mediaType="image/jpeg"' in spl.xml
    assert '<reference value="https://example.com/moon-dust" />' in spl.xml


def test_update_reuses_set_id():
    set_id = "a30accef-f437-4136-808c-9ed4ada5fcf8"
    spl = build_cosmetic_listing(listing(listing_type=ListingType.UPDATE, set_id=set_id, version=2), today=TODAY)
    doc = parse(spl)
    assert doc.find("v3:code", NS).get("code") == "X8888-5"
    assert doc.find("v3:setId", NS).get("root") == set_id
    assert doc.find("v3:versionNumber", NS).get("value") == "2"


def test_invalid_listing_is_refused():
    with pytest.raises(ListingNotValid, match="IG 36.1.5.6"):
        build_cosmetic_listing(listing(products=[edp(facilities=[Facility()])]))


def test_xml_special_characters_are_escaped():
    spl = build_cosmetic_listing(listing(products=[edp(name="Rose & Oud <Intense>")]), today=TODAY)
    assert "Rose &amp; Oud &lt;Intense&gt;" in spl.xml
