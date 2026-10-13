from dataclasses import replace

from mocra_otc_spl_builder import Category, Facility, Ingredient, ListingType, validate_cosmetic_listing

from .cosmetic_fixtures import EXAMPLE_CATEGORY, SMALL_STUDIO, edp, listing


def messages(lst):
    return " | ".join(f.message for f in validate_cosmetic_listing(lst))


def test_good_listing_passes():
    assert validate_cosmetic_listing(listing()) == []


def test_small_business_facility_without_fei_is_allowed_with_name_and_address():
    assert validate_cosmetic_listing(listing(products=[edp(facilities=[SMALL_STUDIO])])) == []


def test_facility_without_fei_must_be_small_business():
    assert "IG 36.1.5.6" in messages(listing(products=[edp(facilities=[Facility()])]))


def test_fei_is_7_or_10_digits():
    assert "IG 36.1.5.4" in messages(listing(products=[edp(facilities=[Facility(fei="12345")])]))


def test_same_fei_for_different_facilities():
    a = Facility(fei="1234567")
    b = Facility(fei="1234567", small_business=True)
    lst = listing(products=[edp(facilities=[a]), edp(name="Dusk Eau de Parfum", facilities=[b])])
    assert "IG 36.1.5.5" in messages(lst)


def test_product_needs_a_facility_category_and_ingredients():
    out = messages(listing(products=[edp(facilities=[], categories=[], ingredients=[])]))
    assert "IG 36.1.6.6" in out and "IG 36.2.2.11" in out and "IG 36.2.2.14" in out


def test_trademark_symbols_not_allowed():
    assert "IG 3.4.2.2" in messages(listing(products=[edp(name="Moon Dust®")]))


def test_duplicate_product_names():
    assert "IG 36.2.2.6" in messages(listing(products=[edp(), edp()]))


def test_leave_on_and_rinse_off_of_same_category():
    cats = [Category("14D1", "body and hand, leave-on"), Category("14D2", "body and hand, rinse-off")]
    assert "IG 3.4.3.5 to 3.4.3.30" in messages(listing(products=[edp(categories=cats)]))


def test_fragrance_once_and_without_unii():
    ings = [Ingredient("Fragrance", unii="X"), Ingredient("Fragrances")]
    out = messages(listing(products=[edp(ingredients=ings)]))
    assert "only one 'fragrance'" in out and "without a UNII" in out


def test_listing_number_format():
    assert "IG 36.2.2.3" in messages(listing(products=[edp(listing_number="53-123")]))


def test_phone_format():
    lst = listing()
    lst.responsible_person = replace(lst.responsible_person, phone="212 555 0100")
    assert "IG 2.1.7" in messages(lst)


def test_label_images_are_jpg():
    assert "IG 2.1.2.7" in messages(listing(products=[edp(label_images=["front.png"])]))


def test_update_needs_earlier_set_id_and_higher_version():
    out = messages(listing(listing_type=ListingType.UPDATE))
    assert "IG 36.1.1.4" in out and "IG 2.1.3.16" in out


def test_us_address_needs_state_and_zip():
    studio = replace(SMALL_STUDIO, address=replace(SMALL_STUDIO.address, state="", postal_code="1120"))
    out = messages(listing(products=[edp(facilities=[studio])]))
    assert "IG 2.1.6.4" in out and "IG 2.1.6.5" in out
