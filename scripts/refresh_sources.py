"""Download the official files this repo's data is built from, and notice when a new version appears.

    python scripts/refresh_sources.py                  # fetch everything in sources/manifest.json
    python scripts/refresh_sources.py --only a,b       # just these ids
    python scripts/refresh_sources.py --build          # then run each changed entry's importer scripts
    python scripts/refresh_sources.py --dry-run        # list what would be fetched, no network

sources/manifest.json says what to fetch. Two kinds of entry:
  file   one URL ("{today}" in it becomes the run date, for eCFR-style dated URLs)
  links  an index page: every link on it that matches the entry's filters is downloaded, so a new
         amendment, tool version or list update shows up as a new file without editing anything

Files are saved under sources/ and recorded (sha256, dates) in sources/fetched.json. A downloaded file
must look like what it claims to be (an HTML error or block page saved as a PDF would hide a real
change), and fetching never edits packaged data: importers (scripts/build_*.py) do, in a pull request
a person reviews. The GitHub Actions job (.github/workflows/refresh-sources.yml) runs this monthly and
opens that pull request, because the sandboxes this is developed in can't reach these hosts.

Exit code: 0 = nothing new, 1 = new or changed files, 2 = some fetches failed (and nothing changed).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
USER_AGENT = "mocra-otc-spl-builder source refresher (+https://github.com/fusillibernie/mocra-otc-spl-builder)"
MAX_BYTES = 50 * 1024 * 1024  # these files are committed to git
DEFAULT_MAX_FILES = 20
DELAY_SECONDS = 1.0
EXTENSIONS = (".pdf", ".xlsx", ".xlsm", ".xls", ".csv", ".zip", ".docx", ".xml", ".json")

# (url) -> (final url, response headers with lower-case names, body)
Opener = Callable[[str], tuple[str, dict, bytes]]


class FetchError(Exception):
    pass


def _explain(error: Exception) -> str:
    return str(error) if isinstance(error, FetchError) else f"unexpected {type(error).__name__}: {error}"


def _tls_context():
    """Verify against the Mozilla CA bundle when certifi is installed; verification is never turned off."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def snippet(body: bytes, limit: int = 160) -> str:
    """The visible start of a response body, for error messages (tags and whitespace removed)."""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", body[:4000].decode("utf-8", "replace"), flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()[:limit]


def describe_http_error(code: int, headers, body: bytes) -> str:
    server = headers.get("server") if headers else None
    detail = snippet(body)
    return f"HTTP {code}" + (f" (server: {server})" if server else "") + (f": {detail!r}" if detail else "")


def _http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # plain HTTP is normal for certificate (AIA) URLs
        return resp.read(1_000_000)


_PEM = re.compile(r"-----BEGIN CERTIFICATE-----.+?-----END CERTIFICATE-----", re.S)
_AIA = re.compile(r"CA Issuers - URI:(\S+)")


def aia_issuer_uri(cert_text: str) -> str | None:
    """The 'CA Issuers' URL from `openssl x509 -text` output: where the issuing certificate can be fetched."""
    m = _AIA.search(cert_text)
    return m.group(1) if m else None


def chase_intermediates(host: str, run=subprocess.run, fetch=_http_get, max_depth: int = 3) -> list[str]:
    """PEMs of the intermediate certificates a server failed to send, found the way browsers find them.

    Some sites (cdph.ca.gov) send only their own certificate; browsers fetch the issuer from the
    certificate's Authority Information Access URL, Python does not. The certificates fetched here are
    only added as candidates: the chain must still verify up to a root in the standard CA bundle, and
    verification is never switched off.
    """
    shown = run(["openssl", "s_client", "-connect", f"{host}:443", "-servername", host, "-showcerts"],
                input="", capture_output=True, text=True, timeout=30).stdout
    sent = _PEM.findall(shown)
    if not sent:
        return []
    found, current = [], sent[0]
    for _ in range(max_depth):
        text = run(["openssl", "x509", "-noout", "-text"], input=current, capture_output=True, text=True).stdout
        uri = aia_issuer_uri(text)
        if not uri:
            break
        data = fetch(uri)
        pems = _to_pems(data, run)
        if not pems:
            break
        found += pems
        current = pems[0]
    return found


def _to_pems(data: bytes, run) -> list[str]:
    """Certificates in a fetched issuer file: PEM, DER, or a PKCS#7 bundle."""
    text = data.decode("latin-1")
    if "BEGIN CERTIFICATE" in text:
        return _PEM.findall(text)
    for cmd in (["openssl", "x509", "-inform", "DER", "-outform", "PEM"],
                ["openssl", "pkcs7", "-inform", "DER", "-print_certs"]):
        out = run(cmd, input=data, capture_output=True)
        pems = _PEM.findall(out.stdout.decode("latin-1") if isinstance(out.stdout, bytes) else out.stdout)
        if out.returncode == 0 and pems:
            return pems
    return []


