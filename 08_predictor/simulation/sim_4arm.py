"""
sim_4arm.py -- 4-arm cascading-failure simulation for v27 manuscript.

Replays 100 paired leader-failure events through vanilla Raft + the
AI-augmented advice interface proposed in this paper. Loads the trained
predictor (model_xl2/best.pt) for ML heads. Outputs per-event recovery
time, Byzantine detection score, and degradation prediction for each
of the 4 arms:

  A: Vanilla Raft (random election timeout in [150, 300] ms, no advice)
  B: +Prediction head only (pre-promote via score-confidence)
  C: +Anomaly head (pre-promote + Byzantine blacklist)
  D: +Full ML (pre-promote + Byzantine + degradation warning)

Recovery-time model follows the Augmentation Safety Theorem of v27:
  - Vanilla Raft expected recovery: T_elect + RTT_quorum + 2*Delta,
    where T_elect ~ Uniform(T_MIN, T_MAX), typical [150, 300] ms.
  - AI-augmented case (a): pre-promote delivered → designated follower
    skips T_elect, recovery = RTT_quorum + 2*Delta.
  - AI-augmented case (b): pre-promote fails / advice ok=F → fall
    back to vanilla Raft path.

Output: results.json with per-event metrics + summary statistics.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).parent.parent / "predictor"))
from model import ScorePredictor  # noqa: E402

# =============================================================================
# Vanilla Raft constants (Ongaro 2014, etcd defaults)
# =============================================================================

T_ELECT_MIN, T_ELECT_MAX = 150, 300            # ms  randomised election timeout
RTT_QUORUM = 30                                 # ms one quorum-RTT for RequestVote
DELTA = 2                                       # ms intra-AZ heartbeat propagation
HEARTBEAT_MS = 50                               # ms heartbeat period
N_NODES = 5
F = 1                                           # crash/Byzantine bound

# =============================================================================
# Event simulator
# =============================================================================


@dataclass
class CascadingEvent:
    event_id: int
    leader_kill_offset_ms: float = 0.0
    primary_kill_offset_ms: float = 0.0  # relative to leader kill
    rng_seed: int = 0


@dataclass
class ArmResult:
    arm: str
    event_id: int
    recovery_time_ms: float
    pre_promote_succeeded: bool
    blacklist_size: int
    byzantine_node_flagged: bool   # arm-level: was the Byzantine node flagged?
    degrade_warning_issued: bool


def compute_baseline_recovery(rng: np.random.Generator) -> float:
    """Vanilla Raft baseline recovery: T_elect + RTT_quorum + 2*Delta + overhead.

    T_elect is the follower's randomised election timeout
    (Uniform(T_ELECT_MIN, T_ELECT_MAX)). On leader-heartbeat timeout the
    first follower whose timer fires invokes RequestVote and, on quorum
    grant, becomes the new leader.
    """
    t_elect = rng.uniform(T_ELECT_MIN, T_ELECT_MAX)
    rho_max = 0.5  # network utilisation
    overhead = DELTA / (1 - rho_max)
    return t_elect + RTT_QUORUM + 2 * DELTA + overhead


def compute_predict_recovery(
    rng: np.random.Generator,
    pre_promote_success: bool,
) -> float:
    """AI-Augmented Raft recovery.

    Case (a) — pre-promote succeeded: designated follower skips the
    randomised election timer and invokes RequestVote at t_kill + Delta;
    recovery = RTT_quorum + 2*Delta.

    Case (b) — pre-promote failed / advice ok=F: fall back to vanilla
    Raft path.
    """
    if pre_promote_success:
        return RTT_QUORUM + 2 * DELTA
    return compute_baseline_recovery(rng)


# =============================================================================
# Predictor wrapper
# =============================================================================


class PredictorWrapper:
    """Loads trained model and provides per-event advice."""

    def __init__(self, checkpoint_path: Path, device: str = "cpu"):
        self.device = device
        self.model = ScorePredictor().to(device)
        ckpt = torch.load(checkpoint_path, map_location=device)
        self.model.load_state_dict(ckpt["model_state_dict"])
        self.model.eval()
        self.epoch = ckpt["epoch"]
        self.val_metrics = ckpt.get("val_metrics", {})
        print(f"[predictor] loaded epoch {self.epoch}, val: {self.val_metrics}")

    @torch.no_grad()
    def infer(self, window: np.ndarray) -> dict:
        """window: (K, d) → advice dict."""
        x = torch.from_numpy(window.astype(np.float32)).unsqueeze(0).to(self.device)
        out = self.model(x)
        return {
            "score_p10": float(out["score"][0, 0, 0]),    # 30s, q=0.1
            "score_med": float(out["score"][0, 0, 1]),    # 30s, q=0.5
            "score_p90": float(out["score"][0, 0, 2]),    # 30s, q=0.9
            "anomaly":   float(out["anomaly"][0, 0]),
            "degrade":   float(out["degrade"][0, 0]),
        }


# =============================================================================
# Per-arm policy
# =============================================================================


def apply_arm_a(advice: dict, **kw) -> dict:
    """Baseline: ignore all advice."""
    return {
        "pre_promote_success": False,
        "blacklist_size": 0,
        "byzantine_flag": False,
        "degrade_warning": False,
    }


def apply_arm_b(advice: dict, pre_promote_threshold: float = 0.07, **kw) -> dict:
    """+Prediction: pre-promote if score band narrow."""
    band = advice["score_p90"] - advice["score_p10"]
    pre_promote = band < pre_promote_threshold and advice["score_med"] > 0.6
    return {
        "pre_promote_success": pre_promote,
        "blacklist_size": 0,
        "byzantine_flag": False,
        "degrade_warning": False,
    }


def apply_arm_c(advice: dict, anomaly_threshold: float = 0.5, **kw) -> dict:
    """+Anomaly: pre-promote + blacklist."""
    out = apply_arm_b(advice)
    flagged = advice["anomaly"] > anomaly_threshold
    out["byzantine_flag"] = flagged
    out["blacklist_size"] = 1 if flagged else 0
    return out


def apply_arm_d(advice: dict, anomaly_threshold: float = 0.5,
                degrade_threshold: float = 0.3, **kw) -> dict:
    """+Full ML: predict + anomaly + degrade."""
    out = apply_arm_c(advice, anomaly_threshold=anomaly_threshold)
    out["degrade_warning"] = advice["degrade"] > degrade_threshold
    return out


ARM_POLICIES = {
    "A": apply_arm_a,
    "B": apply_arm_b,
    "C": apply_arm_c,
    "D": apply_arm_d,
}


# =============================================================================
# Main simulation
# =============================================================================


def load_windows_for_events(data_dir: Path, n_events: int, rng) -> np.ndarray:
    """Pick n_events windows from data_xl2 to back the simulation events."""
    candidate_files = sorted(data_dir.glob("clean_seed*.npy"))
    if not candidate_files:
        raise RuntimeError(f"No clean windows in {data_dir}")
    chosen_file = rng.choice(candidate_files)
    arr = np.load(chosen_file)
    if len(arr) < n_events:
        idx = rng.integers(0, len(arr), size=n_events)
    else:
        idx = rng.choice(len(arr), size=n_events, replace=False)
    return arr[idx]


def load_byzantine_windows(data_dir: Path, n: int, rng) -> np.ndarray:
    """Windows from byzantine scenario for anomaly evaluation."""
    candidate_files = sorted(data_dir.glob("byzantine_seed*.npy"))
    chosen_file = rng.choice(candidate_files)
    arr = np.load(chosen_file)
    idx = rng.integers(0, len(arr), size=n)
    return arr[idx]


def load_degrade_windows(data_dir: Path, n: int, rng) -> tuple[np.ndarray, np.ndarray]:
    """Returns (windows, labels) — windows with known degradation in lookahead."""
    candidate_files = sorted(data_dir.glob("degrade_seed*.npy"))
    chosen_file = rng.choice(candidate_files)
    arr = np.load(chosen_file)
    parquet = chosen_file.with_suffix(".parquet")
    df = pd.read_parquet(parquet)
    pos_mask = df["degrade"].to_numpy() > 0
    pos_idx = np.where(pos_mask)[0]
    neg_idx = np.where(~pos_mask)[0]
    n_pos = min(n // 2, len(pos_idx))
    n_neg = n - n_pos
    chosen = np.concatenate([
        rng.choice(pos_idx, size=n_pos, replace=False) if n_pos > 0 else np.array([], dtype=int),
        rng.choice(neg_idx, size=n_neg, replace=False) if n_neg > 0 else np.array([], dtype=int),
    ])
    rng.shuffle(chosen)
    labels = df["degrade"].to_numpy()[chosen]
    return arr[chosen], labels


def run_simulation(
    n_events: int,
    predictor: PredictorWrapper,
    data_dir: Path,
    out_dir: Path,
    seed: int = 42,
) -> dict:
    rng = np.random.default_rng(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ----- Cascading-failure events (paired across arms) -----
    print(f"\n=== Phase 1: Cascading-failure events ({n_events} per arm) ===")
    cascading_windows = load_windows_for_events(data_dir, n_events, rng)

    # Pre-compute predictor advice once per event (paired design)
    advices = []
    for w in cascading_windows:
        advices.append(predictor.infer(w))

    arm_results = {arm: [] for arm in ARM_POLICIES}

    for arm in ARM_POLICIES:
        arm_rng = np.random.default_rng(seed + ord(arm))
        policy_fn = ARM_POLICIES[arm]
        for k in range(n_events):
            advice = advices[k]
            decision = policy_fn(advice)

            # Recovery time computation
            if arm == "A":
                recovery = compute_baseline_recovery(arm_rng)
            else:
                recovery = compute_predict_recovery(arm_rng, decision["pre_promote_success"])

            # Add cascade-induced jitter
            recovery += arm_rng.normal(0, 5)
            recovery = max(0, recovery)

            arm_results[arm].append({
                "event_id": k,
                "recovery_time_ms": recovery,
                "pre_promote_succeeded": decision["pre_promote_success"],
                "blacklist_size": decision["blacklist_size"],
                "byzantine_node_flagged": decision["byzantine_flag"],
                "degrade_warning_issued": decision["degrade_warning"],
                "advice": advice,
            })

    # ----- Byzantine detection (live overlay) -----
    print("\n=== Phase 2: Byzantine detection (sophisticated attacker overlay) ===")
    n_byz_eval = 200
    byz_windows = load_byzantine_windows(data_dir, n_byz_eval, rng)
    legit_windows = load_windows_for_events(data_dir, n_byz_eval, rng)

    byz_scores = [predictor.infer(w)["anomaly"] for w in byz_windows]
    legit_scores = [predictor.infer(w)["anomaly"] for w in legit_windows]
    y_true_byz = np.concatenate([np.ones(n_byz_eval), np.zeros(n_byz_eval)])
    y_pred_byz = np.concatenate([byz_scores, legit_scores])

    # ----- Degradation maintenance -----
    print("\n=== Phase 3: Degradation maintenance (1h-horizon) ===")
    n_deg_eval = 200
    deg_windows, deg_labels = load_degrade_windows(data_dir, n_deg_eval, rng)
    deg_preds = [predictor.infer(w)["degrade"] for w in deg_windows]

    # ----- Save results -----
    results = {
        "config": {
            "n_events": n_events,
            "n_byz_eval": n_byz_eval,
            "n_deg_eval": n_deg_eval,
            "seed": seed,
            "checkpoint_epoch": predictor.epoch,
        },
        "cascading_events": {arm: arm_results[arm] for arm in ARM_POLICIES},
        "byzantine_detection": {
            "y_true": y_true_byz.tolist(),
            "y_pred_ml": y_pred_byz.tolist(),
        },
        "degrade_maintenance": {
            "y_true": deg_labels.tolist(),
            "y_pred_ml": deg_preds,
        },
    }
    (out_dir / "raw_results.json").write_text(json.dumps(results, indent=2))
    print(f"\nWritten raw_results.json")
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", type=Path,
                    default=Path(__file__).parent.parent / "model_xl2" / "best.pt")
    ap.add_argument("--data-dir", type=Path,
                    default=Path(__file__).parent.parent / "data_xl2")
    ap.add_argument("--out-dir", type=Path,
                    default=Path(__file__).parent / "results")
    ap.add_argument("--n-events", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    predictor = PredictorWrapper(args.checkpoint)
    results = run_simulation(
        args.n_events, predictor, args.data_dir, args.out_dir, args.seed
    )
    print(f"\nSimulation complete. Run eval_sim.py for statistics.")


if __name__ == "__main__":
    raise SystemExit(main())
