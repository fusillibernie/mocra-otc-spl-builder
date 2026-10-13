"""Every document variant we build must pass FDA's SPL schema (IG 2.1.1.1)."""

from dataclasses import replace
from datetime import date

import pytest

pytest.importorskip("lxml")

from mocra_otc_spl_builder import (  # noqa: E402
    Address,
    AuthorizedAgent,
    BusinessType,
    ContactParty,
    Ingredient,
    ListingType,
    RegistrationType,
    build_cosmetic_listing,
    build_facility_registration,
    category,
    schema_errors,
)

from .cosmetic_fixtures import FILLER, SMALL_STUDIO, edp, listing  # noqa: E402
from .test_facility_registration import GRASSE_PLANT, NJ_PLANT, SET_ID, reg  # noqa: E402

TODAY = date(2026, 10, 13)


def full_listing():
    lst = listing(products=[
        edp(
            listing_number="53-000000-000001",
            categories=[category("05B"), category("05A")],
            ingredients=[Ingredient("Alcohol Denat.", unii="TESTUNII01"), Ingredient("Fragrance"), Ingredient("CI 19140", color_additive=True)],
            facilities=[FILLER, SMALL_STUDIO],
            label_images=["front.jpg", "back.jpg"],
            web_page="https://example.com/moon-dust",
            professional_use=True,
        ),
        edp(name="Dusk Eau de Parfum", facilities=[SMALL_STUDIO]),
    ])
    lst.responsible_person = replace(lst.responsible_person, duns="123456789", small_business=True, business_type=BusinessType.MANUFACTURER)
    return lst


LISTINGS = {
    "initial, minimal": listing(signer=None),
    "initial, every optional element": full_listing(),
    "update": listing(listing_type=ListingType.UPDATE, set_id=SET_ID, version=2),
}

FOREIGN_EVERYTHING = replace(GRASSE_PLANT, duns="123456789", parent_company="Grasse Holdings SA", small_business=True,
                             contact=replace(GRASSE_PLANT.contact, address=Address(["1 Route de Nice"], "Grasse", "FRA", "France")))
AGENT = AuthorizedAgent("Our Brand LLC", duns="987654321", contact=ContactParty(phone="+1-212-555-0100", email="reg@delbiado.com", person_name="Pat Example"))
LATER = dict(set_id=SET_ID, version=2)

REGISTRATIONS = {
    "initial, US facility": reg(),
    "initial, foreign facility with every optional element": reg(facility=FOREIGN_EVERYTHING, authorized_agent=AGENT),
    "amendment": reg(registration_type=RegistrationType.AMENDMENT, **LATER),
    "biennial renewal": reg(registration_type=RegistrationType.BIENNIAL_RENEWAL, last_submitted=date(2024, 6, 1), **LATER),
    "abbreviated renewal": reg(registration_type=RegistrationType.ABBREVIATED_RENEWAL, facility=None, products=[], last_submitted=date(2024, 6, 1), **LATER),
    "cancellation": reg(registration_type=RegistrationType.CANCELLATION, facility=None, products=[], **LATER),
    "no signature": reg(signer=None, facility=NJ_PLANT),
}


@pytest.mark.parametrize("name", LISTINGS)
def test_listing_passes_fda_schema(name):
    assert schema_errors(build_cosmetic_listing(LISTINGS[name], today=TODAY).xml) == []


@pytest.mark.parametrize("name", REGISTRATIONS)
def test_registration_passes_fda_schema(name):
    assert schema_errors(build_facility_registration(REGISTRATIONS[name], today=TODAY).xml) == []


def test_schema_catches_a_broken_document():
    xml = build_cosmetic_listing(listing(), today=TODAY).xml.replace("<versionNumber", "<notAnElement")
    errors = schema_errors(xml)
    assert errors and "notAnElement" in errors[0]


def test_preview_renders_with_fdas_stylesheet():
    from mocra_otc_spl_builder import preview_html

    html = preview_html(build_cosmetic_listing(full_listing(), today=TODAY))
    assert "MOON DUST EAU DE PARFUM" in html and "perfumes [fragrance preparations]" in html.lower()
    assert "accessdata.fda.gov/spl/stylesheet/spl.css" not in html and "<style>" in html
