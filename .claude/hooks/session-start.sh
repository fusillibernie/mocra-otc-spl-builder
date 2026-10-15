#!/bin/bash
set -euo pipefail

# Cloud sessions only.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"
python3 -m pip install --quiet -e ".[dev]"

# fragrance-reg-core is private; use a sibling clone if the session has one,
# otherwise try the pinned git tag. Without it, the core-dependent tests skip.
if [ -d "$CLAUDE_PROJECT_DIR/../fragrance-reg-core" ]; then
  python3 -m pip install --quiet -e "$CLAUDE_PROJECT_DIR/../fragrance-reg-core" \
    || echo "warning: could not install sibling fragrance-reg-core" >&2
else
  python3 -m pip install --quiet "fragrance-reg-core @ git+https://github.com/fusillibernie/fragrance-reg-core@v0.5.3" \
    || echo "warning: fragrance-reg-core not installed; core tests will skip" >&2
fi
