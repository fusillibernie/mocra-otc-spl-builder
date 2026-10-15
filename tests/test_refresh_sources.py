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


# --- failures explain themselves ---------------------------------------------------------------

def test_snippet_and_http_error_description():
    page = b"<html><head><style>x{}</style></head><body><h1>Access Denied</h1><script>var a=1;</script><p>Reference #18.4</p></body></html>"
    assert rs.snippet(page) == "Access Denied Reference #18.4"
    text = rs.describe_http_error(403, {"server": "AkamaiGHost"}, page)
    assert text == "HTTP 403 (server: AkamaiGHost): 'Access Denied Reference #18.4'"
    assert rs.describe_http_error(404, {}, b"") == "HTTP 404"


def test_empty_response_says_what_the_server_sent(tmp_path):
    manifest = {"entries": [entry(kind="file", url="https://x.test/a.pdf", save_as="a.pdf")]}
    r = run(manifest, FakeSite({"https://x.test/a.pdf": ({"Server": "nginx", "Content-Length": "0"}, b"")}), tmp_path)
    assert "empty response (server=nginx, content-length=0)" in r.failures[0].error


def test_no_matching_links_reports_what_the_page_contained(tmp_path):
    manifest = {"entries": [entry(kind="links", index_url="https://arb.test/p/", link_text="regulation")]}
    page = b"<html><body><p>Checking your browser before accessing the site.</p><a href='/x'>x</a></body></html>"
    r = run(manifest, FakeSite({"https://arb.test/p/": ({}, page)}), tmp_path)
    error = r.failures[0].error
    assert "1 links" in error and "Checking your browser" in error


# --- dated URLs ----------------------------------------------------------------------------------

def test_dated_url_steps_back_until_the_data_exists(tmp_path):
    manifest = {"entries": [entry(kind="file", url="https://ecfr.test/{today}/t.xml", save_as="t.xml", date_back_days=7)]}
    site = FakeSite({"https://ecfr.test/2026-10-12/t.xml": ({}, b"<?xml version='1.0'?><a/>")})
    r = run(manifest, site, tmp_path, day="2026-10-15")
    assert r.files[0].url == "https://ecfr.test/2026-10-12/t.xml" and r.exit_code == 1
    assert site.requested == ["https://ecfr.test/2026-10-15/t.xml", "https://ecfr.test/2026-10-14/t.xml",
                              "https://ecfr.test/2026-10-13/t.xml", "https://ecfr.test/2026-10-12/t.xml"]


def test_dated_url_gives_up_after_the_window_and_plain_urls_do_not_retry(tmp_path):
    dated = {"entries": [entry(kind="file", url="https://ecfr.test/{today}/t.xml", save_as="t.xml", date_back_days=2)]}
    site = FakeSite({})
    assert run(dated, site, tmp_path).exit_code == 2 and len(site.requested) == 3
    plain = {"entries": [entry(kind="file", url="https://x.test/a.pdf", save_as="a.pdf", date_back_days=5)]}
    site = FakeSite({})
    run(plain, site, tmp_path / "p")
    assert site.requested == ["https://x.test/a.pdf"]


# --- files already in the repo are not saved again --------------------------------------------

def test_a_file_already_stored_under_another_name_is_not_saved_again(tmp_path):
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources/spl_ig_dec_2023.pdf").write_bytes(PDF)
    manifest = {"entries": [entry(kind="file", url="https://x.test/ig.pdf", save_as="ig_current.pdf", save_dir="fda")]}
    site = FakeSite({"https://x.test/ig.pdf": ({}, PDF)})
    r = run(manifest, site, tmp_path)
    assert [f.status for f in r.files] == ["duplicate"] and r.exit_code == 0
    assert not (tmp_path / "sources/fda/ig_current.pdf").exists()
    state = json.loads((tmp_path / "sources/fetched.json").read_text())["fda/ig_current.pdf"]
    assert state["duplicate_of"] == "spl_ig_dec_2023.pdf"
    assert [f.status for f in run(manifest, site, tmp_path, day="2026-11-15").files] == ["same"]

    site.pages["https://x.test/ig.pdf"] = ({}, PDF + b" revised")           # a real revision is saved
    r = run(manifest, site, tmp_path, day="2027-02-01")
    assert [f.status for f in r.files] == ["changed"] and (tmp_path / "sources/fda/ig_current.pdf").exists()
    assert "duplicate_of" not in json.loads((tmp_path / "sources/fetched.json").read_text())["fda/ig_current.pdf"]


def test_duplicates_within_one_run_are_caught(tmp_path):
    manifest = {"entries": [
        entry(id="a", kind="file", url="https://x.test/a.pdf", save_as="a.pdf"),
        entry(id="b", kind="file", url="https://x.test/b.pdf", save_as="b.pdf"),
    ]}
    site = FakeSite({"https://x.test/a.pdf": ({}, PDF), "https://x.test/b.pdf": ({}, PDF)})
    first = run(manifest, site, tmp_path)
    assert [f.status for f in first.files] == ["new", "duplicate"]
    assert "1 already stored under another name" in rs.report(first, "now")
    assert [f.status for f in run(manifest, site, tmp_path, day="2026-11-01").files] == ["same", "same"]


