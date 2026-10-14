# State reporting: CSCP allergens and VOC

Written 2026-10-14. Everything marked **unconfirmed** comes from search-result summaries; cdph.ca.gov,
arb.ca.gov and fda.gov are blocked from the build environment, so no primary page was read.

## Where it lives

Here, in the cosmetics/OTC repo, not in fragrance-reg-core: these are filings a cosmetics and OTC brand
makes, not reference data. The dependency runs one way, as for ingredient lists: this repo calls
fragrance-reg-core (optional `[core]` extra) for allergen and composition calculations and owns the
reporting rules, the data packs and the calendar.

Neither CDPH nor CARB is reached by an API we know of: CSCP is a web portal, and CARB's survey used a
downloadable reporting tool. So the output is a **data pack for a person to enter**, with this package's
field names to be mapped onto the portal or tool. No browser automation of either.

## CSCP (California Safe Cosmetics Program, CDPH): built

`cscp.cscp_report(FinishedProduct)` -> `CscpReport` (rows, findings, warnings, `to_csv()`).

| Reportable | Rule used | Status |
|---|---|---|
| Fragrance allergens | at or above 0.001% (leave-on) / 0.01% (rinse-off), whatever their function. "At or above", unlike EU labeling's "exceeds" | rules in `data/cscp_rules.json`, **unverified** |
| Which substances | flagged `eu_26` / `eu_82` in core's allergen data; CDPH's list appears to track the EU's expanded 82 | **unconfirmed** |
| Other fragrance/flavor ingredients | any concentration, if on CDPH's Reportable Ingredients List (updated twice a year; 6 months to comply) | **list not loaded**; report is never "complete" until it is |

How it decides, per product:
- Allergen totals come from core: supplier declarations or full compositions, scaled by dose, naturals
  estimated from reference data (flagged `estimated`), isomers summed, supplier rounding checked.
- Blocking findings (`complete` is False): no allergen declaration; declaration covers only the 26 list;
  list not loaded; fragrance with no full composition (list ingredients below allergen level can't be
  ruled out). Warnings: estimated naturals, declaration list not stated, a figure within supplier
  rounding of the threshold.
- Core integration uses `LabelingService._allergen_contributions`, private in v0.5.3. Ask core to
  expose it (next release) and switch.

Not built (needs documents or decisions):
1. **Importer for CDPH's Reportable Ingredients List.** Needs the file from CDPH's SB 312 page.
2. **Portal field mapping.** Needs CDPH's reporting instructions/template.
3. **Supplier statements** for list ingredients in a fragrance with no full composition (a place to
   record "supplier certifies none of the list present", with date and who).
4. **Deadlines.** A CDPH FAQ was reported to tie allergen reporting to the EU's dates (2026 new,
   2028 existing): **unconfirmed, and may already be due for new products.** Plus new-product and
   list-update (6 months) timing, as dated obligations like the packaging packs in fragrance-reg-core.
5. Whether CSCP's duty applies to you (who counts as the manufacturer on the label, any exemption).

## VOC: not built yet

Three reports in scope. What is known, all **unconfirmed**:

| Report | Known | Open |
|---|---|---|
| **CARB personal fragrance products (PFP)** | 2025 technical assessment: due 31 Mar 2026 (passed), via CARB's downloadable PFP Reporting Tool. 2025 California sales, brands, formulations, labels, certification, and efforts toward the 50% VOC standard | Is there a recurring duty (section 94513 was cited)? When is the next call? |
| **CARB general consumer products reporting/survey** | Nothing found for 2026 | Is any call-in open? The notice you received, if any, settles it |
| **Aerosols, including OTC antiperspirants** | Aerosol PFPs made from 1 Jan 2031 must meet 50% VOC (non-aerosol PFPs with 10% or less fragrance: 50% from 2031, 70% for 7% or less fragrance before that). CARB's category limits appear to cover antiperspirants/deodorants | Which category limits apply to each product; aerosol vs non-aerosol; other jurisdictions (Ozone Transport Commission states, EPA's national rule) |

Design, to build once the sources are in:
1. **`data/carb_voc_limits.json`**, built by a script from the regulation text (the way
   `scripts/build_cosmetic_categories.py` builds the FDA categories): per category, aerosol or
   not, fragrance-content band, limit %, effective date, source sha256. Replaces fragrance-reg-core's
   8 hand-entered, unverified limits for this purpose (core's PFP limit is a flat 75%, which looks out
   of date). core's `VOCRegulation.OTC` is described as "over-the-counter drugs"; it probably means the
   Ozone Transport Commission.
2. **`voc.voc_report(...)`**: inputs: product VOC % by weight (entered, or computed with core's
   `VOCService`, whose ingredient data is unverified), aerosol or not, fragrance %, category, California
   sales. Outputs: category and limit in force on a date, margin, the next limit change, findings, and a
   data pack for CARB's tool.
3. **Calendar**: dated obligations (reports, limit step-downs) in the same pack format as core's
   packaging obligations, so "what do I owe next" works for CSCP, CARB and FDA together.

## Documents needed (upload through Drive or the chat)

| For | Document | Where |
|---|---|---|
| CSCP | Reportable Ingredients List; CDPH reporting instructions; fragrance allergens fact sheet; Compliance FAQ | CDPH SB 312 page: https://www.cdph.ca.gov/Programs/CCDPHP/DEODC/OHB/CSCP/Pages/SB312.aspx |
| CARB PFP | PFP Reporting Tool and its instructions; the 2025 assessment page | https://ww2.arb.ca.gov/our-work/programs/consumer-products-program/product-reporting/2025-personal-fragrance-products ; instructions: https://ww2.arb.ca.gov/sites/default/files/2026-01/PFP-RT%20Instructions.pdf |
| CARB limits | Consumer Products Regulation text, 17 CCR 94500-94517 incl. definitions, category limits and reporting sections; the 2021 PFP amendments' final regulation order | CARB consumer products program |
| CARB surveys | Any survey or data call-in notice you received | your inbox |
| Other VOC | States you ship aerosols into (for Ozone Transport Commission rules); EPA 40 CFR part 59 subpart C if relevant | |
