"""
cash_flow.py - Cash flow approximation and liquidity analysis.

Estimates monthly inflow/outflow and computes a simple liquidity indicator
per company (stable / warning / critical).

Output: data/json/cash_flow.json
"""

import os
import json
import csv
from collections import defaultdict

TRANSACTIONS_CSV = os.path.join(
    os.path.dirname(__file__), "data", "csv", "transactions.csv"
)
CASH_FLOW_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "cash_flow.json"
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


def _liquidity_indicator(monthly_data: list) -> str:
    """
    Compute a simple liquidity indicator based on net cash flow patterns.

    - stable: positive net flow in most months
    - warning: negative net flow in 30-50% of months
    - critical: negative net flow in >50% of months or overall negative
    """
    if not monthly_data:
        return "warning"

    negative_months = sum(1 for m in monthly_data if m["net_cash_flow"] < 0)
    total_months = len(monthly_data)
    negative_ratio = negative_months / total_months

    total_net = sum(m["net_cash_flow"] for m in monthly_data)

    if total_net < 0 or negative_ratio > 0.5:
        return "critical"
    elif negative_ratio > 0.3:
        return "warning"
    return "stable"


def compute_cash_flow(
    csv_path: str = TRANSACTIONS_CSV,
    output_path: str = CASH_FLOW_JSON,
) -> dict:
    """
    Compute monthly cash flow approximation per company.

    Returns a dict keyed by company_id.
    """
    transactions = _load_transactions(csv_path)

    by_company: dict = defaultdict(list)
    for tx in transactions:
        by_company[tx["company_id"]].append(tx)

    results = {}

    for company_id, txs in by_company.items():
        monthly_inflow: dict = defaultdict(float)
        monthly_outflow: dict = defaultdict(float)

        for tx in txs:
            ym = tx["date"][:7]
            if tx["type"] == "sale":
                monthly_inflow[ym] += tx["amount"]
            else:
                monthly_outflow[ym] += tx["amount"]

        all_months = sorted(set(list(monthly_inflow.keys()) + list(monthly_outflow.keys())))

        monthly_data = []
        for m in all_months:
            inflow = round(monthly_inflow.get(m, 0.0), 2)
            outflow = round(monthly_outflow.get(m, 0.0), 2)
            monthly_data.append({
                "month": m,
                "inflow": inflow,
                "outflow": outflow,
                "net_cash_flow": round(inflow - outflow, 2),
            })

        total_inflow = round(sum(monthly_inflow.values()), 2)
        total_outflow = round(sum(monthly_outflow.values()), 2)
        liquidity = _liquidity_indicator(monthly_data)

        results[company_id] = {
            "company_id": company_id,
            "monthly": monthly_data,
            "total_inflow": total_inflow,
            "total_outflow": total_outflow,
            "total_net": round(total_inflow - total_outflow, 2),
            "liquidity_indicator": liquidity,
        }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)

    stable = sum(1 for r in results.values() if r["liquidity_indicator"] == "stable")
    warning = sum(1 for r in results.values() if r["liquidity_indicator"] == "warning")
    critical = sum(1 for r in results.values() if r["liquidity_indicator"] == "critical")
    print(
        f"[cash_flow] Cash flow analysis for {len(results)} companies → "
        f"Stable: {stable}, Warning: {warning}, Critical: {critical}"
    )
    return results


if __name__ == "__main__":
    compute_cash_flow()
