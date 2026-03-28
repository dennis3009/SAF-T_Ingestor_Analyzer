"""
scoring.py - Enhanced behavioral risk scoring for SAF-T companies.

For each company, computes a score from 0 to 100 (100 = fully healthy).
Penalties are applied for:
  1. Revenue volatility (high coefficient of variation in monthly totals)
  2. Customer concentration (top customer > 50 % of total sales)
  3. Revenue spikes (month-over-month growth > 100 %)
  4. Transaction irregularity (uneven distribution across months)
  5. Trend deterioration (revenue declining for 3+ months)
  6. Dependency increase over time (growing partner concentration)

Output: data/json/scores.json
"""

import os
import json
import math
import csv
from collections import defaultdict

TRANSACTIONS_CSV = os.path.join(
    os.path.dirname(__file__), "data", "csv", "transactions.csv"
)
MONTHLY_METRICS_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "monthly_metrics.json"
)
SCORES_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "scores.json"
)
GRAPH_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "graph.json"
)

RISK_THRESHOLDS = {
    "Healthy": 70,
    "Watch": 40,
    "Risky": 0,
}


def _load_transactions(csv_path: str) -> list:
    """Load transactions from CSV file."""
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                row["amount"] = float(row["amount"])
            except ValueError:
                row["amount"] = 0.0
            rows.append(row)
    return rows


def _coeff_of_variation(values: list) -> float:
    """Coefficient of variation: std / mean. Returns 0 if mean is 0."""
    if not values or len(values) < 2:
        return 0.0
    n = len(values)
    mean = sum(values) / n
    if mean == 0:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / n
    return math.sqrt(variance) / mean


def _risk_level(score: float) -> str:
    if score >= RISK_THRESHOLDS["Healthy"]:
        return "Healthy"
    elif score >= RISK_THRESHOLDS["Watch"]:
        return "Watch"
    return "Risky"


