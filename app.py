"""
app.py - Flask web interface for the SAF-T Ingestor & Analyzer.

Provides a multi-page UI with:
  - Dashboard with portfolio overview
  - Company list with scores, trends, decisions
  - Company detail with risk explanation
  - Interactive network graph
  - Generate / Upload / Analyze actions

Run:
    python app.py
Then open http://127.0.0.1:5000
"""

import os
import sys
import json
import csv
import io
import shutil
import zipfile
import threading

from flask import Flask, render_template, request, jsonify, send_file

# Ensure local modules are importable
sys.path.insert(0, os.path.dirname(__file__))

import generator
import parser as saft_parser
import scoring
import graph_builder
import time_series
import cash_flow
import decision_engine
import risk_propagation
import portfolio as portfolio_mod
import visualize

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_XML_DIR = os.path.join(DATA_DIR, "raw_xml")
JSON_DIR = os.path.join(DATA_DIR, "json")
CSV_DIR = os.path.join(DATA_DIR, "csv")
OUTPUTS_DIR = os.path.join(DATA_DIR, "outputs")
GRAPH_HTML = os.path.join(OUTPUTS_DIR, "graph.html")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB upload limit

# Simple lock to prevent concurrent pipeline runs (single-user PoC)
_pipeline_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_data_dirs() -> None:
    """Remove generated data so we start from a clean slate."""
    for d in [RAW_XML_DIR, JSON_DIR, CSV_DIR, OUTPUTS_DIR]:
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d, exist_ok=True)


def _count_xml_files() -> int:
    """Count XML files currently in the raw_xml folder."""
    if not os.path.isdir(RAW_XML_DIR):
        return 0
    return len([f for f in os.listdir(RAW_XML_DIR) if f.lower().endswith(".xml")])


