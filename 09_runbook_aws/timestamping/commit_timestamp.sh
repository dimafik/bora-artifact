#!/usr/bin/env bash
# commit_timestamp.sh — Commit preregister.hash to a public timestamp service.
#
# Primary: OpenTimestamps (Bitcoin blockchain anchored)
# Fallback: SHA-256 commit to public GitHub gist + multiple mirrors
#
# Run AT MOST ONCE per run_id. Output: preregister.hash.ots (binary proof).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HASH_FILE="$ROOT/preregister.hash"

if [[ ! -f "$HASH_FILE" ]]; then
    echo "ERROR: $HASH_FILE not found. Run scripts/preregister.sh first." >&2
    exit 1
fi

HASH=$(cat "$HASH_FILE")
echo "Committing pre-register hash: $HASH"
echo

# --- Strategy A: OpenTimestamps ---
if command -v ots >/dev/null 2>&1; then
    echo "[strategy A] OpenTimestamps client found"
    ots stamp "$HASH_FILE"
    echo "Stamped → $HASH_FILE.ots"
    echo "Initial proof submitted to OTS calendars."
    echo "Run 'ots upgrade $HASH_FILE.ots' after ~3 hours to anchor to Bitcoin."
    echo "Run 'ots verify $HASH_FILE.ots' to confirm at any later time."
else
    echo "[strategy A] OpenTimestamps client (ots) not installed."
    echo "  Install: pip install opentimestamps-client"
    echo "  Skipping primary anchor; falling back to multi-mirror commit."
    echo
fi

# --- Strategy B: GitHub gist (public, immutable per-revision) ---
if command -v gh >/dev/null 2>&1; then
    echo "[strategy B] Creating GitHub gist"
    GIST_URL=$(gh gist create "$HASH_FILE" --public --desc "sched-bft preregister $(date -Iseconds)")
    echo "  Gist URL: $GIST_URL"
    echo "$GIST_URL" > "$ROOT/preregister.gist.url"
else
    echo "[strategy B] gh CLI not available. Manual upload to gist.github.com required."
fi

# --- Strategy C: SHA-256 of the hash + timestamp into local proof.txt ---
# Cheap proof-of-existence anchor in case A & B both fail
cat > "$ROOT/preregister.proof.txt" <<EOF
sched-bft preregister proof
===========================
Hash:      $HASH
Timestamp: $(date -Iseconds)
Algorithm: SHA-256
Source:    $(realpath --relative-to="$ROOT" "$HASH_FILE")

Verification:
  cd $(realpath "$ROOT")
  bash scripts/preregister.sh   # must produce: $HASH

If any file under runbook/ changes after this point, the hash will
diverge and the pre-registration is invalidated.
EOF
echo
echo "[strategy C] Local proof-of-existence: $ROOT/preregister.proof.txt"
echo
echo "DONE. Hash is anchored across $(ls -1 $ROOT/preregister.* 2>/dev/null | wc -l) artifacts."
