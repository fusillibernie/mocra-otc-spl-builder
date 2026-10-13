"""Renders SPL the way FDA displays it, with FDA's SPL stylesheet 6.2 (bundled in
data/spl_stylesheet/), so the person signing off reviews what FDA will see.

Needs lxml: pip install "mocra-otc-spl-builder[schema]".
"""

from functools import cache
from importlib import resources

from .spl_xml import SplFile

STYLESHEET_DIR = resources.files("mocra_otc_spl_builder") / "data" / "spl_stylesheet"
REMOTE_CSS = '<link rel="stylesheet" type="text/css" href="http://www.accessdata.fda.gov/spl/stylesheet/spl.css">'


@cache
def _transform():
    from lxml import etree

    with resources.as_file(STYLESHEET_DIR / "spl.xsl") as path:
        return etree.XSLT(etree.parse(str(path), etree.XMLParser(no_network=True)))


def preview_html(spl: SplFile) -> str:
    """A standalone HTML page (FDA's CSS inlined, no network needed)."""
    from lxml import etree

    doc = etree.fromstring(spl.xml.split("?>", 2)[2].encode("utf-8"), etree.XMLParser(no_network=True))
    html = etree.tostring(_transform()(doc), method="html", encoding="unicode")
    css = (STYLESHEET_DIR / "spl.css").read_text(encoding="utf-8")
    return html.replace(REMOTE_CSS, f"<style>{css}</style>")
