"""
time_series.py - Time-based analysis and trend detection.

Computes monthly aggregates per company (revenue, expenses, net flow)
and detects trends (improving / stable / deteriorating).

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
    Detect trend from ordered monthly values.

    Rules:
      - 3+ consecutive declining months → deteriorating
      - 3+ consecutive growing months  → improving
      - otherwise                       → stable
    """
    if len(monthly_values) < 3:
        return "stable"

    # Check for consecutive declines
    declining = 0
    max_declining = 0
    for i in range(1, len(monthly_values)):
        if monthly_values[i] < monthly_values[i - 1]:
            declining += 1
            max_declining = max(max_declining, declining)
        else:
            declining = 0

    if max_declining >= 3:
        return "deteriorating"

    # Check for consecutive growth
    growing = 0
    max_growing = 0
    for i in range(1, len(monthly_values)):
        if monthly_values[i] > monthly_values[i - 1]:
            growing += 1
            max_growing = max(max_growing, growing)
        else:
            growing = 0

    if max_growing >= 3:
        return "improving"

    return "stable"


def _detect_spikes(monthly_dict: dict) -> list:
    """Detect months with >100% increase from previous month."""
    spikes = []
    sorted_months = sorted(monthly_dict.keys())
    for i in range(1, len(sorted_months)):
        prev = monthly_dict[sorted_months[i - 1]]
        curr = monthly_dict[sorted_months[i]]
        if prev > 0 and (curr - prev) / prev > 1.0:
            spikes.append({
                "month": sorted_months[i],
                "growth_pct": round((curr - prev) / prev * 100, 1),
            })
    return spikes


def compute_monthly_metrics(
    csv_path: str = TRANSACTIONS_CSV,
    output_path: str = MONTHLY_METRICS_JSON,
) -> list:
    """
    Compute monthly aggregates per company and detect trends.

    Returns a list of company metric dicts.
    """
    transactions = _load_transactions(csv_path)

    # Group by company
    by_company: dict = defaultdict(list)
    for tx in transactions:
        by_company[tx["company_id"]].append(tx)

    results = []

    for company_id, txs in sorted(by_company.items()):
        # Monthly revenue (sales) and expenses (purchases)
        monthly_revenue: dict = defaultdict(float)
        monthly_expenses: dict = defaultdict(float)
        monthly_tx_count: dict = defaultdict(int)

        for tx in txs:
            ym = tx["date"][:7]  # "YYYY-MM"
            monthly_tx_count[ym] += 1
            if tx["type"] == "sale":
                monthly_revenue[ym] += tx["amount"]
            else:
                monthly_expenses[ym] += tx["amount"]

        # All months present
        all_months = sorted(
            set(list(monthly_revenue.keys()) + list(monthly_expenses.keys()))
        )

        months_data = []
        for m in all_months:
            rev = round(monthly_revenue.get(m, 0), 2)
            exp = round(monthly_expenses.get(m, 0), 2)
            months_data.append({
                "month": m,
                "revenue": rev,
                "expenses": exp,
                "net_flow": round(rev - exp, 2),
                "transaction_count": monthly_tx_count.get(m, 0),
            })

        # Trend detection based on revenue
        revenue_values = [monthly_revenue[m] for m in all_months]
        trend = _detect_trend(revenue_values)

        # Spike detection
        spikes = _detect_spikes(monthly_revenue)

        # Revenue decline detection (3 consecutive months)
        declining_months = []
        if len(revenue_values) >= 3:
            streak = []
            sorted_m = sorted(monthly_revenue.keys())
            for i in range(1, len(sorted_m)):
                if monthly_revenue[sorted_m[i]] < monthly_revenue[sorted_m[i - 1]]:
                    if not streak:
                        streak.append(sorted_m[i - 1])
                    streak.append(sorted_m[i])
                else:
                    if len(streak) >= 3:
                        declining_months = list(streak)
                    streak = []
            if len(streak) >= 3:
                declining_months = list(streak)

        total_revenue = sum(monthly_revenue.values())
        total_expenses = sum(monthly_expenses.values())

        results.append({
            "company_id": company_id,
            "months": months_data,
            "trend": trend,
            "total_revenue": round(total_revenue, 2),
            "total_expenses": round(total_expenses, 2),
            "total_net_flow": round(total_revenue - total_expenses, 2),
            "spikes": spikes,
            "declining_months": declining_months,
            "months_active": len(all_months),
        })

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)

    trends = defaultdict(int)
    for r in results:
        trends[r["trend"]] += 1
    print(
        f"[time_series] Computed monthly metrics for {len(results)} companies → "
        f"improving: {trends['improving']}, stable: {trends['stable']}, "
        f"deteriorating: {trends['deteriorating']}"
    )
    return results


if __name__ == "__main__":
    compute_monthly_metrics()
