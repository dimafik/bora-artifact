# xhost_remeasure_2026-09-14 — the potency question, re-measured

The parent directory asks what an evasive delay pattern does to the ordering
service once it has beaten the detector, and answers "nothing measurable". That
answer is kept out of the manuscript because of how it was measured, not what it
found; the parent README lists three reasons. This directory removes two of them
and reports what is left.

**Nothing in the manuscript rests on this directory.** It backs the R3-S4
passage of the response letter.

## What changed

| the parent's limitation | here |
|---|---|
| load generator is `loadgen.sh`, not Caliper | Caliper 0.6.0, 8 workers, on a **c5.2xlarge of its own** |
| noise too large to trust −0.7% to −4.1% | clean baseline **0.069%** over an hour and 44 consecutive measurements (`calibration_1h.csv`) |
| unequal sample counts (n≈212 vs n≈464) | every condition submits the same volume; all 18 rounds commit **27,008** with **0** failures |
| closed-loop needs a standardisation the deployed daemon lacks | **unchanged** — see below |

## One correctness fix

The parent injected the tracks with

```
tc qdisc replace dev eth0 root netem delay ${d}ms
```

which takes netem's default queue of 1000 packets. A queue of that size holds
`rate x delay` packets in flight, so above roughly `limit / delay` packets per
second it overflows and netem **drops**. At the m500 scale that threshold is
about 2000 packets per second, and above it the injected fault is delay *and*
loss rather than delay.

Every qdisc here carries `limit 10000` and is read back after it is set.

## Two adaptations

**Five orderers, not seven.** `tracks_5col/` holds the first five columns of the
parent's `m500_*` tracks. The design property is intact: every orderer at the
same ~500 ms marginal, only orderer3's lag-1 autocorrelation varying.

| track | o3 autocorrelation | other orderers (mean) |
|---|---|---|
| healthy_white | 0.026 | −0.005 |
| pgd_rho_0.0 | 0.059 | −0.007 |
| pgd_rho_0.3 | 0.316 | 0.001 |
| pgd_rho_0.6 | 0.603 | 0.015 |
| pgd_rho_0.8 | 0.798 | −0.009 |
| attack_class_ar1 | 0.886 | −0.011 |

**Port-filtered injection.** These orderers run `--network host`, so a root
qdisc would delay the peer and the control path as well. A `prio` band filtered
on the consensus ports carries the netem instead. Measured with a 300 ms rule
standing: `orderer3:7050` **304.4 ms**, `peer0.org2:7051` **0.2 ms**.

## Result

`results.csv` (this run), `caliper_lines.txt` (Caliper's own report lines).
Three repetitions, condition order rotated each repetition, 180 s per condition
at 150 tx/s.

A note on `results.csv`, because it was wrong and is worth saying so. Caliper's
report line reads `| name | Succ | Fail | Send Rate | Max | Min | Avg |
Throughput |`, and `potency_xhost.sh` took the max into a column it called
`lat_avg` and the min into one it called `lat_max` — so the file claimed a
maximum smaller than its average and never carried the average at all, which is
the number reported below. The parser is fixed and `results.csv` is re-derived
from `caliper_lines.txt`, which ships here and is the instrument's own output;
success, failure and block counts are unchanged and were cross-checked row by
row against the file as it was written.

| track | o3 autocorrelation | committed | failed | mean latency |
|---|---|---|---|---|
| healthy_white | 0.026 | 27,008 | 0 | 0.490 s |
| **pgd_rho_0.0** (white-box AUC 0.003) | 0.059 | 27,008 | 0 | **0.490 s** |
| pgd_rho_0.3 | 0.316 | 27,008 | 0 | 0.483 s |
| pgd_rho_0.6 | 0.603 | 27,008 | 0 | 0.480 s |
| pgd_rho_0.8 | 0.798 | 27,008 | 0 | 0.477 s |
| attack_class_ar1 | 0.886 | 27,008 | 0 | 0.477 s |

Every condition commits the same number with no failures, so the whole signal is
in latency. There it spans **2.8%** while the spread attributable to a
condition's position in the rotation is **2.1%** — the two are not separable.

How fine the instrument is matters here, so the three-decimal means above should
not be read as three-decimal measurements. Caliper reports average latency to
**two** decimals, and across all eighteen rounds it emitted exactly three
distinct values: **0.47, 0.48 and 0.49 s**. Each mean above is three of those
averaged. That is a coarse instrument, and it is the right way to read the
result rather than a caveat against it: at a resolution of 0.01 s, the entire
spread between an adversary that defeated the detector outright and healthy
traffic is **at most two resolution steps**, and the healthy and `pgd_rho_0.0`
conditions never differ by even one. What movement there is runs the wrong way
for the alternative hypothesis: latency *falls* slightly as autocorrelation
rises.

## `saturated_300tps_discarded/` — the first attempt, void

Run at 300 tx/s. Failure rates ran from **6.1%** to **28.9%**, putting every
condition past the knee, and within-condition spread reached 24.7% against an
11.4% spread between conditions. The defect is visible from the failure counts alone, without
reference to the outcome. The operating point was lowered to 150 tx/s, where the
worst condition (`attack_class_ar1`) commits with zero failures, and the run
above is that measurement. The discarded run is kept here rather than deleted.

## What this does not settle

The closed-loop detection figures in the parent — the target sitting in the
blacklist at 3% of forced elections at ρ = 0 rising to 85% at AR(1) — depend on a
per-window standardisation that the deployed daemon does not perform. No change
of rig fixes that, and it is why the potency material remains in the response
letter rather than the manuscript. What is settled here is the containment half,
which needs no detector at all.

## Files

```
results.csv                     6 conditions x 3 repetitions, re-derived
                                from caliper_lines.txt (see the note above)
caliper_lines.txt               Caliper report lines, 18
summary.txt                     run log
calibration_1h.csv              44 consecutive clean measurements, spread 0.069%,
                                produced by ../../01_testbed_harness/alg1/xhost_calibrate.sh
tracks_5col/                    the six tracks, five columns each
saturated_300tps_discarded/     the void first attempt.  Its Caliper report
                                lines were not kept, so its two latency columns
                                are relabelled to what they hold (max, min) and
                                its average latency is not recoverable.  The
                                failure counts, which are why it is void, are
                                unaffected.
potency_xhost.sh                driver
potency_replay.sh               per-host track replay
updateAsset.js                  bounded-state Caliper workload
```

The rig these ran on is brought up by
`../../01_testbed_harness/alg1/xhost_setup_all.sh`, which is shared with the
Experiment B runs in `01_testbed_harness/alg1/expB_2026-09-14/` and lives there
rather than being copied into each run directory.
