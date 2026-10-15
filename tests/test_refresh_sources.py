import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "refresh_sources.py"
spec = importlib.util.spec_from_file_location("refresh_sources", SCRIPT)
rs = importlib.util.module_from_spec(spec)
sys.modules["refresh_sources"] = rs  # dataclasses look the module up by name
spec.loader.exec_module(rs)

PDF = b"%PDF-1.7 regulation text"
XLSX = b"PK\x03\x04 spreadsheet"
BLOCK_PAGE = b"<!DOCTYPE html><html><body>Access denied</body></html>"


class FakeSite:
    """URL -> (headers, body); anything else is a 404."""

    def __init__(self, pages):
        self.pages = pages
        self.requested = []

    def __call__(self, url):
        self.requested.append(url)
        if url not in self.pages:
            raise rs.FetchError("HTTP 404")
        headers, body = self.pages[url]
        return url, {k.lower(): v for k, v in headers.items()}, body


def run(manifest, site, root, day="2026-10-15", **kw):
    return rs.refresh(manifest, root=root, opener=site, today=date.fromisoformat(day), sleep=lambda s: None, **kw)


def entry(**kw):
    return {"id": "e", "name": "Example", "affects": ["data/x.json"], **kw}


def test_new_then_unchanged_then_changed(tmp_path):
    manifest = {"entries": [entry(kind="file", url="https://x.test/a.pdf", save_as="a.pdf", save_dir="carb")]}
    site = FakeSite({"https://x.test/a.pdf": ({}, PDF)})
    r1 = run(manifest, site, tmp_path)
    assert [(f.path, f.status) for f in r1.files] == [("carb/a.pdf", "new")] and r1.exit_code == 1
    assert (tmp_path / "sources/carb/a.pdf").read_bytes() == PDF

    r2 = run(manifest, site, tmp_path, day="2026-11-15")
    assert [f.status for f in r2.files] == ["same"] and r2.exit_code == 0

    site.pages["https://x.test/a.pdf"] = ({}, PDF + b" amended")
    r3 = run(manifest, site, tmp_path, day="2027-01-15")
    assert [f.status for f in r3.files] == ["changed"] and r3.exit_code == 1
    state = json.loads((tmp_path / "sources/fetched.json").read_text())["carb/a.pdf"]
    assert state["first_seen"] == "2026-10-15" and state["changed"] == "2027-01-15" and state["checked"] == "2027-01-15"
    assert (tmp_path / "sources/carb/a.pdf").read_bytes().endswith(b"amended")


def test_a_block_page_is_never_saved_as_the_file(tmp_path):
    manifest = {"entries": [entry(kind="file", url="https://x.test/a.pdf", save_as="a.pdf")]}
    r = run(manifest, FakeSite({"https://x.test/a.pdf": ({"Content-Type": "text/html"}, BLOCK_PAGE)}), tmp_path)
    assert r.files == [] and r.exit_code == 2 and "not a PDF" in r.failures[0].error
    assert not (tmp_path / "sources/a.pdf").exists()


@pytest.mark.parametrize("name, body, ok", [
    ("a.pdf", PDF, True), ("a.pdf", b"<html>", False), ("a.zip", XLSX, True), ("a.xlsx", b"%PDF", False),
    ("a.csv", b"cas,name\n1-1-1,x\n", True), ("a.csv", BLOCK_PAGE, False), ("a.json", b'{"a": 1}', True),
    ("a.json", b"<html>", False), ("a.xml", b"<?xml version='1.0'?><a/>", True), ("a.pdf", b"", False),
])
def test_content_checks(name, body, ok):
    if ok:
        rs.check_content(name, body, {})
    else:
        with pytest.raises(rs.FetchError):
            rs.check_content(name, body, {})


def test_today_placeholder_for_dated_urls(tmp_path):
    manifest = {"entries": [entry(kind="file", url="https://ecfr.test/full/{today}/title-40.xml?part=59", save_as="cfr40-59.xml")]}
    site = FakeSite({"https://ecfr.test/full/2026-10-15/title-40.xml?part=59": ({}, b"<?xml version='1.0'?><DIV/>")})
    assert run(manifest, site, tmp_path).files[0].status == "new"


