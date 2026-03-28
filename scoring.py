"""
scoring.py - Enhanced behavioral risk scoring for SAF-T companies.

For each company, computes a score from 0 to 100 (100 = fully healthy).
Penalties are applied for:
  1. Revenue volatility (high coefficient of variation in monthly totals)
  2. Customer concentration (top customer > 50 % of total sales)
  3. Revenue spikes (month-over-month growth > 100 %)
  4. Transaction irregularity (uneven distribution across months)
  5. Trend deterioration (revenue declining for 3+ consecutive months)
  6. Dependency increase (growing reliance on top partner over time)

Output: data/json/scores.json (with trend + explainability)
"""

import os
import json
import math
import csv
from collections import defaultdict

TRANSACTIONS_CSV = os.path.join(
    os.path.dirname(__file__), "data", "csv", "transactions.csv"
)
SCORES_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "scores.json"
)
GRAPH_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "graph.json"
)
MONTHLY_METRICS_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "monthly_metrics.json"
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


def _detect_trend(monthly: dict) -> str:
    """Detect revenue trend from monthly totals."""
    sorted_months = sorted(monthly.keys())
    if len(sorted_months) < 3:
        return "stable"

    values = [monthly[m] for m in sorted_months]

    # Check for 3 consecutive months of decline
    declining_streak = 0
    max_declining = 0
    for i in range(1, len(values)):
        if values[i] < values[i - 1]:
            declining_streak += 1
            max_declining = max(max_declining, declining_streak)
        else:
            declining_streak = 0

    growing_streak = 0
    max_growing = 0
    for i in range(1, len(values)):
        if values[i] > values[i - 1]:
            growing_streak += 1
            max_growing = max(max_growing, growing_streak)
        else:
            growing_streak = 0

    if max_declining >= 3:
        return "deteriorating"
    if max_growing >= 3:
        return "improving"

    # Overall direction
    third = max(1, len(values) // 3)
    early_avg = sum(values[:third]) / third
    late_avg = sum(values[-third:]) / third
    if early_avg > 0:
        change = (late_avg - early_avg) / early_avg
        if change < -0.15:
            return "deteriorating"
        if change > 0.15:
            return "improving"

    return "stable"


def _dependency_increase(sales: list) -> tuple:
    """
    Check if dependency on top partner is increasing over time.
    Returns (is_increasing, details_string).
    """
    if len(sales) < 6:
        return False, ""

    # Split sales into first half and second half by date
    sorted_sales = sorted(sales, key=lambda t: t["date"])
    mid = len(sorted_sales) // 2
    first_half = sorted_sales[:mid]
    second_half = sorted_sales[mid:]

    def top_concentration(txs):
        by_partner: dict = defaultdict(float)
        total = 0.0
        for t in txs:
            by_partner[t["partner_id"]] += t["amount"]
            total += t["amount"]
        if total == 0:
            return 0.0
        return max(by_partner.values()) / total

    early_conc = top_concentration(first_half)
    late_conc = top_concentration(second_half)

    if late_conc > early_conc + 0.15:
        return True, f"early={early_conc:.0%}, recent={late_conc:.0%}"
    return False, ""


def score_companies(
    csv_path: str = TRANSACTIONS_CSV,
    output_path: str = SCORES_JSON,
) -> list:
    """
    Compute behavioral risk scores for all companies.

    Returns a list of score dicts with trend and explainability.
    """
    transactions = _load_transactions(csv_path)

    # Group transactions by company
    by_company: dict = defaultdict(list)
    for tx in transactions:
        by_company[tx["company_id"]].append(tx)

    scores = []

    for company_id, txs in by_company.items():
        score = 100.0
        reasons = []

        # Only sales count toward revenue metrics
        sales = [t for t in txs if t["type"] == "sale"]
        if not sales:
            scores.append(
                {
                    "company_id": company_id,
                    "score": 50.0,
                    "risk_level": "Watch",
                    "trend": "stable",
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

        # 5. Trend deterioration
        trend = _detect_trend(monthly)
        if trend == "deteriorating":
            penalty = 12
            score -= penalty
            reasons.append(
                f"Revenue trend deteriorating: -{penalty} pts"
            )

        # 6. Dependency increase over time
        dep_increasing, dep_details = _dependency_increase(sales)
        if dep_increasing:
            penalty = 10
            score -= penalty
            reasons.append(
                f"Increasing dependency on top partner ({dep_details}): -{penalty} pts"
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
