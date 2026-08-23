#!/usr/bin/env bash
# verify_timestamp.sh — Re-verify the pre-registration after any run.
# Re-computes hash, compares to committed value, validates OTS proof.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXPECTED=$(cat "$ROOT/preregister.hash")

echo "Expected hash: $EXPECTED"
echo
echo "Recomputing..."
COMPUTED=$(bash "$ROOT/scripts/preregister.sh")
echo "Computed hash: $COMPUTED"
echo

if [[ "$COMPUTED" == "$EXPECTED" ]]; then
    echo "✓ Runbook contents unchanged since preregister."
else
    echo "✗ HASH MISMATCH — pre-registration invalidated." >&2
    exit 1
fi

if [[ -f "$ROOT/preregister.hash.ots" ]] && command -v ots >/dev/null 2>&1; then
    echo
    echo "Verifying OpenTimestamps proof..."
    ots verify "$ROOT/preregister.hash.ots"
fi
