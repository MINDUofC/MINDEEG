#MODEL
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
import joblib
import matplotlib.pyplot as plt
import seaborn as sns

# ====== Load Features ======
script_dir = r"C:\Users\rashe\source\repos\MINDUofC\MINDEEG\Usama MRCP Testing\calibration_data"
file_path = os.path.join(script_dir, "features_ready.npz")
data = np.load(file_path)
X = data["X_combined"]    # shape: (n_trials, 8)
y = data["labels"]        # shape: (n_trials,)

# ====== Split Data (80% train, 20% test) ======
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# ====== Train Classifier ======
clf = LogisticRegression()
clf.fit(X_train, y_train)

# ====== Evaluate ======
y_pred = clf.predict(X_test)
acc = accuracy_score(y_test, y_pred)
print(f"✅ Accuracy: {acc * 100:.2f}%\n")

print("📊 Classification Report:")
print(classification_report(y_test, y_pred, target_names=["Left", "Right"]))

# ====== Confusion Matrix ======
cm = confusion_matrix(y_test, y_pred)
plt.figure(figsize=(5,4))
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=["Left", "Right"], yticklabels=["Left", "Right"])
plt.title("Confusion Matrix")
plt.xlabel("Predicted")
plt.ylabel("Actual")
plt.tight_layout()
plt.show()

# ====== Save Model ======
joblib.dump(clf, os.path.join(script_dir, "trained_model.pkl"))
print("💾 Trained model saved to 'trained_model.pkl'")