def _load_monthly_metrics(path: str) -> dict:
    """Load monthly metrics and return as company_id -> metrics dict."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return {m["company_id"]: m for m in data}


def score_companies(
    csv_path: str = TRANSACTIONS_CSV,
    metrics_path: str = MONTHLY_METRICS_JSON,
    output_path: str = SCORES_JSON,
) -> list:
    """
    Compute behavioral risk scores for all companies.

    Returns a list of score dicts with trend and explanation.
    """
    transactions = _load_transactions(csv_path)
    metrics_map = _load_monthly_metrics(metrics_path)

    # Group transactions by company
    by_company: dict = defaultdict(list)
    for tx in transactions:
        by_company[tx["company_id"]].append(tx)

    scores = []

    for company_id, txs in by_company.items():
        score = 100.0
        reasons = []

        # Get trend from time series if available
        company_metrics = metrics_map.get(company_id, {})
        trend = company_metrics.get("trend", "stable")

        # Only sales count toward revenue metrics
        sales = [t for t in txs if t["type"] == "sale"]
        if not sales:
            scores.append(
                {
                    "company_id": company_id,
                    "score": 50.0,
                    "risk_level": "Watch",
                    "trend": trend,
                    "explanation": ["No sales transactions found"],
                }
            )
            continue

        # --- Monthly revenue totals ---
        monthly: dict = defaultdict(float)
        for t in sales:
            ym = t["date"][:7]  # "YYYY-MM"
            monthly[ym] += t["amount"]

        monthly_values = list(monthly.values())
        months_active = len(monthly_values)

        # 1. Revenue volatility
        cv = _coeff_of_variation(monthly_values)
        if cv > 1.5:
            penalty = 30
            score -= penalty
            reasons.append(
                f"Very high revenue volatility (CV={cv:.2f}): -{penalty} pts"
            )
        elif cv > 0.8:
            penalty = 18
            score -= penalty
            reasons.append(
                f"High revenue volatility (CV={cv:.2f}): -{penalty} pts"
            )

        # 2. Customer concentration
        revenue_by_partner: dict = defaultdict(float)
        total_sales = sum(t["amount"] for t in sales)
        for t in sales:
            revenue_by_partner[t["partner_id"]] += t["amount"]

        if total_sales > 0:
            top_share = max(revenue_by_partner.values()) / total_sales
            if top_share > 0.75:
                penalty = 25
                score -= penalty
                reasons.append(
                    f"Extreme customer concentration "
                    f"(top customer={top_share:.0%}): -{penalty} pts"
                )
            elif top_share > 0.50:
                penalty = 15
                score -= penalty
                reasons.append(
                    f"High customer concentration "
                    f"(top customer={top_share:.0%}): -{penalty} pts"
                )

        # 3. Revenue spikes (MoM growth > 100 %)
        sorted_months = sorted(monthly.keys())
        spike_count = 0
        for i in range(1, len(sorted_months)):
            prev = monthly[sorted_months[i - 1]]
            curr = monthly[sorted_months[i]]
            if prev > 0 and (curr - prev) / prev > 1.0:
                spike_count += 1
        if spike_count > 0:
            penalty = min(spike_count * 15, 30)
            score -= penalty
            reasons.append(
                f"Revenue spike(s) detected ({spike_count} month(s) "
                f"with >100% MoM growth): -{penalty} pts"
            )

        # 4. Transaction irregularity
        if months_active >= 3:
            tx_per_month: dict = defaultdict(int)
            for t in sales:
                tx_per_month[t["date"][:7]] += 1
            tx_counts = list(tx_per_month.values())
            tx_cv = _coeff_of_variation(tx_counts)
            if tx_cv > 1.2:
                penalty = 18
                score -= penalty
                reasons.append(
                    f"Irregular transaction timing (CV={tx_cv:.2f}): -{penalty} pts"
                )

        # 5. Trend deterioration (NEW)
        if trend == "deteriorating":
            penalty = 15
            score -= penalty
            reasons.append(
                f"Revenue trend deteriorating (3+ months declining): -{penalty} pts"
            )

        # 6. Dependency increase over time (NEW)
        # Check if partner concentration is increasing in recent months
        if months_active >= 4:
            half = months_active // 2
            first_half_months = sorted_months[:half]
            second_half_months = sorted_months[half:]

            # Compute concentration for each half
            def _half_concentration(month_list):
                partner_rev = defaultdict(float)
                total = 0
                for t in sales:
                    if t["date"][:7] in month_list:
                        partner_rev[t["partner_id"]] += t["amount"]
                        total += t["amount"]
                if total > 0 and partner_rev:
                    return max(partner_rev.values()) / total
                return 0

            conc_first = _half_concentration(first_half_months)
            conc_second = _half_concentration(second_half_months)
            if conc_second > conc_first + 0.15:
                penalty = 10
                score -= penalty
                reasons.append(
                    f"Customer dependency increasing over time "
                    f"({conc_first:.0%} → {conc_second:.0%}): -{penalty} pts"
                )

        score = max(0.0, round(score, 1))
        if not reasons:
            reasons.append("No significant risk indicators detected")

        scores.append(
            {
                "company_id": company_id,
                "score": score,
                "risk_level": _risk_level(score),
                "trend": trend,
                "explanation": reasons,
            }
        )

    # Sort by score ascending (riskiest first)
    scores.sort(key=lambda x: x["score"])

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(scores, fh, indent=2, ensure_ascii=False)

    risky = sum(1 for s in scores if s["risk_level"] == "Risky")
    watch = sum(1 for s in scores if s["risk_level"] == "Watch")
    healthy = sum(1 for s in scores if s["risk_level"] == "Healthy")
    print(
        f"[scoring] Scored {len(scores)} companies → "
        f"Risky: {risky}, Watch: {watch}, Healthy: {healthy}"
    )
    return scores


if __name__ == "__main__":
    score_companies()


def apply_cycle_penalties(
    cycle_node_ids: list,
    scores_path: str = SCORES_JSON,
) -> list:
    """
    Apply an additional penalty to companies that are part of a detected
    fraud ring cycle.  Updates scores.json in-place.

    Called from main.py after graph_builder has detected cycles.
    """
    if not cycle_node_ids:
        return []

    with open(scores_path, encoding="utf-8") as fh:
        scores = json.load(fh)

    penalty = 35
    updated = []
    for s in scores:
        if s["company_id"] in cycle_node_ids:
            s["score"] = max(0.0, round(s["score"] - penalty, 1))
            s["explanation"].append(
                f"Involved in circular trading (fraud ring): -{penalty} pts"
            )
            s["risk_level"] = _risk_level(s["score"])
            updated.append(s["company_id"])

    scores.sort(key=lambda x: x["score"])

    with open(scores_path, "w", encoding="utf-8") as fh:
        json.dump(scores, fh, indent=2, ensure_ascii=False)

    if updated:
        print(
            f"[scoring] Applied fraud-ring penalty to "
            f"{len(updated)} company(s): {updated}"
        )
    return scores
