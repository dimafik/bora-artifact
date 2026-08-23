# Pre-registration Timestamping

The pre-register hash `aaf44c91...` must be anchored to an immutable
external service BEFORE T+0:00 so that reviewers can verify it was
committed before any data was collected.

## Three-tier strategy (defense in depth)

### Tier A — OpenTimestamps (gold standard)

Anchors the hash into the Bitcoin blockchain. ~3 hour latency to confirmation;
proof file is self-verifying without trusting any third party.

```bash
pip install opentimestamps-client
ots stamp preregister.hash
# Wait ~3h for Bitcoin confirmation
ots upgrade preregister.hash.ots
# Anyone can later verify:
ots verify preregister.hash.ots
```

### Tier B — Public Git commit + GitHub gist

Anchors the hash to GitHub's append-only commit history.

```bash
# Push to a public branch:
git checkout -b preregister/$RUN_ID
git add preregister.hash
git commit -m "Preregister hash for run $RUN_ID"
git push origin preregister/$RUN_ID

# Or create a gist:
gh gist create preregister.hash --public \
  --desc "sched-bft preregister $RUN_ID $(date -Iseconds)"
```

### Tier C — Local proof.txt + multi-mirror

If A and B both fail, write a proof file locally and mirror to multiple
locations (email to self, archive.org Wayback, IPFS pin).

## Use

```bash
bash commit_timestamp.sh   # before T+0:00
bash verify_timestamp.sh   # after run, or by any auditor
```

## What this protects against

Reviewers asking: "Did you do post-hoc tweaking of your stats?"

The cryptographic commit timestamps **predate** the experiment. The
runbook contents (including the analysis script, statistical thresholds,
and stopping rule) cannot have been changed after the timestamp without
breaking the hash.

## What this does NOT protect against

- An attacker who controls both the timestamp services AND the wall clock
  on the local machine. (Bitcoin anchoring makes this prohibitively
  expensive — would require >50% hashrate attack.)
- Disclosure of post-hoc additions clearly marked as "exploratory" rather
  than pre-registered. (Pre-registration only locks the pre-registered
  analyses; exploratory results are allowed but must be honestly labeled.)
