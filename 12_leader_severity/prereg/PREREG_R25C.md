# Pre-registration — R25C: what a degraded *leader* costs (N=7, bracketed)

**Written before the first run of this campaign.** Nothing below may be changed
once run 1 has started; if something must change, this file is superseded by a
new one that says what changed and why, and the runs are reported separately.

- Harness: `alg1/r25_leader_cost3.sh` (derived from `r25_leader_cost2.sh`;
  differences are listed in §7)
- Cluster: the standing 7-orderer `mychannel` cluster, reused via `SKIP_SETUP=1`
- Injected delay: `+200 ms` on `orderer3.example.com` via pumba/netem
- Output prefix: `results/r25c_<timestamp>/`

---

## 1. Why this campaign exists

Reviewer 2, point 5:

> "The demonstrated practical gain is relatively narrow. The paper itself
> acknowledges that BORA is throughput-neutral rather than throughput-improving
> under follower delay, and the main measurable gain is the reduction of the
> targeted orderer's leadership-acquisition rate. It is not yet convincingly
> demonstrated that this translates into sufficiently broad system-level benefit."

The missing link is the cost of the event the guard prevents. One completed run
of the predecessor campaign (`r25b_20260810-233812`, N=5) measured it, and the
manuscript reports that single run. This campaign replaces it with a replicated
one, because the same testbed has documented run-to-run drift of about 20 %
(EC2 recovery reported as "+18 to +43 %" from two runs of one configuration),
and one run cannot distinguish a stable effect from a lucky draw.

## 2. Design

Three arms per run, measured back to back on the same cluster, plus a bracket:

| arm | condition |
|---|---|
| `C_clean` | no delay, whoever leads |
| `F_follower` | orderer3 delayed, a healthy node leads |
| `L_leader` | orderer3 delayed **and** leading |
| `C_clean_post` | no delay, end of run (bracket) |

Each arm is a Caliper sweep at offered 100/200/300/400/500 tx/s, 30 s per rate,
4 workers, `createAsset` workload, on a cluster whose committed-throughput
ceiling is about 570 tx/s. Throughput is cross-checked against ledger
block-height delta; a run whose delta is zero is invalid by construction.

`C_clean_post` serves two purposes: it bounds within-run drift (the three arms
always run in the same order, so drift would otherwise be charged to
`L_leader`), and because orderer3 is the leader by then with the delay off, it
separates "orderer3 is a slow node" from "the injected delay hurts when it
leads".

## 3. Endpoints

**Primary.** Per run, at offered 500 tx/s:

    R = committed_throughput(L_leader) / committed_throughput(C_clean)

**Secondary,** all per run at 500 tx/s unless stated:

- `Rf = throughput(F_follower) / throughput(C_clean)` — the follower-delay
  comparison the manuscript already makes
- failure fraction in `L_leader` = failed / submitted
- mean-latency ratio `L_leader / C_clean`
- `D = throughput(C_clean_post) / throughput(C_clean)` — the drift bracket
- the same quantities at 100, 200, 300, 400 tx/s

## 4. Analysis

Report per-run values in full; no run is dropped from the table.

Primary statistic is the **median of R across valid runs** with a 95 %
bootstrap CI (10,000 resamples, percentile method). The comparison is paired
within run, so no assumption is made about the absolute throughput level being
stable across runs. Secondary endpoints are summarised the same way.

The drift bracket is reported alongside: median `D` with its range. If median
`D < 0.90`, the fixed arm order is a material confound and `R` is reported with
that stated, not silently.

## 5. Sample size and the extension rule

Staged, and the stages are fixed here rather than chosen later.

1. **Pilot: 6 valid runs.** Purpose is feasibility and a variance estimate. No
   decision about the paper's claims is made at this gate.
2. **Main: to 12 valid runs total.**
3. **Extension to 18 valid runs, conditional and pre-specified:** run the
   extension if and only if, at 12 valid runs, the 95 % CI half-width on median
   `R` exceeds **0.05**. Otherwise stop at 12.

**Pooling.** The pilot's 6 runs are pooled with the main runs if and only if the
harness, the cluster configuration and the delay parameter are unchanged between
the stages. If anything changes, the pilot is reported separately and does not
enter the primary analysis.

**No interim peeking.** R is computed only at the two gates above. The direction
of the effect never triggers an extension; only the CI width does. This rule
exists because the manuscript already discloses one stratum (N=21) whose seed
count was extended after an unfavourable result, and that disclosure should not
have to be made twice.

## 6. Validity rules

A run is **invalid** and is replaced by another attempt if any of:

- `verify_clean` aborts (stale netem rule: orderer3 RTT above 50 ms with the
  attack nominally off)
- any arm commits nothing (ledger delta ≤ 0) — the harness exits on this
- pinning fails, so `L_leader` is skipped

Invalid runs are **counted and reported**, with the reason, not silently
discarded. A bracket that fails (`C_clean_post` skipped) does **not** invalidate
the run: the three main arms are already complete and written.

## 7. What differs from `r25_leader_cost2.sh`

1. `leader_id()` reads `consensus_etcdraft_is_leader` from each orderer's
   operations endpoint instead of scraping `Raft leader changed` from the
   container log. On this cluster the log form returns empty — no election has
   occurred in 11 days and the line is beyond a 20,000-line tail — and the
   caller would then restart orderer1 for all 40 pinning attempts.
2. `N=7` and the orderer list covers seven nodes. The cluster is a 7-consenter
   channel; rebuilding it as 5 was rejected because the bring-up path failed in
   5 of 7 attempts in the predecessor campaign and the channel carries 3,647
   blocks of unrelated state.
3. The `C_clean_post` bracket of §2.
4. Output prefix `r25c_` so this campaign is separable from `r25b_`.

Everything else, including the two safety rails (`verify_clean`, the ledger
-delta check) and the `trap` that always tears the attack down, is unchanged.

## 8. What would falsify the manuscript's claim

The manuscript says a delayed follower slows the channel while a delayed leader
stops it. That claim does not survive if the campaign returns **median R > 0.8**
— that is, if holding leadership while delayed costs less than 20 % of committed
throughput, which is what a delayed *follower* already costs. In that case the
severity paragraph is withdrawn from §V-D and the claim is not made in the
abstract, the contributions, or the conclusion.

A weaker but still adverse outcome is median `R` between 0.5 and 0.8: the
asymmetry would hold in direction but not in kind, and the wording "stops it"
would have to go.

## 9. N=7 versus the manuscript's N=5 number

The existing number (467.8 → 127.5 tx/s, −73 %) was measured at N=5. This
campaign runs at N=7 and therefore replaces it rather than adding to it. The
manuscript text will report the N=7 campaign with its replication count, and the
single N=5 run is retained in the artifact but not cited as a result.
