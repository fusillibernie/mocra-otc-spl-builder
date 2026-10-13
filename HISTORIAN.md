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
