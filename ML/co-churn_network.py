"""
Unsupervised co-churn network analysis
Reads cleaned data from intermediate.int_churn_features
and calculates Leiden for community detection.
Results are plotted and summarized for the dashboard.
"""

import os
import duckdb
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler, OneHotEncoder, MinMaxScaler
from sklearn.compose import ColumnTransformer
from scipy.sparse import csr_matrix
from scipy.stats import entropy
import matplotlib.pyplot as plt
import plotly.express as px
import json
import leidenalg
import igraph as ig
import umap

# Paths and configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, '..')
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'churn_data.duckdb')
OUTPUT_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, "results_network"))
SEED=13

# Parameters for analysis tweaking
similarity_thresh = 95
min_community_size = 100

# Let's create the results folder
os.makedirs(OUTPUT_DIR, exist_ok=True)


# Loading intermediate data because we need the complete information for this analysis
con = duckdb.connect(DB_PATH)
con.execute("INSTALL httpfs; LOAD httpfs;")
con.execute(f"""
    SET s3_region='us-east-1';
    SET s3_endpoint='minio:9000';
    SET s3_url_style='path';
    SET s3_access_key_id='admin';
    SET s3_secret_access_key='password';
    SET s3_use_ssl=false;
 """)
df = con.execute("SELECT * FROM intermediate.int_churn_features").fetchdf()
print(f"Clients: {len(df)}")

target_col = "churn"
id_col = "customer_id"
df[target_col] = df[target_col].map({'Yes': 1, 'No': 0})

# Features (excluding ID and target)
feature_cols = [c for c in df.columns if c not in [id_col, target_col]]
X = df[feature_cols]


cat_cols = X.select_dtypes(include=["object", "string"]).columns.tolist()
num_cols = X.select_dtypes("number").columns.tolist()
print(f"Categorical variables: {len(cat_cols)}, numeric: {len(num_cols)}")

preprocessor = ColumnTransformer([
    ("num", StandardScaler(), num_cols),
    ("cat", OneHotEncoder(drop="first", handle_unknown="ignore"), cat_cols)
])
X_encoded = preprocessor.fit_transform(X)
print(f"Dimensions after One-Hot encoding: {X_encoded.shape}")

# Calculate cosine similarity (use float32 to save memory)
similarity_matrix = cosine_similarity(X_encoded).astype(np.float32)

threshold = np.percentile(similarity_matrix, similarity_thresh)   # similarity_thresh = 95 or 98
print(f"Similarity threshold (percentile {similarity_thresh}): {threshold:.4f}")

adjacency_sparse = csr_matrix(
    (similarity_matrix > threshold).astype(np.int8)
)
adjacency_sparse.setdiag(0)
adjacency_sparse.eliminate_zeros()

print(f"Nodes: {adjacency_sparse.shape[0]}, Edges: {adjacency_sparse.nnz // 2}")

# We want to free memory
del similarity_matrix

# We use Leiden algorithm
G_ig = ig.Graph.Weighted_Adjacency(adjacency_sparse, mode='undirected')
partition = leidenalg.find_partition(G_ig, leidenalg.ModularityVertexPartition, seed=SEED)
community_dict = {node: part for node, part in enumerate(partition.membership)}

# Filter tiny communities
community_counts = pd.Series(community_dict).value_counts()
valid_communities = community_counts[community_counts >= min_community_size].index.tolist()

print(f"\nFiltering out communities smaller than {min_community_size} members.")
print(f"Remaining communities: {valid_communities}")

# Keep only customers whose node belongs to a valid community
valid_nodes = [n for n, comm in community_dict.items() if comm in valid_communities]

# After filtering, we calculate network community stats
community_stats = []
for comm_id in valid_communities:
    nodes_in_comm = [n for n, c in community_dict.items() if c == comm_id]
    # use the original dataframe and filter by index
    churn_values = df.loc[df.index.isin(nodes_in_comm), target_col]
    community_stats.append({
        "community_id": comm_id,
        "size": len(nodes_in_comm),
        "churn_rate": churn_values.mean(),
    })

community_df = pd.DataFrame(community_stats)

# Calculate overall churn rate on valid customers
overall_churn_rate = df.loc[df.index.isin(valid_nodes), target_col].mean() * 100

