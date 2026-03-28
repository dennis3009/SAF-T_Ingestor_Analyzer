"""
main.py - Orchestration entry point for the SAF-T Ingestor & Analyzer.

Steps:
  1. Generate synthetic SAF-T XML data
  2. Parse XML into JSON / CSV
  3. Compute time-series monthly metrics
  4. Compute behavioral risk scores
  5. Build transaction network graph
  6. Compute cash flow approximation
  7. Compute credit decisions
  8. Propagate risk through network
  9. Compute portfolio insights
  10. Generate interactive HTML visualisation

Prints a summary report to stdout.
"""

import sys
import os

# Ensure local modules are importable when running from any working directory
sys.path.insert(0, os.path.dirname(__file__))

import generator
import parser
import scoring
import graph_builder
import time_series
import cash_flow
import decision_engine
import risk_propagation
import portfolio
import visualize


def print_separator(title: str = "") -> None:
    line = "=" * 60
    if title:
        print(f"\n{line}")
        print(f"  {title}")
        print(line)
    else:
        print(line)


def main() -> None:
    print_separator("SAF-T Ingestor & Analyzer — Banking Demo")

    # ------------------------------------------------------------------
    # Step 1: Generate synthetic data
    # ------------------------------------------------------------------
    print_separator("Step 1: Generating synthetic SAF-T XML data")
    companies_meta = generator.generate()

    # ------------------------------------------------------------------
    # Step 2: Parse XML -> JSON / CSV
    # ------------------------------------------------------------------
    print_separator("Step 2: Parsing XML files")
    companies, partners, transactions = parser.parse()

    # ------------------------------------------------------------------
    # Step 3: Compute time-series monthly metrics
    # ------------------------------------------------------------------
    print_separator("Step 3: Computing time-series monthly metrics")
    monthly_metrics = time_series.compute_monthly_metrics()

    # ------------------------------------------------------------------
    # Step 4: Compute risk scores (uses time-series trends)
    # ------------------------------------------------------------------
    print_separator("Step 4: Computing behavioral risk scores")
    scores = scoring.score_companies()

    # ------------------------------------------------------------------
    # Step 5: Build network graph
    # ------------------------------------------------------------------
    print_separator("Step 5: Building transaction network graph")
    graph = graph_builder.build_graph()

    # Apply fraud-ring penalties to scores and re-build graph
    cycle_node_ids = graph.get("metrics", {}).get("cycle_node_ids", [])
    if cycle_node_ids:
        scores = scoring.apply_cycle_penalties(cycle_node_ids)
        graph = graph_builder.build_graph()

    # ------------------------------------------------------------------
    # Step 6: Cash flow approximation
    # ------------------------------------------------------------------
    print_separator("Step 6: Computing cash flow approximation")
    cash_flows = cash_flow.compute_cash_flow()

    # ------------------------------------------------------------------
    # Step 7: Credit decisions
    # ------------------------------------------------------------------
    print_separator("Step 7: Computing credit decisions")
    decisions = decision_engine.compute_decisions()

    # ------------------------------------------------------------------
    # Step 8: Risk propagation through network
    # ------------------------------------------------------------------
    print_separator("Step 8: Propagating risk through network")
    graph = risk_propagation.propagate_risk()

    # ------------------------------------------------------------------
    # Step 9: Portfolio insights
    # ------------------------------------------------------------------
    print_separator("Step 9: Computing portfolio insights")
    portfolio_data = portfolio.compute_portfolio()

    # ------------------------------------------------------------------
    # Step 10: Visualise
    # ------------------------------------------------------------------
    print_separator("Step 10: Generating visualisation")
    visualize.visualize()

    # ------------------------------------------------------------------
    # Summary report
    # ------------------------------------------------------------------
    print_separator("SUMMARY REPORT")

    num_companies = len(companies)
    num_transactions = len(transactions)
    risky = [s for s in scores if s["risk_level"] == "Risky"]
    watch = [s for s in scores if s["risk_level"] == "Watch"]
    healthy = [s for s in scores if s["risk_level"] == "Healthy"]

    metrics = graph.get("metrics", {})
    cycles = metrics.get("cycle_details", [])

    print(f"  Companies analysed   : {num_companies}")
    print(f"  Partners detected    : {len(partners)}")
    print(f"  Total transactions   : {num_transactions}")
    print()
    print(f"  Risk breakdown:")
    print(f"    Healthy          : {len(healthy)}")
    print(f"    Watch            : {len(watch)}")
    print(f"    Risky            : {len(risky)}")
    print()

    # Decision breakdown
    approve = sum(1 for d in decisions if d["decision"] == "approve")
    review = sum(1 for d in decisions if d["decision"] == "review")
    reject = sum(1 for d in decisions if d["decision"] == "reject")
    print(f"  Credit decisions:")
    print(f"    Approve          : {approve}")
    print(f"    Review           : {review}")
    print(f"    Reject           : {reject}")
    print()

    if cycles:
        print(f"  FRAUD RING DETECTED: {len(cycles)} cycle(s) found")
        for i, cycle in enumerate(cycles, 1):
            print(f"     Ring {i}: {' -> '.join(cycle)} -> {cycle[0]}")
    else:
        print("  No circular trading patterns detected.")

    print()
    print("  Top 5 riskiest companies:")
    for s in scores[:5]:
        print(
            f"    [{s['risk_level']:7s}] {s['company_id']:12s} "
            f"score={s['score']:5.1f}  |  "
            + "; ".join(s["explanation"][:2])
        )

    # Alerts
    alerts = portfolio_data.get("alerts", [])
    if alerts:
        print()
        print(f"  Alerts ({len(alerts)}):")
        for a in alerts:
            icon = "!!" if a["type"] == "danger" else "!"
            print(f"    [{icon}] {a['message']}")

    print()
    print("  Output files:")
    print("    data/json/monthly_metrics.json  - time-series data")
    print("    data/json/scores.json           - risk scores")
    print("    data/json/cash_flow.json        - cash flow analysis")
    print("    data/json/decisions.json         - credit decisions")
    print("    data/json/portfolio.json         - portfolio overview")
    print("    data/json/graph.json            - network graph + exposure")
    print("    data/outputs/graph.html         - open in browser!")
    print_separator()


if __name__ == "__main__":
    main()
