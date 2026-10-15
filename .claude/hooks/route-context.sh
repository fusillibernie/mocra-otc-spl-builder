#!/bin/bash
# UserPromptSubmit: add the file paths for any topic the prompt mentions.
p=$(jq -r '.prompt // ""' | tr '[:upper:]' '[:lower:]')
S=src/mocra_otc_spl_builder
m() { grep -qE "$1" <<<"$p" && echo "Context ($2): $3"; }
m 'cscp|safe cosmetics|cdph' cscp "$S/cscp.py, $S/data/cscp_rules.json, $S/data/cscp_reportable_ingredients.json (list not loaded yet)"
m 'esg|submit|usp' esg "$S/esg.py (production needs an Approval; test=True is the default)"
m 'facility|registration|fei' facility "$S/facility_registration.py"
m 'listing|cosmetic' listing "$S/cosmetic_spl.py, $S/cosmetic_validation.py, $S/categories.py, $S/data/cosmetic_categories.json"
m 'otc|monograph' otc "$S/completeness.py, $S/data/otc_monographs.json (order URLs unverified)"
m 'schema|xsd|spl' spl "$S/spl_xml.py, $S/schema.py, $S/data/spl_schema/"
m 'ingredient' ingredients "$S/ingredients.py (needs fragrance-reg-core)"
m 'refresh|manifest|source|watch' sources "scripts/refresh_sources.py, scripts/watch_sources.py, sources/manifest.json, sources/README.md"
m 'voc|carb' voc "VOC reporting is not built yet; CARB entries are in sources/manifest.json"
m 'state' state "docs/STATE_REPORTING.md"
exit 0
