# Addendum 01 to PREREG_R25C — invalid run 1, and a warm-up precondition

The pre-registration says it may not be changed once run 1 has started, and that
any change must be recorded in a superseding note that says what changed and
why. Run 1 has started and failed, so this is that note.

**Nothing about the measurement changed.** The delay parameter, the arms, the
endpoints, the analysis, the sample-size stages and the falsification condition
are all exactly as registered. What is added is a precondition check that runs
*before* measurement, in the same spirit as the existing `verify_clean`.

## 1. Run 1 — invalid, with reason

- Output: `results/r25c_20260824-173515/`
- Started 2026-08-24T08:35:15Z, exited rc=1 at 08:38:54Z
- Failure: `C_clean: ledger delta=0 -- NOTHING COMMITTED, measurement invalid`

Cause, from `caliper_C_clean.log`:

    EndorseError: 9 FAILED_PRECONDITION: no combination of peers can be
    derived which satisfy the endorsement policy

The chaincode was installed on both peers with the same package ID, both orgs
had approved, and the committed policy is the default
`/Channel/Application/Endorsement` (a majority). What was missing was the
running chaincode *container* on `peer0.org1`: a peer launches it lazily, on the
first endorsement it is asked for. The container came up during the run
(observed as `Up 4 minutes` immediately afterwards, against `Up 2 days` for
org2), by which time the 30-second round had already failed every transaction.

This is counted as an invalid run under §6 of the pre-registration and is
replaced, not silently dropped. It is very likely the same failure as
`r25b_20260810-233024`, which died with the identical `ledger delta=0` line.

## 2. Added precondition: warm-up

Before each run, both peers are asked a **read-only** query
(`GetAllAssets`), which starts the chaincode container without committing
anything. Measurement proceeds only if both peers answer; otherwise the attempt
is aborted before any load is applied. Script: `warmup.sh`, run by the campaign
runner, not by the harness.

Rationale for putting it outside the harness: `r25_leader_cost3.sh` is
hash-registered (`c997d7b0…9a30`) and unchanged. The guard is part of the
campaign procedure, like the 45-second settle between runs.

## 3. Effect on the registered plan

None. The stages remain pilot 6 → 12 → conditional 18, counted in **valid** runs
as defined in §6. Invalid attempts are reported with their reason in the final
table; this addendum is the first entry.
