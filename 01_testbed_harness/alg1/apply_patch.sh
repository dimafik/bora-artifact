#!/usr/bin/env bash
# Apply BORA hook patch to Fabric v2.5.10 source.
set -e
FABRIC=$HOME/raft-advisor/fabric
CHAIN=$FABRIC/orderer/consensus/etcdraft/chain.go
NODE=$FABRIC/orderer/consensus/etcdraft/node.go

cd $FABRIC
git checkout -- $CHAIN $NODE

# 1. Add encoding/json and net imports to chain.go (after "encoding/pem").
sed -i '/"encoding\/pem"/a\\t"encoding/json"\n\t"net"' $CHAIN

# 2. Add lastBoraSeq field after confState line.
sed -i '/confState        raftpb.ConfState/a\\n\t// BORA: last advice sequence number this Chain has accepted (atomic).\n\tlastBoraSeq uint64' $CHAIN

# 3. Append shouldYieldElection() method to end of chain.go.
cat >> $CHAIN <<'EOF'

// shouldYieldElection consults the BORA sidecar advisor over a
// Unix-domain socket. Returns true iff this orderer's raftID is in
// the current B_t blacklist and BORA is not in fail-open mode.
// Fail-open semantics: socket unreachable, malformed response,
// stale sequence number, or explicit fail_open flag => return false.
func (c *Chain) shouldYieldElection() bool {
	conn, err := net.DialTimeout("unix", "/var/run/raft-advisor.sock", 50*time.Millisecond)
	if err != nil {
		return false
	}
	defer conn.Close()
	conn.SetReadDeadline(time.Now().Add(50 * time.Millisecond))
	var advice struct {
		Blacklist []uint64 `json:"blacklist"`
		Seq       uint64   `json:"seq"`
		FailOpen  bool     `json:"fail_open"`
	}
	if err := json.NewDecoder(conn).Decode(&advice); err != nil {
		return false
	}
	if advice.FailOpen {
		return false
	}
	if advice.Seq <= atomic.LoadUint64(&c.lastBoraSeq) {
		return false
	}
	atomic.StoreUint64(&c.lastBoraSeq, advice.Seq)
	for _, id := range advice.Blacklist {
		if id == c.raftID {
			return true
		}
	}
	return false
}
EOF

# 4. Add BORA tick guard in node.go before n.Tick().
python3 - <<'PYEOF'
import re, pathlib
p = pathlib.Path("$NODE".replace("$NODE", __import__("os").environ.get("NODE", "")) or "/home/jinu337/raft-advisor/fabric/orderer/consensus/etcdraft/node.go")
text = p.read_text()
old = """\t\t\tstatus := n.Status()

\t\t\tn.Tick()"""
new = """\t\t\tstatus := n.Status()

\t\t\t// BORA: blacklisted non-leader orderers suppress their tick so the
\t\t\t// election timer effectively resets without incrementing term.
\t\t\tif status.RaftState != raft.StateLeader && n.chain.shouldYieldElection() {
\t\t\t\tcontinue
\t\t\t}

\t\t\tn.Tick()"""
if old not in text:
    raise SystemExit("Old context not found in node.go; patch target may have changed.")
p.write_text(text.replace(old, new, 1))
print("node.go patched")
PYEOF

echo
echo "=== Patch diff summary ==="
cd $FABRIC
git --no-pager diff --stat
echo "=== chain.go tail ==="
tail -15 $CHAIN
echo "=== node.go around line 130-145 ==="
sed -n '128,150p' $NODE
