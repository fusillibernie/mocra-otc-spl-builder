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
