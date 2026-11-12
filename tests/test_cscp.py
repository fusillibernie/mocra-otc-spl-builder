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
    report = cscp_report(product(), AS_OF, reportable_list=ReportableList())
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


# --- CDPH's April 2026 Reportable Ingredients List, as packaged ---------------------------------

def mixed_list():
    return ReportableList.from_records([
        {"cas": "78-70-6", "name": "Linalool", "lists": ["Annex III"], "when": ["FA"]},
        {"cas": "111-11-1", "name": "Any substance", "lists": ["Prop 65"], "when": ["Any"]},
        {"cas": "222-22-2", "name": "Fragrance-only substance", "lists": ["EC EDs"], "when": ["FF"]},
    ], without_cas=[{"name": "Chromium and chromium compounds", "synonyms": ["chromium"], "lists": ["Prop 65"], "when": ["Any"]}])


def preservative(*constituents):
    return ProductComponent(name="Preservative", percentage=1.0, role=ComponentRole.OTHER, full_composition=list(constituents))


def test_the_packaged_list_is_loaded_with_cdphs_when_to_report_codes():
    cdph = ReportableList.load()
    assert cdph.loaded and cdph.verified and len(cdph.entries) > 3000 and cdph.without_cas
    assert {c for r in cdph.entries.values() for c in r["when"]} == {"Any", "FF", "FA"}
    assert "78-70-6" in cdph.allergen_cas and "5989-27-5" in cdph.allergen_cas      # linalool, limonene


def test_allergens_follow_cdphs_fa_entries_not_cores_eu_flags():
    # Benzyl acetate is in core's EU-82 data but not an FA entry on CDPH's list.
    frag = fragrance(declaration=[Constituent("78-70-6", "Linalool", 4.2), Constituent("140-11-4", "Benzyl acetate", 5.0)])
    assert set(names(cscp_report(product(frag=frag), AS_OF, reportable_list=ReportableList.load()))) == {"Linalool"}


def test_without_the_list_allergens_fall_back_to_core_flags_with_a_warning():
    report = cscp_report(product(), AS_OF, reportable_list=LIST)
    assert any("EU flags" in w for w in report.warnings)


def test_any_applies_to_every_component_but_ff_only_to_fragrance_and_fa_is_left_to_the_allergen_section():
    frag = fragrance(full_composition=[Constituent("78-70-6", "Linalool", 4.2), Constituent("222-22-2", "Fragrance-only substance", 0.1)])
    report = cscp_report(product(preservative(Constituent("111-11-1", "Any substance", 2.0), Constituent("222-22-2", "Fragrance-only substance", 2.0)), frag=frag),
                         AS_OF, reportable_list=mixed_list())
    assert sorted((i.cas_number, i.component, tuple(i.when)) for i in report.listed_ingredients) == [
        ("111-11-1", "Preservative", ("Any",)), ("222-22-2", "Nostalgia", ("FF",))]          # FF in the preservative: not reportable
    assert [a.name for a in report.allergens] == ["Linalool"]                              # not also a list ingredient


def test_components_without_composition_are_called_out_for_any_entries():
    report = cscp_report(product(frag=fragrance(full_composition=[Constituent("78-70-6", "Linalool", 4.2)])), AS_OF, reportable_list=mixed_list())
    assert any("SD Alcohol 40-B" in w and "'Any'" in w for w in report.warnings)


def test_cdph_rows_without_a_cas_number_are_matched_by_name_with_a_warning():
    frag = fragrance(full_composition=[Constituent("78-70-6", "Linalool", 4.2)])
    report = cscp_report(product(preservative(Constituent("7440-47-3", "Chromium", 0.1)), frag=frag), AS_OF, reportable_list=mixed_list())
    assert any("Chromium" in w and "no CAS number" in w for w in report.warnings)
    assert not report.listed_ingredients


# --- Cases the independent review found -------------------------------------------------------

