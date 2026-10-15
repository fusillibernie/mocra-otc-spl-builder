#!/bin/bash
# Blocks Reads that would pull huge or generated files into context.
# A Read with an explicit limit (offset/limit) is allowed on large text files.
input=$(cat)
f=$(jq -r '.tool_input.file_path // ""' <<<"$input")
limit=$(jq -r '.tool_input.limit // ""' <<<"$input")

case "$f" in
  *node_modules*|*/.venv/*|*/venv/*|*/__pycache__/*|*.egg-info/*|*/.pytest_cache/*|*/dist/*|*/build/*|*.lock|*pnpm-lock.yaml)
    echo "Blocked: generated or dependency file. Use Grep with a pattern instead." >&2
    exit 2 ;;
  *.zip|*.gz|*.tar|*.xlsx|*.xls|*.docx|*.pyc|*.whl)
    echo "Blocked: $(basename "$f") is a binary archive. Unzip or convert it in Bash into a scratch directory and Grep the result." >&2
    exit 2 ;;
  *.json|*.xml|*.xsd|*.xsl|*.xslt|*.csv|*.tsv|*.txt|*.md|*.html)
    [ -n "$limit" ] && exit 0
    [ -f "$f" ] || exit 0
    size=$(stat -c%s "$f" 2>/dev/null || stat -f%z "$f")
    if [ "$size" -gt 50000 ]; then
      echo "Blocked: $(basename "$f") is $((size/1024))KB. Use jq/Grep to extract what you need, or Read with offset and limit." >&2
      exit 2
    fi ;;
esac
exit 0