def _open(url: str, context) -> tuple[str, dict, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=60, context=context) as resp:
        body = resp.read(MAX_BYTES + 1)
        return resp.geturl(), {k.lower(): v for k, v in resp.headers.items()}, body


def _missing_issuer(error: BaseException) -> bool:
    reason = getattr(error, "reason", error)
    return isinstance(reason, ssl.SSLCertVerificationError) and "unable to get local issuer" in str(reason)


def urllib_opener(url: str) -> tuple[str, dict, bytes]:
    try:
        try:
            return _open(url, _tls_context())
        except (urllib.error.URLError, ssl.SSLError) as e:
            if isinstance(e, urllib.error.HTTPError) or not _missing_issuer(e):
                raise
            host = urllib.parse.urlparse(url).hostname
            extra, context = [], None
            try:
                extra = chase_intermediates(host)
                if extra:
                    context = _tls_context()
                    context.load_verify_locations(cadata="\n".join(extra))
            except (OSError, ValueError, subprocess.SubprocessError, ssl.SSLError, urllib.error.URLError):
                extra = []  # no openssl, nothing found, an unreadable certificate...: report the original error
            if not extra:
                raise
            return _open(url, context)
    except urllib.error.HTTPError as e:
        raise FetchError(describe_http_error(e.code, e.headers, e.read(4000))) from e
    except (urllib.error.URLError, TimeoutError, ssl.SSLError) as e:
        raise FetchError(f"{type(e).__name__}: {getattr(e, 'reason', e)}") from e


# --- what a downloaded file must look like -------------------------------------------------------

def check_content(name: str, body: bytes, headers: dict) -> None:
    """Raise FetchError if the bytes are not the kind of file the name says (e.g. an HTML block page)."""
    if len(body) > MAX_BYTES:
        raise FetchError(f"larger than {MAX_BYTES // 1024 // 1024} MB")
    if not body:
        seen = ", ".join(f"{k}={headers[k]}" for k in ("server", "content-type", "content-length") if k in headers)
        raise FetchError(f"empty response ({seen or 'no headers'})")
    ext = Path(name).suffix.lower()
    head = body[:512].lstrip(b"\xef\xbb\xbf \r\n\t").lower()
    looks_html = head.startswith((b"<!doctype html", b"<html", b"<head", b"<body"))
    if ext == ".pdf" and not body.startswith(b"%PDF"):
        raise FetchError("not a PDF (a block or error page?)")
    if ext in (".zip", ".xlsx", ".xlsm", ".docx") and not body.startswith(b"PK\x03\x04"):
        raise FetchError(f"not a {ext[1:]} file (a block or error page?)")
    if ext == ".xls" and not body.startswith(b"\xd0\xcf\x11\xe0"):
        raise FetchError("not an .xls file (a block or error page?)")
    if ext == ".json":
        try:
            json.loads(body.decode("utf-8-sig"))
        except ValueError as e:
            raise FetchError(f"not JSON: {e}") from e
    if ext in (".csv", ".xml") and looks_html:
        raise FetchError("an HTML page, not data (a block or error page?)")


def guess_extension(body: bytes, headers: dict) -> str:
    ctype = headers.get("content-type", "").split(";")[0].strip().lower()
    if body.startswith(b"%PDF"):
        return ".pdf"
    if body.startswith(b"PK\x03\x04"):
        return ".xlsx" if "spreadsheet" in ctype else ".zip"
    return {"text/csv": ".csv", "application/json": ".json", "application/xml": ".xml", "text/xml": ".xml"}.get(ctype, "")


def safe_name(name: str) -> str:
    name = urllib.parse.unquote(name).strip().replace("/", "_")
    return re.sub(r"[^A-Za-z0-9._ ()-]", "_", name).strip(" .") or "download"


def filename_for(url: str, link_text: str, body: bytes, headers: dict) -> str:
    """Content-Disposition name, else the URL's file name, else the link text plus a guessed extension."""
    disposition = headers.get("content-disposition", "")
    m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", disposition, re.I)
    if m:
        return safe_name(m.group(1))
    base = Path(urllib.parse.urlparse(url).path).name
    if Path(base).suffix.lower() in EXTENSIONS:
        return safe_name(base)
    return safe_name((link_text or base or "download")[:80]) + guess_extension(body, headers)


# --- link discovery --------------------------------------------------------------------------------

class _Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, re.sub(r"\s+", " ", "".join(self._text)).strip()))
            self._href = None


