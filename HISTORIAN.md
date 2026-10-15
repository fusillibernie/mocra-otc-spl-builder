# HISTORIAN

## 2026-10-13: Started

**What:** Skeleton: data models, monograph table (empty, unverified) and the plan in README.

**Why:** register our own brands' cosmetics (MoCRA) and OTC drugs with FDA without
hand-entering into Cosmetics Direct / CDER Direct each cycle. Both portals only author SPL;
FDA also accepts SPL over ESG NextGen, which has an API for submit/status/acknowledgments.

**Decisions:**
- Generate SPL ourselves; no browser automation of FDA portals.
- A person signs off every submission. Agents prepare and explain, never submit.
- OTC monographs: only the ones our products use, as data with `verified: false` until
  checked against the monograph order. Not a full monograph engine.

## 2026-10-13: Priorities

Cosmetics first. OTC monograph table seeded with five IDs/titles confirmed from FDA order titles,
prioritized by Church & Dwight's OTC lines (reference only). No limits entered; every entry stays
`verified: false` and blocks a listing until the order is read and its section cited.

## 2026-10-13: Cosmetic product listing SPL

**What:** `cosmetic_spl.build_cosmetic_listing` (initial 103572-4 and update X8888-5) and
`cosmetic_validation.validate_cosmetic_listing`. All code values in `codes.py`, each citing the
FDA SPL Implementation Guide (Dec 2023, `sources/spl_ig_vp_dec_2023.pdf`). 31 tests in all.

**Decisions:**
- Validate first and refuse to build on any finding. Every finding cites its IG rule.
- One facility entry per FEI, with one performance/product link per product (IG 36.1.5.5, 36.1.6).
- Products link by listing number once assigned, by name before (IG 36.1.6.3).
- No category list or schema yet. The guide contradicts itself on the category code system;
  we follow the validation rule (6.303) over the examples (6.345). README lists the open questions.
- Test fixtures use a PLACEHOLDER category; the guide's example 01B is baby lotions.

## 2026-10-13: Cosmetic facility registration SPL

**What:** `facility_registration.py` validates and builds all five IG chapter 35 document types.
Shared XML pieces moved to `spl_xml.py`; `ListingNotValid` is now an alias of `SplNotValid`.
43 tests.

**Decisions:**
- One facility per document (IG 35.1.4.1). A US agent is required outside the US and refused
  inside it (IG 35.1.5.1, 35.1.5.3).
- Renewals need `last_submitted` so the 2-year rule (IG 35.1.1.6) can be checked locally.
- The leave-on/rinse-off category rule is not applied to registrations; the guide exempts them.

## 2026-10-13: Ingredients from fragrance-reg-core

**What:** `ingredients.ingredients_from_product(FinishedProduct)` returns the US label ingredient
list for a listing. fragrance-reg-core v0.5.3 is an optional `[core]` extra. 48 tests.

**Decisions:**
- Use fragrance-reg-core's US list as is. The listing must match the printed label
  (IG 36.2.2.12), so nothing is re-sorted here.
- Its ERROR findings (e.g. no INCI name) block; WARNINGs are passed on for a person to read.
- Components with role COLORANT become color additives (COLR, IG 3.4.4.1). fragrance-reg-core
  orders colors by weight; when a color lands before other ingredients we warn rather than move
  it, since the label may group colors at the end.

## 2026-10-13: Real category codes; FDA guidance and ESG API guide added

**What:** `data/cosmetic_categories.json` built from Appendix A of FDA's Dec 2024 registration and
listing guidance by `scripts/build_cosmetic_categories.py` (153 entries, 119 selectable).
`category("05B")` gives a Category; listing and registration validation now reject codes not on
the list, codes that have subcategories (01D -> 01D1/01D2), and mismatched display names. 51 tests.

**Not verified:** display names (generated in the IG 3.4.3.5 style) and code "17".

**Learned from the guidance:** small businesses (<$1M average US cosmetic sales over 3 years,
outside the 612(b) product types) are exempt from both registration and listing; get the FEI
before registering (feiportal@fda.hhs.gov, 7-10 business days); an ESG account takes 1-3 weeks
and needs a business email domain (not Gmail).

## 2026-10-13: ESG NextGen API client

**What:** `esg.py`: token (cached, 1 hour), company info, test/production credentials, payload,
multipart upload, submit with SHA-256, status, acknowledgments. `package_spl` zips the XML with
its .jpg labels (one file per submission, spec 2.2). Standard library only; tests use a fake
FDA server that answers like the spec's examples. 60 tests.

**Decisions:**
- Test submission is the default. Production needs an `Approval(person, sha256)` that matches
  the exact package, so a sign-off can't be reused for a different file.
- `fda_center` / `submission_type` have no defaults; the client refuses to send without them.
- Send both `Authorization: Bearer` and `accesstoken`, because the spec contradicts itself.
- The secret never appears in `repr`.

