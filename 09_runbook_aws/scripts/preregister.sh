#!/usr/bin/env bash
# preregister.sh — Hash every byte of the runbook before T+0:00.
# After this point, ANY change invalidates the pre-registration.
#
# Usage: ./preregister.sh > preregister.hash

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT"

# Hash deterministic file order, excluding outputs and ephemeral data
find . \
    -type f \
    -not -path "./dry_run_output/*" \
    -not -path "./scripts/preregister.sh" \
    -not -name "preregister.hash" \
    -not -name "preregister.hash.ots" \
    -not -name "preregister.proof.txt" \
    -not -name "preregister.gist.url" \
    -not -name "FINAL_STATUS.md" \
    -not -name "TIMESTAMP_INSTRUCTIONS.md" \
    -not -name "*.pyc" \
    -not -path "./__pycache__/*" \
    -print0 \
  | sort -z \
  | xargs -0 sha256sum \
  | sha256sum \
  | awk '{print $1}'
