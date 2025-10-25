# train_ensemble.py  — leakage-safe training with fold-fitted CSP & Riemann mean
import os, json
import numpy as np
from typing import Dict, Tuple
from joblib import dump

from sklearn.model_selection import StratifiedKFold, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import classification_report, accuracy_score

# Utilities
from feature_extraction_utilities_3 import (
    lw_cov, riemann_mean_AIRM, tangent_space, mrcp_features, CHAN_NAMES, MRCP_TAIL_SEC
)
print(f"MRCP_TAIL_SEC: {MRCP_TAIL_SEC}")
from csp_bank_shared import BandTaskCSP  # your wrapper: .fit(X, y, task_name), .transform(X)

# ----- Config (match your collection) -----
FBCSP_BANDS = ["8-12", "12-16", "16-20", "20-26", "26-30"]
TASKS = ["L_vs_R", "B_vs_LR", "Act_vs_Rest"]  # binary tasks inside BandTaskCSP
CSP_N_COMPONENTS = 4

# ===============================
# Helpers for CSP bank per fold
# ===============================
def fit_csp_bank_per_fold(X_bands: Dict[str, np.ndarray], y4: np.ndarray) -> Dict[Tuple[str, str], BandTaskCSP]:
    """
    Fit a CSP bank for each (band, task) on the PROVIDED data (train fold).
    X_bands: dict band-> (n_tr, n_ch, n_samp)
    y4: (n_tr,) 4-class labels: 0=L,1=R,2=Rest,3=Both
    """
    bank = {}
    for band in FBCSP_BANDS:
        Xb = X_bands[band]
        for task in TASKS:
            mdl = BandTaskCSP(n_components=CSP_N_COMPONENTS)
            mdl.fit(Xb, y4, task)   # inside it, you map y4 -> binary per task
            bank[(band, task)] = mdl
    return bank

def transform_with_csp_bank(bank: Dict[Tuple[str, str], BandTaskCSP],
                            X_bands: Dict[str, np.ndarray]) -> np.ndarray:
    parts = []
    for band in FBCSP_BANDS:
        Xb = X_bands[band]
        for task in TASKS:
            parts.append(bank[(band, task)].transform(Xb))  # (n, CSP_N_COMPONENTS) log-power
    return np.concatenate(parts, axis=1)

def riemann_ts_block(X_830: np.ndarray, G: np.ndarray) -> np.ndarray:
    """
    X_830: (n, n_ch, n_samp); G: SPD (n_ch,n_ch)
    """
    covs = [lw_cov(X_830[i]) for i in range(X_830.shape[0])]
    return np.vstack([tangent_space(C, G) for C in covs])

