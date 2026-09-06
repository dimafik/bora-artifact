# Which script builds the patched orderer

Three scripts here patch and build a Fabric orderer, for two different Fabric
versions. Only one matches the paper.

| script | Fabric | complete? | status |
|---|---|---|---|
| **`build_v3.sh`** | **v3.1.4** | yes | **current — this is the build the paper reports** |
| `apply_patch.sh` | v2.5.10 | yes | superseded (wrong version) |
| `build_and_run_ne26.sh` | v2.5 | **no — does not compile** | superseded |

The paper says Fabric v3.1.4 throughout, so `build_v3.sh` is the one to run. It
clones v3.1.4, applies every part of the patch under a `grep -q` guard so it is
idempotent, builds `./cmd/orderer`, and prints `V3_BUILD_OK`.

## The diff on its own does not compile

`chain_go_patch.diff` is the patch as a diff, and it is incomplete by itself:

    if advice.Seq <= atomic.LoadUint64(&c.lastBoraSeq) {

`lastBoraSeq` is never declared in that file. The declaration is a separate
three-line fragment, `chain_lastboraseq.diff`, which adds the field to the
`Chain` struct. No script applies that fragment — `build_v3.sh` and
`apply_patch.sh` both insert the field themselves with `sed`, which is why they
work and a bare `patch -p1 < chain_go_patch.diff` does not.

`build_and_run_ne26.sh` is the exception: it applies only `chain_go_patch.diff`
and would fail with `c.lastBoraSeq undefined`. It targets Fabric v2.5 as well,
so it is two versions and one compile error away from the paper. It is kept
because the Phase A / Phase D measurement structure it encodes is the one the
early runs used.

## How large the patch actually is

| part | added lines |
|---|---|
| `chain.go` — imports (`encoding/json`, `net`) and `shouldYieldElection()` | 37 |
| `node.go` — the tick guard | 6 |
| `chain.go` — the `lastBoraSeq` struct field | 3 |
| **total** | **46** (45 excluding blanks) |

The response letter reports 46. Counting `chain_go_patch.diff` alone gives 43,
which is the number before the struct field, and that count does not describe
anything that compiles.

## What the patch does, against the paper

Both hooks are in the election path and nowhere else; the replication and commit
paths are untouched.

- `shouldYieldElection()` (chain.go) dials the sidecar on
  `/var/run/raft-advisor.sock` with a 50 ms connect timeout and a 50 ms read
  deadline — the 100 ms budget Section III-J accounts for. It returns `false`
  on an unreachable socket, a malformed reply, a stale sequence number, or an
  explicit `fail_open` flag. That is the fail-open semantics of Section II-C:
  every failure mode yields vanilla Raft.
- The tick guard (node.go) skips `n.Tick()` for a non-leader orderer that is in
  `B_t`. Leaders always tick, which is the Active-Leader Rule of Section III-I.
  Section III-F discloses the cost: the early return also skips Fabric's
  activity tracker, so a suppressed orderer stops refreshing the cluster's
  active-node gauge while it yields.

`WHICH_ADVISOR.md` in this directory covers the other half — which advisor
daemon fed those hooks in which campaign.
