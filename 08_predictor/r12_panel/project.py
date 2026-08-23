"""Hard projection onto the threat model, for use inside PGD.

The first panel run used soft penalties for the marginal and autocorrelation
constraints.  The optimiser simply paid the penalty and left the feasible set:
26 of 32 reported worst cases violated it, one asking for autocorrelation >= 0.8
and returning -0.85.  Those are not "a delay attack with matched marginals", they
are a different attack, and reporting them would repeat -- in the opposite
direction -- the error we are correcting in the published numbers.

Projected gradient descent fixes this by construction: after every step the
iterate is mapped back into the feasible set, so every solution the search ever
evaluates is a legal attack.

Feasible set:
    mean(r) = 8, std(r) = 3, lag-1 autocorr(r) >= rho_min, 0.5 <= r <= 60
"""
import torch

MEAN, STD = 8.0, 3.0


def autocorr1(r):
    z = (r - r.mean(1, keepdim=True)) / (r.std(1, keepdim=True) + 1e-9)
    return (z[:, :-1] * z[:, 1:]).mean(1)


def _ema(r, a=0.95):
    """Exponential smoother.  Raises lag-1 autocorrelation towards a."""
    out = [r[:, 0]]
    for t in range(1, r.shape[1]):
        out.append(a * out[-1] + (1 - a) * r[:, t])
    return torch.stack(out, dim=1)


def _fix_marginals(r):
    r = (r - r.mean(1, keepdim=True)) / (r.std(1, keepdim=True) + 1e-9) * STD + MEAN
    return r.clamp(0.5, 60.0)


def project(r, rho_min, bisect=16):
    """Map r into the feasible set.  Called under no_grad between PGD steps.

    The autocorrelation fix is a bisection on how far to blend towards a smoothed
    copy, so a sample that already satisfies the floor is left untouched and one
    that does not is moved the minimum distance that restores it.  Correcting more
    than necessary would weaken the attack, which biases the result in our favour.
    """
    with torch.no_grad():
        r = _fix_marginals(r)
        need = autocorr1(r) < rho_min
        if need.any():
            sm = _fix_marginals(_ema(r))
            lo = torch.zeros(r.shape[0], device=r.device)
            hi = torch.ones(r.shape[0], device=r.device)
            for _ in range(bisect):
                mid = (lo + hi) / 2
                cand = _fix_marginals((1 - mid[:, None]) * r + mid[:, None] * sm)
                low = autocorr1(cand) < rho_min
                lo = torch.where(low, mid, lo)
                hi = torch.where(low, hi, mid)
            blended = _fix_marginals((1 - hi[:, None]) * r + hi[:, None] * sm)
            r = torch.where(need[:, None], blended, r)
        return _fix_marginals(r)


def feasible(r, rho_min, tol_m=0.05, tol_s=0.05, tol_a=0.01):
    """Verification, used on the final iterate and reported alongside the AUC."""
    with torch.no_grad():
        m = r.mean(1); s = r.std(1); a = autocorr1(r)
        return (( (m - MEAN).abs() <= tol_m )
                & ( (s - STD).abs() <= tol_s )
                & ( a >= rho_min - tol_a )).float().mean().item()
