# Official sources

Every code value in `src/` traces back to one of these (see `src/mocra_otc_spl_builder/codes.py`).

| File | What | Version | Got it |
|---|---|---|---|
| `spl_ig_vp_dec_2023.pdf` | FDA SPL Implementation Guide with Validation Procedures v1 (cosmetics: ch. 3.4, 35, 36) | revision 202312080859, December 2023. sha256 `9845e23cb51ee2e7f493b17ed5729b2bc946040244e6f6da2d78c9491a41f983` | 2026-10-13, from https://www.fda.gov/media/84201/download |

Still needed:

- [ ] FDA cosmetic product category list (SPL terminology). The guide uses the codes (01B, 14D1, ...) but does not list them.
- [ ] FDA `spl.xsd` schema, to validate generated XML locally: https://www.accessdata.fda.gov/spl/schema/spl.xsd
- [ ] ESG NextGen API Guide (v1.2.1, August 2026, or newer)
- [ ] OTC Monograph orders for the monographs in `data/otc_monographs.json`
- [ ] Check FDA's SPL resources page for a guide newer than December 2023: https://www.fda.gov/industry/fda-resources-data-standards/structured-product-labeling-resources
