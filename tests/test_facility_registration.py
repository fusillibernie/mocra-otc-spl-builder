import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import date

import pytest

from mocra_otc_spl_builder import (
    Address,
    AuthorizedAgent,
    ContactParty,
    FacilityRegistration,
    RegisteredFacility,
    RegisteredProduct,
    RegistrationType,
    Signer,
    SplNotValid,
    USAgent,
    build_facility_registration,
    validate_facility_registration,
)
from mocra_otc_spl_builder import codes as C

from .cosmetic_fixtures import EXAMPLE_CATEGORY

NS = {"v3": C.HL7_NS}
TODAY = date(2026, 10, 13)
SET_ID = "a30accef-f437-4136-808c-9ed4ada5fcf8"

NJ_PLANT = RegisteredFacility(
    name="Contract Filler Inc",
    fei="1234567",
    address=Address(["2 Plant Rd"], "Camden", "USA", "USA", state="NJ", postal_code="08101"),
    contact=ContactParty(phone="+1-856-555-0100", email="qa@filler.example", person_name="Sam QA"),
)
GRASSE_PLANT = RegisteredFacility(
    name="Atelier de Grasse",
    fei="1234567890",
    address=Address(["1 Route de Nice"], "Grasse", "FRA", "France", postal_code="06130"),
    contact=ContactParty(phone="+33-4-93-00-00-00", email="contact@atelier.example"),
    us_agent=USAgent(name="US Reps Co", phone="+1-800-555-1212", email="agent@usreps.example"),
)
PRODUCT = RegisteredProduct(name="Moon Dust Eau de Parfum", categories=[EXAMPLE_CATEGORY], responsible_person="Our Brand LLC")


def reg(**kw):
    base = dict(
        registration_type=RegistrationType.INITIAL,
        facility=NJ_PLANT,
        products=[PRODUCT],
        signer=Signer("Pat Example", "P. Example"),
    )
    return FacilityRegistration(**{**base, **kw})


def messages(r):
    return " | ".join(f.message for f in validate_facility_registration(r, TODAY))


def parse(spl):
    return ET.fromstring(spl.xml.split("?>", 2)[2])


def test_good_registrations_pass():
    assert validate_facility_registration(reg(), TODAY) == []
    assert validate_facility_registration(reg(facility=GRASSE_PLANT), TODAY) == []


def test_us_agent_rules():
    assert "IG 35.1.5.1" in messages(reg(facility=replace(GRASSE_PLANT, us_agent=None)))
    assert "IG 35.1.5.3" in messages(reg(facility=replace(NJ_PLANT, us_agent=GRASSE_PLANT.us_agent)))
    foreign_phone = replace(GRASSE_PLANT.us_agent, phone="+33-1-00-00-00-00")
    assert "IG 35.1.5.4" in messages(reg(facility=replace(GRASSE_PLANT, us_agent=foreign_phone)))
    no_email = replace(GRASSE_PLANT.us_agent, email="N/A")
    assert validate_facility_registration(reg(facility=replace(GRASSE_PLANT, us_agent=no_email)), TODAY) == []


def test_facility_needs_fei_contact_phone_and_email():
    bad = replace(NJ_PLANT, fei="", contact=ContactParty())
    out = messages(reg(facility=bad))
    assert "IG 35.1.4.4" in out and "phone" in out and "email" in out


def test_products_and_responsible_person_required():
    assert "IG 35.2.1.2" in messages(reg(products=[]))
    assert "IG 35.2.3.1" in messages(reg(products=[replace(PRODUCT, responsible_person="")]))


def test_leave_on_rinse_off_pair_is_allowed_in_registrations():
    from mocra_otc_spl_builder import category

    cats = [category("14D1"), category("14D2")]  # IG 3.4.3.25 exempts registrations
    assert validate_facility_registration(reg(products=[replace(PRODUCT, categories=cats)]), TODAY) == []


def test_amendment_needs_earlier_set_id():
    out = messages(reg(registration_type=RegistrationType.AMENDMENT))
    assert "IG 35.1.1.4" in out and "IG 2.1.3.16" in out


