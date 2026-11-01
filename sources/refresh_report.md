# Source refresh report

Run 2026-11-01T14:44:50+00:00. 18 files seen: 7 new, 0 changed, 9 unchanged, 2 already stored under another name; 11 failures.

## New or changed

A person reads each one, runs or updates the importer, and checks the data files it affects. Old versions stay in git history.

### CARB 2025 personal fragrance products page: reporting tool, instructions, letters

- `sources/carb/pfp/PFP Letter_webpage_0.pdf` (new) from https://ww2.arb.ca.gov/sites/default/files/2025-12/PFP%20Letter_webpage_0.pdf
- `sources/carb/pfp/2025 PFP-RT_v1.02.xlsm` (new) from https://ww2.arb.ca.gov/sites/default/files/2026-07/2025%20PFP-RT_v1.02.xlsm
- `sources/carb/pfp/2025 PFP-RT_Mac_v1.02.xlsm` (new) from https://ww2.arb.ca.gov/sites/default/files/2026-07/2025%20PFP-RT_Mac_v1.02.xlsm
- `sources/carb/pfp/PFP-RT Instructions.pdf` (new) from https://ww2.arb.ca.gov/sites/default/files/2026-01/PFP-RT%20Instructions.pdf
- `sources/carb/pfp/Appendix A _ List of Special Reporting Categories_01_28.pdf` (new) from https://ww2.arb.ca.gov/sites/default/files/2026-01/Appendix%20A%20_%20List%20of%20Special%20Reporting%20Categories_01_28.pdf

Re-check: `docs/STATE_REPORTING.md`, `src/mocra_otc_spl_builder/data/carb_voc_limits.json (planned)`

The PFP reporting tool defines the fields the VOC data pack must match.

### CARB consumer products program: regulation text, final regulation orders, category limits

- `sources/carb/consumer-products/Webinar and Non-Respondent Companies Announcement_8-19-2025.pdf` (new) from https://ww2.arb.ca.gov/sites/default/files/2025-08/Webinar%20and%20Non-Respondent%20Companies%20Announcement_8-19-2025.pdf

Re-check: `src/mocra_otc_spl_builder/data/carb_voc_limits.json (planned)`

17 CCR 94500-94517 and each amendment's Final Regulation Order should be among these. If the right file is not, find its page and add a links entry. CARB amends this regulation every few years.

### CDPH SB 312 page: Reportable Ingredients List, guidance, fact sheets

- `sources/cdph/Reportable_Ingredients_List.xlsx` (new) from https://cscpsubmit.cdph.ca.gov/submission/assets/files/Reportable_Ingredients_List.xlsx

Re-check: `src/mocra_otc_spl_builder/data/cscp_reportable_ingredients.json`, `src/mocra_otc_spl_builder/data/cscp_rules.json`

The Reportable Ingredients List is updated twice a year; companies have 6 months to comply after each update.

## Importers

- `scripts/build_carb_voc_limits.py`: FAILED
  ```
  importer not written yet
  ```
- `scripts/build_cscp_list.py`: FAILED
  ```
  importer not written yet
  ```

## Couldn't fetch

- `fda-cosmetics-registration-listing`: https://www.fda.gov/cosmetics/registration-listing-cosmetic-product-facilities-and-products: no matching links on the index page (117 links, 62724 bytes; page text starts: 'Registration &amp; Listing of Cosmetic Product Facilities and Products | FDA <link rel="stylesheet" media="all" href="/files/css/css_I1lI2DYRy4WvhS49GZC8Z2v9NUF')
- `fda-otc-m019`: https://www.accessdata.fda.gov/drugsatfda_docs/omuf/Order/Final%20Administrative%20Order%20OTC000015_M019-Antiperspirant%20Drug%20Products%20for%20OTC%20Human%20Use.pdf: HTTP 404 (server: AkamaiGHost): 'FDA Apology' (this URL was never confirmed; if it is a 404, fix sources/manifest.json)
- `fda-otc-m021`: https://www.accessdata.fda.gov/drugsatfda_docs/omuf/Order/Final%20Administrative%20Order%20OTC000034_M021-Anticaries%20Drug%20Products%20for%20OTC%20Human%20Use.pdf: HTTP 404 (server: AkamaiGHost): 'FDA Apology' (this URL was never confirmed; if it is a 404, fix sources/manifest.json)
- `fda-otc-m006`: https://www.accessdata.fda.gov/drugsatfda_docs/omuf/Order/Final%20Administrative%20Order%20OTC000013_M006-Topical%20Acne%20drug%20products%20for%20OTC%20Human%20Use.pdf: HTTP 404 (server: AkamaiGHost): 'FDA Apology' (this URL was never confirmed; if it is a 404, fix sources/manifest.json)
- `fda-otc-m020-amendment`: https://www.accessdata.fda.gov/drugsatfda_docs/omuf/order/supportDoc/OTC000039/Final_Administrative_Order.pdf: HTTP 404 (server: AkamaiGHost): 'FDA Apology' (this URL was never confirmed; if it is a 404, fix sources/manifest.json)
- `fda-otc-m003`: https://www.accessdata.fda.gov/drugsatfda_docs/omuf/monographs/OTC%20Monograph_M003-First%20Aid%20Antiseptic%20products%20for%20OTC%20Human%20Use.pdf: HTTP 404 (server: AkamaiGHost): 'FDA Apology' (this URL was never confirmed; if it is a 404, fix sources/manifest.json)
- `cdph-fragrance-allergens-factsheet`: https://www.cdph.ca.gov/Programs/CCDPHP/DEODC/OHB/CSCP/CDPH%20Document%20Library/FragranceAllergensinCosmeticsFactsheet.pdf: HTTP 404 (server: volt-adc): 'File Not Found'
- `ecfr-40-cfr-51-100`: https://www.ecfr.gov/api/versioner/v1/full/{today}/title-40.xml?part=51&section=51.100: HTTP 406: 'This endpoint requires response compression. Send an Accept-Encoding header that permits compression. 11' (this URL was never confirmed; if it is a 404, fix sources/manifest.json)
- `ecfr-40-cfr-59`: https://www.ecfr.gov/api/versioner/v1/full/{today}/title-40.xml?part=59: HTTP 406: 'This endpoint requires response compression. Send an Accept-Encoding header that permits compression. 11' (this URL was never confirmed; if it is a 404, fix sources/manifest.json)
- `ecfr-21-cfr-701`: https://www.ecfr.gov/api/versioner/v1/full/{today}/title-21.xml?part=701: HTTP 406: 'This endpoint requires response compression. Send an Accept-Encoding header that permits compression. 11' (this URL was never confirmed; if it is a 404, fix sources/manifest.json)
- `ecfr-21-cfr-201-66`: https://www.ecfr.gov/api/versioner/v1/full/{today}/title-21.xml?part=201&section=201.66: HTTP 406: 'This endpoint requires response compression. Send an Accept-Encoding header that permits compression. 11' (this URL was never confirmed; if it is a 404, fix sources/manifest.json)
