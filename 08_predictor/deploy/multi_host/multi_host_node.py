"""
multi_host_node.py — Multi-host (multi-region) Raft node.

Extends raft_node.py with explicit per-pair WAN latency injection,
simulating multi-region AWS-style deployment on a single physical
host. Each node is assigned a "region" and inter-region delays are
applied to every outgoing message based on the published AWS
inter-region latency matrix (2024 measurements).

Topology example (5 nodes, 3 regions):
  node 0,1 in us-east-1
  node 2,3 in eu-west-1
  node 4   in ap-northeast-1
  intra-region delay: 1-2 ms
  us-east-1 <-> eu-west-1: 80 ms
  us-east-1 <-> ap-northeast-1: 150 ms
  eu-west-1 <-> ap-northeast-1: 220 ms

Usage:
  python multi_host_node.py --node-id 0 --port 7000 \
    --region us-east-1 \
    --peers 7001:us-east-1 7002:eu-west-1 7003:eu-west-1 7004:ap-northeast-1 \
    [--byzantine] [--ai-augmented]
"""

from __future__ import annotations

import argparse
import json
import random
import socket
import struct
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


# Published AWS multi-region RTT matrix (ms), 2024 measurements
REGION_RTT_MS = {
    ("us-east-1", "us-east-1"): 1.5,
    ("us-east-1", "us-west-2"): 65,
    ("us-east-1", "eu-west-1"): 80,
    ("us-east-1", "ap-northeast-1"): 150,
    ("us-east-1", "ap-southeast-1"): 220,
    ("us-west-2", "us-west-2"): 1.5,
    ("us-west-2", "eu-west-1"): 140,
    ("us-west-2", "ap-northeast-1"): 100,
    ("eu-west-1", "eu-west-1"): 1.5,
    ("eu-west-1", "ap-northeast-1"): 220,
    ("eu-west-1", "ap-southeast-1"): 170,
    ("ap-northeast-1", "ap-northeast-1"): 1.5,
    ("ap-northeast-1", "ap-southeast-1"): 70,
    ("ap-southeast-1", "ap-southeast-1"): 1.5,
}


def inter_region_rtt(a: str, b: str) -> float:
    """Look up inter-region RTT (symmetric)."""
    key = (a, b) if (a, b) in REGION_RTT_MS else (b, a)
    return REGION_RTT_MS.get(key, 100.0)  # default 100 ms unknown


def send_msg(sock: socket.socket, msg: dict) -> None:
    data = json.dumps(msg).encode()
    sock.sendall(struct.pack("!I", len(data)) + data)


def recv_msg(sock: socket.socket) -> dict | None:
    hdr = sock.recv(4)
    if len(hdr) < 4:
        return None
    n = struct.unpack("!I", hdr)[0]
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return json.loads(buf.decode())


@dataclass
class MultiHostState:
    node_id: int
    port: int
    region: str
    peer_regions: dict  # port -> region
    current_term: int = 0
    voted_for: int | None = None
    role: str = "follower"
    leader_id: int | None = None
    election_timeout_ms: float = 0.0
    last_heartbeat: float = 0.0
    blacklist: set = field(default_factory=set)
    is_byzantine: bool = False
    ai_augmented: bool = False
    rtt_samples: dict = field(default_factory=dict)
    cc_samples: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)


