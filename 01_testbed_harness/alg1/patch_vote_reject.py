#!/usr/bin/env python3
# Add the BORA Vote-Grant Predicate to the Fabric etcdraft chain.go:
#  (1) in Consensus(), drop MsgVote/MsgPreVote from a blacklisted candidate;
#  (2) add isCandidateBlacklisted() helper (per-message, not seq-gated).
import sys

f = "/home/jinu337/raft-advisor/fabric-v3.1.4/orderer/consensus/etcdraft/chain.go"
s = open(f).read()
orig = s

if "isCandidateBlacklisted" in s:
    print("already patched; skipping")
    sys.exit(0)

anchor = "\tif err := c.Node.Step(context.TODO(), *stepMsg); err != nil {"
assert s.count(anchor) == 1, "anchor count=%d" % s.count(anchor)

voteblk = (
    "\t// BORA Vote-Grant Predicate: refuse to even process a vote request from a\n"
    "\t// blacklisted candidate, so a flagged node cannot reach a quorum and become\n"
    "\t// leader regardless of its own election-tick behaviour.\n"
    "\tif (stepMsg.Type == raftpb.MsgVote || stepMsg.Type == raftpb.MsgPreVote) && c.isCandidateBlacklisted(stepMsg.From) {\n"
    "\t\tc.logger.Infof(\"BORA: dropping %s from blacklisted candidate %d\", stepMsg.Type, stepMsg.From)\n"
    "\t\treturn nil\n"
    "\t}\n\n"
)
s = s.replace(anchor, voteblk + anchor)

fn = (
    "\n// isCandidateBlacklisted consults the BORA advisor and returns true iff the\n"
    "// given candidate raftID is in the current B_t and BORA is not fail-open. It\n"
    "// is evaluated per incoming vote message and is NOT seq-gated: a standing B_t\n"
    "// must reject every vote attempt by the blacklisted candidate (the Vote-Grant\n"
    "// Predicate).\n"
    "func (c *Chain) isCandidateBlacklisted(id uint64) bool {\n"
    "\tconn, err := net.DialTimeout(\"unix\", \"/var/run/raft-advisor.sock\", 50*time.Millisecond)\n"
    "\tif err != nil {\n\t\treturn false\n\t}\n"
    "\tdefer conn.Close()\n"
    "\tconn.SetReadDeadline(time.Now().Add(50 * time.Millisecond))\n"
    "\tvar advice struct {\n"
    "\t\tBlacklist []uint64 `json:\"blacklist\"`\n"
    "\t\tSeq       uint64   `json:\"seq\"`\n"
    "\t\tFailOpen  bool     `json:\"fail_open\"`\n"
    "\t}\n"
    "\tif err := json.NewDecoder(conn).Decode(&advice); err != nil {\n\t\treturn false\n\t}\n"
    "\tif advice.FailOpen {\n\t\treturn false\n\t}\n"
    "\tfor _, b := range advice.Blacklist {\n\t\tif b == id {\n\t\t\treturn true\n\t\t}\n\t}\n"
    "\treturn false\n}\n"
)
s = s.rstrip() + "\n" + fn

open(f, "w").write(s)
print("patched ok: voteblk=%s fn=%s delta=%d bytes" % (voteblk in s, "isCandidateBlacklisted" in s, len(s) - len(orig)))
