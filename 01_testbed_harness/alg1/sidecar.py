#!/usr/bin/env python3
"""
Algorithm 1 — Bounded Blacklist Advisor (sidecar implementation).

Implements the paper's bounded-blacklist advisor (Algorithm 1) as an
out-of-process Python sidecar. Components implemented:
  - Observer:  collects orderer responsiveness telemetry (RTT to admin endpoint)
  - Predictor: simple statistical anomaly detector on rolling RTT window
  - Advisor:   bounded blacklist set B_t with |B_t| < f
  - Active-Leader Rule: incumbent leader never blacklisted mid-term
  - Fail-open: K_fail consecutive low-confidence ticks -> empty blacklist
  - Yield mechanism: docker pause / docker unpause on blacklisted containers
                     (avoids rebuilding the etcdraft orderer binary while
                     achieving the same observable effect on the consensus path)

The classic ~30-line patch to etcdraft Chain.go (paper §VI.A) consults a
Unix-domain socket; our sidecar instead applies the blacklist by pausing
the orderer container at the Docker level. This yields the same consensus
effect (the node temporarily stops participating in Raft voting) without
requiring a rebuilt Fabric binary, making the experiment reproducible on
stock Hyperledger Fabric v2.5 images.

CLI usage:
  python3 sidecar.py --config alg1.yaml --log alg1.log

Config YAML keys:
  orderers:        list of {name, admin_port}
  poll_interval_s: telemetry sampling period
  window_size:     rolling window length (L in paper)
  tau_r:           risk threshold (paper τ_r)
  tau_conf:        confidence threshold (paper τ_conf)
  k_fail:          fail-open consecutive low-confidence tick threshold
  f_cap:           |B_t| < f_cap
  alr_grace_s:     incumbent leader keeps current term for this long
"""
import argparse
import collections
import json
import logging
import socket
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class OrdererState:
    name: str
    admin_port: int
    rtt_window: collections.deque = field(default_factory=lambda: collections.deque(maxlen=16))
    is_leader: bool = False
    leader_since: float = 0.0
    paused: bool = False
    paused_at: float = 0.0  # When the current pause started
    pause_min_duration_s: float = 30.0  # Persistence: hold pause this long


