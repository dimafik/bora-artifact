# BORA artefact package

Backing data for *BORA: A Bounded Order-Risk Advisor for Provably Safe
ML-Augmented Leader Election in Raft Consensus* (IEEE TNSE).

## Included in full

- `05_formal`
- `08_predictor`
- `11_potency`
- `01_testbed_harness`
- `12_leader_severity`

## Included by file type

- `02_results_raw` — .csv, .json, .md, .txt, plus the `elections.log`
  of the six forced-election runs named in the next section
- `03_caliper` — .json, .yaml, .yml, .md
- `10_figures` — .py, .md, .sh

## Which runs back the exclusion claim

The exclusion figure (Fig. 5a, the operator-supplied panel) is built from four
runs, 92 guarded elections in total with 0 acquisitions by the target. The
figure's baseline counts are listed here too, so the identification can be
checked in both columns rather than one.

| Configuration | Directory | Baseline | Guarded | Live |
|---|---|---|---|---|
| N=5 single-host | `02_results_raw/finalsupp_20260611-144542` | 7/36 | 0/36 | 36/36 |
| N=7 scaling | `02_results_raw/nsweep_N7_121812` | 7/20 | 0/20 | 20/20 |
| N=9 scaling | `02_results_raw/nsweep_N9_122911` | 4/20 | 0/20 | 20/20 |
| physical 5-host AWS | `02_results_raw/xhost_election_154824` | 2/16 | 0/16 | 16/16 |

`01_testbed_harness/alg1/mk_fig_exclusion_stack.py` carries the same four pairs.
Each directory now also ships its `elections.log`, one line per forced election
in the form `[arm] eN: <old leader> -> <new leader>`, so the counts above can be
recomputed by hand.

The two starred rows of Fig. 5a come from `nsweep.sh`, which injects no delay:
their target is a healthy orderer, and the caption says so. The paper's exposure
bound does not rest on these 92. It rests on the closed-loop sweep,
`02_results_raw/x1_N*` — 480 guarded elections at N=7,9,11,15,21 with the target
degraded in every stratum and the blacklist produced by the detector, 0
acquisitions, 476 of 480 electing a leader. The load sweep (74) is in
`02_results_raw/loadsweep_*`.

### The other N=7 runs

Two further N=7 runs from the same session are in this package, and the paper
uses neither.

- `nsweep_N7_115333` — liveness 0/10 in *both* arms. The harness reads the
  leader by grepping each orderer's log for `Raft leader changed`; it found
  none, so the run recorded no election outcome in either arm.
- `nsweep_N7_120309` — the target won 3/20 in the baseline arm and 3/20 under
  the blacklist.

`120309` is the run described in the response letter under "Corrections we made
without being asked" (item 2). Its guarded arm scored 3/20, the chance share of a
six-candidate field and exactly what a guard that had failed open would produce.
Why is not recorded: diagnostics written within minutes of it checked whether the
sidecars survived pause/unpause, and the next run (`121812`, the one in Fig. 5(a))
scored 0/20, but the harness of `120309` was later overwritten. It is counted as a
guard failure of unrecorded cause. The same history exists at N = 5: on the day of
`finalsupp_20260611-144542`, five development runs (`leaderacq4_*`, `leaderacq6_*`,
`votereject_*`) showed no exclusion (guarded 8/47, unguarded 10/47); their healers
judged a sidecar alive by its socket file, which a dead sidecar leaves behind.
`finalsupp` is the first run whose harness checked the sidecar process.

Why the two arms match is not recoverable from this package. `nsweep.sh` prints
`sidecars: <k>/<N>` at bring-up but does not write it to `summary.txt`, so the
run carries no record of whether its sidecars were up, and an orderer whose
advisor is unreachable fails open by design and runs as vanilla Raft. The
harness is not the difference: `nsweep.sh.orig` is the only other version
present and differs from `nsweep.sh` only in a port-table refactor that is
numerically identical for N<=9. The closed-loop campaign preserves bring-up
logs, sidecar state and per-arm raft logs in full, so the same question is
answerable from files there. Both runs ship their `elections.log`.

Other forced-election runs here are outside the 92 for reasons of their own:

