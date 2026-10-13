"""Checks SPL XML against FDA's SPL schema (SchemasR2b, bundled in data/spl_schema/).

Needs lxml: pip install "mocra-otc-spl-builder[schema]".
"""

from functools import cache
from importlib import resources

SCHEMA_DIR = resources.files("mocra_otc_spl_builder") / "data" / "spl_schema"


@cache
def _schema():
    from lxml import etree

    with resources.as_file(SCHEMA_DIR / "SPL.xsd") as path:
        return etree.XMLSchema(etree.parse(str(path), etree.XMLParser(no_network=True)))


def schema_errors(xml: str) -> list[str]:
    """Every schema error as 'line N: message'; empty when the XML is valid (IG 2.1.1.1)."""
    from lxml import etree

    doc = etree.fromstring(xml.encode("utf-8"), etree.XMLParser(no_network=True, resolve_entities=False))
    schema = _schema()
    if schema.validate(doc):
        return []
    return [f"line {e.line}: {e.message}" for e in schema.error_log]
