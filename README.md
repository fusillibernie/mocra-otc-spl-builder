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
- **Phase 2: ESG NextGen API** (`esg.py`, built from the API Specification v1.2 and API
  Guide v1.2.1). Packages the SPL and its label images into one zip, gets a token and
  temporary credentials, uploads, submits with the SHA-256, then reads status and ACKs.
  Test submissions by default; production needs an `Approval` naming the person and the exact
  file's SHA-256. Not yet run against FDA: needs a USP account and API keys (see below).
- **Phase 4: state reporting** (`docs/STATE_REPORTING.md`). California Safe Cosmetics Program
  fragrance allergens: built (`cscp.py`, rules unverified, CDPH's ingredient list not loaded yet).
  CARB VOC reporting for personal fragrance and aerosols (including OTC antiperspirants): planned,
  waiting on CARB's regulation text and reporting tool. Both produce data packs for a person to
  enter, not submissions.
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
        categories=[category("05B")],                   # Perfumes, FDA guidance Appendix A
        ingredients=ingredients_from_product(finished_product).ingredients,  # or [Ingredient("..."), ...]
        facilities=[Facility(fei="1234567")],
    )],
    signer=Signer("Full Name", signature="F. Name"),
))
open(spl.filename, "w").write(spl.xml)   # file name is the document id (IG 2.1.2.6)
```

An invalid listing or registration raises `SplNotValid` with every finding; nothing is built
from a guess. Then, with the `[schema]` extra:

```python
assert schema_errors(spl.xml) == []                     # FDA's SPL schema
open("review.html", "w").write(preview_html(spl))       # what FDA will display, for the sign-off
``` Registration works the same way with `build_facility_registration(FacilityRegistration(...))`.

## Sending to FDA

```python
from mocra_otc_spl_builder.esg import Approval, EsgClient, EsgConfig, package_spl

pkg = package_spl(spl, image_dir="labels/")
client = EsgClient(EsgConfig.from_env())        # ESG_CLIENT_ID, ESG_CLIENT_SECRET, ESG_USER_EMAIL
                                                # (routed to center OC, type SPL by default)
receipt = client.submit(pkg, "Initial listing")  # test submission
# production, after a person has reviewed this exact file:
receipt = client.submit(pkg, "Initial listing", test=False,
                        approval=Approval("Full Name", pkg.sha256))
client.acknowledgements(receipt.core_id)         # ACK1 received, ACK2 at center, ACK3 center's answer
```

Before the first real use: a USP account on a business email (Gmail is refused), a
non-repudiation letter, FDA's approval (1-3 weeks), then API keys from USP "API Management"
(Power User only). Some center/submission types make new users send a test submission first.

## Open questions (resolve before the first real submission)

1. **Category code system.** The guide's validation rule 3.4.3.2 says
   `2.16.840.1.113883.6.303`, but its chapter 35 and 36 examples use `2.16.840.1.113883.6.345`.
   We use the rule's value (`codes.COSMETIC_CATEGORY_SYSTEM`). Confirm with FDA's terminology
   files or spl@fda.hhs.gov.
2. **Category display names.** Codes come from the FDA guidance's Appendix A
   (`data/cosmetic_categories.json`, 119 selectable). The display names are generated in the
   style of IG 3.4.3.5 ("Other baby products, leave-on [Baby products]") because the guide
   shows three different styles; confirm against FDA's terminology file. Group 17 ("Other
   preparations") uses code "17", also unconfirmed.
3. ~~**Schema check.**~~ Done: FDA's SPL schema (SchemasR2b) is bundled and every document
   variant is tested against it (`schema.py`, `tests/test_schema.py`). It found two things
   the guide didn't say: a contact party needs a contact person, and the parent company goes
   before the contact party.
4. **First listing, product code.** For a product with no listing number yet we omit the
   product `<code>`. The schema accepts that; confirm FDA's validator does too.
5. **Abbreviated renewal / cancellation header.** The guide says these carry no facility
   details and identify the registration by set id; we send an empty author organization.
   The schema accepts it; confirm FDA's validator does too.
6. **US agent without email.** The guide says to give "N/A"; we send it as `mailto:N/A`.
7. **ESG routing.** FDA's Center Submission Types page (2026-09-17, photos in `sources/`)
   lists center `OC`, type `SPL`, AS2 routing ID `OC_REGLIST_SPL`. It doesn't say
   "cosmetics"; we infer it from "REGLIST" and from OC issuing the SPL guide. HFP lists no
   SPL type. Confirm with ESGNGSupport@fda.hhs.gov.
8. **ESG package format.** We send one zip (XML plus .jpg labels). Confirm OC/SPL accepts a
   zip (size limit is 100 GB).
9. **ESG header.** The spec's text says `Authorization: Bearer`, its curl examples use
   `accesstoken`; we send both.

## Tests

```bash
pip install -e ".[dev,core]"   # without core or lxml, those tests are skipped
pytest
```
