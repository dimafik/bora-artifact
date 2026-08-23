#!/usr/bin/env bash
set -e
export GOROOT=$HOME/go-install
export GOPATH=$HOME/gopath
export GOCACHE=$HOME/.gocache
export PATH=$GOROOT/bin:$PATH

WS=$HOME/raft-advisor
FABRIC_V3=$WS/fabric-v3.1.4

echo "[1/4] Clone Fabric v3.1.4..."
if [ ! -d $FABRIC_V3 ]; then
  git clone --depth 1 --branch v3.1.4 https://github.com/hyperledger/fabric.git $FABRIC_V3
fi

CHAIN=$FABRIC_V3/orderer/consensus/etcdraft/chain.go
NODE=$FABRIC_V3/orderer/consensus/etcdraft/node.go

echo "[2/4] Inspect v3.1.4 structure..."
echo "chain.go lines: $(wc -l < $CHAIN)"
echo "node.go lines: $(wc -l < $NODE)"
echo "Tick() in node.go:"
grep -n 'n.Tick()' $NODE | head -3
echo "confState in chain.go:"
grep -n 'confState' $CHAIN | head -3
echo "encoding/pem in chain.go:"
grep -n 'encoding/pem\|"sync/atomic"\|"net"\|"encoding/json"' $CHAIN | head -10

echo "[3/4] Apply patch..."
cd $FABRIC_V3
git checkout -- $CHAIN $NODE 2>/dev/null || true

# Imports — only add net and encoding/json if not already present
if ! grep -q '"net"' $CHAIN; then
  sed -i '/"encoding\/pem"/a\\t"encoding/json"\n\t"net"' $CHAIN
fi

# Struct field
if ! grep -q 'lastBoraSeq' $CHAIN; then
  # Insert lastBoraSeq after confState line
  sed -i '/confState        raftpb.ConfState/a\\n\t// BORA: last advice sequence number (atomic).\n\tlastBoraSeq uint64' $CHAIN
fi

# shouldYieldElection method
if ! grep -q 'shouldYieldElection' $CHAIN; then
  cat >> $CHAIN <<'EOF'

// shouldYieldElection consults the BORA sidecar advisor via Unix-domain socket.
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
fi

# Tick guard in node.go
if ! grep -q 'BORA: blacklisted' $NODE; then
python3 <<'PYEOF'
import pathlib, os
p = pathlib.Path(os.environ["NODE"])
text = p.read_text()
old = "status := n.Status()\n\n\t\t\tn.Tick()"
new = ("status := n.Status()\n\n"
       "\t\t\t// BORA: blacklisted non-leader orderers suppress their tick so the\n"
       "\t\t\t// election timer effectively resets without incrementing term.\n"
       "\t\t\tif status.RaftState != raft.StateLeader && n.chain.shouldYieldElection() {\n"
       "\t\t\t\tcontinue\n"
       "\t\t\t}\n\n"
       "\t\t\tn.Tick()")
if old not in text:
    print("OLD context not found, dumping context around Tick:")
    import re
    for m in re.finditer(r'n\.Tick\(\)', text):
        s = max(0, m.start() - 200); e = min(len(text), m.end() + 50)
        print(text[s:e])
        print("---")
    raise SystemExit(1)
p.write_text(text.replace(old, new, 1))
print("node.go patched (v3.1.4)")
PYEOF
fi

echo "[4/4] Build orderer binary..."
cd $FABRIC_V3
go build -o /tmp/orderer-bora-v3 ./cmd/orderer
ls -lh /tmp/orderer-bora-v3
echo "V3_BUILD_OK"
