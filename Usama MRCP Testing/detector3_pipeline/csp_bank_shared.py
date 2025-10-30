# detector3_pipeline/csp_bank_shared.py
import numpy as np
from mne.decoding import CSP

class BandTaskCSP:
    def __init__(self, n_components=4, eps=1e-12):
        # make sure it's a plain Python int (not np.int64 or a float)
        n_comp = None if n_components is None else int(n_components)

        self.csp = CSP(
            n_components=n_comp,
            reg='ledoit_wolf',
            transform_into='average_power',  # then we'll log() ourselves
            norm_trace=True
        )
        self.eps = float(eps)
        self.fitted = False

    def fit(self, X, y, task_name=None):
        self.csp.fit(X, y)
        self.fitted = True
        return self

    def transform(self, X):
        pwr = self.csp.transform(X)               # average power
        return np.log(np.maximum(pwr, 1e-12))     # safe log

