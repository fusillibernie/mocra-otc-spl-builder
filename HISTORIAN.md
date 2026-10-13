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