**Not done:** no run against FDA yet (no USP account; the user has no products to register yet).

## 2026-10-13: ESG route for cosmetic SPL

FDA's Center Submission Types page (photographed; content current as of 2026-09-17) has no
cosmetics entry under HFP. It lists center OC, submission type SPL, AS2 routing ID
OC_REGLIST_SPL (test and production, 100 GB, no test required for new users). We route cosmetic
registration and listing there (`EsgConfig.for_cosmetic_spl`, and `from_env` defaults). This is
an inference to confirm with ESG support before the first production submission.

## 2026-10-13: FDA schema and stylesheet

**What:** FDA's SPL schema (SchemasR2b) and stylesheet 6.2 bundled under `data/`.
`schema_errors(xml)` validates; `tests/test_schema.py` runs 3 listing and 7 registration variants
(every optional element included) through it. `preview_html(spl)` renders with FDA's stylesheet,
CSS inlined, for the person signing off. lxml is the optional `[schema]` extra. 74 tests.

**The schema found two real bugs the guide didn't show:**
- `contactParty` must contain `contactPerson` (IG 2.1.8.3 calls the name optional for
  cosmetics). Facility and authorized-agent contacts now require a person's name.
- The parent company (`assignedEntity1`) goes after `addr` and before `contactParty`; we had it
  after the US agent.

The stylesheet only renders product classification codes under 2.16.840.1.113883.6.303 (in its
device/pesticide templates), mild support for our category code system choice; still to confirm.

## 2026-10-14: State reporting (CSCP and VOC) lives here, not in fragrance-reg-core

The user chose this repo: these are cosmetics and OTC filings. "CPSC allergens" meant California's
CSCP (SB 312); no CPSC allergen report was found. VOC means all of CARB's personal fragrance survey, any
general consumer-products survey, and aerosols including OTC antiperspirants.

**Built:** `cscp.cscp_report` (allergens at or above 0.001% leave-on / 0.01% rinse-off via
fragrance-reg-core, CSV data pack, blocking findings vs warnings), `data/cscp_rules.json` (unverified),
`data/cscp_reportable_ingredients.json` (empty, awaiting importer). 86 tests.

**Decisions:** output is a data pack, not a submission (CSCP is a portal, CARB's survey a downloadable
tool). "At or above", not core's "exceeds". A report is never complete while the Reportable Ingredients
List is unloaded. Calls core's private `_allergen_contributions` for now; ask core to expose it.

**Not built:** VOC (needs CARB's regulation text and reporting tool), the CDPH list importer,
deadlines. cdph.ca.gov and arb.ca.gov are blocked from here like fda.gov; all rules above are from
search summaries and marked unverified. Plan: `docs/STATE_REPORTING.md`.

## 2026-10-15: Pulling official sources and keeping them current

**Why not pull CARB from the dev session:** the sandbox's network policy rejects every government
host (arb.ca.gov, cdph.ca.gov, fda.gov, ecfr.gov, federalregister.gov, govinfo, law.cornell.edu, EPA,
even web.archive.org); only GitHub and PyPI are reachable. So GitHub Actions does the fetching and
git carries the files back.

**Built:** `scripts/refresh_sources.py` (file and link-crawl fetcher with content checks, sha256 state in
`sources/fetched.json`, `{today}` URLs, importer hooks), `sources/manifest.json` (19 entries),
`sources/watchlist.json` (17 pages and APIs), `scripts/watch_sources.py` (copied from core), three
workflows (CI, weekly watch, monthly refresh). 110 tests, using a fake site.

**Decisions:** nothing auto-merges; a failed or blocked fetch is reported, not worked around; large
reference sets (UNII, NDC) are not committed monthly; unconfirmed URLs are flagged `confirmed: false`.

**Unproven until the first run:** every URL, CARB/CDPH/FDA tolerance of automated requests, and the
refresh workflow's push permissions.

## 2026-10-15: First refresh run on GitHub's runners

PR #1 merged; the run was started by hand (the dev session's token can't dispatch workflows: 403).
**Worked:** FDA, entirely. Its files are byte-identical to what we already had, which settles that the Dec 2023
Implementation Guide is still FDA's current revision (as of 2026-10-15), and that our schema, stylesheet and ESG
guides are current. **Failed:** CARB (no links / empty PDF), CDPH (missing intermediate certificate), eCFR (406),
the five OTC orders (404). The PR step failed on the repo setting; the branch carried the files.

**Fixes (this branch):** failures now report server, status and the start of the page; a missing intermediate
certificate is fetched from the certificate's AIA URL while verification stays on against certifi's roots; dated
eCFR URLs step back up to 7 days; files already stored under another name aren't saved again (the SPL guide had
been saved three times). 121 tests.

**Found in FDA's terminology lists:** no cosmetic filing document types and no "distribute" operation code, so the
public lists lag the guide; the `X8888-n` codes for updates and renewals look provisional (README open question 10).
