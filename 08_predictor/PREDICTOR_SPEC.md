# Score-Predictor 형식 명세 (v26 핵심)

**대상**: S-Raft sub-leader 점수식 $Score_i = w_{cc} CC_i + w_{rtt} \text{NORMALIZE}(RTT_i)$를 학습 예측기로 대체.

**기본 가정**: S-Raft v5_3 Eq.(3) Algorithm 1이 권위 명세. 본 명세는 Algorithm 1을 **변경하지 않고** advice $\mathcal{A}$로 확장한다.

---

## 1. 학습 문제 정의

### 1.1 관측 (Observation)

매 heartbeat tick $t$ (디폴트 50 ms)마다 리더가 노드 $i$에 대해 수집:

| 기호 | 정의 | 단위 | 출처 |
|---|---|---|---|
| $cc_i(t)$ | 직전 tick의 instantaneous commit indicator $\mathbb{1}[\tau_{ack}(i,t) \le T_{commit}(t)]$ | {0,1} | Eq.(3) summand |
| $CC_i(t)$ | sliding window 평균 (W=100) | [0,1] | Eq.(3) |
| $rtt_i(t)$ | 직전 ack RTT | ms | heartbeat ack |
| $RTT_i(t)$ | EMA, $\alpha=0.8$ | ms | EMA 갱신 |
| $T_{commit}(t)$ | leader-local 90-percentile over W | ms | leader |
| $\delta CC_i(t)$ | $CC_i(t) - CC_i(t-1)$ | [-1,1] | derived |
| $\delta RTT_i(t)$ | $RTT_i(t) - RTT_i(t-1)$ | ms | derived |
| $(P,S)$ | 현 designation (one-hot) | {0,1}² | piggyback |

### 1.2 입력 시계열 텐서

윈도 길이 $K = 60$ ticks (=3 초 at 50 ms heartbeat):

$$
\mathbf{x}_i^{(t)} \in \mathbb{R}^{K \times d}, \quad d = 8
$$

8 채널: $(cc, CC, rtt, RTT, T_{commit}, \delta CC, \delta RTT, \text{designation})$.

### 1.3 출력 (multi-head)

세 헤드를 단일 backbone 위에 둠.

**Head A — Score 예측 (회귀)**

$$
\hat{Score}_i^{t+H} \in [0,1], \quad H \in \{30s, 60s, 90s\}
$$

3-step 다중 horizon. 손실: Pinball loss with $\tau \in \{0.1, 0.5, 0.9\}$ → 점예측 + 80% 예측구간.

**Head B — Anomaly score (분류)**

$$
\hat{p}_{anom,i}(t) \in [0,1]
$$

해석: 학습 분포 밖일 likelihood. 1-class deep SVDD head 또는 binary head (synthetic Byzantine 주입 시).

**Head C — Degradation 예측 (분류)**

$$
\hat{p}_{degrade,i}(t) \in [0,1], \quad \text{horizon} = 1h
$$

해석: 노드 $i$가 향후 1h 내 $T_{follower}^{max}$ 초과 가능성.

### 1.4 ground truth (training labels)

| Label | 생성 방법 |
|---|---|
| $Score_i^{t+H}$ | $t+H$ 시점에 S-Raft가 실제 계산한 점수 (offline) |
| Byzantine 1/0 | synthetic 데이터: 시뮬레이터가 노드 $i$를 Byzantine으로 표시한 구간 = 1 |
| Degrade 1/0 | 향후 1h 내 timer overshoot 관측 = 1 |

---

## 2. 모델 아키텍처 (Light Transformer)

```
Input  (K=60, d=8)
   │
   ├── Linear embed → (60, 64)
   │
   ├── Positional encoding (sinusoidal)
   │
   ├── TransformerEncoderLayer × 4
   │     d_model=64, n_heads=4, dim_ff=128, dropout=0.1
   │
   ├── Mean-pool over time → (64,)
   │
   ├── Head A (Score regression):
   │     Linear(64, 32) -> ReLU -> Linear(32, 3 horizons × 3 quantiles)
   │
   ├── Head B (Anomaly):
   │     Linear(64, 32) -> ReLU -> Linear(32, 1) -> Sigmoid
   │
   └── Head C (Degrade):
         Linear(64, 32) -> ReLU -> Linear(32, 1) -> Sigmoid
```

**파라미터 수**: ≈ 52 K (PyTorch 기준). Heartbeat마다 inference: P99 ≤ 3 ms on c5n.4xlarge CPU. **GPU 불필요**.

---

## 3. Advice 인터페이스 (S-Raft 알고리즘과의 접점)

S-Raft Algorithm 1의 ranking 라인을 **변경 없이** 유지. 옆에서 advice 객체 $\mathcal{A}$를 생성:

```
struct Advice {
    sleep_ok: bool             // 예측기 신뢰도 충분?
    pre_promote_candidate: Option<NodeId>
    blacklist_set: Set<NodeId>
    maintenance_warnings: Map<NodeId, f64>
}
```

S-Raft가 매 heartbeat 종료 시 advice를 **읽기만**:

```
adv = Predictor.infer(window)        // adv: Advice
if adv.sleep_ok:
    if adv.pre_promote_candidate ∈ rank_top2:
        re-order rank such that pre_promote_candidate is primary candidate
    rank ← rank \ adv.blacklist_set
    emit_warnings(adv.maintenance_warnings)
# else: ignore advice; baseline S-Raft proceeds unchanged
```

