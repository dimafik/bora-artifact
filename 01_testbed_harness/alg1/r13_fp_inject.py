#!/usr/bin/env python3
"""False-positive injector for the R1-3 interface experiment.

R1-3 asks how BORA compares with AWARE / BFTBrain.  We do not reimplement those
systems; we put THEIR interface (the learner has first-class authority over who
leads) on OUR substrate, so the only variable is where the learner's output
enters the protocol.  The experiment then asks the one question that separates
the two interfaces: what does a WRONG prediction cost?

This script supplies the wrong predictions.  It reads the live predictor's
bt.json, adds false positives on healthy nodes according to a PRE-GENERATED
schedule, and writes the augmented advice to its own file.  The real detector is
never modified, and its true positives are passed through untouched.

Why a pre-generated schedule and not a coin flip at run time: every arm must see
the SAME false positives at the SAME offsets, or the comparison is unpaired and
the arm difference is confounded with RNG.  The schedule is a deterministic
function of (rate, seed, duration, N), so `--dump-schedule` reproduces it
exactly without running anything.

  r13_fp_inject.py --rate 10 --seed 1 --dur 300 --n 7 --target 3 \
                   --src /mnt/d/fabric-d2/results/bt.json \
                   --out /mnt/d/fabric-d2/results/bt_r13.json
"""
import argparse, json, os, random, re, sys, time

TICK = 1.0          # schedule granularity
PUSH = 0.3          # how often the augmented advice is rewritten


def schedule(rate_pct, seed, dur, n, target, fp_node=0):
    """[(t_offset, node)] — deterministic in (rate, seed, dur, n, target).

    fp_node pins WHICH healthy node the false positives name.  Uniform-random
    choice looked fairer but had no statistical power: leadership is not
    uniform across orderers (a 3x spread between healthy nodes is documented in
    this testbed), so a randomly chosen victim usually never wins an election in
    ANY arm, and "the guard excluded it" is indistinguishable from "it was never
    going to win".  Pinning the false positive to the measured front-runner puts
    the control where the outcome can actually differ -- and that is also the
    adversary the minimum-hold rule exists for, one that re-aims at whoever is
    about to win.
    """
    rng = random.Random("r13|%d|%d|%d|%d|%d" % (rate_pct, seed, dur, n, target))
    healthy = [i for i in range(1, n + 1) if i != target]
    out = []
    t = 0.0
    while t < dur:
        if rng.random() < rate_pct / 100.0:
            out.append((round(t, 1), fp_node if fp_node else rng.choice(healthy)))
        t += TICK
    return out


def read_true_bl(path):
    """True blacklist from the live predictor; [] if unreadable this instant."""
    try:
        with open(path, "r") as f:
            m = re.search(r'"blacklist"\s*:\s*\[([0-9, ]*)\]', f.read())
        if not m:
            return None
        return [int(x) for x in m.group(1).replace(" ", "").split(",") if x != ""]
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rate", type=int, required=True, help="false positives per 100 ticks")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--dur", type=int, required=True)
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--target", type=int, default=3)
    ap.add_argument("--src", default="/mnt/d/fabric-d2/results/bt.json")
    ap.add_argument("--out", default="/mnt/d/fabric-d2/results/bt_r13.json")
    ap.add_argument("--log", default="/mnt/d/fabric-d2/results/r13_fp.log")
    ap.add_argument("--hold", type=float, default=3.0,
                    help="seconds a false positive stays in force; must exceed one "
                         "forced-election cycle or the guard is never tested with it")
    ap.add_argument("--cap", type=int, default=0,
                    help="Algorithm 1's |B_t| <= f-r-1.  Without it the injector can "
                         "publish a blacklist the advisor itself would never emit, and "
                         "arm C would be answering for a protocol we did not describe.")
    ap.add_argument("--leader-file", default="",
                    help="when set, each false positive names whoever is leader at "
                         "that instant.  Aiming at a fixed non-incumbent measured the "
                         "guard but left the authority arm with nothing to do (it only "
                         "acts when the learner names the INCUMBENT); aiming at the "
                         "incumbent is also the attack ALR exists for.")
    ap.add_argument("--fp-node", type=int, default=0,
                    help="pin false positives to this orderer (the measured "
                         "front-runner); 0 = uniform random among healthy nodes")
    ap.add_argument("--dump-schedule", action="store_true")
    a = ap.parse_args()
    HOLD = a.hold

    sched = schedule(a.rate, a.seed, a.dur, a.n, a.target, a.fp_node)
    if a.dump_schedule:
        for t, node in sched:
            print("%.1f,%d" % (t, node))
        return

    lg = open(a.log, "a", buffering=1)
    lg.write("# start rate=%d seed=%d dur=%d n=%d target=%d events=%d\n"
             % (a.rate, a.seed, a.dur, a.n, a.target, len(sched)))
    t0 = time.time()
    last_bl, seq = [], 0
    while True:
        now = time.time() - t0
        if now > a.dur:
            break
        true_bl = read_true_bl(a.src)
        # A failed read means "no reading this instant", not "nothing is wrong":
        # keep the previous true set rather than silently clearing it.
        if true_bl is None:
            true_bl = last_bl
        else:
            last_bl = true_bl
        active = any(t <= now < t + HOLD for t, _ in sched)
        if a.leader_file:
            fps = []
            if active:
                try:
                    ldr = int(open(a.leader_file).read().strip() or 0)
                except Exception:
                    ldr = 0
                if ldr and ldr != a.target:
                    fps = [ldr]
        else:
            fps = sorted({node for t, node in sched if t <= now < t + HOLD})
        # True positives keep their places; false positives fill what is left of
        # the cap.  Publishing more than the cap would put arm C under a
        # blacklist Algorithm 1 could not have produced.
        merged = list(dict.fromkeys(list(true_bl) + fps))
        if a.cap > 0:
            merged = merged[:a.cap]
        fps = [x for x in fps if x in merged]
        merged = sorted(merged)
        seq += 1
        tmp = a.out + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"blacklist": merged, "seq": seq, "fail_open": False,
                       "true": true_bl, "fp": fps}, f)
        os.replace(tmp, a.out)
        if fps:
            lg.write("%.1f fp=%s true=%s merged=%s\n" % (now, fps, true_bl, merged))
        time.sleep(PUSH)
    lg.write("# done\n")


if __name__ == "__main__":
    main()