# Community size statistics to show
num_communities = len(community_stats)
sizes = community_df["size"]
avg_size = sizes.mean()
median_size = sizes.median()
min_size = sizes.min()
max_size = sizes.max()

print(f"\nTotal communities detected: {num_communities}")
print(f"Community sizes: avg={avg_size:.0f}, median={median_size:.0f}, min={min_size}, max={max_size}")
print("\nCommunities with a higher churn rate:")
print(community_df.sort_values("churn_rate", ascending=False).head(5))

# Save community assignments for downstream use (dashboard, etc.)
community_assignments = pd.DataFrame({
    "customer_id": df[id_col],
    "community": [community_dict[i] for i in range(len(df))]
})
community_assignments.to_csv(os.path.join(OUTPUT_DIR, "community_assignments.csv"), index=False)


# Now, we use UMAP for visualization
print("Reducing dimensionality with UMAP")
reducer = umap.UMAP(n_components=2, random_state=SEED)
X_embedded = reducer.fit_transform(X_encoded)

viz_df = pd.DataFrame({
    "x": X_embedded[:, 0],
    "y": X_embedded[:, 1],
    "churn": df[target_col],
    "community": [community_dict[i] for i in range(len(df))],
    "customer_id": df[id_col].values
})

# The actionable insight: communities at risk of co-churn
high_risk_communities = community_df[community_df["churn_rate"] > 0.4]["community_id"].tolist()
print(f"\nCommunities at risk of co-churn (>40% churn): {high_risk_communities}")
print("We should prioritize retention in these communities because a client leaving might trigger a massive exit")

# Info for the HTML visualization
title_text = (
    f"Customer Communities (Leiden + UMAP)<br>"
    f"Overall churn: {overall_churn_rate:.1f}% | "
    f"Communities: {num_communities} | "
    f"Avg size: {avg_size:.0f} | "
    f"Median size: {median_size:.0f}<br>"
    f"High-risk communities (churn > 40%): {high_risk_communities}"
)

fig = px.scatter(
    viz_df, x="x", y="y",
    color=viz_df["community"].astype(str),
    symbol=viz_df["churn"].map({0: "Stays", 1: "Leaves"}),
    hover_data=["customer_id", "churn", "community"],
    title=title_text,
    color_discrete_sequence=px.colors.qualitative.Alphabet
)

output_file = os.path.join(OUTPUT_DIR, "client_network.html")
fig_json = fig.to_json()
json_path = os.path.join(OUTPUT_DIR, "network_figure.json")
with open(json_path, "w") as f:
    f.write(fig_json)
print(f"Plotly figure saved to {json_path}")
fig.write_html(output_file)
print(f"\nVisualization saved at {output_file}")

# Select original features
comparison_features = [
    "tenure", "monthly_charges", "total_charges",
    "contract", "internet_service", "payment_method",
    "senior_citizen", "partner", "dependents", "phone_service",
    "multiple_lines", "online_security", "online_backup",
    "device_protection", "tech_support", "streaming_tv",
    "streaming_movies", "paperless_billing", "customer_tenure_segment"
]

# Community health index based on ecological resilience
def shannon_diversity(series):
    """Shannon diversity index (base 2) of a categorical series."""
    counts = series.value_counts(normalize=True)
    return entropy(counts, base=2)

chi_data = []
for comm_id in valid_communities:
    nodes = [n for n, c in community_dict.items() if c == comm_id]
    sub = df.loc[nodes]
    contract_diversity = shannon_diversity(sub["contract"])
    retention = 1 - sub[target_col].mean()
    relative_size = len(nodes) / len(valid_nodes)
    # Simple average; you can weight differently if you prefer
    chi = (contract_diversity + retention + relative_size) / 3
    chi_data.append({
        "community_id": comm_id,
        "contract_diversity": contract_diversity,
        "retention": retention,
        "relative_size": relative_size,
        "chi": chi
    })

chi_df = pd.DataFrame(chi_data)
community_df = community_df.merge(chi_df, on="community_id", how="left")

# Bar chart of CHI per community
fig_chi, ax = plt.subplots(figsize=(8, 5))
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
colors_chi = ['#2ca02c' if row.churn_rate < 0.3 else '#ff7f0e' if row.churn_rate < 0.5 else '#d62728'
              for _, row in community_df.iterrows()]
