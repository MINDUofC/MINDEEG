import numpy as np
from sklearn.linear_model import LogisticRegression
import joblib

# ====== Load Features ======
data = np.load("calibration_data/features_ready.npz")
X = data["X_combined"]    # shape: (n_trials, 8)
y = data["labels"]        # shape: (n_trials,)

# ====== Train Classifier on ALL Data ======
clf = LogisticRegression()
clf.fit(X, y)

# ====== Save Model ======
joblib.dump(clf, "trained_model_1.pkl")
print("💾 Model trained and saved to 'trained_model.pkl'")