INDEX = """<html><body>
<a href="/files/2026/reg-order.pdf">Final Regulation Order</a>
<a href="reporting-tool.xlsx">PFP Reporting Tool</a>
<a href="/media/123/download">Instructions for the tool</a>
<a href="/about">About us</a>
<a href="/files/slides.pdf">Board slides</a>
<a href="#top">Top</a>
<a href="mailto:x@y.test">Contact</a>
<a href="/files/2026/reg-order.pdf">Final Regulation Order (again)</a>
</body></html>"""


def links_manifest(**kw):
    return {"entries": [entry(kind="links", index_url="https://arb.test/pfp/", link_text="regulation|tool|instructions",
                              link_url=r"/media/\d+/download", extensions=[".pdf", ".xlsx"], save_dir="carb", **kw)]}


def links_site(extra=None):
    pages = {
        "https://arb.test/pfp/": ({}, INDEX.encode()),
        "https://arb.test/files/2026/reg-order.pdf": ({}, PDF),
        "https://arb.test/pfp/reporting-tool.xlsx": ({}, XLSX),
        "https://arb.test/media/123/download": ({"Content-Disposition": 'attachment; filename="PFP-RT Instructions.pdf"'}, PDF + b" instr"),
        "https://arb.test/files/slides.pdf": ({}, PDF + b" slides"),
    }
    pages.update(extra or {})
    return FakeSite(pages)


def test_links_are_discovered_filtered_and_named(tmp_path):
    site = links_site()
    r = run(links_manifest(), site, tmp_path)
    assert sorted(f.path for f in r.files) == [
        "carb/PFP-RT Instructions.pdf", "carb/reg-order.pdf", "carb/reporting-tool.xlsx"]
    assert "https://arb.test/files/slides.pdf" not in site.requested         # link text didn't match
    assert site.requested.count("https://arb.test/files/2026/reg-order.pdf") == 1   # de-duplicated


def test_a_new_version_appearing_on_the_index_is_picked_up_as_a_new_file(tmp_path):
    run(links_manifest(), links_site(), tmp_path)
    newer = INDEX.replace("</body>", '<a href="/files/2031/reg-order-2031.pdf">Final Regulation Order 2031 amendments</a></body>')
    site = links_site({"https://arb.test/pfp/": ({}, newer.encode()), "https://arb.test/files/2031/reg-order-2031.pdf": ({}, PDF + b" 2031")})
    r = run(links_manifest(), site, tmp_path, day="2031-01-05")
    assert [(f.path, f.status) for f in r.changed] == [("carb/reg-order-2031.pdf", "new")]
    assert (tmp_path / "sources/carb/reg-order.pdf").exists()                 # the old version stays


def test_max_files_and_empty_discovery(tmp_path):
    r = run(links_manifest(max_files=1), links_site(), tmp_path)
    assert len(r.files) == 1
    manifest = {"entries": [entry(kind="links", index_url="https://arb.test/pfp/", link_text="nothing like this", save_dir="x")]}
    r = run(manifest, links_site(), tmp_path / "other")
    assert r.exit_code == 2 and "no matching links" in r.failures[0].error


def test_one_failed_file_does_not_stop_the_rest(tmp_path):
    site = links_site()
    del site.pages["https://arb.test/pfp/reporting-tool.xlsx"]
    r = run(links_manifest(), site, tmp_path)
    assert len(r.files) == 2 and len(r.failures) == 1 and r.exit_code == 1       # changed wins over failed
    assert r.failures[0].what.endswith("reporting-tool.xlsx")


def test_unconfirmed_urls_are_called_out_in_the_report(tmp_path):
    manifest = {"entries": [entry(kind="file", url="https://x.test/guess.zip", save_as="g.zip", confirmed=False)]}
    r = run(manifest, FakeSite({}), tmp_path)
    text = rs.report(r, "now")
    assert "never confirmed" in text and "HTTP 404" in text and r.exit_code == 2


