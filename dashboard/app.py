import json
import os

import duckdb
import joblib
import matplotlib.pyplot as plt
import pandas as pd
import shap
import streamlit as st

# Paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "churn_data.duckdb")
MODEL_PATH = os.path.join(PROJECT_ROOT, "models", "RF_churn_model.pkl")
EXPLAINER_PATH = os.path.join(PROJECT_ROOT, "models", "shap_explainer.pkl")
RESULTS_NET = os.path.join(PROJECT_ROOT, "results_network")
RESULTS_RF = os.path.join(PROJECT_ROOT, "results_RF")

# Page configuration & navigation
st.set_page_config(page_title="Churn Risk Predictor", layout="wide")

st.sidebar.title("Navigation")
view = st.sidebar.radio("Select view", ["Individual Prediction", "Community Analysis"])

# VIEW 1: Individual Random Forest prediction with SHAP
if view == "Individual Prediction":
    st.title("Churn Risk Predictor")
    st.markdown("This model has been trained on the processed pipeline data")

    @st.cache_resource
    def load_artifacts():
        """Load customer-level data + model + explainer."""
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
        if "churn" in df.columns and df["churn"].dtype == "object":
            df["churn"] = df["churn"].map({"Yes": 1, "No": 0})
        model = joblib.load(MODEL_PATH) if os.path.exists(MODEL_PATH) else None
        explainer = joblib.load(EXPLAINER_PATH) if os.path.exists(EXPLAINER_PATH) else None
        return df, model, explainer
        df = con.execute("SELECT * FROM intermediate.int_churn_features").fetchdf()
        if "churn" in df.columns and df["churn"].dtype == "object":
            df["churn"] = df["churn"].map({"Yes": 1, "No": 0})
        model = joblib.load(MODEL_PATH) if os.path.exists(MODEL_PATH) else None
        explainer = joblib.load(EXPLAINER_PATH) if os.path.exists(EXPLAINER_PATH) else None
        return df, model, explainer

    df, model, explainer = load_artifacts()

    # Precompute predictions for all customers
    @st.cache_data
    def compute_all_predictions(df, _model):
        X_all = df.drop(columns=["customer_id", "churn"])
        probas = _model.predict_proba(X_all)[:, 1]
        preds = df[["customer_id", "tenure", "monthly_charges"]].copy()
        preds["churn_probability"] = probas
        return preds.sort_values("churn_probability", ascending=False)

    preds_df = compute_all_predictions(df, model)

    # Merge with original features for richer tables
    feature_df = df[["customer_id", "tenure", "monthly_charges", "contract",
                     "internet_service", "payment_method", "churn"]]
    preds_full = preds_df.merge(feature_df, on="customer_id", how="left")

    # INDIVIDUAL CUSTOMER ANALYSIS (top of page)
    st.sidebar.header("▸ Individual lookup")
    manual_id = st.sidebar.selectbox(
        "Customer ID",
        options=sorted(df["customer_id"].unique()),
        index=None,
        placeholder="Type or select a Customer ID"
    )

    if manual_id:
        customer_id = manual_id
    else:
        customer_id = None

    if customer_id and customer_id in df["customer_id"].values:
        customer_row = df[df["customer_id"] == customer_id].iloc[0]

        with st.container(border=True):
            st.markdown("**▸ Customer Profile**")
            colA, colB, colC = st.columns(3)
            colA.metric("Tenure (meses)", customer_row.get("tenure", "N/A"))
            colB.metric("Cargos mensuales", customer_row.get("monthly_charges", "N/A"))
            colC.metric("Llamadas a soporte", customer_row.get("customer_service_calls", "N/A"))

            if model is not None and explainer is not None:
                target_col = "churn"
                input_data = customer_row.drop(labels=["customer_id", target_col])
                input_df = pd.DataFrame([input_data])

                proba = model.predict_proba(input_df)[0, 1]
                prediction = "High" if proba > 0.5 else "Low"
                st.markdown(f"**▸ Churn risk: {prediction}** ({proba:.1%})")
                st.progress(min(int(proba * 100), 100))

                # SHAP waterfall
                preprocessor = model.named_steps["preprocessor"]
                X_transformed = preprocessor.transform(input_df)

                shap_vals = explainer.shap_values(X_transformed)[0, :, 1]
                exp_val = explainer.expected_value[1]
                if len(shap_vals.shape) != 1:
                    shap_vals = shap_vals.flatten()

                fig, ax = plt.subplots()
                shap.waterfall_plot(
                    shap.Explanation(values=shap_vals,
                                     base_values=exp_val,
                                     data=X_transformed[0],
                                     feature_names=preprocessor.get_feature_names_out()),
                    show=False
                )
                st.pyplot(fig)
    elif customer_id:
        st.warning("Customer ID not found.")

    # GENERAL RISK OVERVIEW
    with st.expander("▸ Risk overview & global importance", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("High-risk (>80%)", f"{len(preds_full[preds_full['churn_probability'] > 0.8])} clients")
            with st.popover("Show sample"):
                st.dataframe(
                    preds_full[preds_full["churn_probability"] > 0.8]
                    .head(5)
                    .style.format({"churn_probability": "{:.1%}"}),
                    column_order=["customer_id", "churn_probability", "tenure",
                                  "monthly_charges", "contract", "internet_service", "payment_method"]
                )

        with col2:
            borderline = preds_full[(preds_full['churn_probability'] > 0.4) & (preds_full['churn_probability'] < 0.6)]
            st.metric("Borderline (40-60%)", f"{len(borderline)} clients")
            with st.popover("Show sample"):
                st.dataframe(
                    borderline.head(5)
                    .style.format({"churn_probability": "{:.1%}"}),
                    column_order=["customer_id", "churn_probability", "tenure",
                                  "monthly_charges", "contract", "internet_service", "payment_method"]
                )

        with col3:
            st.metric("Low-risk (<20%)", f"{len(preds_full[preds_full['churn_probability'] < 0.2])} clients")
            with st.popover("Show sample"):
                st.dataframe(
                    preds_full[preds_full["churn_probability"] < 0.2]
                    .head(5)
                    .style.format({"churn_probability": "{:.1%}"}),
                    column_order=["customer_id", "churn_probability", "tenure",
                                  "monthly_charges", "contract", "internet_service", "payment_method"]
                )

        # Histogram + SHAP side by side
        col_img1, col_img2 = st.columns(2)
        with col_img1:
            st.markdown("**▸ Distribution of predictions**")
            fig_hist, ax_hist = plt.subplots(figsize=(6, 4))
            ax_hist.hist(preds_df["churn_probability"], bins=30, color='#1f77b4', edgecolor='white')
            ax_hist.axvline(x=0.5, color='red', linestyle='--', label='Threshold (0.5)')
            ax_hist.set_xlabel("Churn probability")
            ax_hist.set_ylabel("Customers")
            ax_hist.legend()
            st.pyplot(fig_hist)

        with col_img2:
            st.markdown("**▸ Global feature importance (SHAP)**")
            shap_img_path = os.path.join(RESULTS_RF, "shap_summary.png")
            if os.path.exists(shap_img_path):
                st.image(shap_img_path)
            else:
                st.info("SHAP summary not found. Run the model script first.")

# VIEW 2: Community Analysis (2x2 grid)
elif view == "Community Analysis":
    st.title("Community Analysis")
    st.markdown("Churn communities detected with Leiden and represented with UMAP")

    assignments_path = os.path.join(RESULTS_NET, "community_assignments.csv")
    table_path = os.path.join(RESULTS_NET, "community_churn_table.png")
    bars_path = os.path.join(RESULTS_NET, "community_churn_bars.png")
    chi_path = os.path.join(RESULTS_NET, "community_chi.png")
    network_path = os.path.join(RESULTS_NET, "client_network.html")
    num_comp_path = os.path.join(RESULTS_NET, "community_num_comparison.png")
    cat_comp_path = os.path.join(RESULTS_NET, "community_cat_comparison.png")
    explanation_path = os.path.join(RESULTS_NET, "explanation.md")

    if not os.path.exists(assignments_path):
        st.error("Community assignments not found. Please run `co_churn_network.py` first.")
    else:
        # First row
        row1_col1, row1_col2 = st.columns(2)

        # 1. Community Summary Table
        with row1_col1:
            with st.container(border=True):
                st.markdown("**▸ Community Summary**")
                if os.path.exists(table_path):
                    st.image(table_path)
                else:
                    df_comm = pd.read_csv(assignments_path)
                    comm_stats = df_comm.groupby("community").agg(
                        total_customers=("customer_id", "count")
                    ).reset_index()
                    try:
                        con = duckdb.connect(os.path.join(PROJECT_ROOT, "data", "churn_data.duckdb"))
                        churn_df = con.execute("SELECT * FROM intermediate.int_churn_features").fetchdf()
                        churn_df["churn"] = churn_df["churn"].map({'Yes':1, 'No':0})
                        merged = df_comm.merge(churn_df[["customer_id", "churn"]], on="customer_id", how="left")
                        churn_rate = merged.groupby("community")["churn"].mean()
                        comm_stats["churn_rate"] = comm_stats["community"].map(churn_rate)
                        st.dataframe(comm_stats.style.format({"churn_rate": "{:.1%}"}))
                    except (duckdb.IOException, FileNotFoundError, pd.errors.DatabaseError):
                        st.dataframe(comm_stats)

        # 2. Community Charts (sub-grid 2x2)
        with row1_col2:
            with st.container(border=True):
                st.markdown("**▸ Community Charts**")
                inner_col1, inner_col2 = st.columns(2)
                with inner_col1:
                    if os.path.exists(bars_path):
                        st.markdown("**Churn Rate per Community**")
                        st.image(bars_path)
                    if os.path.exists(num_comp_path):
                        st.markdown("**Highest vs Lowest (Numeric)**")
                        st.image(num_comp_path)
                with inner_col2:
                    if os.path.exists(chi_path):
                        st.markdown("**Community Health Index**")
                        st.image(chi_path)
                    if os.path.exists(cat_comp_path):
                        st.markdown("**Highest vs Lowest (Categorical)**")
                        st.image(cat_comp_path)

        # Second row
        row2_col1, row2_col2 = st.columns(2)

        # 3. Interactive Network
        with row2_col1:
            network_json_path = os.path.join(RESULTS_NET, "network_figure.json")
            if os.path.exists(network_json_path):
                with st.container(border=True):
                    st.markdown("**▸ Customer Network**")
                    with open(network_json_path, "r") as f:
                        fig = json.load(f)
                    st.plotly_chart(fig, width='content', height=600)
            elif os.path.exists(network_path):
                # Fallback al HTML si aún no se ha generado el JSON
                with st.container(border=True):
                    st.markdown("**▸ Customer Network**")
                    with open(network_path, "r", encoding="utf-8") as f:
                        html_content = f.read()
                    st.components.v1.html(html_content, height=600, scrolling=True)
            else:
                with st.container(border=True):
                    st.markdown("**▸ Customer Network**")
                    st.warning("Network file not found.")

        # 4. Insights
        with row2_col2:
            with st.container(border=True):
                st.markdown("**▸ Key Insights**")
                if os.path.exists(explanation_path):
                    with open(explanation_path, "r", encoding="utf-8") as f:
                        md_text = f.read()
                    # Show first few lines as preview
                    preview_lines = md_text.strip().split("\n")[:3]
                    st.markdown("\n".join(preview_lines))
                    st.caption("...")
                    if st.button("View Fullscreen", key="insights_fullscreen"):
                        @st.dialog("Key Insights", width="large")
                        def show_insights():
                            st.markdown(md_text)
                        show_insights()
                else:
                    st.info("Insights file not found.")
