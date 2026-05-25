"""
Supervised churn prediction model.
Reads cleaned data from intermediate.int_churn_features, trains a
Random Forest classifier, evaluates it, and exports the model and
SHAP explainer for the Streamlit dashboard.
"""

import os

import duckdb
import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Paths and configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, '..')
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'churn_data.duckdb')
MODELS_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, 'models'))
RESULTS_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, 'results_RF'))
SEED = 13
TEST_SIZE = 0.2
N_ESTIMATORS = 100

# Let's create the model and results folder
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# Load data from the intermediate layer
con = duckdb.connect(DB_PATH)
con.execute("INSTALL httpfs; LOAD httpfs;")
con.execute("""
    SET s3_region='us-east-1';
    SET s3_endpoint='minio:9000';
    SET s3_url_style='path';
    SET s3_access_key_id='admin';
    SET s3_secret_access_key='password';
    SET s3_use_ssl=false;
 """)
df = con.execute("SELECT * FROM intermediate.int_churn_features").fetchdf()
print(f"Loaded {len(df)} customers from intermediate.int_churn_features")

# Prepare features and target
target_col = "churn"
id_col = "customer_id"

# Convert target to numeric
df[target_col] = df[target_col].astype(str).str.strip().map({'Yes': 1, 'No': 0})
print(f"Churn rate: {df[target_col].mean():.1%}")

# Drop ID and target from features
feature_cols = [c for c in df.columns if c not in [id_col, target_col]]
X = df[feature_cols]
y = df[target_col]

# Identify column types
cat_cols = X.select_dtypes(include=['object', 'string']).columns.tolist()
num_cols = X.select_dtypes(include=['number']).columns.tolist()

print(f"Categorical features: {len(cat_cols)}")
print(f"Numeric features: {len(num_cols)}")

# Build preprocessing pipeline
preprocessor = ColumnTransformer([
    ("num", StandardScaler(), num_cols),
    ("cat", OneHotEncoder(drop='first', handle_unknown='ignore'), cat_cols)
])

# Train/Test split (stratified due to imbalance)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=TEST_SIZE, stratify=y, random_state=SEED
)

# Train Random Forest
model = Pipeline([
    ("preprocessor", preprocessor),
    ("classifier", RandomForestClassifier(
        n_estimators=N_ESTIMATORS,
        class_weight='balanced',
        random_state=SEED,
        n_jobs=-1
    ))
])

print("Training Random Forest...")
model.fit(X_train, y_train)
print("Training complete.")

# Evaluate
y_pred = model.predict(X_test)
y_proba = model.predict_proba(X_test)[:, 1]

print("\nClassification Report:")
print(classification_report(y_test, y_pred, target_names=['No Churn', 'Churn']))

roc_auc = roc_auc_score(y_test, y_proba)
print(f"ROC-AUC: {roc_auc:.4f}")

# Confusion matrix
cm = confusion_matrix(y_test, y_pred)
print(f"Confusion Matrix:\n{cm}")

# SHAP explainability
print("\nComputing SHAP values...")
X_test_transformed = model.named_steps['preprocessor'].transform(X_test)
feature_names = model.named_steps['preprocessor'].get_feature_names_out()

explainer = shap.TreeExplainer(model.named_steps['classifier'])
shap_values_raw = explainer.shap_values(X_test_transformed)

# Adapt to different SHAP output formats
if isinstance(shap_values_raw, list):
    # Old format: list of two arrays (one per class)
    shap_vals = shap_values_raw[1]               # class 1 = churn
    exp_val = explainer.expected_value[1]
elif isinstance(shap_values_raw, np.ndarray) and shap_values_raw.ndim == 3:
    # Newer SHAP (≥0.40) returns (n_samples, n_features, n_classes)
    shap_vals = shap_values_raw[:, :, 1]         # class 1
    exp_val = explainer.expected_value[1] if isinstance(explainer.expected_value, (list, np.ndarray)) else explainer.expected_value
else:
    # Fallback for binary with single array
    shap_vals = shap_values_raw
    exp_val = explainer.expected_value

print(f"SHAP values for class 1 shape: {shap_vals.shape}")

# Summary plot
plt.figure(figsize=(10, 6))
shap.summary_plot(shap_vals, X_test_transformed, feature_names=feature_names, show=False)
plt.tight_layout()
plt.savefig(os.path.join(RESULTS_DIR, "shap_summary.png"), dpi=150)
plt.close()
print(f"SHAP summary saved to {RESULTS_DIR}/shap_summary.png")

# Feature importance (mean absolute SHAP)
feat_list = list(feature_names)
print(f"Number of features: {len(feat_list)}, SHAP array shape: {shap_vals.shape}")

# Ensure consistency
if len(feat_list) != shap_vals.shape[1]:
    print(f"Warning: Mismatch! Features: {len(feat_list)}, SHAP columns: {shap_vals.shape[1]}. Truncating to SHAP columns.")
    feat_list = feat_list[:shap_vals.shape[1]]

imp = np.abs(shap_vals).mean(axis=0)
if len(imp.shape) > 1:
    imp = imp.flatten()

importance_df = pd.DataFrame({
    'feature': feat_list,
    'importance': imp
}).sort_values('importance', ascending=False).head(15)

print("\nTop 15 features by mean |SHAP|:")
for _, row in importance_df.iterrows():
    print(f"  {row['feature']}: {row['importance']:.4f}")

# Export model and explainer
joblib.dump(model, os.path.join(MODELS_DIR, "RF_churn_model.pkl"))
joblib.dump(explainer, os.path.join(MODELS_DIR, "shap_explainer.pkl"))

print(f"\nModel saved to {os.path.join(MODELS_DIR, 'RF_churn_model.pkl')}")
print(f"Explainer saved to {os.path.join(MODELS_DIR, 'shap_explainer.pkl')}")
print("Done. You can now run the dashboard.")