- `votereject_20260611-143542` — a null result, and previously mis-described
  here. Its `summary.txt` reads `BORA [3]: orderer3 won 3/15` against
  `base []: orderer3 won 4/15`, which is no effect. It did **not** isolate the
  vote-grant guard: `vote_reject_test.sh` runs the v4 orderer, which carries
  both guards, and nothing in it disables the tick guard. Its healer also tests
  only `test -S` on the socket file, which `final_suppression.sh` later
  identified as insufficient ("a stale socket file is not a live advisor; every
  prior run fail-opened on dead sidecars"), so the advisor was not verified live
  and both guards fail open together when it is not. The run therefore bears on
  advisor liveness, not on which guard is necessary. The paper reports it that
  way; the earlier claim that it showed "complete exclusion requires both
  guards" has been removed from both.
- `auto6h_run` (EXP-A, six runs) — an early configuration; the target won 1 to 3
  per 12.
- `leaderacq*` — pilot runs of 3 to 12 elections; the target won in all but
  `leaderacq4_20260611-135740` (0/4).
- `leaderacq_20260611-134900` — the columns in its `results.csv` are shifted, so
  the win and liveness fields cannot be recovered from it.
- `leaderscn2_20260611-134257` — only the baseline arm ran.
- `INVALID_*` and `archive/` — excluded by name, and throughput rather than
  election experiments.

## A defect we left in place

`08_predictor/predictor/train.py` splits train, val and test by offsetting seed
buckets by +1000 and +2000, then expands each seed into four scenario variants
by adding i*1000. The two offsets are the same size, so the buckets intersect:
three of val's four scenario blocks and two of test's four sit inside the
training set, and the val/test metrics the script prints are optimistic.

No number in the paper rests on them. Detection is measured live
(`02_results_raw/mldetect_*`, `02_results_raw/x1_N*`), and Table IV comes from
`08_predictor/r11_necessity_baselines.py`, which splits at seed offsets 0 and
10,000 -- a gap the scenario stride of at most 3,000 cannot bridge.

We left the script as it ran rather than correcting it. The deployed checkpoint
was trained by this code, and a corrected split here would describe a model the
shipped weights are not.

## The detector-swap sweep

`02_results_raw/b20_sweep_20260903-162221/` is the closed-loop campaign run a
second time with a zero-parameter mean-RTT threshold where the Transformer
normally sits. Six runs, N = 7, 9, 11, 15, 21, 21, four seeds of ten elections
each: 240 forced elections per arm, the same size as the published campaign.
The target wins 24/240 unguarded and 0/240 under the threshold, matching the
learned advisor. That directory's README states what the run does and does not
show; the short version is that it establishes the bound, not the detector.

The advisor's per-cycle log ships gzipped (53,031 lines, 13 MB raw, 0.4 MB
compressed) because the precision figures rest on it and a summary would not
let a reader check them. `partial_N15_run4.log` is an aborted first attempt at
N=15, kept as a record and deliberately outside the aggregator's file glob.

## The two detection runs, and which one the paper uses

`02_results_raw/` holds two runs from the same session, and the paper reports
one of them.

- `mldetect_20260611-171955` (159 lines) is the reported run. Its first logged
  cycle reads `Bt=[] ... o3:0.85(rtt0)`: every orderer healthy, blacklist empty.
- `mldetect_20260611-171546` (163 lines) is **not** reported. Its first logged
  cycle already reads `Bt=[3] ... o3:0.42(rtt499)`, so residual delay from the
  preceding experiment was still on orderer 3 when the daemon started and the
  run had no clean baseline to detect against.

Both ship. The selection rule is the one stated: a run whose baseline is already
contaminated at T0 cannot measure detection latency from a clean state. The
reported figures are therefore a single 84 s run, which the paper now says in a
footnote.

## The September 2026 cross-host runs

Three directories were added after the first release, all measured on a
five-host EC2 cluster with one orderer per instance, the load generator on a
machine of its own, `netem` given an explicit `limit 10000`, and a bounded-state
Caliper workload. That rig holds a clean baseline to **0.069%** over an hour and
44 consecutive measurements. Each carries its own README; this is the map.

| directory | what it measures | where it lands |
|---|---|---|
| `01_testbed_harness/alg1/xhost_detect_2026-09-13/` | detection latency, held fraction and false positives across hosts, three runs | **the manuscript** — the Section V-B sentence reporting 3.3-4.6 s, 92-94% held and 0 of 2,028, and the Section V-A inventory line that no longer says detection rests on one host |
| `11_potency/xhost_remeasure_2026-09-14/` | what the evasion sequences do to the ordering service, re-measured on instrumentation that removes three of the original's four objections | **the response letter only**, R3-S4. The fourth objection stands and no rig fixes it |
| `01_testbed_harness/alg1/expB_2026-09-14/` | whether the guard buys measurable throughput over a horizon containing forced elections — six runs | **nowhere.** No claim in the paper or the letter rests on it |

The rig scripts these share are in `01_testbed_harness/alg1/`
(`xhost_setup_all.sh`, `xhost_calibrate.sh`, `xhost_caliper.sh`,
`xhost_caliper_net.sh`, `xhost_cc_or.sh`, `local_setup.sh`,
`score_xhost.py`, `score_xhost2.py`) rather than copied into each run
directory; one-shot drivers live with the run they produced.

Two things in these directories are corrections rather than additions, and are
recorded here because they change what an earlier file said.

