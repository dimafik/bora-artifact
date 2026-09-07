# Which script builds the patched orderer

Three scripts here patch and build a Fabric orderer, for two different Fabric
versions, and the patch itself arrives in two pieces. Only one path matches the
paper.

| script | Fabric | applies | status |
|---|---|---|---|
| **`build_v3.sh`** | **v3.1.4** | tick guard + vote guard | **current — this is the build the paper reports** |
| `apply_patch.sh` | v2.5.10 | tick guard only | superseded (wrong version, half the guard) |
| `build_and_run_ne26.sh` | v2.5 | **does not compile** | superseded |

The paper says Fabric v3.1.4 throughout, so `build_v3.sh` is the one to run. It
clones v3.1.4, applies every part of the patch under a guard so it is
idempotent, builds `./cmd/orderer`, and prints `V3_BUILD_OK`.

## The election guard is two guards, in two files

Section V-C measures "the full election guard: election-tick suppression *and*
the vote-grant predicate", and Algorithm 2 states both. They patch different
call sites and live in different files.

| guard | where | what it does |
|---|---|---|
| tick suppression | `chain_go_patch.diff` → `node.go` | a non-leader orderer in `B_t` skips `n.Tick()`, so its election timer effectively resets |
| `shouldYieldElection()` | `chain_go_patch.diff` → `chain.go` | the advisor dial behind the tick guard; **seq-gated**, so one advice sequence number fires once |
| vote-grant predicate | **`patch_vote_reject.py`** → `chain.go` | `Consensus()` drops `MsgVote`/`MsgPreVote` from a blacklisted candidate via `isCandidateBlacklisted()`; **not seq-gated**, because a standing `B_t` must reject *every* vote attempt |

The seq-gating difference is the one Algorithm 2 marks in its line for the vote
guard, and it is real in the code: `shouldYieldElection()` compares
`advice.Seq` against `lastBoraSeq` and returns false on a stale one;
`isCandidateBlacklisted()` has no such check.

Running `build_v3.sh` applies both. Running the diff alone gives you half.

## The diff on its own does not compile

`chain_go_patch.diff` is the tick-guard half as a diff, and it is incomplete by
itself:

    if advice.Seq <= atomic.LoadUint64(&c.lastBoraSeq) {

`lastBoraSeq` is never declared in that file. The declaration is a separate
three-line fragment, `chain_lastboraseq.diff`, which adds the field to the
`Chain` struct. No script applies that fragment — `build_v3.sh` and
`apply_patch.sh` both insert the field themselves with `sed`, which is why they
work and a bare `patch -p1 < chain_go_patch.diff` does not.

`build_and_run_ne26.sh` is the exception: it applies only `chain_go_patch.diff`
and would fail with `c.lastBoraSeq undefined`. It targets Fabric v2.5 as well.
It is kept because the Phase A / Phase D measurement structure it encodes is the
one the early runs used.

## How large the patch actually is

| part | added lines |
|---|---|
| `chain.go` — imports (`encoding/json`, `net`) and `shouldYieldElection()` | 37 |
| `node.go` — the tick guard | 6 |
| `chain.go` — the `lastBoraSeq` struct field | 3 |
| `chain.go` — the vote block in `Consensus()` | 8 |
| `chain.go` — `isCandidateBlacklisted()` | 31 |
| **total** | **85** (82 excluding blanks) |

Counting `chain_go_patch.diff` alone gives 43, which is the tick guard before
its struct field and without the vote guard; that count does not describe
anything that compiles, and it leaves out the half Section V-C names.

## What the patch does, against the paper

All three pieces are in the election path and nowhere else; the replication and
commit paths are untouched.

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
- `isCandidateBlacklisted()` (chain.go) is the same dial with the same two
  deadlines and the same fail-open cases, minus the sequence check, and it is
  consulted per incoming vote message. Dropping the message rather than voting
  no is what keeps a blacklisted candidate from reaching a quorum.

`WHICH_ADVISOR.md` in this directory covers the other half — which advisor
daemon fed those hooks in which campaign.
