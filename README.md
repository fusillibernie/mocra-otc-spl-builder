# mocra-otc-spl-builder

Builds FDA Structured Product Labeling (SPL) XML for our own brands, checks it before it
leaves, and (later) submits it through the ESG NextGen API.

| Submission | Law | Renewal |
|---|---|---|
| Cosmetic facility registration | MoCRA (FD&C Act §607) | every 2 years |
| Cosmetic product listing | MoCRA (FD&C Act §607) | yearly update |
| Establishment registration, NDC labeler code, OTC drug listing | FD&C Act §510 | yearly (Oct–Dec) |

## How it works

1. **Data in**: products, facilities and the responsible person as typed records (`models.py`).
   Cosmetic ingredient lists come from `fragrance-reg-core`'s `labeling_service`.
2. **Completeness check**: every missing or unverified field becomes a finding. Nothing is guessed.
3. **SPL out**: deterministic XML built from FDA's SPL Implementation Guides (`sources/`).
4. **Validate** against FDA's SPL validation rules before anything is sent.
5. **Human sign-off**: a named person approves each submission. Not configurable.
6. **Submit + acknowledgments** via the ESG NextGen API (later phase).

Agents help with steps 1, 2 and with reading FDA error acknowledgments. They never submit.

## Status

Skeleton only.

- **Phase 1: cosmetics.** Facility registration and product listing SPL, validated locally.
- **Phase 2: ESG NextGen API** submission and acknowledgments.
- **Phase 3: OTC.** Priority monographs, modeled on Church & Dwight's OTC lines: M019
  antiperspirant, M021 anticaries, M006 topical acne, M020 sunscreen, M003 first aid antiseptic.
  Hand sanitizer, oral pain and anorectal still need their governing monograph identified
  (`data/otc_monographs.json`). See `sources/README.md` for the FDA
documents that must be downloaded before any XML code is written. No SPL code values
(LOINC section codes, document type codes, OIDs) are to be typed from memory.

## Tests

```bash
pip install -e ".[dev]"
pytest
```
