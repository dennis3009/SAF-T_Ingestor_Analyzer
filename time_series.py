"""
time_series.py - Time-based analysis and trend detection.

Computes monthly aggregates per company (revenue, expenses, net flow),
detects trends, and tracks score history.

Output: data/json/monthly_metrics.json
"""

import os
import json
import csv
from collections import defaultdict

TRANSACTIONS_CSV = os.path.join(
    os.path.dirname(__file__), "data", "csv", "transactions.csv"
)
MONTHLY_METRICS_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "monthly_metrics.json"
)


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


def _detect_trend(monthly_values: list) -> str:
    """
    Detect trend from a list of (month, value) tuples sorted by month.

    Returns: 'improving', 'stable', or 'deteriorating'
    """
    if len(monthly_values) < 3:
        return "stable"

    values = [v for _, v in monthly_values]

    # Check for 3 consecutive months of decline
    declining_streak = 0
    max_declining = 0
    for i in range(1, len(values)):
        if values[i] < values[i - 1]:
            declining_streak += 1
            max_declining = max(max_declining, declining_streak)
        else:
            declining_streak = 0

    # Check for 3 consecutive months of growth
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

    # Check overall direction using first vs last third
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


def _detect_spikes(monthly_values: list) -> list:
    """Detect months with >100% increase month-over-month."""
    spikes = []
    for i in range(1, len(monthly_values)):
        prev_month, prev_val = monthly_values[i - 1]
        curr_month, curr_val = monthly_values[i]
        if prev_val > 0 and (curr_val - prev_val) / prev_val > 1.0:
            spikes.append({
                "month": curr_month,
                "previous": round(prev_val, 2),
                "current": round(curr_val, 2),
                "increase_pct": round((curr_val - prev_val) / prev_val * 100, 1),
            })
    return spikes


def compute_monthly_metrics(
    csv_path: str = TRANSACTIONS_CSV,
    output_path: str = MONTHLY_METRICS_JSON,
) -> dict:
    """
    Compute monthly aggregates per company and detect trends.

    Returns a dict keyed by company_id.
    """
    transactions = _load_transactions(csv_path)

    # Group by company
    by_company: dict = defaultdict(list)
    for tx in transactions:
        by_company[tx["company_id"]].append(tx)

    results = {}

    for company_id, txs in by_company.items():
        # Monthly revenue (sales)
        monthly_revenue: dict = defaultdict(float)
        monthly_expenses: dict = defaultdict(float)

        for tx in txs:
            ym = tx["date"][:7]  # "YYYY-MM"
            if tx["type"] == "sale":
                monthly_revenue[ym] += tx["amount"]
            else:
                monthly_expenses[ym] += tx["amount"]

        all_months = sorted(set(list(monthly_revenue.keys()) + list(monthly_expenses.keys())))

        monthly_data = []
        for m in all_months:
            rev = round(monthly_revenue.get(m, 0.0), 2)
            exp = round(monthly_expenses.get(m, 0.0), 2)
            monthly_data.append({
                "month": m,
                "revenue": rev,
                "expenses": exp,
                "net_flow": round(rev - exp, 2),
            })

        # Trend detection on revenue
        revenue_series = [(m, monthly_revenue.get(m, 0.0)) for m in all_months]
        revenue_trend = _detect_trend(revenue_series)

        # Spike detection
        spikes = _detect_spikes(revenue_series)

        # Net flow trend
        net_series = [(d["month"], d["net_flow"]) for d in monthly_data]
        net_trend = _detect_trend(net_series)

        # Total metrics
        total_revenue = round(sum(monthly_revenue.values()), 2)
        total_expenses = round(sum(monthly_expenses.values()), 2)

        results[company_id] = {
            "company_id": company_id,
            "monthly": monthly_data,
            "total_revenue": total_revenue,
            "total_expenses": total_expenses,
            "total_net_flow": round(total_revenue - total_expenses, 2),
            "months_active": len(all_months),
            "revenue_trend": revenue_trend,
            "net_flow_trend": net_trend,
            "spikes": spikes,
            "trend": revenue_trend,  # primary trend indicator
        }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)

    improving = sum(1 for r in results.values() if r["trend"] == "improving")
    stable = sum(1 for r in results.values() if r["trend"] == "stable")
    deteriorating = sum(1 for r in results.values() if r["trend"] == "deteriorating")
    print(
        f"[time_series] Computed monthly metrics for {len(results)} companies → "
        f"Improving: {improving}, Stable: {stable}, Deteriorating: {deteriorating}"
    )
    return results


if __name__ == "__main__":
    compute_monthly_metrics()
