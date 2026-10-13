"""Writes examples/sample_cosmetic_listing.xml from the test fixtures (fake company and FEI)."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.cosmetic_fixtures import SMALL_STUDIO, edp, listing  # noqa: E402

from mocra_otc_spl_builder import build_cosmetic_listing  # noqa: E402

products = [edp(label_images=["moon-dust-front.jpg"]), edp(name="Dusk Eau de Parfum", facilities=[SMALL_STUDIO])]
spl = build_cosmetic_listing(listing(products=products), today=date(2026, 10, 13))
out = Path(__file__).with_name("sample_cosmetic_listing.xml")
out.write_text(spl.xml)
print(out)