def _load_json_safe(filename: str) -> list | dict:
    """Load a JSON file from the json dir, return [] or {} on failure."""
    path = os.path.join(JSON_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _get_summary() -> dict:
    """Build a summary dict from the generated JSON outputs."""
    summary: dict = {"ok": True}

    # Companies
    companies = _load_json_safe("companies.json")
    summary["num_companies"] = len(companies) if isinstance(companies, list) else 0

    # Partners
    partners = _load_json_safe("partners.json")
    summary["num_partners"] = len(partners) if isinstance(partners, list) else 0

    # Transactions
    tx_path = os.path.join(CSV_DIR, "transactions.csv")
    if os.path.exists(tx_path):
        with open(tx_path, encoding="utf-8") as fh:
            summary["num_transactions"] = sum(1 for _ in fh) - 1
    else:
        summary["num_transactions"] = 0

    # Scores
    scores = _load_json_safe("scores.json")
    if isinstance(scores, list) and scores:
        summary["scores"] = scores
        summary["risk_healthy"] = sum(1 for s in scores if s["risk_level"] == "Healthy")
        summary["risk_watch"] = sum(1 for s in scores if s["risk_level"] == "Watch")
        summary["risk_risky"] = sum(1 for s in scores if s["risk_level"] == "Risky")
        summary["top5"] = scores[:5]
    else:
        summary["scores"] = []
        summary["risk_healthy"] = 0
        summary["risk_watch"] = 0
        summary["risk_risky"] = 0
        summary["top5"] = []

    # Graph metrics
    graph = _load_json_safe("graph.json")
    if isinstance(graph, dict):
        metrics = graph.get("metrics", {})
        summary["num_edges"] = metrics.get("num_edges", 0)
        summary["cycles"] = metrics.get("cycle_details", [])
        summary["cycle_node_ids"] = metrics.get("cycle_node_ids", [])
    else:
        summary["num_edges"] = 0
        summary["cycles"] = []
        summary["cycle_node_ids"] = []

    # Portfolio
    portfolio_data = _load_json_safe("portfolio.json")
    if isinstance(portfolio_data, dict):
        summary["portfolio"] = portfolio_data
    else:
        summary["portfolio"] = {}

    # Decisions
    decisions = _load_json_safe("decisions.json")
    if isinstance(decisions, list):
        summary["decisions"] = decisions
    else:
        summary["decisions"] = []

    return summary


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the single-page UI."""
    xml_count = _count_xml_files()
    return render_template("index.html", xml_count=xml_count)


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """Generate SAF-T XML data for a period and return a downloadable ZIP."""
    with _pipeline_lock:
        try:
            data = request.get_json(silent=True) or {}
            year = int(data.get("year", 2025))
            mode = data.get("mode", "month")  # "month" or "year"
            month = int(data.get("month", 1)) if mode == "month" else None

            # Validate inputs
            if year < 2000 or year > 2100:
                return jsonify({"ok": False, "message": "Year must be between 2000 and 2100."}), 400
            if month is not None and (month < 1 or month > 12):
                return jsonify({"ok": False, "message": "Month must be between 1 and 12."}), 400

            # Generate XML files in-memory
            files = generator.generate_for_period(year=year, month=month)

            # Build ZIP in-memory
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for filename, xml_content in sorted(files.items()):
                    zf.writestr(filename, xml_content)
            buf.seek(0)

            # Build a descriptive download name
            if month:
                zip_name = f"saft_data_{year}_{month:02d}.zip"
            else:
                zip_name = f"saft_data_{year}_full_year.zip"

            return send_file(
                buf,
                mimetype="application/zip",
                as_attachment=True,
                download_name=zip_name,
            )

        except Exception as exc:
            import traceback
            traceback.print_exc()
            return jsonify({"ok": False, "message": str(exc)}), 500


@app.route("/api/clean", methods=["POST"])
def api_clean():
    """Clear all generated/imported data."""
    with _pipeline_lock:
        try:
            _clear_data_dirs()
            return jsonify({
                "ok": True,
                "message": "All data cleared.",
                "xml_count": 0,
            })
        except Exception as exc:
            return jsonify({"ok": False, "message": str(exc)}), 500


@app.route("/api/upload", methods=["POST"])
def api_upload():
    """Upload a ZIP file containing SAF-T XML reports."""
    with _pipeline_lock:
        try:
            if "file" not in request.files:
                return jsonify({"ok": False, "message": "No file uploaded."}), 400

            uploaded = request.files["file"]
            if not uploaded.filename:
                return jsonify({"ok": False, "message": "Empty filename."}), 400

            if not uploaded.filename.lower().endswith(".zip"):
                return jsonify({"ok": False, "message": "Please upload a .zip file."}), 400

            # Ensure raw_xml dir exists (don't clear — user may import multiple ZIPs)
            os.makedirs(RAW_XML_DIR, exist_ok=True)

            # Extract XML files from ZIP
            extracted = 0
            with zipfile.ZipFile(uploaded.stream, "r") as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    basename = os.path.basename(info.filename)
                    if basename.lower().endswith(".xml"):
                        data = zf.read(info.filename)
                        target = os.path.normpath(os.path.join(RAW_XML_DIR, basename))
                        # Prevent path traversal
                        if not target.startswith(os.path.normpath(RAW_XML_DIR)):
                            continue
                        with open(target, "wb") as fh:
                            fh.write(data)
                        extracted += 1

            if extracted == 0:
                return jsonify({
                    "ok": False,
                    "message": "No .xml files found inside the ZIP.",
                }), 400

            return jsonify({
                "ok": True,
                "message": f"Imported {extracted} XML file(s).",
                "xml_count": _count_xml_files(),
            })

        except zipfile.BadZipFile:
            return jsonify({"ok": False, "message": "Invalid ZIP file."}), 400
        except Exception as exc:
            return jsonify({"ok": False, "message": str(exc)}), 500


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """Run the full analysis pipeline."""
    with _pipeline_lock:
        try:
            xml_count = _count_xml_files()
            if xml_count == 0:
                return jsonify({
                    "ok": False,
                    "message": "No XML files to analyze. Generate sample data or upload a ZIP first.",
                }), 400

            # Step 1: Parse XML -> JSON / CSV
            saft_parser.parse()

            # Step 2: Time-series monthly metrics
            time_series.compute_monthly_metrics()

            # Step 3: Score companies (uses time-series trends)
            scores = scoring.score_companies()

            # Step 4: Build graph
            graph = graph_builder.build_graph()

            # Step 5: Apply fraud-ring cycle penalties
            cycle_node_ids = graph.get("metrics", {}).get("cycle_node_ids", [])
            if cycle_node_ids:
                scores = scoring.apply_cycle_penalties(cycle_node_ids)
                graph = graph_builder.build_graph()

            # Step 6: Cash flow
            cash_flow.compute_cash_flow()

            # Step 7: Decisions
            decision_engine.compute_decisions()

            # Step 8: Risk propagation
            risk_propagation.propagate_risk()

            # Step 9: Portfolio
            portfolio_mod.compute_portfolio()

            # Step 10: Visualize
            visualize.visualize()

            # Build summary
            summary = _get_summary()
            summary["message"] = "Analysis complete."
            return jsonify(summary)

        except Exception as exc:
            import traceback
            traceback.print_exc()
            return jsonify({"ok": False, "message": str(exc)}), 500


@app.route("/api/portfolio")
def api_portfolio():
    """Return portfolio data."""
    data = _load_json_safe("portfolio.json")
    return jsonify(data)


@app.route("/api/companies")
def api_companies():
    """Return company list with scores, trends, and decisions."""
    scores = _load_json_safe("scores.json")
    decisions = _load_json_safe("decisions.json")
    metrics = _load_json_safe("monthly_metrics.json")
    cash_flows = _load_json_safe("cash_flow.json")

    decision_map = {d["company_id"]: d for d in decisions} if isinstance(decisions, list) else {}
    metrics_map = {m["company_id"]: m for m in metrics} if isinstance(metrics, list) else {}
    cash_flow_map = {c["company_id"]: c for c in cash_flows} if isinstance(cash_flows, list) else {}

    result = []
    if isinstance(scores, list):
        for s in scores:
            cid = s["company_id"]
            d = decision_map.get(cid, {})
            m = metrics_map.get(cid, {})
            cf = cash_flow_map.get(cid, {})
            result.append({
                "company_id": cid,
                "score": s.get("score", 0),
                "risk_level": s.get("risk_level", "Watch"),
                "trend": s.get("trend", "stable"),
                "explanation": s.get("explanation", []),
                "decision": d.get("decision", "review"),
                "recommended_credit_limit": d.get("recommended_credit_limit", 0),
                "total_revenue": m.get("total_revenue", 0),
                "total_expenses": m.get("total_expenses", 0),
                "liquidity": cf.get("liquidity", "stable"),
            })

    return jsonify(result)


@app.route("/api/company/<company_id>")
def api_company_detail(company_id):
    """Return detailed data for a single company."""
    scores = _load_json_safe("scores.json")
    decisions = _load_json_safe("decisions.json")
    metrics = _load_json_safe("monthly_metrics.json")
    cash_flows = _load_json_safe("cash_flow.json")
    graph = _load_json_safe("graph.json")

    score = next((s for s in scores if s["company_id"] == company_id), None)
    decision = next((d for d in decisions if d["company_id"] == company_id), None)
    metric = next((m for m in metrics if m["company_id"] == company_id), None)
    cf = next((c for c in cash_flows if c["company_id"] == company_id), None)

    if not score:
        return jsonify({"error": "Company not found"}), 404

    # Find top partners from graph edges
    top_partners = []
    if isinstance(graph, dict):
        edges = graph.get("edges", [])
        partner_volumes = {}
        for e in edges:
            if e["source"] == company_id:
                partner_volumes[e["target"]] = partner_volumes.get(e["target"], 0) + e["weight"]
            elif e["target"] == company_id:
                partner_volumes[e["source"]] = partner_volumes.get(e["source"], 0) + e["weight"]
        sorted_partners = sorted(partner_volumes.items(), key=lambda x: -x[1])[:5]

        # Get partner labels from graph nodes
        node_labels = {n["id"]: n.get("label", n["id"]) for n in graph.get("nodes", [])}
        for pid, vol in sorted_partners:
            top_partners.append({
                "partner_id": pid,
                "label": node_labels.get(pid, pid),
                "volume": round(vol, 2),
            })

    # Find exposure data from graph node
    exposure = {}
    if isinstance(graph, dict):
        node = next((n for n in graph.get("nodes", []) if n["id"] == company_id), None)
        if node:
            exposure = {
                "exposure_score": node.get("exposure_score", 0),
                "exposure_level": node.get("exposure_level", "low"),
                "direct_exposure": node.get("direct_exposure", []),
                "indirect_exposure": node.get("indirect_exposure", []),
            }

    return jsonify({
        "company_id": company_id,
        "score": score,
        "decision": decision,
        "metrics": metric,
        "cash_flow": cf,
        "top_partners": top_partners,
        "exposure": exposure,
    })


@app.route("/graph")
def serve_graph():
    """Serve the generated graph HTML for iframe embedding."""
    if not os.path.exists(GRAPH_HTML):
        return "<p style='padding:2rem;color:#64748b;'>No graph generated yet. Run analysis first.</p>", 404
    return send_file(GRAPH_HTML)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Ensure data directories exist
    for d in [RAW_XML_DIR, JSON_DIR, CSV_DIR, OUTPUTS_DIR]:
        os.makedirs(d, exist_ok=True)

    print("=" * 60)
    print("  SAF-T Ingestor & Analyzer - Banking Demo")
    print("  Open http://127.0.0.1:5000 in your browser")
    print("=" * 60)
    app.run(debug=True, host="127.0.0.1", port=5000)