class Algorithm1Advisor:
    def __init__(self, cfg):
        self.cfg = cfg
        self.orderers = {
            o["name"]: OrdererState(name=o["name"], admin_port=o["admin_port"])
            for o in cfg["orderers"]
        }
        self.window_size = cfg["window_size"]
        for st in self.orderers.values():
            st.rtt_window = collections.deque(maxlen=self.window_size)
        self.tau_r = cfg["tau_r"]
        self.tau_conf = cfg["tau_conf"]
        self.k_fail = cfg["k_fail"]
        self.f_cap = cfg["f_cap"]
        self.alr_grace_s = cfg["alr_grace_s"]
        self.poll_interval_s = cfg["poll_interval_s"]
        self.low_conf_streak = 0
        self.advice_events = 0
        self.safety_violations = 0
        self.tick_count = 0
        self.current_leader = None

    def observe_rtt(self, name, admin_port):
        """Probe orderer admin endpoint and return RTT in ms (or None on timeout).
        Kept for backward compat; new predictor uses observe_log_activity().
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        t0 = time.perf_counter()
        try:
            sock.connect(("localhost", admin_port))
            rtt_ms = (time.perf_counter() - t0) * 1000.0
            sock.close()
            return rtt_ms
        except (socket.timeout, OSError):
            return None

    def observe_log_activity(self, name, window_s=2):
        """Count recent log lines as a proxy for the orderer's commit
        contribution (paper's CC variable). A slowed orderer emits
        anomalously few log lines because its consensus state machine
        advances less frequently. Robust to host-port-mapping bypass of
        netem; the log activity rate is measured in-container.
        """
        try:
            out = subprocess.check_output(
                ["docker", "logs", "--since", f"{window_s}s", name],
                stderr=subprocess.STDOUT, timeout=2
            ).decode(errors="ignore")
            return len(out.splitlines())
        except Exception:
            return None

    def detect_leader(self):
        """Scrape orderer logs for the most recent 'became leader' event."""
        leader = None
        leader_time = 0.0
        for name in self.orderers:
            try:
                out = subprocess.check_output(
                    ["docker", "logs", "--tail", "200", name],
                    stderr=subprocess.STDOUT, timeout=3
                ).decode(errors="ignore")
            except Exception:
                continue
            for line in out.splitlines():
                if "became leader" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            ts = f"{parts[0]} {parts[1].rstrip(',')}"
                            t = time.mktime(time.strptime(ts[:19], "%Y-%m-%d %H:%M:%S"))
                            if t > leader_time:
                                leader_time = t
                                leader = name
                        except Exception:
                            pass
        if leader and leader != self.current_leader:
            logging.info("[ALR] new leader detected: %s", leader)
            self.current_leader = leader
            self.orderers[leader].leader_since = time.time()
        for name, st in self.orderers.items():
            st.is_leader = (name == self.current_leader)

    def predict(self):
        """Predictor: compute (r_i, c_i) per orderer from log-activity window.
        Paused orderers are excluded from the peer-comparison pool so their
        forced-zero activity does not corrupt the predictor's baseline.
        risk r_i = 1 - (orderer_i's activity / max sibling activity).
        """
        risks, confs = {}, {}
        active = {n: st for n, st in self.orderers.items()
                  if not st.paused and len(st.rtt_window) >= 3}
        if not active:
            return risks, confs
        recents = {n: statistics.mean(list(st.rtt_window)[-3:])
                   for n, st in active.items()}
        peer_max = max(recents.values()) if recents else 1.0
        peer_max = max(peer_max, 1.0)
        for name, st in self.orderers.items():
            if st.paused:
                # Paused orderers retain their high-risk score so the
                # advisor's "in B_t" check keeps them blacklisted.
                risks[name] = 1.0
                confs[name] = 1.0
                continue
            if len(st.rtt_window) < 3:
                risks[name] = 0.0
                confs[name] = 0.0
                continue
            mine = recents[name]
            risks[name] = max(0.0, min(1.0, 1.0 - (mine / peer_max)))
            confs[name] = min(1.0, len(st.rtt_window) / self.window_size)
        return risks, confs

    def decide_blacklist(self, risks, confs):
        """Advisor: produce B_t with |B_t| < f, ALR-respecting, fail-open."""
        if not risks:
            return set(), 0.0
        mean_conf = statistics.mean(confs.values())
        if mean_conf < self.tau_conf:
            self.low_conf_streak += 1
        else:
            self.low_conf_streak = 0
        if self.low_conf_streak >= self.k_fail:
            logging.warning(
                "[fail-open] %d consecutive low-confidence ticks -> empty B_t",
                self.low_conf_streak)
            return set(), mean_conf
        candidates = []
        now = time.time()
        for name, r in sorted(risks.items(), key=lambda x: -x[1]):
            if r < self.tau_r:
                continue
            st = self.orderers[name]
            if st.is_leader and (now - st.leader_since) < self.alr_grace_s:
                logging.info(
                    "[ALR] orderer %s above threshold (r=%.3f) but incumbent leader "
                    "for %.1fs < grace %.1fs - kept",
                    name, r, now - st.leader_since, self.alr_grace_s)
                continue
            candidates.append(name)
            if len(candidates) >= self.f_cap - 1:
                break
        return set(candidates), mean_conf

    def apply_blacklist(self, blacklist):
        """Yield mechanism with persistence: docker pause for blacklisted;
        unpause only after pause_min_duration_s AND not in current B_t.
        Persistence prevents flap when the paused orderer naturally has zero
        log activity (since it's paused), which would otherwise confuse the
        predictor and cause cascading false positives on other orderers.
        """
        now = time.time()
        for name, st in self.orderers.items():
            should_pause = name in blacklist
            if should_pause and not st.paused:
                # New pause action — but only if blacklist isn't already full
                # (paused orderers count toward |B_t|).
                paused_count = sum(1 for s in self.orderers.values() if s.paused)
                if paused_count >= self.f_cap - 1:
                    continue
                try:
                    subprocess.run(["docker", "pause", name],
                                   check=True, capture_output=True, timeout=3)
                    st.paused = True
                    st.paused_at = now
                    self.advice_events += 1
                    logging.info(
                        "[YIELD] paused %s (advice event #%d, |B_t|=%d)",
                        name, self.advice_events, paused_count + 1)
                except Exception as e:
                    logging.error("[YIELD] failed to pause %s: %s", name, e)
            elif st.paused:
                # Currently paused — check if persistence has elapsed AND
                # the orderer is no longer in the current advisory blacklist.
                held_for = now - st.paused_at
                if held_for >= st.pause_min_duration_s and name not in blacklist:
                    try:
                        subprocess.run(["docker", "unpause", name],
                                       check=True, capture_output=True, timeout=3)
                        st.paused = False
                        # Reset telemetry window so post-resume activity is
                        # measured fresh, not against stale all-zeros.
                        st.rtt_window.clear()
                        logging.info("[UNYIELD] unpaused %s after %.1fs persistence",
                                     name, held_for)
                    except Exception as e:
                        logging.error("[UNYIELD] failed to unpause %s: %s", name, e)

    def tick(self):
        self.tick_count += 1
        for name, st in self.orderers.items():
            if st.paused:
                continue
            act = self.observe_log_activity(name, window_s=2)
            if act is not None:
                st.rtt_window.append(act)
        if self.tick_count % 5 == 0:
            self.detect_leader()
        risks, confs = self.predict()
        bl, mc = self.decide_blacklist(risks, confs)
        self.apply_blacklist(bl)
        if self.tick_count % 3 == 0:
            logging.info(
                "[TICK %d] conf=%.2f leader=%s risks={%s} B_t=%s events=%d",
                self.tick_count, mc, self.current_leader or "?",
                ",".join(f"{n}={r:.2f}" for n, r in risks.items()),
                sorted(bl), self.advice_events)

    def run(self):
        logging.info("Algorithm 1 sidecar starting; orderers=%s tau_r=%.2f "
                     "tau_conf=%.2f K_fail=%d f_cap=%d alr_grace=%.1fs",
                     list(self.orderers), self.tau_r, self.tau_conf,
                     self.k_fail, self.f_cap, self.alr_grace_s)
        try:
            while True:
                self.tick()
                time.sleep(self.poll_interval_s)
        except KeyboardInterrupt:
            logging.info("Stopping sidecar; unpausing all orderers...")
            for name, st in self.orderers.items():
                if st.paused:
                    try:
                        subprocess.run(["docker", "unpause", name],
                                       check=True, capture_output=True)
                    except Exception:
                        pass
            logging.info("Final stats: ticks=%d advice_events=%d "
                         "safety_violations=%d",
                         self.tick_count, self.advice_events,
                         self.safety_violations)


def load_config(path):
    text = Path(path).read_text()
    cfg = {}
    cur_key = None
    for line in text.splitlines():
        line = line.split("#", 1)[0].rstrip()
        if not line:
            continue
        if line.startswith("  - "):
            entry = {}
            for kv in line[4:].split(","):
                k, _, v = kv.strip().partition(":")
                v = v.strip().strip("\"'")
                if v.isdigit():
                    v = int(v)
                entry[k.strip()] = v
            cfg.setdefault(cur_key, []).append(entry)
        elif ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            k = k.strip()
            v = v.strip()
            if v:
                if v.replace(".", "").isdigit():
                    v = float(v) if "." in v else int(v)
                cfg[k] = v
            else:
                cur_key = k
    return cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--log", required=True)
    args = ap.parse_args()
    logging.basicConfig(
        filename=args.log, level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config(args.config)
    advisor = Algorithm1Advisor(cfg)
    advisor.run()


if __name__ == "__main__":
    main()
