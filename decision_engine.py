"""
decision_engine.py - Bank-oriented decision output layer.

For each company, computes a recommended credit limit and
decision (approve / review / reject) based on scoring and trends.

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
DECISIONS_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "decisions.json"
)


def _compute_credit_limit(score: float, total_revenue: float, trend: str) -> float:
    """
    Simple heuristic: credit limit as a percentage of annual revenue,
    scaled by risk score and trend.
    """
    # Base: 20% of total revenue
    base = total_revenue * 0.20

    # Scale by score (0-100 → 0.0-1.0)
    score_factor = score / 100.0

    # Trend adjustment
    trend_factor = {
        "improving": 1.15,
        "stable": 1.0,
        "deteriorating": 0.70,
    }.get(trend, 1.0)

    limit = base * score_factor * trend_factor
    return round(max(0, limit), 2)


def _make_decision(score: float, trend: str, risk_level: str) -> tuple:
    """
    Decision logic:
      - High score (>=70) + stable/improving trend → approve
      - Medium score (40-69) or deteriorating trend → review
      - Low score (<40) → reject

    Returns (decision, reasons).
    """
    reasons = []

    if score >= 70 and trend in ("stable", "improving"):
        decision = "approve"
        reasons.append(f"Strong risk score ({score:.0f}/100)")
        if trend == "improving":
            reasons.append("Positive revenue trend")
        else:
            reasons.append("Stable financial performance")
    elif score < 40:
        decision = "reject"
        reasons.append(f"High-risk score ({score:.0f}/100)")
        if trend == "deteriorating":
            reasons.append("Deteriorating financial trend")
        if risk_level == "Risky":
            reasons.append("Multiple risk indicators present")
    else:
        decision = "review"
        if score < 70:
            reasons.append(f"Moderate risk score ({score:.0f}/100) requires review")
        if trend == "deteriorating":
            reasons.append("Deteriorating trend detected")
        if risk_level == "Watch":
            reasons.append("Company flagged for monitoring")

    return decision, reasons


def compute_decisions(
    scores_path: str = SCORES_JSON,
    metrics_path: str = MONTHLY_METRICS_JSON,
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

    decisions = []

    for s in scores:
        cid = s["company_id"]
        score = s["score"]
        risk_level = s["risk_level"]
        trend = s.get("trend", "stable")

        # Get revenue from metrics
        company_metrics = metrics.get(cid, {})
        total_revenue = company_metrics.get("total_revenue", 0)
        if not trend or trend == "stable":
            trend = company_metrics.get("trend", "stable")

        credit_limit = _compute_credit_limit(score, total_revenue, trend)
        decision, reasons = _make_decision(score, trend, risk_level)

        decisions.append({
            "company_id": cid,
            "score": score,
            "risk_level": risk_level,
            "trend": trend,
            "recommended_credit_limit": credit_limit,
            "decision": decision,
            "explanation": reasons,
        })

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(decisions, fh, indent=2, ensure_ascii=False)

    approved = sum(1 for d in decisions if d["decision"] == "approve")
    review = sum(1 for d in decisions if d["decision"] == "review")
    rejected = sum(1 for d in decisions if d["decision"] == "reject")
    print(
        f"[decision_engine] Decisions for {len(decisions)} companies → "
        f"Approve: {approved}, Review: {review}, Reject: {rejected}"
    )
    return decisions


if __name__ == "__main__":
    compute_decisions()
