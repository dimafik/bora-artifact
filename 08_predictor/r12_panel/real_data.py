"""E1: the same questions, asked of real testbed telemetry.

The strongest objection to the multi-node results is that the task is synthetic
and was built to suit an attention layer.  The predictor daemon logged the actual
per-node RTT of the Fabric testbed for two months, with the injections we ran, so
the question can be asked again with nothing synthetic in it:

    1,068,862 ticks   N = 5, 7, 9, 11, 15, 21
    node 3 delayed alone              518,511 ticks
    nodes {2,3,4,5,6,7,8,11} delayed   79,841 ticks   <- "many nodes slow"
    clean                             ~355,000 ticks

Two tasks, and the pair is the point:

  RAW   the delayed node's RTT really is higher (0-1 ms vs 100-160 ms), so the
        absolute level is a cue and a per-node scorer should already work.  This
        is deployment as it stands.
  NORM  each node's window normalised to mean 0 / std 1, which deletes exactly
        the cue a moment-matched adversary deletes.  What is left is the relation
        between nodes -- the regime the paper's own threat model describes.

If the relational layer helps on NORM but not on RAW, that is the honest finding
and it says precisely when the architecture matters.
"""
import re, sys, json
import numpy as np

sys.path.insert(0, "."); sys.path.insert(0, "..")
import gen

LOG = r"D:\프랑스 업데이트\TNSE 스페셜이슈 논문\experiments\02_results_raw\predictor_daemon.log"
TICK = re.compile(r"^(\d+\.\d+) .*scores=(.*)$")
NODE = re.compile(r"o(\d+):[-\d.]+\(rtt(\d+)\)")
HOT_MS = 50            # a node counts as delayed above this
WIN = gen.K            # 60 ticks, the daemon's own window
STRIDE = 20


def parse(path=LOG, max_ticks=None):
    """-> list of segments, each (N, hot_frozenset, array (T, N) of RTT)."""
    segs, cur, cur_key = [], [], None
    n = 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for ln in f:
            m = TICK.match(ln)
            if not m:
                continue
            d = NODE.findall(m.group(2))
            if not d:
                continue
            ids = [int(i) for i, _ in d]
            rtt = np.array([float(r) for _, r in d], dtype=np.float32)
            hot = frozenset(i for i, r in zip(ids, rtt) if r > HOT_MS)
            key = (tuple(ids), hot)
            if key != cur_key:
                if len(cur) >= WIN:
                    segs.append((cur_key[0], cur_key[1], np.stack(cur)))
                cur, cur_key = [], key
            cur.append(rtt)
            n += 1
            if max_ticks and n >= max_ticks:
                break
    if cur_key and len(cur) >= WIN:
        segs.append((cur_key[0], cur_key[1], np.stack(cur)))
    return segs


def windows(seg_arr, stride=STRIDE):
    T = seg_arr.shape[0]
    return [seg_arr[i:i + WIN] for i in range(0, T - WIN + 1, stride)]


def build(segs, nodes_n, mode, max_per_class=4000, seed=0):
    """mode: 'raw' keeps the level cue, 'norm' deletes it per node.

    Returns X (S, N, WIN, 8), y_det (0 = many/none slow, 1 = exactly one slow),
    y_attr (index of the slow node, valid where y_det == 1).
    """
    rng = np.random.default_rng(seed)
    one, many = [], []
    for ids, hot, arr in segs:
        if len(ids) != nodes_n:
            continue
        for w in windows(arr):
            (one if len(hot) == 1 else many).append((w, ids, hot))
    rng.shuffle(one); rng.shuffle(many)
    one, many = one[:max_per_class], many[:max_per_class]

    X, ydet, yattr = [], [], []
    for group, lab in ((many, 0), (one, 1)):
        for w, ids, hot in group:
            chans = []
            for j in range(nodes_n):
                r = w[:, j].astype(np.float64)
                if mode == "norm":
                    r = (r - r.mean()) / (r.std() + 1e-6) * 3.0 + 8.0
                chans.append(gen.window(np.clip(r, 0.5, None)))
            X.append(np.stack(chans))
            ydet.append(lab)
            yattr.append(ids.index(next(iter(hot))) if lab == 1 else -1)
    # torch tensors, matching what every other task builder returns; the first
    # version handed numpy straight to the model and died on the first forward.
    import torch
    return (torch.tensor(np.stack(X), dtype=torch.float32),
            torch.tensor(np.array(ydet), dtype=torch.float32),
            torch.tensor(np.array(yattr), dtype=torch.long))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    segs = parse()
    from collections import Counter
    c = Counter((len(i), len(h)) for i, h, _ in segs)
    print("segments (N, #hot) ->", dict(sorted(c.items())))
    tot = Counter()
    for ids, hot, a in segs:
        tot[(len(ids), len(hot))] += max(0, (a.shape[0] - WIN) // STRIDE + 1)
    print("windows  (N, #hot) ->", dict(sorted(tot.items())))
    json.dump({"n_segments": len(segs)}, open("real_data_summary.json", "w"))
