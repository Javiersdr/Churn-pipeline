import os
from typing import Literal

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

app = FastAPI()
MODEL_PATH = os.path.join("models", "RF_churn_model.pkl")
EXPLAINER_PATH = os.path.join("models", "shap_explainer.pkl")

model = joblib.load(MODEL_PATH)
explainer = joblib.load(EXPLAINER_PATH)

# We get the number of features
# (will be used later for top_n in SHAP so that you can choose how many features to see)
feature_names = model.named_steps['preprocessor'].get_feature_names_out()
MAX_FEATURES = len(feature_names)

# To avoid conflicts between customer tenure segment and tenure due to the first being dependent on the second
# we calculate it with this simple function
def add_tenure_segment(df):
    df["customer_tenure_segment"] = pd.cut(
        df["tenure"],
        bins=[-1, 12, 48, float("inf")],
        labels=["New", "Mid", "Loyal"]
    )
    return df

class CustomerFeatures(BaseModel):
    gender: Literal["Male", "Female"]
    senior_citizen: int = Field(..., ge = 0, le = 1)
    partner: Literal["Yes", "No"]
    dependents: Literal["Yes", "No"]
    tenure: int = Field(..., ge = 1, description="Must be >= 1")
    phone_service: Literal["Yes", "No"]
    multiple_lines: Literal["Yes", "No", "No phone service"]
    internet_service: Literal["DSL", "Fiber optic", "No"]
    online_security: Literal["Yes", "No", "No internet service"]
    online_backup: Literal["Yes", "No", "No internet service"]
    device_protection: Literal["Yes", "No", "No internet service"]
    tech_support: Literal["Yes", "No", "No internet service"]
    streaming_tv: Literal["Yes", "No", "No internet service"]
    streaming_movies: Literal["Yes", "No", "No internet service"]
    contract: Literal["Month-to-month", "One year", "Two year"]
    paperless_billing: Literal["Yes", "No"]
    payment_method: Literal[
        "Electronic check",
        "Mailed check",
        "Bank transfer (automatic)",
        "Credit card (automatic)",
    ]
    monthly_charges: float = Field(..., ge = 0.0)
    total_charges: float = Field(..., ge = 0.0)

@app.get("/")
def root():
    html_content = """
    <html>
    <head><title>Churn Predictor API</title></head>
    <body style="font-family: sans-serif; padding: 20px;">
        <h1>Churn Prediction API</h1>
        <p>Predict customer churn and understand why with SHAP.</p>
        <ul>
            <li><a href="/form">Interactive demo</a></li>
            <li><a href="/docs">API documentation</a></li>
            <li><a href="/health">Health check</a></li>
        </ul>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/predict")
def predict(features: CustomerFeatures,
            explain: bool = Query(True),
            top_n: int = Query(5, ge=1, le=MAX_FEATURES)):
    input_df = pd.DataFrame([features.model_dump()])
    input_df = add_tenure_segment(input_df)

    prediction = model.predict_proba(input_df)[0, 1]
    response = {"churn_probability": prediction}

    if explain and explainer is not None:
        X_transformed = model.named_steps["preprocessor"].transform(input_df)

        shap_raw = explainer.shap_values(X_transformed)
        if isinstance(shap_raw, list):
            shap_vals = shap_raw[1][0]
        else:
            shap_vals = shap_raw[0, :, 1] if shap_raw.ndim == 3 else shap_raw[0]

        feature_names = model.named_steps["preprocessor"].get_feature_names_out()
        contributions = [
            {"feature": str(name), "impact": float(val)}
            for name, val in zip(feature_names, shap_vals)
        ]
        total_shift = sum(abs(item["impact"]) for item in contributions)
        for item in contributions:
            item["impact"] = round((item["impact"] / total_shift) * 100, 1) if total_shift != 0 else 0.0

        contributions.sort(key=lambda x: abs(x["impact"]), reverse=True)

        exp_val = explainer.expected_value
        base_val = float(exp_val[1]) if isinstance(exp_val, (list, np.ndarray)) and len(exp_val) > 1 else float(exp_val)

        response["base_value"] = base_val
        response["top_factors"] = contributions[:top_n]

    return response

@app.get("/form", response_class=HTMLResponse)
def form():
    return FileResponse("templates/form.html")
