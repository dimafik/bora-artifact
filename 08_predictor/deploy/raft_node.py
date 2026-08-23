"""
raft_node.py — Real multi-process Raft node with TCP sockets.

Each node runs as a separate OS process and communicates via real TCP
connections. Implements:
  - Randomized election timeout
  - RequestVote / AppendEntries RPCs
  - Real wall-clock RTT measurements
  - Byzantine telemetry injection (one node can lie)
  - AI-Augmented blacklist advice (consumed by leader)

Usage:
  python raft_node.py --node-id 0 --port 6000 \
    --peers 6001 6002 6003 6004 \
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
LOG_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Message protocol (JSON over length-prefixed TCP)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Raft node
# ---------------------------------------------------------------------------


@dataclass
class RaftState:
    node_id: int
    port: int
    peers: list[int]
    current_term: int = 0
    voted_for: int | None = None
    log: list[dict] = field(default_factory=list)
    role: str = "follower"   # follower / candidate / leader
    leader_id: int | None = None
    election_timeout_ms: float = 0.0
    last_heartbeat: float = 0.0
    blacklist: set = field(default_factory=set)  # AI-augmented
    is_byzantine: bool = False
    ai_augmented: bool = False
    # Telemetry collected per peer
    rtt_samples: dict = field(default_factory=dict)  # peer_id -> list[ms]
    cc_samples: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)


class RaftNode:
    def __init__(self, state: RaftState):
        self.state = state
        self.lock = threading.Lock()
        self.log_path = LOG_DIR / f"node_{state.node_id}.log"
        self.metrics_path = LOG_DIR / f"node_{state.node_id}.metrics.json"
        self.running = True
        self.state.election_timeout_ms = random.uniform(150, 300)
        self.state.last_heartbeat = time.time()
        for p in state.peers:
            self.state.rtt_samples[p] = []
            self.state.cc_samples[p] = []
        self.state.metrics = dict(
            elections_started=0, votes_cast=0,
            leader_changes=0, ai_blacklist_events=0,
            byzantine_advice_rejected=0,
            rtt_p99=[], cc_mean=[],
        )

    def log(self, msg: str) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(f"{time.time():.4f} [node-{self.state.node_id}] [{self.state.role}] term={self.state.current_term} :: {msg}\n")

    # ----- Server loop -----
    def serve(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", self.state.port))
        srv.listen(64)
        srv.settimeout(0.1)
        while self.running:
            try:
                client, _ = srv.accept()
                threading.Thread(target=self.handle_request, args=(client,), daemon=True).start()
            except socket.timeout:
                continue
        srv.close()

    def handle_request(self, sock: socket.socket) -> None:
        try:
            msg = recv_msg(sock)
            if msg is None:
                return
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
        sender = msg.get("from")
        term = msg.get("term", 0)
        # Term update rule
        if term > self.state.current_term:
            self.state.current_term = term
            self.state.role = "follower"
            self.state.voted_for = None
        if mtype == "RequestVote":
            return self.handle_request_vote(msg)
        elif mtype == "AppendEntries":
            return self.handle_append_entries(msg)
        return None

    def handle_request_vote(self, msg: dict) -> dict:
        candidate = msg["from"]
        term = msg["term"]
        granted = False
        if term >= self.state.current_term and self.state.voted_for in (None, candidate):
            # Blacklist check (AI-augmented)
            if self.state.ai_augmented and candidate in self.state.blacklist:
                self.state.metrics["byzantine_advice_rejected"] += 1
                self.log(f"vote DENIED for {candidate} (blacklisted)")
            else:
                granted = True
                self.state.voted_for = candidate
                self.state.metrics["votes_cast"] += 1
                self.log(f"vote GRANTED to {candidate}")
        return dict(type="RequestVoteResponse", term=self.state.current_term,
                    granted=granted, from_=self.state.node_id)

    def handle_append_entries(self, msg: dict) -> dict:
        leader = msg["from"]
        term = msg["term"]
        # If from current leader
        if term >= self.state.current_term:
            self.state.role = "follower"
            self.state.leader_id = leader
            self.state.last_heartbeat = time.time()
            if leader != self.state.leader_id:
                self.state.metrics["leader_changes"] += 1
            # Process advice (blacklist)
            advice = msg.get("advice")
            if self.state.ai_augmented and advice is not None:
                new_blacklist = set(advice.get("blacklist", []))
                if new_blacklist != self.state.blacklist:
                    self.state.blacklist = new_blacklist
                    self.state.metrics["ai_blacklist_events"] += 1
            return dict(type="AppendEntriesResponse", term=self.state.current_term,
                        success=True, from_=self.state.node_id)
        return dict(type="AppendEntriesResponse", term=self.state.current_term,
                    success=False, from_=self.state.node_id)

    # ----- Election loop -----
    def election_loop(self) -> None:
        while self.running:
            time.sleep(0.020)
            with self.lock:
                role = self.state.role
                elapsed_ms = (time.time() - self.state.last_heartbeat) * 1000
            if role == "follower" and elapsed_ms > self.state.election_timeout_ms:
                self.start_election()
            elif role == "leader":
                self.send_heartbeats()
                time.sleep(0.030)

    def start_election(self) -> None:
        with self.lock:
            self.state.current_term += 1
            self.state.role = "candidate"
            self.state.voted_for = self.state.node_id
            self.state.metrics["elections_started"] += 1
            self.state.last_heartbeat = time.time()
            self.state.election_timeout_ms = random.uniform(150, 300)
            term = self.state.current_term
            self.log(f"starting election (term {term})")
        votes = 1  # self-vote
        # Send RequestVote to all peers in parallel
        threads = []
        results = []

        def request_vote(peer_port: int) -> None:
            try:
                t0 = time.time()
                with socket.create_connection(("127.0.0.1", peer_port), timeout=0.5) as s:
                    send_msg(s, dict(type="RequestVote", term=term,
                                     from_=self.state.node_id))
                    resp = recv_msg(s)
                rtt_ms = (time.time() - t0) * 1000
                if resp and resp.get("granted"):
                    results.append((peer_port, True, rtt_ms))
                else:
                    results.append((peer_port, False, rtt_ms))
            except Exception:
                results.append((peer_port, False, None))

        for p in self.state.peers:
            th = threading.Thread(target=request_vote, args=(p,), daemon=True)
            th.start(); threads.append(th)
        for th in threads:
            th.join(timeout=0.5)

        for peer_port, granted, rtt in results:
            if granted:
                votes += 1
            if rtt is not None:
                self.state.rtt_samples[peer_port].append(rtt)
                if len(self.state.rtt_samples[peer_port]) > 100:
                    self.state.rtt_samples[peer_port].pop(0)
        # Need majority
        with self.lock:
            n_total = 1 + len(self.state.peers)
            if votes > n_total // 2:
                self.state.role = "leader"
                self.state.leader_id = self.state.node_id
                self.state.metrics["leader_changes"] += 1
                self.log(f"WON election with {votes}/{n_total} votes")
            else:
                self.state.role = "follower"
                self.log(f"LOST election with {votes}/{n_total} votes")

    def send_heartbeats(self) -> None:
        term = self.state.current_term
        advice = None
        if self.state.ai_augmented:
            advice = dict(blacklist=list(self.compute_blacklist()))

        def send_hb(peer_port: int) -> None:
            try:
                t0 = time.time()
                with socket.create_connection(("127.0.0.1", peer_port), timeout=0.2) as s:
                    msg = dict(type="AppendEntries", term=term,
                               from_=self.state.node_id, advice=advice)
                    # Byzantine: lie about own RTT (inject lower reported RTT)
                    if self.state.is_byzantine:
                        msg["telemetry_rtt"] = 5.0  # lying low RTT
                    send_msg(s, msg)
                    resp = recv_msg(s)
                rtt_ms = (time.time() - t0) * 1000
                if resp and resp.get("success"):
                    self.state.rtt_samples[peer_port].append(rtt_ms)
                    if len(self.state.rtt_samples[peer_port]) > 100:
                        self.state.rtt_samples[peer_port].pop(0)
                    # Commit contribution
                    self.state.cc_samples[peer_port].append(1.0)
                else:
                    self.state.cc_samples[peer_port].append(0.0)
                if len(self.state.cc_samples[peer_port]) > 100:
                    self.state.cc_samples[peer_port].pop(0)
            except Exception:
                self.state.cc_samples[peer_port].append(0.0)

        threads = [threading.Thread(target=send_hb, args=(p,), daemon=True)
                   for p in self.state.peers]
        for th in threads:
            th.start()
        for th in threads:
            th.join(timeout=0.2)

    def compute_blacklist(self) -> set:
        """Memory-enabled detector: lag-1 autocorrelation of CC.
        Blacklist if low autocorrelation (likely Byzantine IID)."""
        blacklist = set()
        for peer, samples in self.state.cc_samples.items():
            if len(samples) < 16:
                continue
            arr = samples[-32:]
            # Lag-1 autocorrelation
            mean = sum(arr) / len(arr)
            num = sum((arr[i] - mean) * (arr[i+1] - mean) for i in range(len(arr)-1))
            den = sum((a - mean)**2 for a in arr)
            if den < 1e-6:
                continue
            ac = num / den
            # Risk: 1 - |ac|; flag if risk > 0.7 (low autocorr → IID/Byzantine)
            if abs(ac) < 0.3:
                blacklist.add(peer)
        return blacklist

    def metrics_logger(self) -> None:
        while self.running:
            time.sleep(2.0)
            with self.lock:
                snapshot = dict(
                    timestamp=time.time(),
                    role=self.state.role,
                    term=self.state.current_term,
                    leader_id=self.state.leader_id,
                    blacklist=list(self.state.blacklist),
                    metrics=dict(self.state.metrics),
                    rtt_p99={p: sorted(rs)[int(0.99 * len(rs))]
                             if len(rs) > 10 else None
                             for p, rs in self.state.rtt_samples.items()},
                    cc_mean={p: sum(cs)/len(cs) if cs else None
                             for p, cs in self.state.cc_samples.items()},
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
    ap.add_argument("--peers", type=int, nargs="+", required=True)
    ap.add_argument("--byzantine", action="store_true")
    ap.add_argument("--ai-augmented", action="store_true")
    args = ap.parse_args()
    state = RaftState(node_id=args.node_id, port=args.port,
                      peers=args.peers,
                      is_byzantine=args.byzantine,
                      ai_augmented=args.ai_augmented)
    node = RaftNode(state)
    print(f"Node {args.node_id} starting on port {args.port} "
          f"(byzantine={args.byzantine}, ai_augmented={args.ai_augmented})")
    node.run()


if __name__ == "__main__":
    main()
