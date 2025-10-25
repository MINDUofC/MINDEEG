# feature_extraction utilities
import numpy as np
from typing import List, Tuple
from numpy.linalg import eigh
from scipy.signal import hilbert
from sklearn.covariance import LedoitWolf

# Channel order (must match collection/training)
CHAN_NAMES = ["FC4","C4","CP4","C2","C1","CP3","C3","FC3"]
IDX_C4 = CHAN_NAMES.index("C4")
IDX_C3 = CHAN_NAMES.index("C3")

# MRCP window tail (seconds) used inside each 1-s trial
MRCP_TAIL_SEC = 0.6

# --------- SPD / Riemann utilities ---------
def lw_cov(X: np.ndarray) -> np.ndarray:
    """
    Ledoit–Wolf covariance (SPD).
    X: (n_ch, n_samp) -> cov: (n_ch, n_ch)
    """
    cov = LedoitWolf().fit(X.T).covariance_
    cov = 0.5 * (cov + cov.T)  # symmetrize
    return cov

def _spd_invsqrt(C: np.ndarray) -> np.ndarray:
    w, V = eigh(C); w = np.clip(w, 1e-12, None)
    return V @ np.diag(1.0/np.sqrt(w)) @ V.T

def _spd_sqrt(C: np.ndarray) -> np.ndarray:
    w, V = eigh(C); w = np.clip(w, 1e-12, None)
    return V @ np.diag(np.sqrt(w)) @ V.T

def _spd_log(C: np.ndarray) -> np.ndarray:
    w, V = eigh(C); w = np.clip(w, 1e-12, None)
    return V @ np.diag(np.log(w)) @ V.T

def _spd_exp(C: np.ndarray) -> np.ndarray:
    w, V = eigh(C)
    return V @ np.diag(np.exp(w)) @ V.T

def riemann_mean_AIRM(Cs: List[np.ndarray], iters: int = 8) -> np.ndarray:
    """
    Affine-Invariant Riemannian Metric (AIRM) mean via iterative log–exp updates.
    Cs: list of SPD matrices (n_ch, n_ch)
    """
    G = np.mean(Cs, axis=0)  # Euclidean init
    for _ in range(iters):
        G_inv_sqrt = _spd_invsqrt(G)
        logs = [_spd_log(G_inv_sqrt @ C @ G_inv_sqrt) for C in Cs]
        delta = np.mean(logs, axis=0)
        G = _spd_sqrt(G) @ _spd_exp(delta) @ _spd_sqrt(G)
        G = 0.5 * (G + G.T)
    return G

def tangent_space(C: np.ndarray, G: np.ndarray) -> np.ndarray:
    """
    Log-map SPD C to tangent space at mean G (AIRM).
    Returns upper-triangular vectorization with sqrt(2) on off-diagonals.
    """
    Z = _spd_invsqrt(G) @ C @ _spd_invsqrt(G)
    S = _spd_log(Z)
    n = S.shape[0]
    out = []
    for i in range(n):
        for j in range(i, n):
            v = S[i, j]
            if i != j:
                v *= np.sqrt(2.0)
            out.append(v)
    return np.array(out, dtype=np.float64)

# --------- MRCP features (no learning) ---------
def mrcp_features(mrcp_trials: np.ndarray, fs: int) -> Tuple[np.ndarray, List[str]]:
    """
    mrcp_trials: (n_trials, n_ch, n_samp) from 0.05–5 Hz branch (after CAR)
    Returns: (X_mrcp, feature_names)
    """
    n_trials, n_ch, n_samp = mrcp_trials.shape
    tail = min(int(round(MRCP_TAIL_SEC * fs)), n_samp)
    idx0 = n_samp - tail

    feats = []
    for tr in range(n_trials):
        X = mrcp_trials[tr]
        seg = X[:, idx0:]  # (n_ch, tail)

        mean = seg.mean(axis=1)

        t = np.linspace(0, 1, seg.shape[1], endpoint=True)
        t = t - t.mean()
        denom = np.sum(t * t) + 1e-12
        slope = (seg @ t) / denom

        vmin = seg.min(axis=1)
        area = seg.sum(axis=1) / float(seg.shape[1])

        # Laterality index from C3/C4 envelope over tail
        c3 = X[IDX_C3]; c4 = X[IDX_C4]
        env_c3 = np.abs(hilbert(c3))[idx0:].mean()
        env_c4 = np.abs(hilbert(c4))[idx0:].mean()
        li = (env_c3 - env_c4) / (env_c3 + env_c4 + 1e-12)

        feats.append(np.concatenate([mean, slope, vmin, area, [li]]))

    def _names(prefix): return [f"{prefix}_{ch}" for ch in CHAN_NAMES]
    names = _names("mrcp_mean") + _names("mrcp_slope") + _names("mrcp_min") + _names("mrcp_area") + ["mrcp_LI_C3C4"]
    return np.vstack(feats), names