def discover(entry: dict, index_html: str, base_url: str) -> list[tuple[str, str]]:
    """(absolute url, link text) for each link on the page that the entry's filters accept, in page order."""
    parser = _Links()
    parser.feed(index_html)
    extensions = tuple(e.lower() for e in entry.get("extensions", EXTENSIONS))
    text_re = re.compile(entry["link_text"], re.I) if entry.get("link_text") else None
    url_re = re.compile(entry["link_url"], re.I) if entry.get("link_url") else None
    found, seen = [], set()
    for href, text in parser.links:
        if not href or href.startswith(("#", "mailto:", "javascript:", "tel:")):
            continue
        url = urllib.parse.urljoin(base_url, href).split("#")[0]
        path = urllib.parse.urlparse(url).path.lower()
        by_ext = path.endswith(extensions)
        by_url = bool(url_re and url_re.search(url))
        if not (by_ext or by_url):
            continue
        if text_re and not (text_re.search(text) or text_re.search(url)):
            continue
        if url not in seen:
            seen.add(url)
            found.append((url, text))
    return found[: entry.get("max_files", DEFAULT_MAX_FILES)]


# --- the run ------------------------------------------------------------------------------------

@dataclass
class FileResult:
    entry_id: str
    path: str  # relative to sources/
    status: str  # new | changed | same
    url: str


@dataclass
class Failure:
    entry_id: str
    what: str
    error: str
    confirmed: bool = True


@dataclass
class Result:
    files: list[FileResult] = field(default_factory=list)
    failures: list[Failure] = field(default_factory=list)
    builds: list[tuple[str, bool, str]] = field(default_factory=list)
    entries: dict[str, dict] = field(default_factory=dict)

    @property
    def changed(self) -> list[FileResult]:
        return [f for f in self.files if f.status in ("new", "changed")]

    @property
    def exit_code(self) -> int:
        return 1 if self.changed else (2 if self.failures else 0)


def _hash_index(root: Path) -> dict[str, str]:
    """sha256 -> path (relative to sources/) of every data file already stored, so a file that is
    already in the repo under another name isn't saved again."""
    base, index = root / "sources", {}
    skip = {"fetched.json", "manifest.json", "watchlist.json", "watch_state.json"}
    if base.exists():
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix.lower() in EXTENSIONS and p.name not in skip and p.stat().st_size <= MAX_BYTES:
                index.setdefault(hashlib.sha256(p.read_bytes()).hexdigest(), str(p.relative_to(base)))
    return index


def _save(root: Path, state: dict, entry: dict, rel: str, url: str, body: bytes, today: str, result: Result,
          index: dict[str, str] | None = None) -> None:
    index = index if index is not None else {}
    sha = hashlib.sha256(body).hexdigest()
    old = state.get(rel)
    other = index.get(sha)
    if old is None and other and other != rel:
        status = "duplicate"
    else:
        status = "new" if old is None else ("same" if old["sha256"] == sha else "changed")
    if status in ("new", "changed"):
        path = root / "sources" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        index[sha] = rel
    record = {
        "id": entry["id"], "url": url, "sha256": sha, "bytes": len(body),
        "first_seen": old["first_seen"] if old else today,
        "changed": today if status in ("new", "changed") else (old["changed"] if old else today),
        "checked": today,
    }
    if status == "duplicate" or (status == "same" and old and old.get("duplicate_of")):
        record["duplicate_of"] = other or old["duplicate_of"]
    state[rel] = record
    result.files.append(FileResult(entry["id"], rel, status, url))


