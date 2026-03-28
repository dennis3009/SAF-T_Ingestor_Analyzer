"""
portfolio.py - Portfolio-level aggregated insights across all companies.

Computes:
  - total companies, risk distribution, top risky, average score
  - detected cycles, alerts, decision distribution

Output: data/json/portfolio.json
"""

import os
import json

SCORES_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "scores.json"
)
MONTHLY_METRICS_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "monthly_metrics.json"
)
DECISIONS_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "decisions.json"
)
CASH_FLOW_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "cash_flow.json"
)
GRAPH_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "graph.json"
)
PORTFOLIO_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "portfolio.json"
)


def compute_portfolio(
    scores_path: str = SCORES_JSON,
    metrics_path: str = MONTHLY_METRICS_JSON,
    decisions_path: str = DECISIONS_JSON,
    cash_flow_path: str = CASH_FLOW_JSON,
    graph_path: str = GRAPH_JSON,
    output_path: str = PORTFOLIO_JSON,
) -> dict:
    """
    Compute portfolio-level insights.

    Returns a portfolio dict.
    """
    with open(scores_path, encoding="utf-8") as fh:
        scores = json.load(fh)

    with open(metrics_path, encoding="utf-8") as fh:
        metrics = json.load(fh)

    with open(decisions_path, encoding="utf-8") as fh:
        decisions = json.load(fh)

    with open(cash_flow_path, encoding="utf-8") as fh:
        cash_flows = json.load(fh)

    with open(graph_path, encoding="utf-8") as fh:
        graph = json.load(fh)

    # Risk distribution
    risk_distribution = {"Healthy": 0, "Watch": 0, "Risky": 0}
    for s in scores:
        rl = s.get("risk_level", "Watch")
        risk_distribution[rl] = risk_distribution.get(rl, 0) + 1

    # Decision distribution
    decision_distribution = {"approve": 0, "review": 0, "reject": 0}
    for d in decisions:
        dec = d.get("decision", "review")
        decision_distribution[dec] = decision_distribution.get(dec, 0) + 1

    # Liquidity distribution
    liquidity_distribution = {"stable": 0, "warning": 0, "critical": 0}
    for cf in cash_flows:
        liq = cf.get("liquidity", "stable")
        liquidity_distribution[liq] = liquidity_distribution.get(liq, 0) + 1

    # Average score
    avg_score = (
        round(sum(s["score"] for s in scores) / len(scores), 1)
        if scores else 0
    )

    # Top 10 riskiest
    top_risky = []
    for s in scores[:10]:
        top_risky.append({
            "company_id": s["company_id"],
            "score": s["score"],
            "risk_level": s["risk_level"],
            "explanation": s.get("explanation", [])[:2],
        })

    # Graph metrics
    graph_metrics = graph.get("metrics", {})
    cycles = graph_metrics.get("cycle_details", [])

    # Trend distribution
    trend_distribution = {"improving": 0, "stable": 0, "deteriorating": 0}
    for m in metrics:
        t = m.get("trend", "stable")
        trend_distribution[t] = trend_distribution.get(t, 0) + 1

    # Generate alerts
    alerts = []

    deteriorating_count = trend_distribution.get("deteriorating", 0)
    if deteriorating_count > 0:
        alerts.append({
            "type": "warning",
            "message": f"{deteriorating_count} company(ies) with deteriorating revenue trend",
        })

    critical_count = liquidity_distribution.get("critical", 0)
    if critical_count > 0:
        alerts.append({
            "type": "danger",
            "message": f"{critical_count} company(ies) with critical liquidity",
        })

    reject_count = decision_distribution.get("reject", 0)
    if reject_count > 0:
        alerts.append({
            "type": "danger",
            "message": f"{reject_count} company(ies) recommended for credit rejection",
        })

    if cycles:
        alerts.append({
            "type": "danger",
            "message": f"{len(cycles)} fraud ring(s) detected in transaction network",
        })

    risky_count = risk_distribution.get("Risky", 0)
    if risky_count > 0:
        alerts.append({
            "type": "warning",
            "message": f"{risky_count} company(ies) classified as Risky",
        })

    # Total revenue and exposure
    total_revenue = sum(m.get("total_revenue", 0) for m in metrics)
    total_credit_exposure = sum(
        d.get("recommended_credit_limit", 0) for d in decisions
    )

    portfolio = {
        "total_companies": len(scores),
        "average_score": avg_score,
        "total_revenue": round(total_revenue, 2),
        "total_credit_exposure": round(total_credit_exposure, 2),
        "risk_distribution": risk_distribution,
        "decision_distribution": decision_distribution,
        "trend_distribution": trend_distribution,
        "liquidity_distribution": liquidity_distribution,
        "top_risky": top_risky,
        "cycles_detected": len(cycles),
        "cycle_details": cycles,
        "alerts": alerts,
        "num_edges": graph_metrics.get("num_edges", 0),
        "num_nodes": graph_metrics.get("num_nodes", 0),
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(portfolio, fh, indent=2, ensure_ascii=False)

    print(
        f"[portfolio] Portfolio: {len(scores)} companies, "
        f"avg score: {avg_score}, "
        f"{len(alerts)} alert(s)"
    )
    return portfolio


if __name__ == "__main__":
    compute_portfolio()