ax.bar(community_df["community_id"].astype(str), community_df["chi"], color=colors_chi)
ax.set_xlabel("Community")
ax.set_ylabel("Community Health Index")
ax.set_title("Community Health Index (CHI) by community\n(Green = low churn, Orange = moderate, Red = high)")
plt.tight_layout()
fig_chi.savefig(os.path.join(OUTPUT_DIR, "community_chi.png"), dpi=150)
plt.close()

# Print summary
print("\nCommunity Health Index (CHI):")
print(community_df[["community_id", "churn_rate", "chi"]].sort_values("chi", ascending=False))

# Visualizations

# Summary table (community_id, size, churn_rate)
fig_table, ax = plt.subplots(figsize=(14, len(community_df) * 0.8 + 2))
ax.axis('off')
table_data = community_df[["community_id", "size", "churn_rate"]].copy()
table_data["churn_rate"] = table_data["churn_rate"].apply(lambda x: f"{x:.1%}")
table_data.columns = ["Community", "Size", "Churn rate"]
table = ax.table(cellText=table_data.values, colLabels=table_data.columns,
                 cellLoc='center', loc='center')
table.auto_set_font_size(False)
table.set_fontsize(12)
table.scale(1, 1.8)
for key, cell in table.get_celld().items():
    if key[0] == 0:
        cell.set_fontsize(14)
        cell.set_text_props(weight='bold')
plt.title("Client communities by churn rate", fontsize=16, fontweight='bold', pad=20)
plt.tight_layout()
fig_table.savefig(os.path.join(OUTPUT_DIR, "community_churn_table.png"), dpi=150, bbox_inches='tight')
plt.close()

# Bar chart of churn rate per community
fig_bar, ax = plt.subplots(figsize=(10, 6))
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
colors = ['#d62728' if row.churn_rate > 0.4 else '#1f77b4' for _, row in community_df.iterrows()]
ax.bar(community_df["community_id"].astype(str), community_df["churn_rate"], color=colors)
ax.axhline(y=overall_churn_rate / 100, color='gray', linestyle='--',
           label=f'Global average ({overall_churn_rate:.1f}%)')
ax.set_xlabel("Community")
ax.set_ylabel("Churn rate")
ax.set_title("Churn rate per community\n(Red > 40%: High risk)", fontsize=15, fontweight='bold')
ax.legend()
plt.tight_layout()
fig_bar.savefig(os.path.join(OUTPUT_DIR, "community_churn_bars.png"), dpi=150)
plt.close()

# High‑risk vs low‑risk comparison (all high‑risk comms vs all low‑risk)
high_risk_comms = community_df[community_df["churn_rate"] > 0.4]["community_id"].tolist()
low_risk_comms  = community_df[community_df["churn_rate"] <= 0.4]["community_id"].tolist()

hr_mask = df.index.isin([n for n, c in community_dict.items() if c in high_risk_comms])
lr_mask = df.index.isin([n for n, c in community_dict.items() if c in low_risk_comms])

hr_customers = df[hr_mask]
lr_customers = df[lr_mask]

# Grouped bar chart: high‑risk vs low‑risk (numeric features)
num_features = [f for f in comparison_features if f in df.columns and df[f].dtype in ['int64', 'float64']]
if num_features:
    hr_means = hr_customers[num_features].mean()
    lr_means = lr_customers[num_features].mean()
    x = np.arange(len(num_features))
    width = 0.35

    fig_bar_comp, ax = plt.subplots(figsize=(10, 6))
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.bar(x - width/2, hr_means, width, label='High-risk communities', color='#d62728')
    ax.bar(x + width/2, lr_means, width, label='Low-risk communities', color='#1f77b4')
    ax.set_ylabel('Average value')
    ax.set_title('Average profile: high-risk vs low-risk communities (numeric features)')
    ax.set_xticks(x)
    ax.set_xticklabels([f.replace('_', ' ').title() for f in num_features], rotation=30, ha='right')
    ax.legend()
    plt.tight_layout()
    fig_bar_comp.savefig(os.path.join(OUTPUT_DIR, "community_numeric_comparison.png"), dpi=150)
    plt.close()

