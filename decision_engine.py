"""
decision_engine.py - Bank-oriented decision layer.

For each company computes:
  - recommended_credit_limit (heuristic based on revenue and risk)
  - decision: approve / review / reject

Output: data/json/decisions.json
"""

import os
import json

SCORES_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "scores.json"
)
MONTHLY_METRICS_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "monthly_metrics.json"
)
CASH_FLOW_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "cash_flow.json"
)
DECISIONS_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "decisions.json"
)


def _compute_credit_limit(
    total_revenue: float,
    score: float,
    risk_level: str,
    liquidity: str,
) -> float:
    """
    Simple heuristic for credit limit based on revenue and risk.

    Base: 30% of annual revenue
    Adjustments:
      - Healthy: 100% of base
      - Watch: 50% of base
      - Risky: 10% of base
      - Critical liquidity: halved
    """
    base = total_revenue * 0.30

    if risk_level == "Healthy":
        multiplier = 1.0
    elif risk_level == "Watch":
        multiplier = 0.5
    else:
        multiplier = 0.1

    # Score-based fine-tuning
    score_factor = score / 100.0
    limit = base * multiplier * score_factor

    # Liquidity penalty
    if liquidity == "critical":
        limit *= 0.5
    elif liquidity == "warning":
        limit *= 0.75

    return round(max(0, limit), 2)


def _make_decision(
    score: float,
    trend: str,
    risk_level: str,
    liquidity: str,
    in_cycle: bool,
) -> tuple:
    """
    Determine credit decision and explanation.

    Returns (decision, explanation).
    """
    reasons = []

    # Fraud ring → automatic reject
    if in_cycle:
        return "reject", "Company involved in detected circular trading (fraud ring)."

    # Risk-based primary decision
    if risk_level == "Risky":
        decision = "reject"
        reasons.append(f"High risk profile (score: {score:.1f})")
    elif risk_level == "Watch":
        decision = "review"
        reasons.append(f"Moderate risk profile (score: {score:.1f})")
    else:
        decision = "approve"
        reasons.append(f"Healthy risk profile (score: {score:.1f})")

    # Trend adjustment
    if trend == "deteriorating":
        if decision == "approve":
            decision = "review"
        reasons.append("Revenue trend is deteriorating")
    elif trend == "improving":
        reasons.append("Revenue trend is improving")

    # Liquidity adjustment
    if liquidity == "critical":
        if decision == "approve":
            decision = "review"
        elif decision == "review":
            decision = "reject"
        reasons.append("Critical liquidity situation")
    elif liquidity == "warning":
        if decision == "approve":
            decision = "review"
        reasons.append("Liquidity warning indicators present")

    return decision, "; ".join(reasons)


def compute_decisions(
    scores_path: str = SCORES_JSON,
    metrics_path: str = MONTHLY_METRICS_JSON,
    cash_flow_path: str = CASH_FLOW_JSON,
    output_path: str = DECISIONS_JSON,
) -> list:
    """
    Compute credit decisions for all companies.

    Returns a list of decision dicts.
    """
    with open(scores_path, encoding="utf-8") as fh:
        scores = json.load(fh)

    with open(metrics_path, encoding="utf-8") as fh:
        metrics = json.load(fh)

    with open(cash_flow_path, encoding="utf-8") as fh:
        cash_flows = json.load(fh)

    metrics_map = {m["company_id"]: m for m in metrics}
    cash_flow_map = {c["company_id"]: c for c in cash_flows}

    decisions = []

    for s in scores:
        cid = s["company_id"]
        m = metrics_map.get(cid, {})
        cf = cash_flow_map.get(cid, {})

        trend = m.get("trend", "stable")
        total_revenue = m.get("total_revenue", 0)
        liquidity = cf.get("liquidity", "stable")
        in_cycle = any(
            "fraud ring" in r.lower() or "circular trading" in r.lower()
            for r in s.get("explanation", [])
        )

        decision, explanation = _make_decision(
            s["score"], trend, s["risk_level"], liquidity, in_cycle
        )
        credit_limit = _compute_credit_limit(
            total_revenue, s["score"], s["risk_level"], liquidity
        )

        decisions.append({
            "company_id": cid,
            "score": s["score"],
            "risk_level": s["risk_level"],
            "trend": trend,
            "liquidity": liquidity,
            "decision": decision,
            "recommended_credit_limit": credit_limit,
            "explanation": explanation,
        })

    # Sort by decision priority: reject first, then review, then approve
    priority = {"reject": 0, "review": 1, "approve": 2}
    decisions.sort(key=lambda d: (priority.get(d["decision"], 9), d["score"]))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(decisions, fh, indent=2, ensure_ascii=False)

    approve = sum(1 for d in decisions if d["decision"] == "approve")
    review = sum(1 for d in decisions if d["decision"] == "review")
    reject = sum(1 for d in decisions if d["decision"] == "reject")
    print(
        f"[decision_engine] Decisions for {len(decisions)} companies → "
        f"approve: {approve}, review: {review}, reject: {reject}"
    )
    return decisions


if __name__ == "__main__":
    compute_decisions()
