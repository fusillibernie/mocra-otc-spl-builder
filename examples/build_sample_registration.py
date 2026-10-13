"""Writes examples/sample_facility_registration.xml from the test fixtures (fake facility and FEI)."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.test_facility_registration import GRASSE_PLANT, reg  # noqa: E402

from mocra_otc_spl_builder import build_facility_registration  # noqa: E402

spl = build_facility_registration(reg(facility=GRASSE_PLANT), today=date(2026, 10, 13))
out = Path(__file__).with_name("sample_facility_registration.xml")
out.write_text(spl.xml)
print(out)
