import csv
import io
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

from mocra_otc_spl_builder import ReportableList, cscp_report  # noqa: E402

AS_OF = date(2026, 10, 14)
LIST = ReportableList.from_records([{"cas": "123-45-6", "name": "Example Listed Substance", "lists": ["Example list"]}])


def fragrance(pct=18.0, declaration=None, basis="eu_82", full_composition=None):
    return ProductComponent(
        name="Nostalgia", percentage=pct, role=ComponentRole.FRAGRANCE, allergen_list_basis=basis,
        allergen_declaration=declaration if declaration is not None else [
            Constituent("5989-27-5", "Limonene", 8.0),
            Constituent("78-70-6", "Linalool", 4.2),
            Constituent("5392-40-5", "Citral", 0.004),
        ],
        full_composition=full_composition or [],
    )


def product(*extra, frag=None, leave_on=True, alcohol=None):
    frag = frag or fragrance()
    rest = 100.0 - frag.percentage - sum(c.percentage for c in extra)
    return FinishedProduct(
        name="Nostalgia Eau de Parfum", product_type=ProductType.FINE_FRAGRANCE, is_leave_on=leave_on,
        components=[ProductComponent(name="SD Alcohol 40-B", percentage=alcohol or rest, inci_name="ALCOHOL DENAT."), frag, *extra],
        markets=[Market.US],
    )


def names(report):
    return {a.name: a for a in report.allergens}


def test_allergens_above_the_leave_on_threshold_are_reported_with_cas():
    report = cscp_report(product(), AS_OF, reportable_list=LIST)
    rows = names(report)
    assert set(rows) == {"Limonene", "Linalool"}          # citral: 0.004% x 18% = 0.00072% < 0.001%
    assert rows["Linalool"].cas_number == "78-70-6"
    assert rows["Linalool"].percentage == pytest.approx(4.2 * 0.18)
    assert rows["Linalool"].threshold == 0.001 and report.leave_on
    assert [a.name for a in report.allergens] == ["Limonene", "Linalool"]     # by weight


def test_exactly_at_the_threshold_is_reportable_unlike_eu_labeling():
    # 0.01% of a 10% fragrance = 0.001% of the product: "at or above" is reportable.
    frag = fragrance(10.0, declaration=[Constituent("78-70-6", "Linalool", 0.01)])
    assert set(names(cscp_report(product(frag=frag), AS_OF, reportable_list=LIST))) == {"Linalool"}
    just_under = fragrance(10.0, declaration=[Constituent("78-70-6", "Linalool", 0.0099)])
    assert not cscp_report(product(frag=just_under), AS_OF, reportable_list=LIST).allergens


def test_rinse_off_threshold_is_ten_times_higher():
    frag = fragrance(10.0, declaration=[Constituent("78-70-6", "Linalool", 0.05)])    # 0.005% of the product
    assert cscp_report(product(frag=frag, leave_on=True), AS_OF, reportable_list=LIST).allergens
    rinse = cscp_report(product(frag=frag, leave_on=False), AS_OF, reportable_list=LIST)
    assert not rinse.allergens and rinse.leave_on is False


def test_rounding_near_the_threshold_is_a_warning():
    # A 40% concentrate declaring 0.002% (3 decimals): 0.0008% of the product, but rounding allows 0.0010%.
    frag = fragrance(40.0, declaration=[Constituent("78-70-6", "Linalool", 0.002, reported_decimals=3)])
    report = cscp_report(product(frag=frag), AS_OF, reportable_list=LIST)
    assert not report.allergens and any("rounding allows" in w for w in report.warnings)


def test_missing_declaration_blocks_the_report():
    frag = fragrance(declaration=[], basis=None)
    report = cscp_report(product(frag=frag), AS_OF, reportable_list=LIST)
    assert not report.complete and any("allergen declaration" in f.message for f in report.findings)


def test_declaration_for_the_old_list_blocks_and_unknown_basis_warns():
    old = cscp_report(product(frag=fragrance(basis="eu_26")), AS_OF, reportable_list=LIST)
    assert not old.complete and any("'eu_26' list only" in f.message for f in old.findings)
    unknown = cscp_report(product(frag=fragrance(basis=None)), AS_OF, reportable_list=LIST)
    assert any("doesn't say which list" in w for w in unknown.warnings)
    assert not any(f.field == "allergens" for f in unknown.findings)


def test_natural_allergens_are_estimated_and_flagged():
    lavender = ProductComponent(
        name="Lavender oil", percentage=0.5, role=ComponentRole.BOTANICAL, inci_name="LAVANDULA ANGUSTIFOLIA OIL",
        cas_number="8000-28-0", botanical=Botanical("Lavandula Angustifolia", "Lavender"))
    report = cscp_report(product(lavender), AS_OF, reportable_list=LIST)
    assert names(report)["Linalool"].estimated                                   # lavender adds to the fragrance's linalool
    assert any("estimated" in w for w in report.warnings)


def test_the_unloaded_reportable_list_means_never_complete():
    report = cscp_report(product(), AS_OF)                                       # the packaged list is empty
    assert not report.list_loaded and not report.complete
    assert any(f.field == "reportable_ingredients_list" for f in report.findings)
    assert report.allergens                                                      # allergens are still computed


def test_list_ingredients_are_found_at_any_concentration():
    frag = fragrance(full_composition=[
        Constituent("78-70-6", "Linalool", 4.2),
        Constituent("123-45-6", "Example Listed Substance", 0.0001),
    ])
    report = cscp_report(product(frag=frag), AS_OF, reportable_list=LIST)
    assert report.complete
    [hit] = report.listed_ingredients
    assert (hit.cas_number, hit.component, hit.lists) == ("123-45-6", "Nostalgia", ["Example list"])
    assert hit.max_percentage == pytest.approx(0.0001 * 0.18)


def test_fragrance_without_full_composition_cannot_rule_out_list_ingredients():
    report = cscp_report(product(), AS_OF, reportable_list=LIST)
    assert not report.complete and any("no full composition" in f.message for f in report.findings)


def test_csv_pack_has_one_row_per_reportable_item():
    frag = fragrance(full_composition=[Constituent("78-70-6", "Linalool", 4.2), Constituent("123-45-6", "Example Listed Substance", 0.5)])
    rows = list(csv.DictReader(io.StringIO(cscp_report(product(frag=frag), AS_OF, reportable_list=LIST).to_csv())))
    assert [(r["section"], r["ingredient"]) for r in rows] == [
        ("fragrance allergen", "Linalool"), ("reportable list ingredient", "Example Listed Substance")]
    assert rows[0]["type"] == "leave-on" and rows[0]["cas"] == "78-70-6" and rows[1]["threshold_percent"] == "any"


def test_rules_are_marked_unverified():
    assert not cscp_report(product(), AS_OF, reportable_list=LIST).rules_verified
