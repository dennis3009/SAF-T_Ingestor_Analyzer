"""
main.py - Orchestration entry point for the SAF-T Ingestor & Analyzer.

Steps:
  1.  Generate synthetic SAF-T XML data
  2.  Parse XML into JSON / CSV
  3.  Compute behavioral risk scores
  4.  Build transaction network graph (+ risk propagation)
  5.  Compute time-series / monthly metrics
  6.  Compute cash-flow approximation
  7.  Generate credit decisions
  8.  Build portfolio-level insights
  9.  Generate interactive HTML UI
  10. Print summary report

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
    print_separator("Step 1: Generating synthetic SAF-T XML data …")
    companies_meta = generator.generate()

    # ------------------------------------------------------------------
    # Step 2: Parse XML → JSON / CSV
    # ------------------------------------------------------------------
    print_separator("Step 2: Parsing XML files …")
    companies, partners, transactions = parser.parse()

    # ------------------------------------------------------------------
    # Step 3: Compute risk scores
    # ------------------------------------------------------------------
    print_separator("Step 3: Computing behavioral risk scores …")
    scores = scoring.score_companies()

    # ------------------------------------------------------------------
    # Step 4: Build network graph
    # ------------------------------------------------------------------
    print_separator("Step 4: Building transaction network graph …")
    graph = graph_builder.build_graph()

    # Apply fraud-ring penalties to scores and re-build graph with updated data
    cycle_node_ids = graph.get("metrics", {}).get("cycle_node_ids", [])
    if cycle_node_ids:
        scores = scoring.apply_cycle_penalties(cycle_node_ids)
        # Rebuild graph so node risk levels reflect updated scores
        graph = graph_builder.build_graph()

    # ------------------------------------------------------------------
    # Step 5: Time-series monthly metrics
    # ------------------------------------------------------------------
    print_separator("Step 5: Computing monthly metrics & trends …")
    monthly_metrics = time_series.compute_monthly_metrics()

    # ------------------------------------------------------------------
    # Step 6: Cash flow approximation
    # ------------------------------------------------------------------
    print_separator("Step 6: Computing cash flow analysis …")
    cash_flow_data = cash_flow.compute_cash_flow()

    # ------------------------------------------------------------------
    # Step 7: Credit decisions
    # ------------------------------------------------------------------
    print_separator("Step 7: Generating credit decisions …")
    decisions = decision_engine.compute_decisions()

    # ------------------------------------------------------------------
    # Step 8: Portfolio insights
    # ------------------------------------------------------------------
    print_separator("Step 8: Computing portfolio insights …")
    portfolio_data = portfolio.compute_portfolio()

    # ------------------------------------------------------------------
    # Step 9: Generate UI
    # ------------------------------------------------------------------
    print_separator("Step 9: Generating interactive UI …")
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
    cycle_nodes = metrics.get("cycle_node_ids", [])

    print(f"  Companies analysed   : {num_companies}")
    print(f"  Partners detected    : {len(partners)}")
    print(f"  Total transactions   : {num_transactions}")
    print()
    print(f"  Risk breakdown:")
    print(f"    ✅ Healthy          : {len(healthy)}")
    print(f"    ⚠️  Watch            : {len(watch)}")
    print(f"    🔴 Risky            : {len(risky)}")
    print()

    if cycles:
        print(f"  ⚠  FRAUD RING DETECTED: {len(cycles)} cycle(s) found")
        for i, cycle in enumerate(cycles, 1):
            print(f"     Ring {i}: {' → '.join(cycle)} → {cycle[0]}")
    else:
        print("  No circular trading patterns detected.")

    # Decision summary
    approved = sum(1 for d in decisions if d["decision"] == "approve")
    review = sum(1 for d in decisions if d["decision"] == "review")
    rejected = sum(1 for d in decisions if d["decision"] == "reject")
    print()
    print(f"  Credit decisions:")
    print(f"    ✅ Approve          : {approved}")
    print(f"    🔍 Review           : {review}")
    print(f"    ❌ Reject           : {rejected}")

    print()
    print("  Top 5 riskiest companies:")
    for s in scores[:5]:
        trend = s.get("trend", "stable")
        print(
            f"    [{s['risk_level']:7s}] {s['company_id']:12s} "
            f"score={s['score']:5.1f}  trend={trend:13s}  |  "
            + "; ".join(s["explanation"][:2])
        )

    print()
    print("  Output files:")
    print("    data/raw_xml/              — synthetic SAF-T XML files")
    print("    data/json/companies.json")
    print("    data/json/partners.json")
    print("    data/json/scores.json      — risk scores + explanations")
    print("    data/json/graph.json       — network + risk propagation")
    print("    data/json/monthly_metrics.json — time-series data")
    print("    data/json/cash_flow.json   — cash flow analysis")
    print("    data/json/decisions.json   — credit decisions")
    print("    data/json/portfolio.json   — portfolio summary")
    print("    data/csv/transactions.csv")
    print("    data/outputs/index.html    ← open in browser!")
    print_separator()


if __name__ == "__main__":
    main()
