# Official sources

Every code value in `src/` traces back to one of these (see `src/mocra_otc_spl_builder/codes.py`).

| File | What | Version | Got it |
|---|---|---|---|
| `fda_guidance_cosmetics_registration_listing_2024-12.pdf` | FDA Guidance for Industry: Registration and Listing of Cosmetic Product Facilities and Products. Appendix A = category codes (`scripts/build_cosmetic_categories.py`) | December 2024 | 2026-10-13, uploaded |
| `esg_nextgen_api_specification_v1.2_2026-03.pdf` | ESG NextGen API Specification: endpoints, headers, bodies, errors (`esg.py`) | v1.2, March 2026 | 2026-10-13, uploaded |
| `esg_nextgen_api_guide_v1.2.1_2026-08.pdf` | ESG NextGen API Guide: account, API keys, call order | v1.2.1, August 2026 | 2026-10-13, uploaded |
| `esg_nextgen_usp_user_guide_v1.8_2026-09.pdf` | ESG NextGen Unified Submission Portal guide: registration, test submissions, ACKs | v1.8, September 2026 | 2026-10-13, uploaded |
| `spl_ig_vp_dec_2023.pdf` | FDA SPL Implementation Guide with Validation Procedures v1 (cosmetics: ch. 3.4, 35, 36) | revision 202312080859, December 2023. sha256 `9845e23cb51ee2e7f493b17ed5729b2bc946040244e6f6da2d78c9491a41f983` | 2026-10-13, from https://www.fda.gov/media/84201/download |

Bundled in the package (`src/mocra_otc_spl_builder/data/`), from FDA's SPL resources page, uploaded 2026-10-13:

- `spl_schema/`: SPL schema SchemasR2b, from `SPL-Schema-Update.zip` (sha256 `03419c6db5b1f391bef030c4abfdc02e4b2c5f24bb2dc9e65cc6da7b48ebaedb`)
- `spl_stylesheet/`: SPL stylesheet 6.2, from `SPL-Stylesheet-Update.zip` (sha256 `cd807832d074da618af91b66a2375e669554b02fbc516b14864bd9be83f5a5ff`)

Still needed:

- [ ] FDA SPL terminology file for cosmetic categories, to confirm the exact display names and the code system OID (the codes themselves come from the guidance's Appendix A).
- [x] FDA "Center Submission Types" page, photographed 2026-10-13 (content current as of 2026-09-17): `center_submission_types_2026-09-17/`. Cosmetic SPL route inferred as OC / SPL.
- [ ] OTC Monograph orders for the monographs in `data/otc_monographs.json`
- [ ] Check FDA's SPL resources page for a guide newer than December 2023: https://www.fda.gov/industry/fda-resources-data-standards/structured-product-labeling-resources
