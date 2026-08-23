"""
run_deploy.py — Orchestrate a real 5-node Raft deployment and measure
operational metrics. Spawns 5 raft_node.py processes, runs them for
DURATION_SEC, then aggregates metrics from logs/.

Scenarios:
  (a) Vanilla 5-node Raft (no Byzantine, no AI)
  (b) Vanilla + 1 Byzantine node (lies about RTT)
  (c) AI-Augmented Raft + 1 Byzantine node
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
LOG_DIR = HERE / "logs"
RESULTS_DIR = HERE / "deploy_results"
PYTHON = sys.executable


def run_scenario(scenario: str, duration_sec: int = 30, n_nodes: int = 5):
    """scenario in {'vanilla', 'byzantine', 'ai_byzantine'}."""
    if LOG_DIR.exists():
        shutil.rmtree(LOG_DIR)
    LOG_DIR.mkdir()
    base_port = 7000
    ports = [base_port + i for i in range(n_nodes)]
    processes = []
    for i, p in enumerate(ports):
        peers = [pp for pp in ports if pp != p]
        cmd = [PYTHON, str(HERE / "raft_node.py"),
               "--node-id", str(i), "--port", str(p),
               "--peers"] + [str(pp) for pp in peers]
        if scenario in ("byzantine", "ai_byzantine") and i == n_nodes - 1:
            cmd.append("--byzantine")
        if scenario == "ai_byzantine":
            cmd.append("--ai-augmented")
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        processes.append(proc)
    print(f"[{scenario}] Spawned {len(processes)} nodes; running {duration_sec}s")
    time.sleep(duration_sec)
    # Terminate
    for proc in processes:
        try:
            proc.terminate()
        except Exception:
            pass
    for proc in processes:
        try:
            proc.wait(timeout=2.0)
        except Exception:
            proc.kill()
    # Aggregate metrics
    return aggregate_metrics(scenario, n_nodes)


def aggregate_metrics(scenario: str, n_nodes: int) -> dict:
    """Read each node's metrics file and aggregate."""
    elections = 0
    leader_changes = 0
    blacklist_events = 0
    byzantine_advice_rejected = 0
    leaders_observed = set()
    byzantine_ever_leader = False
    rtt_all = []
    for i in range(n_nodes):
        mfile = LOG_DIR / f"node_{i}.metrics.json"
        if not mfile.exists():
            continue
        try:
            with mfile.open("r", encoding="utf-8") as f:
                m = json.load(f)
        except Exception:
            continue
        leaders_observed.add(m.get("leader_id"))
        if m.get("leader_id") == n_nodes - 1:  # Byzantine node ID
            byzantine_ever_leader = True
        elections += m["metrics"].get("elections_started", 0)
        leader_changes += m["metrics"].get("leader_changes", 0)
        blacklist_events += m["metrics"].get("ai_blacklist_events", 0)
        byzantine_advice_rejected += m["metrics"].get("byzantine_advice_rejected", 0)
        for p, val in (m.get("rtt_p99") or {}).items():
            if val is not None:
                rtt_all.append(val)
    return dict(
        scenario=scenario,
        elections=elections,
        leader_changes=leader_changes,
        blacklist_events=blacklist_events,
        byzantine_advice_rejected=byzantine_advice_rejected,
        unique_leaders=len(leaders_observed),
        byzantine_was_leader=byzantine_ever_leader,
        median_rtt_p99=float(sorted(rtt_all)[len(rtt_all)//2]) if rtt_all else None,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=int, default=20)
    ap.add_argument("--n-nodes", type=int, default=5)
    args = ap.parse_args()
    RESULTS_DIR.mkdir(exist_ok=True)
    all_results = []
    for scenario in ["vanilla", "byzantine", "ai_byzantine"]:
        result = run_scenario(scenario, args.duration, args.n_nodes)
        print(f"  Result: {json.dumps(result, indent=2)}")
        all_results.append(result)
    out_file = RESULTS_DIR / "deploy_results.json"
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults: {out_file}")
    # Generate REPORT
    md = ["# v28 Real Multi-Process Raft Deployment Results", ""]
    md.append("Each row = real 5-node Raft cluster running for given duration "
              "with actual TCP sockets, election timers, and heartbeats.")
    md.append("")
    md.append("| Scenario | Elections | Leader changes | Blacklist events | Byz advice rejected | Unique leaders | Byz was leader? | Median p99 RTT (ms) |")
    md.append("|---|---:|---:|---:|---:|---:|:---:|---:|")
    for r in all_results:
        rtt_str = f"{r['median_rtt_p99']:.2f}" if r['median_rtt_p99'] is not None else "n/a"
        byz_str = "YES" if r['byzantine_was_leader'] else "NO"
        md.append(f"| {r['scenario']} | {r['elections']} | {r['leader_changes']} | "
                  f"{r['blacklist_events']} | {r['byzantine_advice_rejected']} | "
                  f"{r['unique_leaders']} | {byz_str} | {rtt_str} |")
    (RESULTS_DIR / "REPORT.md").write_text("\n".join(md) + "\n",
                                            encoding="utf-8")
    print(f"Report: {RESULTS_DIR / 'REPORT.md'}")


if __name__ == "__main__":
    main()
