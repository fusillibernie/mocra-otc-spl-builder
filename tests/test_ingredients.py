from datetime import date

import pytest

pytest.importorskip("fragrance_reg_core")

from fragrance_reg_core.models.product import (  # noqa: E402
    Botanical,
    ComponentRole,
    Constituent,
    FinishedProduct,
    ProductComponent,
)
from fragrance_reg_core.models.regulatory import Market, ProductType  # noqa: E402

from mocra_otc_spl_builder import (  # noqa: E402
    Category,
    CosmeticListing,
    CosmeticProduct,
    Facility,
    ResponsiblePerson,
    build_cosmetic_listing,
    ingredients_from_product,
)

AS_OF = date(2026, 10, 13)


def edp(*extra, alcohol=78.5):
    return FinishedProduct(
        name="Nostalgia Eau de Parfum",
        product_type=ProductType.FINE_FRAGRANCE,
        components=[
            ProductComponent(name="SD Alcohol 40-B", percentage=alcohol, inci_name="ALCOHOL DENAT."),
            ProductComponent(
                name="Nostalgia", percentage=18.0, role=ComponentRole.FRAGRANCE, allergen_list_basis="eu_82",
                allergen_declaration=[Constituent("78-70-6", "Linalool", 4.2)],
            ),
            ProductComponent(name="Deionized water", percentage=3.0, inci_name="AQUA"),
            ProductComponent(
                name="Lavender oil", percentage=0.5, role=ComponentRole.BOTANICAL,
                inci_name="LAVANDULA ANGUSTIFOLIA OIL", botanical=Botanical("Lavandula Angustifolia", "Lavender"),
            ),
            *extra,
        ],
        markets=[Market.US],
    )


def test_us_label_list_in_label_order():
    result = ingredients_from_product(edp(), as_of=AS_OF)
    assert result.ok
    assert [i.name for i in result.ingredients] == [
        "Alcohol Denat.", "Fragrance", "Water", "Lavandula Angustifolia (Lavender) Oil",
    ]
    assert result.label_text.startswith("Ingredients: Alcohol Denat., Fragrance")
    assert not any(i.color_additive for i in result.ingredients)


def test_fragrance_entry_is_plain_fragrance_without_unii():
    fragrance = ingredients_from_product(edp(), as_of=AS_OF).ingredients[1]
    assert fragrance.name.lower() == "fragrance" and fragrance.unii == ""  # IG 3.4.4.7


def test_colorant_is_a_color_additive_and_order_is_flagged():
    color = ProductComponent(name="Yellow 5", percentage=1.0, role=ComponentRole.COLORANT, inci_name="CI 19140")
    result = ingredients_from_product(edp(color, alcohol=77.5), as_of=AS_OF)
    flagged = [i for i in result.ingredients if i.color_additive]
    assert [i.name for i in flagged] == ["CI 19140"]
    assert any("color additive is listed before" in w for w in result.warnings)


def test_missing_inci_blocks_the_listing():
    unnamed = ProductComponent(name="Mystery base", percentage=0.0)
    result = ingredients_from_product(edp(unnamed), as_of=AS_OF)
    assert not result.ok
    assert any("label.no_inci" in f.message for f in result.findings)


def test_feeds_straight_into_a_listing():
    result = ingredients_from_product(edp(), as_of=AS_OF)
    listing = CosmeticListing(
        responsible_person=ResponsiblePerson("Our Brand LLC", phone="+1-212-555-0100"),
        products=[CosmeticProduct(
            name="Nostalgia Eau de Parfum",
            categories=[Category("PLACEHOLDER", "fragrance category from FDA's list")],
            ingredients=result.ingredients,
            facilities=[Facility(fei="1234567")],
        )],
    )
    xml = build_cosmetic_listing(listing, today=AS_OF).xml
    assert "<name>Lavandula Angustifolia (Lavender) Oil</name>" in xml
