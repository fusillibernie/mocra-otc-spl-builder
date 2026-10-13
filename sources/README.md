# Official sources

Every code value in `src/` traces back to one of these (see `src/mocra_otc_spl_builder/codes.py`).

| File | What | Version | Got it |
|---|---|---|---|
| `fda_guidance_cosmetics_registration_listing_2024-12.pdf` | FDA Guidance for Industry: Registration and Listing of Cosmetic Product Facilities and Products. Appendix A = category codes (`scripts/build_cosmetic_categories.py`) | December 2024 | 2026-10-13, uploaded |
| `esg_nextgen_api_guide_v1.2_2026-03.pdf` | ESG NextGen API Guide (token, submission ID, upload, status, acknowledgments) | v1.2, March 2026 | 2026-10-13, uploaded |
| `spl_ig_vp_dec_2023.pdf` | FDA SPL Implementation Guide with Validation Procedures v1 (cosmetics: ch. 3.4, 35, 36) | revision 202312080859, December 2023. sha256 `9845e23cb51ee2e7f493b17ed5729b2bc946040244e6f6da2d78c9491a41f983` | 2026-10-13, from https://www.fda.gov/media/84201/download |

Still needed:

- [ ] FDA SPL terminology file for cosmetic categories, to confirm the exact display names and the code system OID (the codes themselves come from the guidance's Appendix A).
- [ ] The complete SPL schema set. `spl.xsd` only includes `PORP_MT050032UV.xsd`, which pulls in further files; FDA's SPL resources page offers the set as a zip.
- [ ] ESG NextGen API Specification v1.0 (.docx, "User Guides" on FDA's ESG NextGen page): exact headers and request bodies.
- [ ] FDA "Center Submission Types" page: the center and submission type values for cosmetic SPL (the API guide's sample routes cosmetics to HFP).
- [ ] OTC Monograph orders for the monographs in `data/otc_monographs.json`
- [ ] Check FDA's SPL resources page for a guide newer than December 2023: https://www.fda.gov/industry/fda-resources-data-standards/structured-product-labeling-resources