def refresh(manifest: dict, root: Path = ROOT, opener: Opener = urllib_opener, today: date | None = None,
            only: set[str] | None = None, sleep: Callable[[float], None] = time.sleep, build: bool = False) -> Result:
    today = today or date.today()
    stamp = today.isoformat()
    state_path = root / "sources" / "fetched.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    result = Result()
    first = True

    def get(url: str):
        nonlocal first
        if not first:
            sleep(DELAY_SECONDS)
        first = False
        return opener(url)

    def get_dated(entry: dict):
        """Fetch entry['url']; if it has {today}, step back a day at a time (up to date_back_days) when
        the newest data isn't published yet (the eCFR answers 406 for a date past its latest update)."""
        error = None
        for back in range(entry.get("date_back_days", 0) + 1):
            url = entry["url"].replace("{today}", (today - timedelta(days=back)).isoformat())
            try:
                return (url, *get(url))
            except FetchError as e:
                error = e
                if "{today}" not in entry["url"]:
                    break
        raise error

    index = _hash_index(root)
    for entry in manifest["entries"]:
        if only and entry["id"] not in only:
            continue
        result.entries[entry["id"]] = entry
        confirmed = entry.get("confirmed", True)
        save_dir = entry.get("save_dir", "").strip("/")
        prefix = f"{save_dir}/" if save_dir else ""
        try:
            if entry["kind"] == "file":
                url, final, headers, body = get_dated(entry)
                name = safe_name(entry["save_as"])
                check_content(name, body, headers)
                _save(root, state, entry, prefix + name, url, body, stamp, result, index)
            elif entry["kind"] == "links":
                final, headers, body = get(entry["index_url"])
                links = discover(entry, body.decode("utf-8", errors="replace"), final)
                if not links:
                    counter = _Links()
                    page = body.decode("utf-8", errors="replace")
                    counter.feed(page)
                    raise FetchError(f"no matching links on the index page ({len(counter.links)} links, {len(body)} bytes; "
                                     f"page text starts: {snippet(body)!r})")
                for url, text in links:
                    try:
                        final_url, headers, data = get(url)
                        name = filename_for(final_url, text, data, headers)
                        check_content(name, data, headers)
                        _save(root, state, entry, prefix + name, url, data, stamp, result, index)
                    except Exception as e:  # one bad file (a dropped connection, odd bytes) must not stop the rest
                        result.failures.append(Failure(entry["id"], url, _explain(e), confirmed))
            else:
                raise FetchError(f"unknown kind {entry['kind']!r}")
        except Exception as e:
            result.failures.append(Failure(entry["id"], entry.get("url") or entry.get("index_url", ""), _explain(e), confirmed))

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if build:
        changed_ids = {f.entry_id for f in result.changed}
        for entry_id in sorted(changed_ids):
            for script in result.entries[entry_id].get("build", []):
                path = root / script
                if not path.exists():
                    result.builds.append((script, False, "importer not written yet"))
                    continue
                proc = subprocess.run([sys.executable, str(path)], cwd=root, capture_output=True, text=True)
                tail = (proc.stdout + proc.stderr).strip().splitlines()[-5:]
                result.builds.append((script, proc.returncode == 0, "\n".join(tail)))
    return result


def report(result: Result, now: str) -> str:
    out = [f"# Source refresh report\n\nRun {now}. {len(result.files)} files seen: "
           f"{sum(f.status == 'new' for f in result.files)} new, {sum(f.status == 'changed' for f in result.files)} changed, "
           f"{sum(f.status == 'same' for f in result.files)} unchanged, "
           f"{sum(f.status == 'duplicate' for f in result.files)} already stored under another name; "
           f"{len(result.failures)} failures.\n"]
    by_entry: dict[str, list[FileResult]] = {}
    for f in result.changed:
        by_entry.setdefault(f.entry_id, []).append(f)
    if by_entry:
        out.append("## New or changed\n\nA person reads each one, runs or updates the importer, and checks the data "
                   "files it affects. Old versions stay in git history.\n")
        for entry_id, files in by_entry.items():
            entry = result.entries[entry_id]
            out.append(f"### {entry['name']}\n")
            out += [f"- `sources/{f.path}` ({f.status}) from {f.url}" for f in files]
            if entry.get("affects"):
                out.append(f"\nRe-check: {', '.join('`' + a + '`' for a in entry['affects'])}")
            if entry.get("note"):
                out.append(f"\n{entry['note']}")
            out.append("")
    if result.builds:
        out.append("## Importers\n")
        out += [f"- `{s}`: {'ok' if ok else 'FAILED'}" + (f"\n  ```\n  {detail}\n  ```" if detail else "") for s, ok, detail in result.builds]
        out.append("")
    if result.failures:
        out.append("## Couldn't fetch\n")
        for f in result.failures:
            guess = "" if f.confirmed else " (this URL was never confirmed; if it is a 404, fix sources/manifest.json)"
            out.append(f"- `{f.entry_id}`: {f.what}: {f.error}{guess}")
        out.append("")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", help="Comma-separated entry ids")
    parser.add_argument("--build", action="store_true", help="Run importers for entries that changed")
    parser.add_argument("--dry-run", action="store_true", help="List the entries; no network")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "sources" / "manifest.json").read_text(encoding="utf-8"))
    only = set(args.only.split(",")) if args.only else None
    if args.dry_run:
        for e in manifest["entries"]:
            if not only or e["id"] in only:
                print(f"{e['id']:32} {e['kind']:6} {e.get('url') or e.get('index_url')}")
        return 0
    result = refresh(manifest, only=only, build=args.build)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    text = report(result, now)
    (ROOT / "sources" / "refresh_report.md").write_text(text, encoding="utf-8")
    print(text)
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