# ===============================
# Main training
# ===============================
def train_models(
    npz_path: str,
    models_dir: str,
    fs_decl: int = 125.44,
    k_folds: int = 5,
):
    os.makedirs(models_dir, exist_ok=True)

    # ---- Load band-limited trials (already detrend + bandpass + CAR in collection) ----
    D = np.load(npz_path, allow_pickle=True)
    y4 = D["class_types"].astype(int)  # 0=L,1=R,2=Rest,3=Both
    X_bands_full = {k: D[k] for k in ["8-30","8-12","12-16","16-20","20-26","26-30","0.05-5"]}
    n_trials = y4.shape[0]

    # ---- Base learner definitions (each has its own scaler) ----
    # BaseA: LDA on FBCSP (4-class)
    baseA_tpl = Pipeline([
        ("scaler", StandardScaler()),
        ("lda", LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto"))
    ])
    # BaseB: LR on Riemann TS (4-class)
    baseB_tpl = Pipeline([
        ("scaler", StandardScaler(with_mean=True, with_std=True)),
        ("lr", LogisticRegression(
            solver="lbfgs", C=1.0, max_iter=5000, n_jobs=-1, class_weight="balanced"))
    ])
    # BaseC: LR on MRCP (binary Active vs Rest)
    baseC_tpl = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(
            penalty="l2", solver="liblinear",
            C=1.0, max_iter=5000, class_weight="balanced"))
    ])

    # ---- OOF stacking (leakage-safe) ----
    seed = int(np.random.SeedSequence().entropy % (2**32))
    print(f"CV seed: {seed}")
    skf = StratifiedKFold(n_splits=k_folds, shuffle=True, random_state=seed)

    oof_meta = np.zeros((n_trials, 9), dtype=np.float32)  # [pA(4), pB(4), pC(1)]
    oof_y = y4.copy()

    for fold, (tr, va) in enumerate(skf.split(np.zeros_like(y4), y4), 1):
        # ===== Fit CSP bank on TR only =====
        csp_bank_tr = fit_csp_bank_per_fold(
            {b: X_bands_full[b][tr] for b in FBCSP_BANDS}, y4[tr]
        )
        # Transform TR/VA with that bank
        X_fbcsp_tr = transform_with_csp_bank(csp_bank_tr, {b: X_bands_full[b][tr] for b in FBCSP_BANDS})
        X_fbcsp_va = transform_with_csp_bank(csp_bank_tr, {b: X_bands_full[b][va] for b in FBCSP_BANDS})

        # ===== Fit Riemann mean on TR only (8–30) =====
        G_tr = riemann_mean_AIRM([lw_cov(X_bands_full["8-30"][i]) for i in tr], iters=8)
        X_riem_tr = riemann_ts_block(X_bands_full["8-30"][tr], G_tr)
        X_riem_va = riemann_ts_block(X_bands_full["8-30"][va], G_tr)

        # ===== MRCP features (no learning) =====
        X_mrcp_tr, _ = mrcp_features(X_bands_full["0.05-5"][tr], fs=fs_decl)
        X_mrcp_va, _ = mrcp_features(X_bands_full["0.05-5"][va], fs=fs_decl)
        y_active_tr = (y4[tr] != 2).astype(int)
        y_active_va = (y4[va] != 2).astype(int)

        # ===== Fit bases on TR; predict VA =====
        baseA = baseA_tpl.__class__(steps=baseA_tpl.steps)  # fresh clones
        baseB = baseB_tpl.__class__(steps=baseB_tpl.steps)
        baseC = baseC_tpl.__class__(steps=baseC_tpl.steps)

        baseA.fit(X_fbcsp_tr, y4[tr])
        baseB.fit(X_riem_tr,  y4[tr])
        baseC.fit(X_mrcp_tr,  y_active_tr)

        pA = baseA.predict_proba(X_fbcsp_va)            # (|va|, 4)
        pB = baseB.predict_proba(X_riem_va)             # (|va|, 4)
        pC_full = baseC.predict_proba(X_mrcp_va)        # (|va|, 2) -> [:,1] is Active
        pC = pC_full[:, 1:2]

        oof_meta[va] = np.hstack([pA, pB, pC])

        # quick fold diagnostics
        y_hat_A = np.argmax(pA, axis=1)
        y_hat_B = np.argmax(pB, axis=1)
        y_hat_C = np.argmax(pC_full, axis=1)  # 0=Rest, 1=Active

        print(f"[fold {fold}] baseA acc ~ {accuracy_score(y4[va],       y_hat_A):.3f}")
        print(f"[fold {fold}] baseB acc ~ {accuracy_score(y4[va],       y_hat_B):.3f}")
        print(f"[fold {fold}] baseC acc ~ {accuracy_score(y_active_va, y_hat_C):.3f}")

    # ---- Tune meta on OOF (log-loss) ----
    meta_grid = GridSearchCV(
        LogisticRegression(n_jobs=-1),
        param_grid={
            "C": [0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0],
            "class_weight": [None, "balanced"],
            "solver": ["lbfgs"],   # multinomial default
            "penalty": ["l2"],
            "max_iter": [5000],
        },
        scoring="neg_log_loss",
        cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=seed),
        n_jobs=-1
    )
    meta_grid.fit(oof_meta, oof_y)
    meta = meta_grid.best_estimator_
    print("Best meta:", meta_grid.best_params_)

    # =========================================================
    # REFIT ON ALL DATA for DEPLOY (save final artifacts)
    # =========================================================

    # Final CSP bank on ALL data
    csp_bank_full = fit_csp_bank_per_fold(
        {b: X_bands_full[b] for b in FBCSP_BANDS}, y4
    )
    X_fbcsp_full = transform_with_csp_bank(csp_bank_full, {b: X_bands_full[b] for b in FBCSP_BANDS})

    # Final Riemann mean on ALL data (8–30)
    G_full = riemann_mean_AIRM([lw_cov(X_bands_full["8-30"][i]) for i in range(n_trials)], iters=8)
    X_riem_full = riemann_ts_block(X_bands_full["8-30"], G_full)

    # MRCP on ALL
    X_mrcp_full, _ = mrcp_features(X_bands_full["0.05-5"], fs=fs_decl)
    y_active_full = (y4 != 2).astype(int)

    # Final base models on ALL
    baseA_full = Pipeline([("scaler", StandardScaler()),
                           ("lda", LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto"))])
    baseB_full = Pipeline([("scaler", StandardScaler(with_mean=True, with_std=True)),
                           ("lr", LogisticRegression(solver="lbfgs", C=1.0, max_iter=5000, n_jobs=-1, class_weight="balanced"))])
    baseC_full = Pipeline([("scaler", StandardScaler()),
                           ("lr", LogisticRegression(penalty="l2", solver="liblinear", C=1.0, max_iter=5000, class_weight="balanced"))])

    baseA_full.fit(X_fbcsp_full, y4)
    baseB_full.fit(X_riem_full,  y4)
    baseC_full.fit(X_mrcp_full,  y_active_full)

    # Stacked sanity report (in-sample)
    pA_all = baseA_full.predict_proba(X_fbcsp_full)
    pB_all = baseB_full.predict_proba(X_riem_full)
    pC_all = baseC_full.predict_proba(X_mrcp_full)[:, 1:2]
    X_meta_all = np.hstack([pA_all, pB_all, pC_all])

    y_pred_all = meta.predict(X_meta_all)
    print("\n=== Stacked in-sample report (sanity) ===")
    print(classification_report(y4, y_pred_all, digits=3))

    # ---- Save everything needed for LIVE ----
    # 1) CSP bank (for FBCSP live transform)
    dump(csp_bank_full, os.path.join(models_dir, "csp_models.joblib"))
    # 2) Riemann mean
    np.save(os.path.join(models_dir, "riem_mean.npy"), G_full)
    # 3) Base learners + Meta
    dump(baseA_full, os.path.join(models_dir, "baseA_fbcsp_lda.joblib"))
    dump(baseB_full, os.path.join(models_dir, "baseB_riem_lr.joblib"))
    dump(baseC_full, os.path.join(models_dir, "baseC_mrcp_active_lr.joblib"))
    dump(meta,        os.path.join(models_dir, "meta_lr.joblib"))

    # 4) Metadata for correct stacking order live
    config = {
        "channels": CHAN_NAMES,
        "bands": FBCSP_BANDS,
        "csp_components": CSP_N_COMPONENTS,
        "mrcp_tail_sec": MRCP_TAIL_SEC,
        "k_folds": k_folds,
        "stack_input_order": [
            "baseA_proba[0:4]=[Left,Right,Rest,Both]",
            "baseB_proba[0:4]=[Left,Right,Rest,Both]",
            "baseC_active_proba"
        ]
    }
    with open(os.path.join(models_dir, "ensemble_meta.json"), "w") as f:
        json.dump(config, f, indent=2)

    print("\n✅ Saved models to:", os.path.abspath(models_dir))
    return {
        "baseA": baseA_full, "baseB": baseB_full, "baseC": baseC_full, "meta": meta
    }

# ---------- CLI ----------
if __name__ == "__main__":
    NPZ = r"C:\Users\rashe\source\repos\MINDUofC\MINDEEG\Usama MRCP Testing\calibration_data\four_class_clench_trials_from_pause.npz"
    MODELS_DIR = r"C:\Users\rashe\source\repos\MINDUofC\MINDEEG\Usama MRCP Testing\calibration_data\models"

    train_models(
        npz_path=NPZ,
        models_dir=MODELS_DIR,
        fs_decl=125,
        k_folds=5,
    )
