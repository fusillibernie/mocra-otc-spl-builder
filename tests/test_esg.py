import io
import json
import zipfile
from datetime import date

import pytest

from mocra_otc_spl_builder import build_cosmetic_listing
from mocra_otc_spl_builder.esg import Approval, EsgClient, EsgConfig, EsgError, Package, package_spl

from .cosmetic_fixtures import edp, listing

CORE_ID = "ci261013120000.0123456789abcdef0123456789abcdef"
PAYLOAD = "6f10c466-b10a-43be-84d2-fc27cc661a28"


class FakeFda:
    """Answers like the spec's examples and records every call."""

    def __init__(self):
        self.calls = []
        self.fail = {}

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, headers, body))
        for key, (status, payload) in self.fail.items():
            if key in url:
                return status, json.dumps(payload).encode()
        if "/as/token.oauth2" in url:
            return 200, b'{"access_token": "tok-1", "token_type": "Bearer", "expires_in": 3600}'
        if "/companies" in url:
            return 200, json.dumps({"user_id": 4909, "company_id": 5842, "company_status": "Approved", "esgngcode": "ESGNG390"}).encode()
        if "/credentials/api" in url:
            return 200, json.dumps({"core_id": CORE_ID, "temp_user": f"4909-{CORE_ID}", "temp_password": "temp-pw", "esgngcode": "ESGNG210"}).encode()
        if url.endswith("/fileupload/payload"):
            return 200, json.dumps({"data": {"payloadId": PAYLOAD}}).encode()
        if url.endswith("/file"):
            return 200, b'{"data": {"status": "DRAFT", "message": "Draft saved successfully."}}'
        if url.endswith("/submit"):
            return 200, b'{"data": {"message": "Successful"}}'
        if "/submissions/" in url:
            return 200, json.dumps({"core_id": CORE_ID, "status": "Submitted to Center", "esgngcode": "ESGNG270"}).encode()
        if "/acknowledgements/" in url:
            return 200, json.dumps({"core_id": CORE_ID, "acknowledgements": [{"acknowledgement": "ACK1c", "status": "Upload Received"}]}).encode()
        return 404, b"{}"

    def urls(self):
        return [(m, u.split("?")[0]) for m, u, _, _ in self.calls]


def client(fda=None, **cfg):
    config = EsgConfig("cid", "secret", "regulatory@delbiado.com", fda_center="HFP-PLACEHOLDER", submission_type="TYPE-PLACEHOLDER", **cfg)
    return EsgClient(config, transport=fda or FakeFda())


def package():
    return package_spl(build_cosmetic_listing(listing(), today=date(2026, 10, 13)))


def test_package_is_one_zip_named_by_document_id():
    spl = build_cosmetic_listing(listing(), today=date(2026, 10, 13))
    pkg = package_spl(spl)
    assert pkg.filename == f"{spl.document_id}.zip"
    assert zipfile.ZipFile(io.BytesIO(pkg.content)).namelist() == [spl.filename]


def test_package_includes_label_images(tmp_path):
    (tmp_path / "front.jpg").write_bytes(b"\xff\xd8jpeg")
    spl = build_cosmetic_listing(listing(products=[edp(label_images=["front.jpg"])]), today=date(2026, 10, 13))
    names = zipfile.ZipFile(io.BytesIO(package_spl(spl, tmp_path).content)).namelist()
    assert names == [spl.filename, "front.jpg"]
    with pytest.raises(ValueError, match="image_dir"):
        package_spl(spl)


def test_test_submission_runs_the_spec_sequence():
    fda = FakeFda()
    pkg = package()
    receipt = client(fda).submit(pkg, "Initial listing")
    assert receipt.core_id == CORE_ID and receipt.test and receipt.sha256 == pkg.sha256
    assert fda.urls() == [
        ("POST", "https://external-api-esgng.fda.gov/as/token.oauth2"),
        ("GET", "https://external-api-esgng.fda.gov/api/esgng/v1/companies"),
        ("POST", "https://external-api-esgng.fda.gov/api/esgng/v1/credentials/api/test"),
        ("GET", "https://upload-api-esgng.fda.gov/rest/forms/v1/fileupload/payload"),
        ("POST", f"https://upload-api-esgng.fda.gov/rest/forms/v1/fileupload/payload/{PAYLOAD}/file"),
        ("POST", f"https://upload-api-esgng.fda.gov/rest/forms/v1/fileupload/payload/{PAYLOAD}/submit"),
    ]
    token_call, _, creds_call, _, upload_call, submit_call = fda.calls
    assert "grant_type=client_credentials&scope=openid%20profile" in token_call[1]
    assert token_call[3] == b"client_id=cid&client_secret=secret"
    assert creds_call[2]["Authorization"] == "Bearer tok-1" and creds_call[2]["accesstoken"] == "tok-1"
    creds_body = json.loads(creds_call[3])
    assert creds_body["file_count"] == 1 and creds_body["user_id"] == "4909" and creds_body["company_id"] == "5842"
    assert pkg.content in upload_call[3] and "multipart/form-data; boundary=" in upload_call[2]["Content-Type"]
    assert json.loads(submit_call[3]) == {"username": f"4909-{CORE_ID}", "password": "temp-pw", "sha256_checksum": pkg.sha256}
    assert "Authorization" not in submit_call[2]  # spec 2.6: no token


def test_production_needs_approval_of_this_exact_file():
    pkg = package()
    with pytest.raises(PermissionError, match="Approval"):
        client().submit(pkg, "x", test=False)
    with pytest.raises(PermissionError, match="different file"):
        client().submit(pkg, "x", test=False, approval=Approval("Pat Example", "0" * 64))
    fda = FakeFda()
    receipt = client(fda).submit(pkg, "x", test=False, approval=Approval("Pat Example", pkg.sha256))
    assert receipt.approved_by == "Pat Example" and not receipt.test
    assert any(u.endswith("/credentials/api") for _, u in fda.urls())


def test_no_routing_values_no_submission():
    c = EsgClient(EsgConfig("cid", "secret", "regulatory@delbiado.com"), transport=FakeFda())
    with pytest.raises(ValueError, match="Center Submission Types"):
        c.submit(package(), "x")


def test_token_is_reused_until_near_expiry():
    fda, now = FakeFda(), [0.0]
    c = EsgClient(client().config, transport=fda, clock=lambda: now[0])
    c.status(CORE_ID)
    c.status(CORE_ID)
    now[0] = 3550.0
    c.status(CORE_ID)
    assert sum("/as/token.oauth2" in u for _, u in fda.urls()) == 2


def test_status_and_acknowledgements():
    c = client()
    assert c.status(CORE_ID)["status"] == "Submitted to Center"
    assert c.acknowledgements(CORE_ID)[0]["acknowledgement"] == "ACK1c"


def test_errors_carry_the_esgng_code():
    fda = FakeFda()
    fda.fail["/credentials/api"] = (400, {"esgngcode": "ESGNG219", "esgngdescription": "Invalid user, company, or center submission type."})
    with pytest.raises(EsgError, match="ESGNG219") as e:
        client(fda).submit(package(), "x")
    assert e.value.status == 400 and e.value.step == "credentials"


def test_secret_never_in_repr():
    assert "'secret'" not in repr(client().config)