def test_renewal_is_every_two_years():
    renew = dict(registration_type=RegistrationType.BIENNIAL_RENEWAL, set_id=SET_ID, version=2)
    assert "IG 35.1.1.6" in messages(reg(**renew))  # date missing
    assert "IG 35.1.1.6" in messages(reg(**renew, last_submitted=date(2025, 12, 1)))
    assert validate_facility_registration(reg(**renew, last_submitted=date(2024, 6, 30)), TODAY) == []


def test_abbreviated_renewal_and_cancellation_carry_no_details():
    for kind in (RegistrationType.ABBREVIATED_RENEWAL, RegistrationType.CANCELLATION):
        assert "IG 35.1.4.2" in messages(reg(registration_type=kind, set_id=SET_ID, version=3))


def test_xml_initial_registration():
    doc = parse(build_facility_registration(reg(authorized_agent=AuthorizedAgent("Our Brand LLC")), today=TODAY))
    assert doc.find("v3:code", NS).get("code") == "103573-2"
    top = doc.find("v3:author/v3:assignedEntity/v3:representedOrganization", NS)
    assert top.find("v3:name", NS) is None  # no labeler (IG 35.1.2.7)
    registrant = top.find("v3:assignedEntity/v3:assignedOrganization", NS)
    assert registrant.find("v3:name", NS).text == "Our Brand LLC"
    facility = registrant.find("v3:assignedEntity/v3:assignedOrganization", NS)
    assert [i.get("root") for i in facility.findall("v3:id", NS)] == [C.FEI_ROOT]
    assert facility.find("v3:addr/v3:state", NS).text == "NJ"
    telecoms = [t.get("value") for t in facility.findall("v3:contactParty/v3:telecom", NS)]
    assert telecoms == ["tel:+1-856-555-0100", "mailto:qa@filler.example"]
    assert facility.find("v3:assignedEntity", NS) is None  # no US agent
    note = doc.find("v3:legalAuthenticator/v3:noteText", NS).text
    assert note == C.SIGNING_STATEMENT_REGISTRATION and "and renew" in note
    product = doc.find(".//v3:section/v3:subject/v3:manufacturedProduct", NS)
    assert product.find("v3:manufacturerOrganization/v3:name", NS).text == "Our Brand LLC"
    assert [c.tag.split("}")[1] for c in product.find("v3:manufacturedProduct", NS)] == ["name", "asSpecializedKind"]


def test_xml_foreign_facility_has_us_agent_and_parent():
    facility = replace(GRASSE_PLANT, parent_company="Grasse Holdings SA", duns="123456789", small_business=True)
    doc = parse(build_facility_registration(reg(facility=facility), today=TODAY))
    entity = doc.find(".//v3:representedOrganization/v3:assignedEntity/v3:assignedOrganization/v3:assignedEntity", NS)
    org = entity.find("v3:assignedOrganization", NS)
    assert [i.get("root") for i in org.findall("v3:id", NS)] == [C.DUNS_ROOT, C.FEI_ROOT]
    agent = org.find("v3:assignedEntity", NS)
    assert agent.find("v3:performance/v3:actDefinition/v3:code", NS).get("code") == "C73330"
    assert org.find("v3:assignedEntity1/v3:representedOrganization/v3:name", NS).text == "Grasse Holdings SA"
    assert entity.find("v3:subjectOf/v3:characteristic/v3:code", NS).get("code") == "SPLSMALLBUSINESS"


def test_xml_cancellation_has_empty_body():
    spl = build_facility_registration(
        reg(registration_type=RegistrationType.CANCELLATION, facility=None, products=[], set_id=SET_ID, version=2),
        today=TODAY,
    )
    doc = parse(spl)
    assert doc.find("v3:code", NS).get("code") == "X8888-3"
    assert doc.find("v3:setId", NS).get("root") == SET_ID
    body = doc.find("v3:component/v3:structuredBody", NS)
    assert body is not None and len(body) == 0


def test_invalid_registration_is_refused():
    with pytest.raises(SplNotValid, match="IG 35.1.4.1"):
        build_facility_registration(reg(facility=None), today=TODAY)
