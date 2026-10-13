"""Client for FDA's ESG NextGen API: token, submission credentials, upload, submit, status, ACKs.

Follows the ESG NextGen API Specification v1.2 (March 2026) and API Guide v1.2.1 (August 2026),
both in sources/. Standard library only.

A production submission needs an Approval: a named person signing off on the exact file
(matched by SHA-256). Test submissions do not. Nothing here decides on its own to submit.
"""

import hashlib
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from .spl_xml import SplFile

API_BASE = "https://external-api-esgng.fda.gov"  # spec 2.1, 2.2, 2.7 to 2.9
UPLOAD_BASE = "https://upload-api-esgng.fda.gov"  # spec 2.4 to 2.6

# (method, url, headers, body) -> (status, body)
Transport = Callable[[str, str, dict, bytes | None], tuple[int, bytes]]


class EsgError(RuntimeError):
    def __init__(self, step: str, status: int, body: dict | str):
        self.step, self.status, self.body = step, status, body
        code = body.get("esgngcode", "") if isinstance(body, dict) else ""
        detail = (body.get("esgngdescription") or body.get("error") or body) if isinstance(body, dict) else body
        super().__init__(f"{step}: HTTP {status} {code} {detail}".strip())


@dataclass
class EsgConfig:
    client_id: str
    client_secret: str
    user_email: str  # the USP account's business email
    # From FDA's "Center Submission Types" page. No defaults: a wrong value routes the file wrongly.
    fda_center: str = ""
    submission_type: str = ""
    api_base: str = API_BASE
    upload_base: str = UPLOAD_BASE

    @classmethod
    def from_env(cls) -> "EsgConfig":
        """ESG_CLIENT_ID, ESG_CLIENT_SECRET, ESG_USER_EMAIL, ESG_FDA_CENTER, ESG_SUBMISSION_TYPE."""
        env = os.environ
        return cls(
            client_id=env["ESG_CLIENT_ID"],
            client_secret=env["ESG_CLIENT_SECRET"],
            user_email=env["ESG_USER_EMAIL"],
            fda_center=env.get("ESG_FDA_CENTER", ""),
            submission_type=env.get("ESG_SUBMISSION_TYPE", ""),
        )

    def __repr__(self) -> str:  # never print the secret
        return f"EsgConfig(client_id={self.client_id!r}, user_email={self.user_email!r}, fda_center={self.fda_center!r}, submission_type={self.submission_type!r})"


@dataclass(frozen=True)
class Package:
    """The single file sent to ESG (spec 2.2: file_count can only be one)."""

    filename: str
    content: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


def package_spl(spl: SplFile, image_dir: str | Path | None = None) -> Package:
    """Zip the SPL XML with its label images (IG 2.1.2.7: only the .xml and its .jpg files)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(spl.filename, spl.xml.encode("utf-8"))
        for name in spl.images:
            if image_dir is None:
                raise ValueError(f"{name} is referenced by the SPL but no image_dir was given")
            z.write(Path(image_dir) / name, arcname=name)
    return Package(f"{spl.document_id}.zip", buf.getvalue())


@dataclass(frozen=True)
class Approval:
    """A person's sign-off on one exact package. Required for production submissions."""

    approved_by: str
    package_sha256: str
    approved_at: datetime = field(default_factory=datetime.now)


@dataclass
class SubmissionReceipt:
    core_id: str
    payload_id: str
    filename: str
    sha256: str
    test: bool
    approved_by: str = ""
    submitted_at: datetime = field(default_factory=datetime.now)


