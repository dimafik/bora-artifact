# Which advisor produced which result

Five advisor implementations sit in this repository. They are not variants of
one program kept for convenience: each was written for a different experiment,
and two of them implement substep (d) of Algorithm 1 differently from the paper.
A reader comparing an arbitrary one against Algorithm 1 would reasonably
conclude the paper and the code disagree. This file says which is which.

| file | what it produced | status |
|---|---|---|
| `predictor_daemon_n.py` | **the closed-loop sweep**: 720 forced elections, N = 7--21, the 0/240 exclusion | **the evaluated build** |
| `predictor_daemon_meanrtt.py` | the B-20 detector swap, WSL-side variant below | current, secondary |
| `predictor_daemon_meanrtt_wsl.py` | the B-20 sweep as run (`02_results_raw/b20_sweep_20260903-162221`) | current, secondary |
| `../../08_predictor/predictor_daemon.py` | the in-loop detection trace of Fig. 4 / Section V-B | superseded; see its own header |
| `sidecar.py` | no reported number | early prototype |

## Where the implementations differ from Algorithm 1

**The cap.** `predictor_daemon_n.py` applies substep (c) as written,
`cap = max(0, f - r - 1)`, and logs `r` and the applied cap every cycle;
`02_results_raw/cap_audit/` checks all 50,440 of them. The two `meanrtt` files
copy that code unchanged. `08_predictor/predictor_daemon.py` applies a *static*
`fcap=2` that ignores `r`, which is why its header marks it superseded and why
no closed-loop cap result comes from it. `sidecar.py` uses a configured
`f_cap` and likewise ignores `r`.

**The fail-open counter.** Algorithm 1 substep (d) counts consecutive rounds in
which `B_t` came out empty and, on reaching `K_fail`, emits an explicit
`fail_open` flag. `sidecar.py` instead counts consecutive ticks whose *mean
confidence* falls below `tau_conf` and returns an empty set without the flag --
a different trigger and a different payload. `predictor_daemon_n.py` runs
neither: it emits a fixed `fail_open: False`. That gap is not hidden, it is
what Section II means by "the evaluated build does not realise it. It emits a
fixed fail-open flag instead of running the counter." The counter is a design
requirement in this paper, not a measured property, and `sidecar.py` should not
be read as the reference for it.

**The yield mechanism.** `sidecar.py` yields by `docker pause` / `docker
unpause` on the blacklisted container, which avoids rebuilding the orderer
binary. Everything reported end-to-end uses the patched binary and the
in-orderer election-guard hook instead. Lemma 4 in the paper relates the two:
both project into vanilla Raft, the pause path onto a trace in which the node
is additionally crash-stopped.

## The one to read against Algorithm 1

    01_testbed_harness/alg1/predictor_daemon_n.py

It is the file the headline exclusion result came from, it is the one whose cap
matches substep (c) line for line, and its per-cycle log is the input to
`02_results_raw/cap_audit/`.