- **`netem`'s default queue.** Runs before 2026-09-14 injected delay with
  `tc qdisc replace ... netem delay ${d}ms`, which takes a queue of 1000
  packets. Above roughly `limit / delay` packets per second that queue overflows
  and netem drops, so the injected fault is delay *and* loss. Measured with the
  default, a +200 ms delayed follower appeared to cost 68% of clean throughput;
  with `limit 10000` it costs **0.14%** (that re-calibration's Caliper output was
  not archived). The September campaign runs set the limit explicitly; the
  isolation control `expB_2026-09-14/evidence/04_isolation_no_elections/` did not
  read the qdisc back and is void as a delay measurement.
  `expB_2026-09-14/evidence/03_xhost_pilot_default_queue/` is the run that
  shows the artifact.
- **A mislabelled results file.** `11_potency/xhost_remeasure_2026-09-14/
  potency_xhost.sh` read Caliper's *max* latency into a column called `lat_avg`
  and its *min* into one called `lat_max`, and never recorded the average at
  all — the number the response letter reports. The parser is fixed and
  `results.csv` is re-derived from `caliper_lines.txt`, the instrument's own
  output, which ships beside it. Success, failure and block counts are
  unchanged and were checked row by row.

## Deliberately omitted

Bulk transcripts and rendered assets that no number in the paper depends on. They are reproducible from the scripts included here.


## Removed after the first release

`07_theory_scripts` (180 files) and six files at the top of `05_formal`
(`ISRaftMC*.tla`, `TLA_PLUS_VERIFICATION_LOG.md`, `Apalache_README.md`, and the
old `05_formal/README.md`) were shipped in error. They belong to a different
paper on mixed-criticality scheduling: mode switching, CPL/PSR, schedulability,
KZG witness commitments. Checked before removal — files in `07_theory_scripts`
mentioning BORA: **0**; times the BORA manuscript references that directory:
**0**. Removed 2026-08-26.

A caveat on that test. This project's own working directory was named
`IS-Raft-LAC` before the system was renamed to BORA, and that fragment still
appears in 36 files here: 15 TLC logs, 12 shell scripts, 7 Python scripts, one
text file, and this manifest. (`git grep -l IS-Raft-LAC | wc -l`.) Those paths
refer to *this* work, not to the removed paper, so "files mentioning BORA: 0"
shows only that the rename post-dates them. The logs are kept verbatim because
they are records of runs that actually happened; editing them would
misrepresent what was executed.

`09_runbook_aws` (34 files) was removed on the same grounds. Its README is
"5-Hour AWS Fabric Live Experiment — Schedulable Byzantine Consensus", its
playbooks deploy a BRAO sidecar, its packer image builds Fabric **2.5.4**, and
`preregister.hash` with its OpenTimestamps proof anchors *that* design. None of
it produced a number in this paper. The physical five-host runs were driven by
`01_testbed_harness/alg1/xhost_bora_election.sh`, which SSHes to five
hand-provisioned hosts and hot-swaps the patched Fabric **v3.1.4** binary — no
terraform, no ansible, no packer. Checked before removal — files in
`09_runbook_aws` mentioning BORA: **3** (`caliper/benchmark-e{1,2,3}.yaml`);
times anything else in this repository referenced those three: **0**; times the
BORA manuscript references that directory: **0**. Removed 2026-09-03.

173 files under `08_predictor/` were removed on the same grounds: its old
`README.md` and five design documents (`PREDICTOR_SPEC.md`,
`THEORETICAL_FOUNDATION.md`, `WHY_AI_NECESSARY.md`,
`AUGMENTATION_THEOREM.md`, `AWS_EXPERIMENT_DESIGN_v26.md`), `paper/`
(4 files), `tla/` (3) and `simulation/` (160). They belong to an earlier
project of ours built on a different consensus algorithm, and their
vocabulary describes the opposite of what BORA does: that README opened
with a thesis of learning a sub-leader ranking function *inside* the
consensus path, and a table whose "Blockchain core touched?" row read
"Yes -- consensus ranking function". BORA is a bounded advisor outside
that path that can only remove candidacy. `paper/` additionally held draft
manuscript sections for that other project, and `tla/` a specification
`05_formal/` supersedes. Checked before removal -- times any remaining file
in this repository references any of those paths: **0** (eight path
patterns, swept). Removed 2026-09-06.

That check looked inside this repository and nowhere else, and it was not
enough: the manuscript cited one of the removed files, the capacity sweep in
`simulation/gen_fig7_v40_ucurve.py`. That sweep was run on a PBFT benchmark
rather than on this paper's Fabric testbed, so the claim was withdrawn from the
paper rather than the files restored. The removal stands and nothing in the
manuscript depends on them.

Kept deliberately, and why: `08_predictor/predictor/` is the training code
the deployed checkpoint came from and this manifest cites it above;
`08_predictor/deploy/` holds the Dockerfile, helm chart and multi-region
manifests that Section III-H uses; `model_*/`, `data_small/` and
`necessity_output/` are read by scripts that remain. A new
`08_predictor/README.md` maps what is left to the claim each part supports.

## Not included, by policy

Private keys and credentials are excluded by pattern (`*.pem`, `*.key`, `*.ppk`, `id_rsa*`, `*.pfx`, `*.p12`) and the package is re-scanned after assembly. The scan found none.
