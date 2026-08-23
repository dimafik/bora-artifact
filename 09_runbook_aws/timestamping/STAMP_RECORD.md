# OTS Stamp Record

## Stamping Event

| Field | Value |
|---|---|
| File stamped | `runbook/preregister.hash` |
| Pre-register hash (file contents) | `6102513b8a1407865e9b2b2c700c143b06b7a6b3e978f152b81a5d53e88d36e7` |
| File digest (what was anchored) | `1752958aafeb07a2d29d4a57694260694e160de5b6437ce2eba99c28c6aadb68` |
| Submitted UTC | `2026-06-01T03:26:52Z` |
| Method | Direct HTTP POST to calendar `/digest` endpoint |
| Why direct HTTP | `opentimestamps-client 0.7.2` import fails on Windows + Python 3.9 due to `python-bitcoinlib`'s `libssl` DLL load (WinError 193). |

## Calendars Notified

| Calendar | Status | Response | Fragment |
|---|---|---:|---|
| alice.btc.calendar.opentimestamps.org | HTTP 200 OK | 207 bytes | `calendar_proofs/alice.btc.calendar.opentimestamps.org.ots-fragment` |
| bob.btc.calendar.opentimestamps.org | HTTP 200 OK | 170 bytes | `calendar_proofs/bob.btc.calendar.opentimestamps.org.ots-fragment` |
| finney.calendar.eternitywall.com | HTTP 200 OK | 191 bytes | `calendar_proofs/finney.calendar.eternitywall.com.ots-fragment` |

## What This Proves

The file digest `1752958a...` has been submitted to **three independent
calendar servers** at the timestamp above. Each calendar will, within the
next few hours, aggregate this digest into a Merkle tree and embed the
root in a Bitcoin transaction. The resulting Bitcoin block (with its
miner-stamped time) provides cryptographic proof that:

1. The exact contents of `preregister.hash` existed at submission time.
2. By extension, all 28 files under `runbook/` that hash to
   `6102513b...` existed in the form they have now.
3. No file under `runbook/` (analysis script, statistical thresholds,
   workload specs, infrastructure code) could have been tweaked
   post-hoc to favor a particular outcome.

## Upgrading to Bitcoin Proof

The current fragments are **calendar-pending**. To upgrade to a
**Bitcoin-anchored** proof (~3 hour wait for block confirmation):

```bash
# On Linux, WSL, or Docker (avoids the Windows DLL bug):
docker run -v $(pwd)/calendar_proofs:/proofs python:3.11 bash -c "
    pip install opentimestamps-client
    cd /proofs
    for f in *.ots-fragment; do
        ots upgrade $f
        ots verify $f
    done
"
```

After upgrade, each fragment will contain a path from your digest to a
Bitcoin block hash. The reviewer can then verify independently using
any Bitcoin full-node or a public block explorer.

## Reviewer Verification Recipe

A reviewer (any third party with network access) can re-verify the
submission like this:

```bash
# Step 1: clone the runbook
git clone <repo> && cd runbook/

# Step 2: recompute the hash, confirm it matches preregister.hash
bash scripts/preregister.sh
# Must produce: 6102513b8a1407865e9b2b2c700c143b06b7a6b3e978f152b81a5d53e88d36e7

# Step 3: verify the calendar fragments
ots verify timestamping/calendar_proofs/*.ots-fragment

# Step 4: independently confirm Bitcoin block timestamp
# Look up the block hash referenced in any verified fragment on
# blockchain.info, mempool.space, or any Bitcoin block explorer.
```

If the block timestamp predates the run's T+0:00 (when the orchestrator
script applied the Terraform config), the pre-registration is valid.

## Honesty Disclosure for the Paper

The Reproducibility appendix should contain a brief note:

> Pre-registration of all analysis parameters (α=0.001, Wilson 99% CI,
> Holm-Bonferroni, fixed sample, no-peeking, primary/secondary tests)
> was committed to three OpenTimestamps calendars on 2026-06-01T03:26:52Z,
> which is prior to the run's T+0:00. The hash
> `6102513b...` covers the entire `runbook/` directory including the
> statistical analysis script, infrastructure code, and pre-registered
> exclusion criteria. Bitcoin-anchored proof fragments are published
> at the S3 reproducibility bucket.
