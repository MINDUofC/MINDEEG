# Hidden_Markov_Model.py
import numpy as np
from collections import deque

class StickyHMM:
    """
    K-state HMM with strong self-transitions and fixed-lag online Viterbi.
    We delay committing decisions by `lag` observations to reduce jitter.
    """
    def __init__(self, A: np.ndarray, pi: np.ndarray = None, lag: int = 5):
        A = np.asarray(A, float)
        assert A.ndim == 2 and A.shape[0] == A.shape[1]
        self.K = A.shape[0]
        self.logA = np.log(np.clip(A, 1e-12, 1.0))
        if pi is None:
            pi = np.ones(self.K) / self.K
        self.logpi = np.log(np.clip(pi, 1e-12, 1.0))
        self.lag = max(int(lag), 0)

        # Viterbi buffers
        self.delta = []           # list of (K,) log-scores
        self.psi = []             # list of (K,) backpointers (int)
        self.t = 0                # number of obs processed
        self.best_idx_hist = deque()  # argmax(delta_t) over time for fast start

    def step(self, log_emiss: np.ndarray):
        log_emiss = np.asarray(log_emiss, float).reshape(-1)
        assert log_emiss.size == self.K

        if self.t == 0:
            delta_t = self.logpi + log_emiss
            psi_t = np.full(self.K, -1, dtype=np.int32)
        else:
            prev = self.delta[-1]  # (K,)
            scores = np.empty(self.K)
            psi_t  = np.empty(self.K, dtype=np.int32)
            for j in range(self.K):
                cand = prev + self.logA[:, j]
                bp = int(np.argmax(cand))
                psi_t[j]  = bp
                scores[j] = cand[bp]
            delta_t = scores + log_emiss

        self.delta.append(delta_t)
        self.psi.append(psi_t)
        self.t += 1

        # Not enough history to commit a fixed-lag decision yet
        if self.t <= self.lag:
            return None

        # Backtrack `lag` steps using LOCAL indices (lists may be trimmed)
        steps = min(self.lag, len(self.psi) - 1)
        idx = int(np.argmax(self.delta[-1]))  # start from best at current time
        for k in range(steps):
            local = len(self.psi) - 1 - k          # local row index
            bp = int(self.psi[local][idx])         # backpointer at that row
            if bp < 0:                             # hit the start (initial frame)
                break
            idx = bp

        # Optional: keep buffers bounded
        max_keep = self.lag + 2
        if len(self.delta) > max_keep:
            self.delta.pop(0)
            self.psi.pop(0)

        return idx