class MultiHostRaftNode:
    def __init__(self, state: MultiHostState):
        self.state = state
        self.lock = threading.Lock()
        self.log_path = LOG_DIR / f"mh_node_{state.node_id}.log"
        self.metrics_path = LOG_DIR / f"mh_node_{state.node_id}.metrics.json"
        self.running = True
        # WAN-aware election timeout (longer for multi-region)
        self.state.election_timeout_ms = random.uniform(800, 1500)
        self.state.last_heartbeat = time.time()
        for p in state.peer_regions:
            self.state.rtt_samples[p] = []
            self.state.cc_samples[p] = []
        self.state.metrics = dict(
            elections_started=0, votes_cast=0, leader_changes=0,
            ai_blacklist_events=0, byzantine_advice_rejected=0,
        )

    def log(self, msg: str) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(f"{time.time():.4f} [mh-{self.state.node_id}/{self.state.region}] "
                    f"[{self.state.role}] term={self.state.current_term} :: {msg}\n")

    def wan_delay(self, peer_port: int) -> float:
        """Compute WAN delay to peer based on regions."""
        peer_region = self.state.peer_regions[peer_port]
        rtt_total = inter_region_rtt(self.state.region, peer_region)
        return (rtt_total / 2) / 1000  # one-way in seconds

    def serve(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", self.state.port))
        srv.listen(64)
        srv.settimeout(0.1)
        while self.running:
            try:
                client, _ = srv.accept()
                threading.Thread(target=self.handle_request,
                                 args=(client,), daemon=True).start()
            except socket.timeout:
                continue
        srv.close()

    def handle_request(self, sock: socket.socket) -> None:
        try:
            msg = recv_msg(sock)
            if msg is None:
                return
            # Simulate INBOUND WAN delay (jitter included)
            sender_port = msg.get("from_port", 0)
            if sender_port in self.state.peer_regions:
                delay = self.wan_delay(sender_port) * (1 + random.gauss(0, 0.05))
                time.sleep(max(0, delay))
            with self.lock:
                response = self.process_message(msg)
            if response is not None:
                send_msg(sock, response)
        except Exception as e:
            self.log(f"handle_request error: {e}")
        finally:
            sock.close()

    def process_message(self, msg: dict) -> dict | None:
        mtype = msg.get("type")
        term = msg.get("term", 0)
        if term > self.state.current_term:
            self.state.current_term = term
            self.state.role = "follower"
            self.state.voted_for = None
        if mtype == "RequestVote":
            return self.handle_vote(msg)
        elif mtype == "AppendEntries":
            return self.handle_append(msg)
        return None

    def handle_vote(self, msg: dict) -> dict:
        candidate = msg["from"]
        term = msg["term"]
        granted = False
        if term >= self.state.current_term and self.state.voted_for in (None, candidate):
            if self.state.ai_augmented and candidate in self.state.blacklist:
                self.state.metrics["byzantine_advice_rejected"] += 1
                self.log(f"vote DENIED for {candidate} (blacklisted)")
            else:
                granted = True
                self.state.voted_for = candidate
                self.state.metrics["votes_cast"] += 1
        return dict(type="RequestVoteResponse", term=self.state.current_term,
                    granted=granted, from_=self.state.node_id)

    def handle_append(self, msg: dict) -> dict:
        leader = msg["from"]
        term = msg["term"]
        if term >= self.state.current_term:
            prev_leader = self.state.leader_id
            self.state.role = "follower"
            self.state.leader_id = leader
            self.state.last_heartbeat = time.time()
            if prev_leader != leader and prev_leader is not None:
                self.state.metrics["leader_changes"] += 1
            advice = msg.get("advice")
            if self.state.ai_augmented and advice is not None:
                new_bl = set(advice.get("blacklist", []))
                if new_bl != self.state.blacklist:
                    self.state.blacklist = new_bl
                    self.state.metrics["ai_blacklist_events"] += 1
            return dict(type="AppendEntriesResponse", term=self.state.current_term,
                        success=True, from_=self.state.node_id)
        return dict(type="AppendEntriesResponse", term=self.state.current_term,
                    success=False, from_=self.state.node_id)

    def election_loop(self) -> None:
        while self.running:
            time.sleep(0.050)
            with self.lock:
                role = self.state.role
                elapsed = (time.time() - self.state.last_heartbeat) * 1000
            if role == "follower" and elapsed > self.state.election_timeout_ms:
                self.start_election()
            elif role == "leader":
                self.send_heartbeats()
                time.sleep(0.150)  # WAN-aware heartbeat interval

    def start_election(self) -> None:
        with self.lock:
            self.state.current_term += 1
            self.state.role = "candidate"
            self.state.voted_for = self.state.node_id
            self.state.metrics["elections_started"] += 1
            self.state.last_heartbeat = time.time()
            self.state.election_timeout_ms = random.uniform(800, 1500)
            term = self.state.current_term
            self.log(f"starting election (term {term})")
        votes = 1
        results = []
        threads = []

        def request_vote(peer_port: int) -> None:
            try:
                # Outbound WAN delay
                delay = self.wan_delay(peer_port) * (1 + random.gauss(0, 0.05))
                time.sleep(max(0, delay))
                t0 = time.time()
                with socket.create_connection(("127.0.0.1", peer_port),
                                              timeout=2.0) as s:
                    send_msg(s, dict(type="RequestVote", term=term,
                                     from_=self.state.node_id,
                                     from_port=self.state.port))
                    resp = recv_msg(s)
                rtt = (time.time() - t0) * 1000
                results.append((peer_port, resp and resp.get("granted"), rtt))
            except Exception:
                results.append((peer_port, False, None))

        for p in self.state.peer_regions:
            th = threading.Thread(target=request_vote, args=(p,), daemon=True)
            th.start(); threads.append(th)
        for th in threads:
            th.join(timeout=2.5)
        for peer_port, granted, rtt in results:
            if granted:
                votes += 1
            if rtt is not None:
                self.state.rtt_samples[peer_port].append(rtt)
                if len(self.state.rtt_samples[peer_port]) > 100:
                    self.state.rtt_samples[peer_port].pop(0)
        with self.lock:
            n_total = 1 + len(self.state.peer_regions)
            if votes > n_total // 2:
                self.state.role = "leader"
                self.state.leader_id = self.state.node_id
                self.log(f"WON election with {votes}/{n_total} votes")
            else:
                self.state.role = "follower"
                self.log(f"LOST election with {votes}/{n_total} votes")

    def send_heartbeats(self) -> None:
        term = self.state.current_term
        advice = None
        if self.state.ai_augmented:
            advice = dict(blacklist=list(self.compute_blacklist()))

        def hb(peer_port: int) -> None:
            try:
                delay = self.wan_delay(peer_port) * (1 + random.gauss(0, 0.05))
                time.sleep(max(0, delay))
                t0 = time.time()
                with socket.create_connection(("127.0.0.1", peer_port),
                                              timeout=1.0) as s:
                    msg = dict(type="AppendEntries", term=term,
                               from_=self.state.node_id,
                               from_port=self.state.port, advice=advice)
                    if self.state.is_byzantine:
                        msg["telemetry_rtt"] = 5.0  # lying
                    send_msg(s, msg)
                    resp = recv_msg(s)
                rtt = (time.time() - t0) * 1000
                self.state.rtt_samples[peer_port].append(rtt)
                if len(self.state.rtt_samples[peer_port]) > 100:
                    self.state.rtt_samples[peer_port].pop(0)
                cc = 1.0 if resp and resp.get("success") else 0.0
                self.state.cc_samples[peer_port].append(cc)
                if len(self.state.cc_samples[peer_port]) > 100:
                    self.state.cc_samples[peer_port].pop(0)
            except Exception:
                self.state.cc_samples[peer_port].append(0.0)

        threads = [threading.Thread(target=hb, args=(p,), daemon=True)
                   for p in self.state.peer_regions]
        for th in threads:
            th.start()
        for th in threads:
            th.join(timeout=1.5)

    def compute_blacklist(self) -> set:
        bl = set()
        for peer, samples in self.state.cc_samples.items():
            if len(samples) < 16:
                continue
            arr = samples[-32:]
            mean = sum(arr) / len(arr)
            num = sum((arr[i] - mean) * (arr[i+1] - mean) for i in range(len(arr)-1))
            den = sum((a - mean)**2 for a in arr)
            if den < 1e-6:
                continue
            ac = num / den
            if abs(ac) < 0.3:
                bl.add(peer)
        return bl

    def metrics_logger(self) -> None:
        while self.running:
            time.sleep(2.0)
            with self.lock:
                snapshot = dict(
                    timestamp=time.time(),
                    region=self.state.region,
                    role=self.state.role,
                    term=self.state.current_term,
                    leader_id=self.state.leader_id,
                    blacklist=list(self.state.blacklist),
                    metrics=dict(self.state.metrics),
                    rtt_p99={p: sorted(rs)[min(int(0.99*len(rs)), len(rs)-1)]
                             if len(rs) > 5 else None
                             for p, rs in self.state.rtt_samples.items()},
                )
            with self.metrics_path.open("w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2)

    def run(self) -> None:
        threads = [
            threading.Thread(target=self.serve, daemon=True),
            threading.Thread(target=self.election_loop, daemon=True),
            threading.Thread(target=self.metrics_logger, daemon=True),
        ]
        for th in threads:
            th.start()
        try:
            while self.running:
                time.sleep(1.0)
        except KeyboardInterrupt:
            self.running = False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--node-id", type=int, required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--region", type=str, required=True)
    ap.add_argument("--peers", type=str, nargs="+", required=True,
                    help="Format: port:region")
    ap.add_argument("--byzantine", action="store_true")
    ap.add_argument("--ai-augmented", action="store_true")
    args = ap.parse_args()
    peer_regions = {}
    for spec in args.peers:
        port_s, region = spec.split(":")
        peer_regions[int(port_s)] = region
    state = MultiHostState(
        node_id=args.node_id, port=args.port, region=args.region,
        peer_regions=peer_regions, is_byzantine=args.byzantine,
        ai_augmented=args.ai_augmented)
    node = MultiHostRaftNode(state)
    print(f"Multi-host node {args.node_id} in {args.region} on port {args.port}")
    node.run()


if __name__ == "__main__":
    main()