# --- certificates a server forgot to send ----------------------------------------------------

LEAF_TEXT = """Certificate:
    X509v3 extensions:
        Authority Information Access:
            CA Issuers - URI:http://cacerts.example.test/issuing-ca.crt
            OCSP - URI:http://ocsp.example.test
"""


def test_aia_uri_is_read_from_openssl_output():
    assert rs.aia_issuer_uri(LEAF_TEXT) == "http://cacerts.example.test/issuing-ca.crt"
    assert rs.aia_issuer_uri("Certificate:\n    X509v3 extensions:\n") is None


class FakeOpenssl:
    def __init__(self):
        self.calls = []

    def __call__(self, cmd, input=None, capture_output=True, text=False, timeout=None):
        self.calls.append(cmd[:3])
        class Out:
            returncode = 0
        out = Out()
        if cmd[1] == "s_client":
            out.stdout = "noise\n-----BEGIN CERTIFICATE-----\nLEAF\n-----END CERTIFICATE-----\n"
        elif cmd[1] == "x509" and "-text" in cmd:
            out.stdout = LEAF_TEXT if "LEAF" in input else "Certificate:\n"      # the intermediate has no further issuer URL
        elif cmd[1] == "x509":                                                     # DER -> PEM
            out.stdout = b"-----BEGIN CERTIFICATE-----\nINTERMEDIATE\n-----END CERTIFICATE-----\n"
        return out


def test_missing_intermediates_are_fetched_from_the_issuer_url():
    fetched = []
    pems = rs.chase_intermediates("www.cdph.test", run=FakeOpenssl(), fetch=lambda url: fetched.append(url) or b"\x30\x82der")
    assert fetched == ["http://cacerts.example.test/issuing-ca.crt"]
    assert len(pems) == 1 and "INTERMEDIATE" in pems[0]


def test_no_certificate_sent_means_nothing_to_chase():
    class Silent(FakeOpenssl):
        def __call__(self, cmd, **kw):
            out = super().__call__(cmd, **kw)
            if cmd[1] == "s_client":
                out.stdout = ""
            return out
    assert rs.chase_intermediates("down.test", run=Silent(), fetch=lambda url: b"") == []


def test_only_a_missing_issuer_triggers_the_chase():
    import ssl

    missing = ssl.SSLCertVerificationError(1, "certificate verify failed: unable to get local issuer certificate")
    expired = ssl.SSLCertVerificationError(1, "certificate verify failed: certificate has expired")
    assert rs._missing_issuer(missing) and not rs._missing_issuer(expired)
    assert not rs._missing_issuer(ValueError("x"))


def test_a_failed_certificate_chase_is_one_failed_fetch_not_a_crash(monkeypatch):
    import ssl
    import urllib.error

    error = urllib.error.URLError(ssl.SSLCertVerificationError(1, "certificate verify failed: unable to get local issuer certificate"))

    def always_fails(url, context):
        raise error

    monkeypatch.setattr(rs, "_open", always_fails)
    for chase in (lambda host: (_ for _ in ()).throw(FileNotFoundError("openssl")), lambda host: []):
        monkeypatch.setattr(rs, "chase_intermediates", chase)
        with pytest.raises(rs.FetchError, match="unable to get local issuer certificate"):
            rs.urllib_opener("https://www.cdph.test/page")


def test_a_non_certificate_error_is_not_chased(monkeypatch):
    import ssl
    import urllib.error

    expired = urllib.error.URLError(ssl.SSLCertVerificationError(1, "certificate verify failed: certificate has expired"))
    monkeypatch.setattr(rs, "_open", lambda url, context: (_ for _ in ()).throw(expired))
    monkeypatch.setattr(rs, "chase_intermediates", lambda host: pytest.fail("must not chase an expired certificate"))
    with pytest.raises(rs.FetchError, match="expired"):
        rs.urllib_opener("https://www.cdph.test/page")


def test_an_unexpected_error_fails_that_file_only(tmp_path):
    class Flaky(FakeSite):
        def __call__(self, url):
            if url.endswith("reporting-tool.xlsx"):
                raise ConnectionResetError("connection reset by peer")
            return super().__call__(url)

    site = Flaky(links_site().pages)
    r = run(links_manifest(), site, tmp_path)
    assert len(r.files) == 2 and "unexpected ConnectionResetError" in r.failures[0].error

    manifest = {"entries": [entry(id="a", kind="file", url="https://x.test/a.pdf", save_as="a.pdf"),
                            entry(id="b", kind="file", url="https://x.test/b.pdf", save_as="b.pdf")]}
    site = Flaky({"https://x.test/b.pdf": ({}, PDF)})
    site.pages["https://x.test/a.pdf"] = ({}, PDF)
    broken = lambda url: (_ for _ in ()).throw(UnicodeError("bad")) if url.endswith("a.pdf") else site(url)
    r = run(manifest, broken, tmp_path / "x")
    assert [f.entry_id for f in r.files] == ["b"] and r.failures[0].entry_id == "a"