# Build explanation text for the overall high‑risk vs low‑risk
comparisons = []
for col in comparison_features:
    if col not in df.columns:
        continue
    if df[col].dtype in ['int64', 'float64']:
        hr_avg = hr_customers[col].mean()
        lr_avg = lr_customers[col].mean()
        rel_diff = abs(hr_avg - lr_avg) / abs(lr_avg) if lr_avg != 0 else abs(hr_avg - lr_avg)
        comparisons.append({
            "feature": col, "type": "numeric", "hr_val": hr_avg, "lr_val": lr_avg, "rel_diff": rel_diff
        })
    else:
        hr_mode = hr_customers[col].mode().iloc[0] if not hr_customers[col].mode().empty else "N/A"
        lr_mode = lr_customers[col].mode().iloc[0] if not lr_customers[col].mode().empty else "N/A"
        if hr_mode != lr_mode:
            hr_freq = (hr_customers[col] == hr_mode).mean()
            lr_freq = (lr_customers[col] == lr_mode).mean()
            comparisons.append({
                "feature": col, "type": "categorical",
                "hr_mode": hr_mode, "lr_mode": lr_mode,
                "hr_freq": hr_freq, "lr_freq": lr_freq,
                "rel_diff": abs(hr_freq - lr_freq)
            })

comparisons.sort(key=lambda x: x["rel_diff"], reverse=True)
top_comparisons = comparisons[:8]

if top_comparisons:
    explanation_items = []
    for c in top_comparisons:
        col_name = c["feature"].replace("_", " ").title()
        if c["type"] == "numeric":
            explanation_items.append(
                f"- **{col_name}**: average {c['hr_val']:.1f} (high-risk) vs {c['lr_val']:.1f} (low-risk)"
            )
        else:
            explanation_items.append(
                f"- **{col_name}**: predominantly '{c['hr_mode']}' ({c['hr_freq']:.0%} of high-risk) "
                f"vs '{c['lr_mode']}' ({c['lr_freq']:.0%} of low-risk)"
            )
    overall_explanation = "\n".join(explanation_items)
else:
    overall_explanation = "No significant differences were found."

# Direct comparison: highest‑churn community vs lowest‑churn community
top_churn_comm = community_df.loc[community_df["churn_rate"].idxmax(), "community_id"]
bottom_churn_comm = community_df.loc[community_df["churn_rate"].idxmin(), "community_id"]

top_mask = df.index.isin([n for n, c in community_dict.items() if c == top_churn_comm])
bottom_mask = df.index.isin([n for n, c in community_dict.items() if c == bottom_churn_comm])

top_customers = df[top_mask]
bottom_customers = df[bottom_mask]

print(f"\n--- Direct comparison: Community {int(top_churn_comm)} "
      f"({community_df.loc[community_df['community_id']==top_churn_comm, 'churn_rate'].values[0]:.1%} churn) "
      f"vs Community {int(bottom_churn_comm)} "
      f"({community_df.loc[community_df['community_id']==bottom_churn_comm, 'churn_rate'].values[0]:.1%} churn) ---")

direct_comparisons = []
for col in comparison_features:
    if col not in df.columns:
        continue
    if df[col].dtype in ['int64', 'float64']:
        top_avg = top_customers[col].mean()
        bottom_avg = bottom_customers[col].mean()
        direct_comparisons.append({
            "feature": col, "type": "numeric",
            "top_val": top_avg, "bottom_val": bottom_avg,
            "diff": abs(top_avg - bottom_avg)
        })
    else:
        top_mode = top_customers[col].mode().iloc[0] if not top_customers[col].mode().empty else "N/A"
        bottom_mode = bottom_customers[col].mode().iloc[0] if not bottom_customers[col].mode().empty else "N/A"
        if top_mode != bottom_mode:
            top_freq = (top_customers[col] == top_mode).mean()
            bottom_freq = (bottom_customers[col] == bottom_mode).mean()
            direct_comparisons.append({
                "feature": col, "type": "categorical",
                "top_mode": top_mode, "bottom_mode": bottom_mode,
                "top_freq": top_freq, "bottom_freq": bottom_freq,
                "diff": abs(top_freq - bottom_freq)
            })

direct_comparisons.sort(key=lambda x: x["diff"], reverse=True)
top_direct = direct_comparisons[:10]

print("\nKey differences:")
for c in top_direct:
    col_name = c["feature"].replace("_", " ").title()
    if c["type"] == "numeric":
        print(f"  • {col_name}: {c['top_val']:.1f} vs {c['bottom_val']:.1f}")
    else:
        print(f"  • {col_name}: '{c['top_mode']}' vs '{c['bottom_mode']}'")

