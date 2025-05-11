import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
import joblib
import matplotlib.pyplot as plt
import seaborn as sns
import os

# ====== Load Features ======
file_path = os.path.join(os.path.dirname(__file__), "features_ready.npz")
data = np.load(file_path)
X = data["X_combined"]    # shape: (n_trials, 8)
y = data["labels"]        # shape: (n_trials,) → values: 0 (left), 1 (right), 2 (rest)

# ====== Split Data (80% train, 20% test) ======
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# ====== Train Classifier ======
clf = LogisticRegression(max_iter=1000, multi_class='multinomial', solver='lbfgs')
clf.fit(X_train, y_train)

# ====== Evaluate ======
y_pred = clf.predict(X_test)
acc = accuracy_score(y_test, y_pred)
print(f"✅ Accuracy: {acc * 100:.2f}%\n")

# ====== Report ======
class_names = ["Left", "Right", "Rest"]
print("📊 Classification Report:")
print(classification_report(y_test, y_pred, target_names=class_names))

# ====== Confusion Matrix ======
cm = confusion_matrix(y_test, y_pred)
plt.figure(figsize=(6, 5))
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", 
            xticklabels=class_names, yticklabels=class_names)
plt.title("Confusion Matrix (3-Class)")
plt.xlabel("Predicted")
plt.ylabel("Actual")
plt.tight_layout()
plt.show()

# ====== Save Model ======
joblib.dump(clf, "trained_model.pkl")
print("💾 Trained model saved to 'trained_model.pkl'")

