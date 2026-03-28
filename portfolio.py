"""
portfolio.py - Portfolio-level aggregated insights.

Computes summary statistics across all companies for the dashboard.

Output: data/json/portfolio.json
"""

import os
import json

SCORES_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "scores.json"
)
DECISIONS_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "decisions.json"
)
MONTHLY_METRICS_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "monthly_metrics.json"
)
GRAPH_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "graph.json"
)
CASH_FLOW_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "cash_flow.json"
)
PORTFOLIO_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "portfolio.json"
)


def compute_portfolio(
    scores_path: str = SCORES_JSON,
    decisions_path: str = DECISIONS_JSON,
    metrics_path: str = MONTHLY_METRICS_JSON,
    graph_path: str = GRAPH_JSON,
    cash_flow_path: str = CASH_FLOW_JSON,
    output_path: str = PORTFOLIO_JSON,
) -> dict:
    """
    Compute portfolio-level insights.

    Returns a portfolio dict.
    """
    with open(scores_path, encoding="utf-8") as fh:
        scores = json.load(fh)
    with open(decisions_path, encoding="utf-8") as fh:
        decisions = json.load(fh)
    with open(metrics_path, encoding="utf-8") as fh:
        metrics = json.load(fh)
    with open(graph_path, encoding="utf-8") as fh:
        graph = json.load(fh)
    with open(cash_flow_path, encoding="utf-8") as fh:
        cash_flow = json.load(fh)

    # Risk distribution
    risk_dist = {"Healthy": 0, "Watch": 0, "Risky": 0}
    for s in scores:
        rl = s.get("risk_level", "Watch")
        if rl in risk_dist:
            risk_dist[rl] += 1

    # Decision distribution
    decision_dist = {"approve": 0, "review": 0, "reject": 0}
    for d in decisions:
        dec = d.get("decision", "review")
        if dec in decision_dist:
            decision_dist[dec] += 1

    # Trend distribution
    trend_dist = {"improving": 0, "stable": 0, "deteriorating": 0}
    for m in metrics.values():
        t = m.get("trend", "stable")
        if t in trend_dist:
            trend_dist[t] += 1

    # Liquidity distribution
    liquidity_dist = {"stable": 0, "warning": 0, "critical": 0}
    for cf in cash_flow.values():
        li = cf.get("liquidity_indicator", "warning")
        if li in liquidity_dist:
            liquidity_dist[li] += 1

    # Top 10 riskiest companies
    top_risky = sorted(scores, key=lambda x: x["score"])[:10]

    # Average score
    avg_score = round(
        sum(s["score"] for s in scores) / len(scores), 1
    ) if scores else 0

    # Cycles from graph
    graph_metrics = graph.get("metrics", {})
    cycles_detected = graph_metrics.get("cycles_detected", 0)
    cycle_details = graph_metrics.get("cycle_details", [])

    # Alerts
    alerts = []
    deteriorating_count = trend_dist["deteriorating"]
    if deteriorating_count > 0:
        alerts.append({
            "type": "warning",
            "message": f"{deteriorating_count} company(ies) with deteriorating trend",
        })
    risky_count = risk_dist["Risky"]
    if risky_count > 0:
        alerts.append({
            "type": "danger",
            "message": f"{risky_count} company(ies) flagged as Risky",
        })
    rejected_count = decision_dist["reject"]
    if rejected_count > 0:
        alerts.append({
            "type": "danger",
            "message": f"{rejected_count} company(ies) recommended for rejection",
        })
    if cycles_detected > 0:
        alerts.append({
            "type": "warning",
            "message": f"{cycles_detected} fraud ring cycle(s) detected",
        })
    critical_liq = liquidity_dist["critical"]
    if critical_liq > 0:
        alerts.append({
            "type": "danger",
            "message": f"{critical_liq} company(ies) with critical liquidity",
        })

    # Total revenue across portfolio
    total_portfolio_revenue = round(
        sum(m.get("total_revenue", 0) for m in metrics.values()), 2
    )

    portfolio = {
        "total_companies": len(scores),
        "average_score": avg_score,
        "total_portfolio_revenue": total_portfolio_revenue,
        "risk_distribution": risk_dist,
        "decision_distribution": decision_dist,
        "trend_distribution": trend_dist,
        "liquidity_distribution": liquidity_dist,
        "top_10_risky": [
            {
                "company_id": s["company_id"],
                "score": s["score"],
                "risk_level": s["risk_level"],
            }
            for s in top_risky
        ],
        "cycles_detected": cycles_detected,
        "cycle_details": cycle_details,
        "alerts": alerts,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(portfolio, fh, indent=2, ensure_ascii=False)

    print(
        f"[portfolio] Portfolio summary: {len(scores)} companies, "
        f"avg score {avg_score}, {len(alerts)} alert(s)"
    )
    return portfolio


if __name__ == "__main__":
    compute_portfolio()