# Grouped bar chart for numeric features (direct comparison)
if num_features:
    top_means = top_customers[num_features].mean()
    bottom_means = bottom_customers[num_features].mean()
    x = np.arange(len(num_features))
    width = 0.35

    fig_num_comp, ax = plt.subplots(figsize=(10, 6))
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.bar(x - width/2, top_means, width, label=f'Community {int(top_churn_comm)} (high churn)', color='#d62728')
    ax.bar(x + width/2, bottom_means, width, label=f'Community {int(bottom_churn_comm)} (low churn)', color='#1f77b4')
    ax.set_ylabel('Average value')
    ax.set_title(f'Highest vs lowest churn-risk: Community {int(top_churn_comm)} vs Community {int(bottom_churn_comm)} (charges)')
    ax.set_xticks(x)
    ax.set_xticklabels([f.replace('_', ' ').title() for f in num_features], rotation=30, ha='right')
    ax.legend()
    plt.tight_layout()
    fig_num_comp.savefig(os.path.join(OUTPUT_DIR, "community_num_comparison.png"), dpi=150)
    plt.close()

# Grouped bar chart for categorical features (with category labels)
cat_diffs = [c for c in top_direct if c["type"] == "categorical"]
if cat_diffs:
    fig_cat, ax_cat = plt.subplots(figsize=(12, 6))
    ax_cat.spines['top'].set_visible(False)
    ax_cat.spines['right'].set_visible(False)
    labels = [c["feature"].replace("_", " ").title() for c in cat_diffs]
    x = np.arange(len(labels))
    width = 0.35

    bars1 = ax_cat.bar(x - width/2, [c["top_freq"] for c in cat_diffs], width,
                       label=f'Community {int(top_churn_comm)} (high churn)', color='#d62728')
    bars2 = ax_cat.bar(x + width/2, [c["bottom_freq"] for c in cat_diffs], width,
                       label=f'Community {int(bottom_churn_comm)} (low churn)', color='#1f77b4')

    for i, c in enumerate(cat_diffs):
        ax_cat.text(bars1[i].get_x() + bars1[i].get_width()/2, bars1[i].get_height() + 0.02,
                    c['top_mode'], ha='center', va='bottom', fontsize=8, color='#d62728', fontweight='bold')
        ax_cat.text(bars2[i].get_x() + bars2[i].get_width()/2, bars2[i].get_height() + 0.02,
                    c['bottom_mode'], ha='center', va='bottom', fontsize=8, color='#1f77b4', fontweight='bold')

    ax_cat.set_ylabel('Proportion')
    ax_cat.set_title('Categorical feature differences between highest- and lowest-churn communities')
    ax_cat.set_xticks(x)
    ax_cat.set_xticklabels(labels, rotation=45, ha='right')
    ax_cat.legend()
    plt.tight_layout()
    fig_cat.savefig(os.path.join(OUTPUT_DIR, "community_cat_comparison.png"), dpi=150)
    plt.close()

# Save combined Markdown explanation
if high_risk_comms:
    community_names = ", ".join(map(str, high_risk_comms[:-1])) + " and " + str(high_risk_comms[-1]) if len(high_risk_comms) > 1 else str(high_risk_comms[0])
else:
    community_names = "no high‑risk communities"

if top_direct:
    direct_lines = [f"- **{c['feature'].replace('_', ' ').title()}**: "
                   f"{c['top_val']:.1f} vs {c['bottom_val']:.1f}" if c['type'] == 'numeric'
                   else f"- **{c['feature'].replace('_', ' ').title()}**: "
                   f"'{c['top_mode']}' vs '{c['bottom_mode']}'"
                   for c in top_direct]
    direct_explanation = "\n".join(direct_lines)
else:
    direct_explanation = "No differences found."

# Final summary prints to check everything went okay and what is the output folder
total_high_risk_clients = community_df[community_df["community_id"].isin(high_risk_comms)]["size"].sum()
total_valid_clients = len(valid_nodes)
pct_high_risk = total_high_risk_clients / total_valid_clients * 100
print(f"\nTotal clients in high-risk communities: {total_high_risk_clients:.0f} ({pct_high_risk:.1f}% of valid clients)")
print(f"All files saved in {OUTPUT_DIR}")