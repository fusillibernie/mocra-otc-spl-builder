#!/bin/bash
# Small test output: dots, short tracebacks, no warnings summary.
# Extra args pass through (e.g. a path or -k expr). Use plain `pytest` only when
# a failure needs the full verbose output.
cd "$(dirname "$0")/.."
exec python3 -m pytest -q --no-header --tb=short -p no:warnings -p no:cacheprovider "$@"