def _urllib_transport(method: str, url: str, headers: dict, body: bytes | None) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class EsgClient:
    def __init__(self, config: EsgConfig, transport: Transport | None = None, clock=time.monotonic):
        self.config = config
        self._send = transport or _urllib_transport
        self._clock = clock
        self._token: str | None = None
        self._token_expires = 0.0

    # --- plumbing -----------------------------------------------------------------------

    def _call(self, step: str, method: str, url: str, headers: dict | None = None, body: bytes | None = None) -> dict:
        status, raw = self._send(method, url, headers or {}, body)
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, UnicodeDecodeError):
            data = raw.decode("utf-8", "replace")
        if status != 200 or not isinstance(data, dict):
            raise EsgError(step, status, data)
        return data

    def _auth(self) -> dict:
        # The spec's text says Authorization: Bearer; its curl examples use an accesstoken
        # header. Both are sent.
        token = self.token()
        return {"Authorization": f"Bearer {token}", "accesstoken": token, "Content-Type": "application/json"}

    # --- spec 2.1: token ----------------------------------------------------------------

    def token(self) -> str:
        """OAuth2 client-credentials token, reused until a minute before it expires (1 hour)."""
        if self._token and self._clock() < self._token_expires - 60:
            return self._token
        query = urllib.parse.urlencode({"grant_type": "client_credentials", "scope": "openid profile"}, quote_via=urllib.parse.quote)
        body = urllib.parse.urlencode({"client_id": self.config.client_id, "client_secret": self.config.client_secret}).encode()
        data = self._call("token", "POST", f"{self.config.api_base}/as/token.oauth2?{query}",
                          {"Content-Type": "application/x-www-form-urlencoded"}, body)
        self._token = data["access_token"]
        self._token_expires = self._clock() + float(data.get("expires_in", 3600))
        return self._token

    # --- spec 2.8: user and company ids -------------------------------------------------

    def company_info(self) -> dict:
        query = urllib.parse.urlencode({"user_email": self.config.user_email})
        return self._call("company_info", "GET", f"{self.config.api_base}/api/esgng/v1/companies?{query}", self._auth())

    # --- spec 2.2 / 2.3: submission id and temporary credentials ------------------------

    def request_credentials(self, name: str, description: str, test: bool, company: dict | None = None) -> dict:
        if not (self.config.fda_center and self.config.submission_type):
            raise ValueError("Set fda_center and submission_type from FDA's 'Center Submission Types' page first")
        company = company or self.company_info()
        body = {
            "user_id": str(company["user_id"]),
            "fda_center": self.config.fda_center,
            "company_id": str(company["company_id"]),
            "submission_type": self.config.submission_type,
            "submission_name": name,
            "submission_protocol": "API",
            "file_count": 1,
            "description": description,
        }
        path = "/api/esgng/v1/credentials/api" + ("/test" if test else "")
        return self._call("credentials", "POST", self.config.api_base + path, self._auth(), json.dumps(body).encode())

    # --- spec 2.4 to 2.6: payload, upload, submit ---------------------------------------

    def new_payload(self) -> dict:
        return self._call("payload", "GET", f"{self.config.upload_base}/rest/forms/v1/fileupload/payload",
                          {"Content-Type": "application/json"})["data"]

    def upload(self, payload_id: str, package: Package) -> dict:
        boundary = uuid.uuid4().hex
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{package.filename}\"\r\n"
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + package.content + f"\r\n--{boundary}--\r\n".encode()
        headers = {**self._auth(), "Content-Type": f"multipart/form-data; boundary={boundary}"}
        url = f"{self.config.upload_base}/rest/forms/v1/fileupload/payload/{payload_id}/file"
        return self._call("upload", "POST", url, headers, body)["data"]

    def submit_payload(self, payload_id: str, temp_user: str, temp_password: str, sha256: str) -> dict:
        body = json.dumps({"username": temp_user, "password": temp_password, "sha256_checksum": sha256}).encode()
        url = f"{self.config.upload_base}/rest/forms/v1/fileupload/payload/{payload_id}/submit"
        return self._call("submit", "POST", url, {"Content-Type": "application/json"}, body)["data"]

    # --- spec 2.7 / 2.9: status and acknowledgments -------------------------------------

    def status(self, core_id: str) -> dict:
        return self._call("status", "GET", f"{self.config.api_base}/api/esgng/v1/submissions/{core_id}", self._auth())

    def acknowledgements(self, core_id: str) -> list[dict]:
        url = f"{self.config.api_base}/api/esgng/v1/acknowledgements/{core_id}"
        return self._call("acknowledgements", "GET", url, self._auth()).get("acknowledgements", [])

    # --- the whole flow -----------------------------------------------------------------

    def submit(self, package: Package, description: str, *, test: bool = True, approval: Approval | None = None) -> SubmissionReceipt:
        """Send one package. test=True by default; production needs an Approval of this exact file."""
        if not test:
            if approval is None:
                raise PermissionError("A production submission needs a person's Approval")
            if approval.package_sha256 != package.sha256:
                raise PermissionError("The Approval is for a different file than the one being sent")
        creds = self.request_credentials(package.filename, description, test)
        payload = self.new_payload()
        self.upload(payload["payloadId"], package)
        self.submit_payload(payload["payloadId"], creds["temp_user"], creds["temp_password"], package.sha256)
        return SubmissionReceipt(
            core_id=creds["core_id"],
            payload_id=payload["payloadId"],
            filename=package.filename,
            sha256=package.sha256,
            test=test,
            approved_by=approval.approved_by if approval else "",
        )
