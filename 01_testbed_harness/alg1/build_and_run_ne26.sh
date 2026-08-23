#!/usr/bin/env bash
#
# build_and_run_ne26.sh — Plan E Track A
# Build patched Fabric v2.5 orderer with Algorithm 1 election-hook patch,
# deploy to the 5-orderer D2 testbed, and run NE26 paired comparison
# (Phase A: no patch, Phase D: with patch + sidecar live).
#
# Prerequisites (verified before running):
#   - Go 1.20+
#   - Docker Desktop + WSL2 Ubuntu (or native Linux)
#   - Fabric v2.5 source available
#   - 5-orderer D2 testbed up and running (./network up)
#   - Algorithm 1 sidecar (sidecar.py) available
#
# Run:
#   chmod +x build_and_run_ne26.sh
#   ./build_and_run_ne26.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${WORKSPACE:-$HOME/raft-advisor}"
FABRIC_SRC="${FABRIC_SRC:-$WORKSPACE/fabric}"
PATCH_FILE="${SCRIPT_DIR}/chain_go_patch.diff"
SEEDS=3
CONCURRENCY_POINTS=(1 2 4 8 16)
PHASE_A_TAG="phaseA_attack_only_no_patch"
PHASE_D_TAG="phaseD_attack_with_chain_go_patch"
OUT_DIR="${SCRIPT_DIR}/../results/ne26_$(date +%Y-%m-%d)"

# -------------------------------------------------------------------------
# Pre-flight checks
# -------------------------------------------------------------------------
echo "[Pre-flight] Checking environment..."
command -v go >/dev/null || { echo "ERROR: go not installed"; exit 1; }
command -v docker >/dev/null || { echo "ERROR: docker not installed"; exit 1; }
[[ -f "$PATCH_FILE" ]] || { echo "ERROR: patch file $PATCH_FILE not found"; exit 1; }
mkdir -p "$OUT_DIR"

# -------------------------------------------------------------------------
# Step 1: Clone Fabric v2.5 source (if not already)
# -------------------------------------------------------------------------
if [[ ! -d "$FABRIC_SRC" ]]; then
    echo "[Step 1/6] Cloning Fabric v2.5 source..."
    git clone --depth 1 --branch v2.5.10 \
        https://github.com/hyperledger/fabric.git "$FABRIC_SRC"
else
    echo "[Step 1/6] Fabric source already at $FABRIC_SRC"
fi

# -------------------------------------------------------------------------
# Step 2: Apply Chain.go patch
# -------------------------------------------------------------------------
echo "[Step 2/6] Applying ~30-line Chain.go patch..."
cd "$FABRIC_SRC"
git checkout -- orderer/consensus/etcdraft/chain.go || true
patch -p1 < "$PATCH_FILE" || {
    echo "ERROR: patch failed (file may have drifted in v2.5.10); manual merge required"
    exit 1
}
echo "  ✓ Patch applied"

# -------------------------------------------------------------------------
# Step 3: Build orderer binary
# -------------------------------------------------------------------------
echo "[Step 3/6] Building patched orderer binary..."
make orderer 2>&1 | tail -5
[[ -f build/bin/orderer ]] || { echo "ERROR: build failed"; exit 1; }
echo "  ✓ build/bin/orderer ready ($(du -h build/bin/orderer | cut -f1))"
cp build/bin/orderer "$OUT_DIR/orderer.patched"

# -------------------------------------------------------------------------
# Step 4: Phase A — measure with vanilla binary (no patch)
# -------------------------------------------------------------------------
echo "[Step 4/6] Phase A: vanilla orderer + attack (no Algorithm 1)..."
"$SCRIPT_DIR/run-alg1-experiment.sh" \
    --yield-mechanism none \
    --phase "$PHASE_A_TAG" \
    --seeds "$SEEDS" \
    --concurrency "${CONCURRENCY_POINTS[@]}" \
    --output "$OUT_DIR/phase_a"
echo "  ✓ Phase A complete: $OUT_DIR/phase_a"

# -------------------------------------------------------------------------
# Step 5: Deploy patched binary to all 5 orderers + run sidecar
# -------------------------------------------------------------------------
echo "[Step 5/6] Deploying patched binary + starting sidecar..."
for n in 1 2 3 4 5; do
    docker cp "$OUT_DIR/orderer.patched" "orderer${n}.example.com:/usr/local/bin/orderer"
    docker exec "orderer${n}.example.com" chmod +x /usr/local/bin/orderer
done
docker-compose -f network.yaml restart orderer{1..5}.example.com
sleep 30  # Allow cluster reconvergence

# Start the 270-line Algorithm 1 sidecar
nohup python3 "$SCRIPT_DIR/sidecar.py" \
    --config "$SCRIPT_DIR/alg1.yaml" \
    --output "$OUT_DIR/sidecar.log" &
SIDECAR_PID=$!
echo "  ✓ Sidecar PID=$SIDECAR_PID, B_t exposed at /var/run/raft-advisor.sock"

# -------------------------------------------------------------------------
# Step 6: Phase D — measure with patched binary + sidecar live
# -------------------------------------------------------------------------
echo "[Step 6/6] Phase D: patched orderer + sidecar + same attack..."
"$SCRIPT_DIR/run-alg1-experiment.sh" \
    --yield-mechanism chain-go-patch \
    --phase "$PHASE_D_TAG" \
    --seeds "$SEEDS" \
    --concurrency "${CONCURRENCY_POINTS[@]}" \
    --output "$OUT_DIR/phase_d"
echo "  ✓ Phase D complete: $OUT_DIR/phase_d"

# Stop sidecar
kill "$SIDECAR_PID" 2>/dev/null || true

# -------------------------------------------------------------------------
# Generate summary
# -------------------------------------------------------------------------
cat > "$OUT_DIR/SUMMARY.md" <<EOF
# NE26 — Plan E Track A Measurement Summary

**Date**: $(date -u +%Y-%m-%d_%H:%M:%S_UTC)
**Yield mechanisms compared**:
  - Phase A: none (vanilla orderer, attack only)
  - Phase D: chain.go election-hook patch (real Algorithm 1 implementation)

**Seeds per phase**: $SEEDS
**Concurrency points**: ${CONCURRENCY_POINTS[*]}

**Patch summary**: ~30-line addition to orderer/consensus/etcdraft/chain.go:
  - shouldYieldElection() Unix-socket consultation before campaign()
  - Fail-open on socket-unreachable / fail_open flag set

**Output directories**:
  - Phase A: $OUT_DIR/phase_a/
  - Phase D: $OUT_DIR/phase_d/
  - Sidecar log: $OUT_DIR/sidecar.log

**Comparison metric**: paired TPS / p99 at each concurrency point.
EOF

echo ""
echo "=========================================="
echo "  NE26 measurement complete"
echo "  Summary: $OUT_DIR/SUMMARY.md"
echo "=========================================="