**핵심 불변량**:
1. Score 계산 ($Score_i = w_{cc} CC_i + w_{rtt} \text{NORMALIZE}(RTT_i)$) 자체는 변경 없음.
2. Advice는 *후처리* — top-2 안에서의 재배치 + blacklist removal 만 허용.
3. $|adv.\text{blacklist\_set}| < f$ (Byzantine bound) 강제. 위반 시 advice 전체 무시.
4. $adv.\text{sleep\_ok}=\text{false}$ 시 시스템은 baseline S-Raft.

---

## 4. Augmentation Safety Theorem

**Theorem (Augmentation Safety).** S-Raft 정리 1 (Election Safety), 정리 2 (Detection Priority), 정리 3 (Bounded Cascading Recovery)가 advice $\mathcal{A}$ 도입 후에도 성립한다.

**증명 (스케치).**

**T1 (Election Safety) 보존.** Advice는 rank 내 top-2 재배치와 blacklist 제거만 수행. 표결(vote majority) 절차는 변경 없음. 동일 term에서 majority overlap → 적어도 한 노드가 두 후보 모두에게 표를 줄 수 없음 (Raft 원본 증명 그대로). $\square$

**T2 (Detection Priority) 보존.** Tier별 timeout $T_{primary} < T_{secondary} < T_{follower}$의 절대값은 변경 없음. Advice가 노드의 *tier 멤버십*을 바꾸어도 (예: maintenance warning → 강제 follower tier 강등), 각 tier 내 timer 분포 식은 그대로 → Lemma 1 (split-vote probability) 적용 가능. $\square$

**T3 (Bounded Cascading Recovery) 부등호 strengthening.** Cascade 시각 $t_{kill}^{(1)}$에서 advice가 pre-promote을 수행해 둔 경우:

$$
t_{recover}^{AI} = t_{kill}^{(1)} + T_{Promote}^{1RTT} + 2\Delta
$$

이는 baseline bound

$$
t_{recover}^{baseline} = t_{kill}^{(1)} + T_{secondary}^{max} + 2\Delta + O\left(\frac{\Delta}{1-\rho_{max}}\right)
$$

보다 항상 작거나 같다 ($T_{secondary}^{max} \ge T_{Promote}^{1RTT}$ by tier 정의). pre-promote 실패 시 ($\mathcal{A}$.sleep_ok=false) baseline 그대로. 그러므로

$$
\boxed{t_{recover}^{AI} \le t_{recover}^{baseline} \quad \forall \omega \in \Omega}
$$

즉 *positive-only enhancer*. $\square$

**Corollary (Byzantine Bound 보존).** $|adv.\text{blacklist\_set}| < f$ 강제로 $f < N/3$ Byzantine bound 그대로. blacklist는 정의상 보수적 (false positive는 liveness 약화이나 safety 영향 없음).

---

## 5. 학습 데이터 생성

### 5.1 Source: S-Raft 시뮬레이터 로그

기존 `experiments/aws_realistic_benchmark.py`를 확장해 노드별 시계열 로그를 추출.

### 5.2 합성 라벨

| Task | 라벨 생성 절차 |
|---|---|
| Score 예측 | $t+H$ 시점의 실제 score 기록 → supervised label |
| Byzantine | $i$ 번째 노드를 시뮬레이터에서 "ACK 즉시 보내지만 실제 commit 누락" 모드로 토글, 해당 윈도를 label=1 |
| Degradation | 시뮬레이터에 합성 GC stall (500 ms × 30회) 주입 → overshoot 발생한 윈도를 1h pre-window label=1 |

### 5.3 데이터 분할

| Split | 구성 |
|---|---|
| Train | 시드 0-79 × 6 워크로드 × 4 시나리오 = 1,920 traces |
| Val | 시드 80-89 × 6 워크로드 × 4 시나리오 = 240 traces |
| Test (clean) | 시드 90-99 × 6 워크로드 × 4 시나리오 = 240 traces |
| Test (OOD) | 비잔틴 mix 5/10/20%, 네트워크 jitter 3×, 새 워크로드 trace_overflow |

---

## 6. 평가 지표

| 헤드 | 지표 |
|---|---|
| Score | pinball loss, RMSE @ H={30,60,90}s, coverage of 80% PI |
| Anomaly | AUC-ROC, AUC-PR, F1 @ optimal threshold, FPR@95%TPR |
| Degrade | precision@k (k=top 5% of cluster), recall@1h, calibration ECE |

**Acceptance 조건 (사전등록)**:

- Score H=30s RMSE ≤ 0.04 (baseline static formula은 분포 변화 시 ≥ 0.12)
- Anomaly AUC-ROC ≥ 0.90
- Degrade precision@10% ≥ 0.70 with recall ≥ 0.50

**Safety 강제 조건**: AI off 상태에서 baseline S-Raft 정리 3 bound 그대로 — Augmentation Safety Theorem 형식 증명 + TLA+ Apalache 자동 검증.

---

## 7. 배포 비용

- Inference: c5n.4xlarge CPU, P99 = 3 ms / node-tick
- Memory: 모델 4 MB + 윈도 버퍼 (60 × 8 × 8 byte × N nodes) = 24 KB at N=5
- Network: 0 추가 — 윈도는 리더 local
- 학습: T4 GPU 30 분, 또는 c5n.4xlarge CPU 8 시간 (one-shot)
- 학습 데이터: 1,920 traces × 100 MB ≈ 192 GB → S3에 한 번 저장

S-Raft 자체의 $W=100$ ack timestamps overhead (≈16 KB at N=21)와 동일 자리수 — 자원 부담 없음.
