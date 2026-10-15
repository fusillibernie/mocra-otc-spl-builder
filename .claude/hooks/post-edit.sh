#!/bin/bash
# After an edit: stay silent when clean, report only real failures (max 15 lines).
# Python: syntax check, plus ruff for syntax errors and undefined names when ruff is
# installed (unused imports are skipped: both repos re-export on purpose). JSON: must parse. No auto-formatting,
# because neither repo has a formatter configured and it would churn diffs.
f=$(jq -r '.tool_input.file_path // ""')
[ -f "$f" ] || exit 0

case "$f" in
  *.py)
    out=$(python3 -m py_compile "$f" 2>&1) || { echo "$out" | head -15 >&2; exit 2; }
    if command -v ruff >/dev/null 2>&1; then
      out=$(ruff check --quiet --no-cache --select E9,F63,F7,F82 --output-format concise "$f" 2>&1) \
        || { echo "$out" | head -15 >&2; exit 2; }
    fi ;;
  *.json)
    out=$(jq empty "$f" 2>&1) || { echo "Invalid JSON in $(basename "$f"): $out" | head -15 >&2; exit 2; } ;;
esac
exit 0
