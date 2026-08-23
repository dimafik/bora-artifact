# Pre-Registration Anchoring — User Action Required

The `opentimestamps-client` is installed and ready. The actual network call
to OTS calendar servers (which commits the hash to the Bitcoin blockchain)
was held back for explicit user authorization, since:

1. It transmits the runbook hash to public servers.
2. It is **irreversible** — once anchored, the commitment cannot be retracted.
3. Re-anchoring with the same hash creates a 2nd, redundant proof.

## Recommended one-liner (run when ready)

```bash
cd "submission/runbook"
ots stamp preregister.hash
# wait ~3 hours for Bitcoin confirmation
ots upgrade preregister.hash.ots
# at any later time, anyone can verify:
ots verify preregister.hash.ots
```

The output `preregister.hash.ots` is a small binary file (~500 bytes) that
contains an independent cryptographic proof anchored to Bitcoin's block
chain. It is self-verifying — no need to trust OTS, AWS, or this conversation.

## Current artifacts (no exfiltration required)

| File | Purpose |
|---|---|
| `preregister.hash` | SHA-256 of all 28 runbook files |
| `preregister.proof.txt` | Local timestamp + verification recipe (no network call) |
| `scripts/preregister.sh` | Recompute hash for verification |
| `timestamping/verify_timestamp.sh` | One-command auditor verification |

## What to do AFTER the run completes (T+5:00)

1. Push `preregister.hash` + `preregister.hash.ots` to the public S3 bucket
   alongside the raw data and `REPORT.md`.
2. Include the OTS proof URL in the manuscript's Reproducibility section.
3. Reviewers verify by downloading `preregister.hash.ots` and running
   `ots verify`. They get a Bitcoin-anchored timestamp predating any data
   collection.

## Why this matters

A reviewer asks: "Did you cherry-pick stats post-hoc?"

You answer: "Here is a Bitcoin block hash that incorporates a SHA-256 of my
entire analysis pipeline, timestamped before any tx ran. The block height
is X, mined at time T. Any change to a single byte of my analysis would
break the hash. Reviewer can reproduce: clone repo, run `ots verify`."

The reviewer can no longer claim post-hoc tweaking without accusing you
of forging a Bitcoin proof — a position no honest reviewer takes.
