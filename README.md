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

- **Phase 1: cosmetics.** Both MoCRA submissions build, each checked first against the
  guide's rules (every finding cites its rule number):
  - facility registration, chapter 35 (`facility_registration.py`): initial, amendment,
    biennial renewal, abbreviated renewal, cancellation. `examples/sample_facility_registration.xml`
  - product listing, chapter 36 (`cosmetic_spl.py`, `cosmetic_validation.py`): initial and
    update. `examples/sample_cosmetic_listing.xml`

  - ingredients from a fragrance-reg-core `FinishedProduct` (`ingredients.py`, needs the
    `[core]` extra): the US label list in label order, colorants marked as color additives,
    fragrance-reg-core errors passed through as blocking findings.

  Order in practice: register each facility first (FDA's registration number and the FEI
  come from that), then list products against those facilities.
- **Phase 2: ESG NextGen API** submission and acknowledgments.
- **Phase 3: OTC.** Priority monographs, modeled on Church & Dwight's OTC lines: M019
  antiperspirant, M021 anticaries, M006 topical acne, M020 sunscreen, M003 first aid antiseptic.
  Hand sanitizer, oral pain and anorectal still need their governing monograph identified
  (`data/otc_monographs.json`).

```python
from mocra_otc_spl_builder import *

spl = build_cosmetic_listing(CosmeticListing(
    responsible_person=ResponsiblePerson("Our Brand LLC", phone="+1-212-555-0100",
                                         business_type=BusinessType.DISTRIBUTOR),
    products=[CosmeticProduct(
        name="Moon Dust Eau de Parfum",
        categories=[Category(code, display_name)],      # from FDA's category list
        ingredients=ingredients_from_product(finished_product).ingredients,  # or [Ingredient("..."), ...]
        facilities=[Facility(fei="1234567")],
    )],
    signer=Signer("Full Name", signature="F. Name"),
))
open(spl.filename, "w").write(spl.xml)   # file name is the document id (IG 2.1.2.6)
```

An invalid listing or registration raises `SplNotValid` with every finding; nothing is built
from a guess. Registration works the same way with `build_facility_registration(FacilityRegistration(...))`.

## Open questions (resolve before the first real submission)

1. **Category code system.** The guide's validation rule 3.4.3.2 says
   `2.16.840.1.113883.6.303`, but its chapter 35 and 36 examples use `2.16.840.1.113883.6.345`.
   We use the rule's value (`codes.COSMETIC_CATEGORY_SYSTEM`). Confirm with FDA's terminology
   files or spl@fda.hhs.gov.
2. **Category list.** Not in the guide; needs FDA's SPL terminology file.
3. **Schema check.** Element order follows the guide's examples but has not been validated
   against `spl.xsd` (fda.gov is blocked from the build environment).
4. **First listing, product code.** For a product with no listing number yet we omit the
   product `<code>`; the facility link uses an empty `<code/>` as the guide says the schema
   requires. Confirm the product element is accepted without it.
5. **Abbreviated renewal / cancellation header.** The guide says these carry no facility
   details and identify the registration by set id; we send an empty author organization.
   Confirm FDA accepts that.
6. **US agent without email.** The guide says to give "N/A"; we send it as `mailto:N/A`.

## Tests

```bash
pip install -e ".[dev,core]"   # without core, the ingredient tests are skipped
pytest
```