def test_an_fa_allergen_declared_under_cdphs_cas_is_reported_even_if_core_resolves_the_name_elsewhere():
    # Core matches "Spearmint Oil" to 8022-56-8, which CDPH doesn't list; CDPH lists 8008-79-5.
    frag = fragrance(declaration=[Constituent("8008-79-5", "Spearmint Oil", 1.0)])           # 0.18% of the product
    report = cscp_report(product(frag=frag), AS_OF, reportable_list=ReportableList.load())
    [row] = report.allergens
    assert row.cas_number == "8008-79-5" and row.percentage == pytest.approx(0.18) and not row.estimated
    assert any("plain sum" in w for w in report.warnings)


def test_cdph_fa_cas_that_core_does_not_have_are_reported():
    frag = fragrance(full_composition=[Constituent("23696-85-7", "beta-Damascenone", 0.5)])      # 0.09% of the product
    assert [a.cas_number for a in cscp_report(product(frag=frag), AS_OF, reportable_list=ReportableList.load()).allergens] == ["23696-85-7"]


def test_a_component_that_is_itself_a_listed_substance_is_reported():
    benzyl_alcohol = ProductComponent(name="Benzyl Alcohol", percentage=1.0, role=ComponentRole.OTHER, cas_number="100-51-6")
    report = cscp_report(product(benzyl_alcohol), AS_OF, reportable_list=ReportableList.load())
    assert "100-51-6" in {a.cas_number for a in report.allergens}
    prop65 = ProductComponent(name="Preservative", percentage=1.0, role=ComponentRole.OTHER, cas_number="111-11-1")
    assert [i.cas_number for i in cscp_report(product(prop65), AS_OF, reportable_list=mixed_list()).listed_ingredients] == ["111-11-1"]


def test_ff_in_a_non_fragrance_component_asks_whether_it_is_a_flavor():
    flavor = ProductComponent(name="Flavor", percentage=1.0, role=ComponentRole.OTHER, full_composition=[Constituent("222-22-2", "Fragrance-only substance", 50.0)])
    report = cscp_report(product(flavor), AS_OF, reportable_list=mixed_list())
    assert not report.listed_ingredients and any("flavor" in w and "Flavor" in w for w in report.warnings)


def test_the_same_listed_substance_in_two_components_is_one_row_with_the_summed_percentage():
    a = preservative(Constituent("111-11-1", "Any substance", 2.0))
    b = ProductComponent(name="Booster", percentage=2.0, role=ComponentRole.OTHER, full_composition=[Constituent("111-11-1", "Any substance", 10.0)])
    [hit] = cscp_report(product(a, b), AS_OF, reportable_list=mixed_list()).listed_ingredients
    assert hit.max_percentage == pytest.approx(0.02 + 0.2) and hit.component == "Preservative; Booster"


def test_a_declared_ff_substance_below_allergen_level_is_listed_even_without_a_full_composition():
    lilial = fragrance(declaration=[Constituent("80-54-6", "Lilial", 0.0001)])
    report = cscp_report(product(frag=lilial), AS_OF, reportable_list=ReportableList.load())
    assert [i.cas_number for i in report.listed_ingredients] == ["80-54-6"]


def test_a_listed_entry_that_is_not_reportable_does_not_hide_a_later_cas_that_is():
    both = Constituent("78-70-6", "Mixed", 1.0, other_cas=["111-11-1"])                          # FA-only, then Any
    cdph = mixed_list()
    frag = fragrance(declaration=[both])
    assert "111-11-1" in {i.cas_number for i in cscp_report(product(preservative(both), frag=frag), AS_OF, reportable_list=cdph).listed_ingredients}


def test_build_script_helpers():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("build_cscp_list", Path(__file__).parents[1] / "scripts" / "build_cscp_list.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.cas_ok("78-70-6") and not mod.cas_ok("661791-31-9")
    assert mod.when_codes("FA, FF") == ["FA", "FF"] and mod.when_codes("Any") == ["Any"]
    with pytest.raises(ValueError):
        mod.when_codes("Sometimes")
    assert mod.CAS_IN.findall("50-00-0 (Formaldehyde)\n463-57-0 (Methylene Glycol)") == ["50-00-0", "463-57-0"]
