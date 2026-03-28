"""
cash_flow.py - Cash flow approximation from transaction data.

Estimates monthly inflow (sales) and outflow (purchases) per company
and computes a simple liquidity indicator.

Output: data/json/cash_flow.json
"""

import os
import json

MONTHLY_METRICS_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "monthly_metrics.json"
)
CASH_FLOW_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "cash_flow.json"
)


def _liquidity_status(months_data: list) -> str:
    """
    Compute liquidity indicator from monthly cash flow data.

    Rules:
      - If net flow is negative for 3+ months → critical
      - If net flow is negative for any month → warning
      - Otherwise → stable
    """
    negative_months = sum(1 for m in months_data if m["net_flow"] < 0)

    if negative_months >= 3:
        return "critical"
    elif negative_months > 0:
        return "warning"
    return "stable"


def compute_cash_flow(
    metrics_path: str = MONTHLY_METRICS_JSON,
    output_path: str = CASH_FLOW_JSON,
) -> list:
    """
    Compute cash flow approximation per company.

    Returns a list of cash flow dicts.
    """
    with open(metrics_path, encoding="utf-8") as fh:
        monthly_metrics = json.load(fh)

    results = []

    for company in monthly_metrics:
        months = company["months"]
        total_inflow = sum(m["revenue"] for m in months)
        total_outflow = sum(m["expenses"] for m in months)
        net_cash_flow = total_inflow - total_outflow

        # Monthly cash flow details
        monthly_cash_flow = []
        cumulative = 0
        for m in months:
            cumulative += m["net_flow"]
            monthly_cash_flow.append({
                "month": m["month"],
                "inflow": m["revenue"],
                "outflow": m["expenses"],
                "net": m["net_flow"],
                "cumulative": round(cumulative, 2),
            })

        liquidity = _liquidity_status(months)

        # Cash flow coverage ratio (inflow / outflow)
        coverage_ratio = (
            round(total_inflow / total_outflow, 2)
            if total_outflow > 0 else 999.0
        )

        results.append({
            "company_id": company["company_id"],
            "total_inflow": round(total_inflow, 2),
            "total_outflow": round(total_outflow, 2),
            "net_cash_flow": round(net_cash_flow, 2),
            "coverage_ratio": coverage_ratio,
            "liquidity": liquidity,
            "monthly": monthly_cash_flow,
        })

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)

    critical = sum(1 for r in results if r["liquidity"] == "critical")
    warning = sum(1 for r in results if r["liquidity"] == "warning")
    stable = sum(1 for r in results if r["liquidity"] == "stable")
    print(
        f"[cash_flow] Cash flow for {len(results)} companies → "
        f"stable: {stable}, warning: {warning}, critical: {critical}"
    )
    return results


if __name__ == "__main__":
    compute_cash_flow()