def test_only_limits_the_entries(tmp_path):
    manifest = {"entries": [
        entry(id="a", kind="file", url="https://x.test/a.pdf", save_as="a.pdf"),
        entry(id="b", kind="file", url="https://x.test/b.pdf", save_as="b.pdf"),
    ]}
    site = FakeSite({"https://x.test/a.pdf": ({}, PDF), "https://x.test/b.pdf": ({}, PDF + b"b")})
    assert [f.entry_id for f in run(manifest, site, tmp_path, only={"b"}).files] == ["b"]


def test_importers_run_only_for_changed_entries_and_only_if_written(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/build_x.py").write_text("open('built.txt', 'w').write('ok')\nprint('built')\n")
    manifest = {"entries": [entry(kind="file", url="https://x.test/a.pdf", save_as="a.pdf",
                                  build=["scripts/build_x.py", "scripts/build_missing.py"])]}
    site = FakeSite({"https://x.test/a.pdf": ({}, PDF)})
    r = run(manifest, site, tmp_path, build=True)
    assert [(s, ok) for s, ok, _ in r.builds] == [("scripts/build_x.py", True), ("scripts/build_missing.py", False)]
    assert (tmp_path / "built.txt").read_text() == "ok"
    (tmp_path / "built.txt").unlink()
    assert run(manifest, site, tmp_path, build=True).builds == []                   # nothing changed: nothing rebuilt
    assert not (tmp_path / "built.txt").exists()


def test_report_lists_what_to_recheck(tmp_path):
    manifest = {"entries": [entry(kind="file", url="https://x.test/a.pdf", save_as="a.pdf", note="Re-read section 94509.")]}
    text = rs.report(run(manifest, FakeSite({"https://x.test/a.pdf": ({}, PDF)}), tmp_path), "now")
    assert "`sources/a.pdf` (new)" in text and "`data/x.json`" in text and "Re-read section 94509." in text


def test_packaged_manifest_is_well_formed():
    manifest = json.loads((SCRIPT.parent.parent / "sources" / "manifest.json").read_text())
    ids = [e["id"] for e in manifest["entries"]]
    assert len(ids) == len(set(ids)) and ids
    for e in manifest["entries"]:
        assert e["kind"] in ("file", "links") and e["name"] and e["affects"]
        assert e["url" if e["kind"] == "file" else "index_url"].startswith("https://")
        if e["kind"] == "file":
            assert e["save_as"]
        for script in e.get("build", []):
            assert script.startswith("scripts/build_")


def test_packaged_watchlist_is_well_formed():
    root = SCRIPT.parent.parent
    watchlist = json.loads((root / "sources" / "watchlist.json").read_text())["sources"]
    ids = [s["id"] for s in watchlist]
    assert len(ids) == len(set(ids)) and ids
    for s in watchlist:
        assert s["name"] and s["affects"] and s["url"].startswith("https://")
        if s.get("method") == "json":
            assert s["list_key"] and s["keep"]
    # every page the manifest crawls is also watched weekly for announcements
    watched = {s["url"] for s in watchlist}
    assert "https://ww2.arb.ca.gov/our-work/programs/consumer-products-program" in watched
    assert "https://www.cdph.ca.gov/Programs/CCDPHP/DEODC/OHB/CSCP/Pages/SB312.aspx" in watched


def test_watch_script_loads_and_reduces_a_page():
    spec = importlib.util.spec_from_file_location("watch_sources", SCRIPT.parent / "watch_sources.py")
    watch = importlib.util.module_from_spec(spec)
    sys.modules["watch_sources"] = watch
    spec.loader.exec_module(watch)
    text = watch.page_text("<html><nav>skip</nav><p>Reporting is due 1 March.</p><p>Last updated 3:45 pm</p></html>")
    assert text == "Reporting is due 1 March."
