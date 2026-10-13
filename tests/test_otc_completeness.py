from mocra_otc_spl_builder import ActiveIngredient, Facility, OtcProduct, check_otc_product

PLANT = Facility(fei="1234567890")


def fields(findings):
    return {f.field for f in findings}


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


def test_packaged_monographs_stay_unverified_until_limits_are_entered():
    from mocra_otc_spl_builder.completeness import load_monographs

    data = load_monographs()
    assert data["metadata"]["verified"] is False
    for m in data["monographs"]:
        assert m["verified"] is False or m["active_ingredients"], m["id"]


def test_packaged_unverified_monograph_blocks_listing():
    assert "not yet verified" in check_otc_product(_otc())[0].message
