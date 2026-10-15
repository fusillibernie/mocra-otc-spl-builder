# Source refresh report

Run 2026-10-15T04:02:26+00:00. 11 files seen: 11 new, 0 changed, 0 unchanged; 15 failures.

## New or changed

A person reads each one, runs or updates the importer, and checks the data files it affects. Old versions stay in git history.

### FDA SPL Implementation Guide with Validation Procedures (current)

- `sources/fda/spl_implementation_guide_current.pdf` (new) from https://www.fda.gov/media/84201/download

Re-check: `src/mocra_otc_spl_builder/codes.py`, `src/mocra_otc_spl_builder/cosmetic_validation.py`, `src/mocra_otc_spl_builder/facility_registration.py`, `src/mocra_otc_spl_builder/cosmetic_spl.py`

FDA keeps this media id pointing at the current guide. A change means a new revision: diff it against sources/spl_ig_vp_dec_2023.pdf (chapters 2, 3.4, 35, 36 for cosmetics; 4 onward for OTC drug listing).

### FDA SPL resources page: schema, stylesheet, guides, code lists

- `sources/fda/spl/spl_ig_vp_dec_2023.pdf` (new) from https://www.fda.gov/media/84201/download
- `sources/fda/spl/SPL-Schema-Update.zip` (new) from https://www.fda.gov/media/84209/download
- `sources/fda/spl/SPL-Stylesheet-Update.zip` (new) from https://www.fda.gov/media/86046/download
- `sources/fda/spl/terminology_lists.zip` (new) from https://www.fda.gov/media/86426/download

Re-check: `src/mocra_otc_spl_builder/data/spl_schema/`, `src/mocra_otc_spl_builder/data/spl_stylesheet/`, `src/mocra_otc_spl_builder/codes.py`

A new schema or stylesheet bundle: replace the copies under data/spl_schema/ and data/spl_stylesheet/ and re-run tests/test_schema.py.

### FDA cosmetics registration and listing page: guidance, category list, forms

- `sources/fda/cosmetics/spl_ig_vp_dec_2023.pdf` (new) from https://www.fda.gov/media/84201/download?attachment

Re-check: `src/mocra_otc_spl_builder/data/cosmetic_categories.json`, `src/mocra_otc_spl_builder/cosmetic_validation.py`

A new guidance revision can change Appendix A (the category codes): point scripts/build_cosmetic_categories.py at it and re-run.

### ESG NextGen user guides (API guide and specification, USP guide)

- `sources/fda/esg/esg_nextgen_user_guide_for_the_unified_submission_portal_v1.8_-_september_2026.pdf` (new) from https://www.fda.gov/media/194894/download?attachment
- `sources/fda/esg/esg_nextgen_unified_submission_portal_passkey_set-up_quick_guide.pdf` (new) from https://www.fda.gov/media/194299/download?attachment
- `sources/fda/esg/esg_nextgen_as2_guide_for_industry_users_v2.2_-_july_2026.pdf` (new) from https://www.fda.gov/media/193542/download?attachment
- `sources/fda/esg/esg_nextgen_api_guide_v1.2.1_-_august_2026.pdf` (new) from https://www.fda.gov/media/194410/download?attachment
- `sources/fda/esg/esg_nextgen_api_specification_v1.2_-_march_2026.pdf` (new) from https://www.fda.gov/media/191612/download?attachment

Re-check: `src/mocra_otc_spl_builder/esg.py`

Check endpoints, headers, request bodies and error codes in esg.py against the new specification.

## Couldn't fetch

- `fda-otc-m019`: https://www.accessdata.fda.gov/drugsatfda_docs/omuf/Order/Final%20Administrative%20Order%20OTC000015_M019-Antiperspirant%20Drug%20Products%20for%20OTC%20Human%20Use.pdf: HTTP 404
- `fda-otc-m021`: https://www.accessdata.fda.gov/drugsatfda_docs/omuf/Order/Final%20Administrative%20Order%20OTC000034_M021-Anticaries%20Drug%20Products%20for%20OTC%20Human%20Use.pdf: HTTP 404
- `fda-otc-m006`: https://www.accessdata.fda.gov/drugsatfda_docs/omuf/Order/Final%20Administrative%20Order%20OTC000013_M006-Topical%20Acne%20drug%20products%20for%20OTC%20Human%20Use.pdf: HTTP 404
- `fda-otc-m020-amendment`: https://www.accessdata.fda.gov/drugsatfda_docs/omuf/order/supportDoc/OTC000039/Final_Administrative_Order.pdf: HTTP 404
- `fda-otc-m003`: https://www.accessdata.fda.gov/drugsatfda_docs/omuf/monographs/OTC%20Monograph_M003-First%20Aid%20Antiseptic%20products%20for%20OTC%20Human%20Use.pdf: HTTP 404
- `carb-pfp-2025`: https://ww2.arb.ca.gov/our-work/programs/consumer-products-program/product-reporting/2025-personal-fragrance-products: no matching links on the index page (page changed, or the filters are too tight?)
- `carb-pfp-tool-instructions`: https://ww2.arb.ca.gov/sites/default/files/2026-01/PFP-RT%20Instructions.pdf: empty response
- `carb-consumer-products`: https://ww2.arb.ca.gov/our-work/programs/consumer-products-program: no matching links on the index page (page changed, or the filters are too tight?)
- `cdph-fragrance-allergens-factsheet`: https://www.cdph.ca.gov/Programs/CCDPHP/DEODC/OHB/CSCP/CDPH%20Document%20Library/FragranceAllergensinCosmeticsFactsheet.pdf: URLError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1032)
- `cdph-cscp-sb312`: https://www.cdph.ca.gov/Programs/CCDPHP/DEODC/OHB/CSCP/Pages/SB312.aspx: URLError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1032)
- `cdph-cscp-reporting-guidance`: https://www.cdph.ca.gov/Programs/CCDPHP/DEODC/OHB/CSCP/Pages/ReportingGuidance.aspx: URLError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1032)
- `ecfr-40-cfr-51-100`: https://www.ecfr.gov/api/versioner/v1/full/{today}/title-40.xml?part=51&section=51.100: HTTP 406 (this URL was never confirmed; if it is a 404, fix sources/manifest.json)
- `ecfr-40-cfr-59`: https://www.ecfr.gov/api/versioner/v1/full/{today}/title-40.xml?part=59: HTTP 406 (this URL was never confirmed; if it is a 404, fix sources/manifest.json)
- `ecfr-21-cfr-701`: https://www.ecfr.gov/api/versioner/v1/full/{today}/title-21.xml?part=701: HTTP 406 (this URL was never confirmed; if it is a 404, fix sources/manifest.json)
- `ecfr-21-cfr-201-66`: https://www.ecfr.gov/api/versioner/v1/full/{today}/title-21.xml?part=201&section=201.66: HTTP 406 (this URL was never confirmed; if it is a 404, fix sources/manifest.json)
