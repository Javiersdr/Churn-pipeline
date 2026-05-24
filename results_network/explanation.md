## Co‑Abandonment Analysis: Results

We applied network analysis (Leiden algorithm) to 7,043 telecom customers, identifying **7 distinct communities** of similar users. The global churn rate is **26.5%**, but risk is not evenly distributed.

### High‑Risk Communities (churn > 40%)
Communities **1** and **3** concentrate a disproportionate share of churn:

- **Community 1**: 48.5% churn (1,342 clients)
- **Community 3**: 43.2% churn (1,090 clients)

These two groups alone contain **2,432 clients at high risk of leaving** – approximately 35% of the customer base.

### What Makes High‑Risk Communities Different?

High‑risk communities (churn > 40%) differ from low‑risk communities (churn ≤ 40%) in several key aspects:

**Financial profile**
- **Total Charges**: 1,467€ (high‑risk) vs 2,782€ (low‑risk) — lower total spend, often because they are newer clients.
- **Monthly Charges**: 73.4€ (high‑risk) vs 60.7€ (low‑risk) — higher monthly bills despite lower total spend.

**Contract & engagement**
- **Customer Tenure Segment**: predominantly 'New' (61% of high‑risk) vs 'Mid' (46% of low‑risk) — shorter relationships.
- **Payment Method**: mainly 'Electronic check' (51%) vs 'Bank transfer (automatic)' (26%) — less commitment.
- **Tech Support**: 77% do **not** use tech support (vs 34% in low‑risk).

**Service adoption**
- **Device Protection**, **Online Backup**, **Streaming TV**, **Streaming Movies**: high‑risk customers consistently opt out of add‑on services. For example, 69% lack device protection (vs 37% in low‑risk).

**Interpretation**: High‑risk customers are typically newer clients with higher monthly charges, paying by electronic check, who haven't adopted additional services. They show low engagement and commitment, making them vulnerable to competitors.

---

### Extreme Comparison: Most Vulnerable vs Most Resilient

**Community 1** (48.5% churn) vs **Community 5** (1.2% churn)

| Feature | Community 1 (High Risk) | Community 5 (Low Risk) |
|---------|------------------------|------------------------|
| Tenure Segment | New | Loyal |
| Monthly Charges | 61.8€ | 21.9€ |
| Internet Service | DSL | No internet |
| Dependents | No | Yes |
| Payment Method | Electronic check | Bank transfer (automatic) |
| Streaming / Add‑ons | No | No internet service |

**Key Insight**: The most resilient community consists primarily of customers **without internet service** — basic phone plan users with long tenure and low bills. Their stability comes from simplicity, not from being "loyal" in the traditional sense. In contrast, the most vulnerable group has internet (DSL or Fiber) but rejects add‑on services, pays by electronic check, and has very short tenure.

---

### Community Health Index (CHI)

Inspired by ecological resilience theory, the CHI combines three dimensions:
- **Contract diversity** (Shannon index): more varied contracts = healthier community.
- **Retention rate** (1 – churn rate): higher retention = healthier.
- **Relative size**: larger communities contribute more to overall portfolio stability.

A higher CHI indicates a more resilient community. The index ranges from 0 to 1, with values above 0.8 being very healthy.

| Community | CHI | Retention | Contract Diversity | Relative Size |
|-----------|-----|-----------|-------------------|---------------|
| 0 | 0.846 | 89.4% | 1.42 | 0.22 |
| 4 | 0.806 | 88.5% | 1.41 | 0.13 |
| 2 | 0.647 | 71.8% | 1.03 | 0.19 |
| 5 | 0.643 | 98.8% | 0.86 | 0.08 |
| 3 | 0.610 | 56.8% | 1.11 | 0.16 |
| 1 | 0.446 | 51.5% | 0.60 | 0.22 |

**Interpretation**: Communities 0 and 4 are the healthiest (high retention, diverse contracts). Communities 1 and 3 are the most fragile — not only do they have high churn, but their low contract diversity suggests they are "trapped" in month‑to‑month plans, reinforcing their risk profile.

---

### Recommendations

1. **Target high‑risk communities (1 and 3)**: ~2,400 clients with high monthly charges, short tenure, and low service adoption. Offer annual contracts with discounts, bundle internet with add‑ons (streaming, backup), and incentivize switching to automatic payment.

2. **Protect the resilient segment (Community 5)**: These customers are stable but low‑value. Don't try to upsell aggressively; instead, ensure they never have a reason to leave.

3. **Monitor the borderline communities (0, 2, 4)**: They are currently healthy but could shift if market conditions change. The CHI provides an early‑warning metric.