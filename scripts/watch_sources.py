"""Watch the official pages the regulatory data depends on, and report changes.

Copied from fragrance-reg-core/scripts/watch_sources.py; keep the two in sync.

    python scripts/watch_sources.py                # check all sources, write the report
    python scripts/watch_sources.py --summarize    # also ask Claude what each change affects
                                                   # (needs ANTHROPIC_API_KEY and the anthropic package)

For each page in sources/watchlist.json this fetches the page, reduces it to plain text, and compares
a fingerprint with sources/watch_state.json. Changed pages go into sources/watch_report.md with the
changed lines (when the previous text is in the local cache) and the data files to re-check.

Nothing here edits the regulatory data. A person (or a reviewed pull request) decides whether a change
matters. The weekly GitHub Actions job (.github/workflows/watch.yml) runs this and opens a pull request
with the report and the new fingerprints.

Exit code: 0 = no changes, 1 = changes found, 2 = some pages couldn't be fetched (and none changed).
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import html
import json
import re
import ssl
import sys
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATCHLIST = ROOT / "sources" / "watchlist.json"
STATE = ROOT / "sources" / "watch_state.json"
REPORT = ROOT / "sources" / "watch_report.md"
CACHE = ROOT / "sources" / "watch_cache"  # full text for diffs; not committed
USER_AGENT = "mocra-otc-spl-builder source watcher (+https://github.com/fusillibernie/mocra-otc-spl-builder)"
MAX_DIFF_LINES = 60
MIN_PAGE_CHARS = 400   # less visible text than this is a block page or an error shell
EXCERPT_CHARS = 600

# Lines that change on every visit without the content changing.
VOLATILE = re.compile(
    r"(last (updated|modified|reviewed)|date modified|page updated|copyright|©|\bcookie|skip to (main )?content"
    r"|share this page|print this page|\b\d{1,2}:\d{2}\b)", re.I)


class _Text(HTMLParser):
    """Visible text, one block per line; drops script, style, nav, header and footer."""
    SKIP = {"script", "style", "noscript", "nav", "header", "footer", "svg", "form"}
    BLOCK = {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "br", "td", "th", "dd", "dt"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def page_text(raw: str) -> str:
    parser = _Text()
    parser.feed(raw)
    lines = (re.sub(r"\s+", " ", html.unescape(line)).strip() for line in "".join(parser.parts).splitlines())
    return "\n".join(line for line in lines if line and not VOLATILE.search(line))


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _tls_context():
    """Verify certificates against the Mozilla CA bundle when certifi is installed.

    Some Windows Python installs ship an incomplete CA store (fda.gov failed to verify with it);
    certifi gives the standard bundle. Verification stays on either way.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def fetch(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
    with urllib.request.urlopen(req, timeout=timeout, context=_tls_context()) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def json_text(raw: str, source: dict) -> str:
    """A stable text projection of an API response: the listed fields of each list item.

    Used for official APIs (eCFR versions, Federal Register searches), which are meant for
    programmatic access and change only when the underlying record does.
    """
    data = json.loads(raw)
    items = data.get(source["list_key"], []) or []
    for key, value in (source.get("filter") or {}).items():
        items = [i for i in items if str(i.get(key, "")) == value]
    rows = [{k: i.get(k) for k in source["keep"]} for i in items]
    return "\n".join(json.dumps(r, sort_keys=True) for r in rows) or "(no records)"


def summarize(source: dict, diff: str) -> str:
    """Ask Claude what a change means for the data files. Optional; needs an API key."""
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-opus-5-5",
        max_tokens=1500,
        messages=[{"role": "user", "content": (
            f"A page that cosmetics and OTC drug filing data depends on has changed.\n\nPage: {source['name']} "
            f"({source['url']})\nData files that depend on it: {', '.join(source['affects'])}\n\n"
            f"Changed lines (unified diff):\n{diff}\n\n"
            "In under 120 words: is this a substantive regulatory change (a new limit, date, threshold, "
            "list entry or requirement) or cosmetic (layout, navigation, wording with the same meaning)? "
            "If substantive, say exactly what changed and which data file needs checking. Don't speculate "
            "beyond the diff.")}],
    )
    if response.stop_reason == "refusal":
        return "(summary unavailable)"
    return next((b.text for b in response.content if b.type == "text"), "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--summarize", action="store_true", help="Summarize each change with Claude")
    parser.add_argument("--only", help="Comma-separated source ids to check")
    args = parser.parse_args()

    sources = json.loads(WATCHLIST.read_text(encoding="utf-8"))["sources"]
    if args.only:
        wanted = set(args.only.split(","))
        sources = [s for s in sources if s["id"] in wanted]
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    CACHE.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    changed, failed, first_seen, manual = [], [], [], []
    for source in sources:
        sid = source["id"]
        if source.get("method") == "manual":
            manual.append(source)
            continue
        try:
            raw = fetch(source["url"])
            text = json_text(raw, source) if source.get("method") == "json" else page_text(raw)
            if source.get("method") != "json" and len(text) < MIN_PAGE_CHARS:
                # A block page or error shell, not the content: fingerprinting it would hide real changes.
                raise ValueError(f"page text is only {len(text)} characters (blocked or an error page?): "
                                 f"{text[:200]!r}")
        except Exception as e:  # network errors are reported, not fatal
            failed.append((source, f"{type(e).__name__}: {e}"))
            print(f"  FAILED   {sid}: {e}")
            continue
        new = fingerprint(text)
        old = state.get(sid, {}).get("fingerprint")
        cache_file = CACHE / f"{sid}.txt"
        previous = cache_file.read_text(encoding="utf-8") if cache_file.exists() else None
        if old is None:
            first_seen.append(source)
            print(f"  NEW      {sid}")
        elif old != new:
            diff = ""
            if previous is not None:
                lines = list(difflib.unified_diff(previous.splitlines(), text.splitlines(),
                                                  "before", "after", n=1, lineterm=""))
                diff = "\n".join(lines[:MAX_DIFF_LINES]) + ("\n..." if len(lines) > MAX_DIFF_LINES else "")
            changed.append((source, diff, text[:EXCERPT_CHARS]))
            print(f"  CHANGED  {sid}")
        else:
            print(f"  same     {sid}")
        cache_file.write_text(text, encoding="utf-8")
        state[sid] = {"fingerprint": new, "checked": now,
                      "changed": now if old != new else state.get(sid, {}).get("changed", now)}

    STATE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    out = [f"# Source watch report\n\nRun {now}. {len(sources)} sources checked: "
           f"{len(changed)} changed, {len(first_seen)} first seen, {len(failed)} couldn't be fetched.\n"]
    if changed:
        out.append("## Changed\n\nReview each page. If a rule changed, update the data file, its `checked` date "
                   "and sources, and the tests.\n")
        for source, diff, excerpt in changed:
            out.append(f"### {source['name']}\n\n{source['url']}\n\nRe-check: {', '.join('`' + a + '`' for a in source['affects'])}\n")
            if args.summarize and diff:
                try:
                    out.append(f"**Claude's reading:** {summarize(source, diff)}\n")
                except Exception as e:  # summary is a convenience
                    out.append(f"(summary failed: {type(e).__name__})\n")
            out.append(f"```diff\n{diff}\n```\n" if diff else
                       "No previous text cached here, so only the fingerprint is known to differ. Open the page. "
                       f"Start of the text received:\n\n```\n{excerpt}\n```\n")
    if first_seen:
        out.append("## First seen\n\n" + "\n".join(f"- {s['name']} ({s['url']})" for s in first_seen) + "\n")
    if failed:
        out.append("## Couldn't fetch\n\n" + "\n".join(f"- {s['name']}: {err}" for s, err in failed) + "\n")
    if manual:
        out.append("## Check by hand\n\nThese sites don't allow automated checks.\n\n" +
                   "\n".join(f"- {s['name']} ({s['url']}): {s.get('reminder', '')}" for s in manual) + "\n")
    REPORT.write_text("\n".join(out), encoding="utf-8")
    print(f"\nReport: {REPORT}")
    return 1 if changed else (2 if failed else 0)


if __name__ == "__main__":
    sys.exit(main())
