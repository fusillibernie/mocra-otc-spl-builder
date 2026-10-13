from mocra_otc_spl_builder import (
    ActiveIngredient,
    CosmeticProduct,
    Facility,
    OtcProduct,
    ResponsiblePerson,
    check_cosmetic_product,
    check_otc_product,
)

RP = ResponsiblePerson(name="Our Brand LLC", address="1 Main St, New York, NY 10001")
PLANT = Facility(name="Contract Filler Inc", address="2 Plant Rd, NJ", fei="1234567890")


def fields(findings):
    return {f.field for f in findings}


def test_complete_cosmetic_has_no_findings():
    product = CosmeticProduct(
        name="Eau de Parfum",
        responsible_person=RP,
        facilities=[PLANT],
        category_codes=["placeholder"],
        ingredients=["Alcohol Denat.", "Fragrance", "Water"],
        label_files=["label.pdf"],
    )
    assert check_cosmetic_product(product) == []


def test_cosmetic_gaps_are_reported_not_guessed():
    product = CosmeticProduct(
        name="EdP", responsible_person=ResponsiblePerson("", ""), facilities=[Facility("Plant", "addr")]
    )
    assert fields(check_cosmetic_product(product)) == {
        "facilities[0]", "responsible_person", "category_codes", "ingredients", "label_files",
    }


def _otc(**kw):
    base = dict(
        name="SPF 30 Lotion",
        labeler_name="Our Brand LLC",
        labeler_code="12345",
        facilities=[PLANT],
        monograph_id="M020",
        active_ingredients=[ActiveIngredient("Zinc Oxide", unii="TEST-UNII", strength="20 g/100 g")],
        drug_facts_file="drug_facts.pdf",
    )
    return OtcProduct(**{**base, **kw})


def test_unknown_monograph_is_a_finding():
    assert fields(check_otc_product(_otc(), {"metadata": {}, "monographs": []})) == {"monograph_id"}


def test_unverified_monograph_is_a_finding():
    data = {"metadata": {"verified": False}, "monographs": [{"id": "M020"}]}
    assert "not yet verified" in check_otc_product(_otc(), data)[0].message


def test_verified_monograph_and_complete_product_passes():
    data = {"metadata": {"verified": False}, "monographs": [{"id": "M020", "verified": True}]}
    assert check_otc_product(_otc(), data) == []


def test_otc_needs_labeler_code_and_active_details():
    data = {"metadata": {}, "monographs": [{"id": "M020", "verified": True}]}
    product = _otc(labeler_code="", active_ingredients=[ActiveIngredient("Zinc Oxide")])
    assert fields(check_otc_product(product, data)) == {"labeler_code", "active_ingredients[0]"}


def test_packaged_monograph_table_starts_empty_and_unverified():
    from mocra_otc_spl_builder.completeness import load_monographs

    data = load_monographs()
    assert data["metadata"]["verified"] is False
    assert data["monographs"] == []
