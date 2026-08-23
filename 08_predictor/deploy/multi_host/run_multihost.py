"""
run_multihost.py — Orchestrate multi-region Raft deployment.

5-node topology across 3 AWS regions:
  node 0,1 in us-east-1   (intra: 1.5 ms)
  node 2,3 in eu-west-1   (intra: 1.5 ms)
  node 4   in ap-northeast-1
  us-east-1 <-> eu-west-1: 80 ms
  us-east-1 <-> ap-northeast-1: 150 ms
  eu-west-1 <-> ap-northeast-1: 220 ms

3 scenarios:
  (a) vanilla
  (b) byzantine (node 4 = byzantine)
  (c) ai_byzantine
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
LOG_DIR = HERE / "logs"
RESULTS = HERE / "multihost_results"
PYTHON = sys.executable

TOPOLOGY = [
    (0, 8000, "us-east-1"),
    (1, 8001, "us-east-1"),
    (2, 8002, "eu-west-1"),
    (3, 8003, "eu-west-1"),
    (4, 8004, "ap-northeast-1"),
]


def run_scenario(scenario: str, duration: int) -> dict:
    if LOG_DIR.exists():
        shutil.rmtree(LOG_DIR)
    LOG_DIR.mkdir(parents=True)
    procs = []
    for (nid, port, region) in TOPOLOGY:
        peers = [(p, r) for (i, p, r) in TOPOLOGY if i != nid]
        peer_args = [f"{p}:{r}" for p, r in peers]
        cmd = [PYTHON, str(HERE / "multi_host_node.py"),
               "--node-id", str(nid), "--port", str(port),
               "--region", region, "--peers"] + peer_args
        if scenario in ("byzantine", "ai_byzantine") and nid == 4:
            cmd.append("--byzantine")
        if scenario == "ai_byzantine":
            cmd.append("--ai-augmented")
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        procs.append(p)
    print(f"[{scenario}] {len(procs)} multi-region nodes; running {duration}s")
    time.sleep(duration)
    for p in procs:
        try:
            p.terminate()
        except Exception:
            pass
    for p in procs:
        try:
            p.wait(timeout=2)
        except Exception:
            p.kill()
    return aggregate(scenario)


def aggregate(scenario: str) -> dict:
    elections = 0
    leader_changes = 0
    blacklist_events = 0
    byz_rejected = 0
    leaders = set()
    byz_was_leader = False
    rtts = []
    for (nid, _, region) in TOPOLOGY:
        mf = LOG_DIR / f"mh_node_{nid}.metrics.json"
        if not mf.exists():
            continue
        try:
            m = json.loads(mf.read_text(encoding="utf-8"))
        except Exception:
            continue
        leaders.add(m.get("leader_id"))
        if m.get("leader_id") == 4:
            byz_was_leader = True
        elections += m["metrics"].get("elections_started", 0)
        leader_changes += m["metrics"].get("leader_changes", 0)
        blacklist_events += m["metrics"].get("ai_blacklist_events", 0)
        byz_rejected += m["metrics"].get("byzantine_advice_rejected", 0)
        for _, v in (m.get("rtt_p99") or {}).items():
            if v is not None:
                rtts.append(v)
    return dict(
        scenario=scenario,
        elections=elections, leader_changes=leader_changes,
        blacklist_events=blacklist_events,
        byzantine_rejected=byz_rejected,
        unique_leaders=len(leaders),
        byzantine_was_leader=byz_was_leader,
        rtt_p99_median=float(sorted(rtts)[len(rtts)//2]) if rtts else None,
        rtt_p99_max=float(max(rtts)) if rtts else None,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=int, default=45)
    args = ap.parse_args()
    RESULTS.mkdir(exist_ok=True)
    all_r = []
    for sc in ["vanilla", "byzantine", "ai_byzantine"]:
        r = run_scenario(sc, args.duration)
        print(f"  Result: {json.dumps(r, indent=2)}")
        all_r.append(r)
    (RESULTS / "multihost_results.json").write_text(
        json.dumps(all_r, indent=2), encoding="utf-8")
    md = ["# v28 Multi-Region Cloud Raft Deployment (RD2)", ""]
    md.append("5-node deployment across 3 AWS regions (us-east-1, eu-west-1, ap-northeast-1).")
    md.append("WAN delays per AWS 2024 measurement matrix:")
    md.append("  - us-east-1 <-> eu-west-1: 80 ms")
    md.append("  - us-east-1 <-> ap-northeast-1: 150 ms")
    md.append("  - eu-west-1 <-> ap-northeast-1: 220 ms")
    md.append("")
    md.append("| Scenario | Elections | Leader chg | Unique leaders | Byz was leader? | p99 RTT median (ms) | p99 RTT max (ms) |")
    md.append("|---|---:|---:|---:|:---:|---:|---:|")
    for r in all_r:
        med = f"{r['rtt_p99_median']:.1f}" if r['rtt_p99_median'] else "n/a"
        mx = f"{r['rtt_p99_max']:.1f}" if r['rtt_p99_max'] else "n/a"
        byz = "YES" if r['byzantine_was_leader'] else "NO"
        md.append(f"| {r['scenario']} | {r['elections']} | {r['leader_changes']} | "
                  f"{r['unique_leaders']} | {byz} | {med} | {mx} |")
    (RESULTS / "REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\nReport: {RESULTS / 'REPORT.md'}")


if __name__ == "__main__":
    main()
