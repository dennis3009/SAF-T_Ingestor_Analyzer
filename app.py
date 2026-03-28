"""
app.py - Flask web interface for the SAF-T Ingestor & Analyzer.

Provides a single-page UI with:
  - Generate sample SAF-T XML files
  - Upload a ZIP of SAF-T XML reports
  - Analyze data (parse → score → graph → visualise)
  - View interactive network graph

Run:
    python app.py
Then open http://127.0.0.1:5000
"""

import os
import sys
import json
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


def _get_summary() -> dict:
    """Build a summary dict from the generated JSON outputs."""
    summary: dict = {"ok": True}

    # Companies
    companies_path = os.path.join(JSON_DIR, "companies.json")
    if os.path.exists(companies_path):
        with open(companies_path, encoding="utf-8") as fh:
            companies = json.load(fh)
        summary["num_companies"] = len(companies)
    else:
        summary["num_companies"] = 0

    # Partners
    partners_path = os.path.join(JSON_DIR, "partners.json")
    if os.path.exists(partners_path):
        with open(partners_path, encoding="utf-8") as fh:
            partners = json.load(fh)
        summary["num_partners"] = len(partners)
    else:
        summary["num_partners"] = 0

    # Transactions
    tx_path = os.path.join(CSV_DIR, "transactions.csv")
    if os.path.exists(tx_path):
        with open(tx_path, encoding="utf-8") as fh:
            summary["num_transactions"] = sum(1 for _ in fh) - 1  # minus header
    else:
        summary["num_transactions"] = 0

    # Scores
    scores_path = os.path.join(JSON_DIR, "scores.json")
    if os.path.exists(scores_path):
        with open(scores_path, encoding="utf-8") as fh:
            scores = json.load(fh)
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
    graph_path = os.path.join(JSON_DIR, "graph.json")
    if os.path.exists(graph_path):
        with open(graph_path, encoding="utf-8") as fh:
            graph = json.load(fh)
        metrics = graph.get("metrics", {})
        summary["num_edges"] = metrics.get("num_edges", 0)
        summary["cycles"] = metrics.get("cycle_details", [])
        summary["cycle_node_ids"] = metrics.get("cycle_node_ids", [])
    else:
        summary["num_edges"] = 0
        summary["cycles"] = []
        summary["cycle_node_ids"] = []

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
    """Generate synthetic SAF-T XML data."""
    with _pipeline_lock:
        try:
            _clear_data_dirs()
            companies = generator.generate()
            return jsonify({
                "ok": True,
                "message": f"Generated {len(companies)} SAF-T XML files.",
                "xml_count": _count_xml_files(),
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

            # Clear existing data
            _clear_data_dirs()

            # Extract XML files from ZIP
            extracted = 0
            with zipfile.ZipFile(uploaded.stream, "r") as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    # Only extract .xml files, flatten directory structure
                    basename = os.path.basename(info.filename)
                    if basename.lower().endswith(".xml"):
                        data = zf.read(info.filename)
                        target = os.path.join(RAW_XML_DIR, basename)
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
                "xml_count": extracted,
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

            # Step 1: Parse XML → JSON / CSV
            saft_parser.parse()

            # Step 2: Score companies
            scores = scoring.score_companies()

            # Step 3: Build graph
            graph = graph_builder.build_graph()

            # Step 4: Apply fraud-ring cycle penalties
            cycle_node_ids = graph.get("metrics", {}).get("cycle_node_ids", [])
            if cycle_node_ids:
                scores = scoring.apply_cycle_penalties(cycle_node_ids)
                graph = graph_builder.build_graph()

            # Step 5: Visualize
            visualize.visualize()

            # Build summary
            summary = _get_summary()
            summary["message"] = "Analysis complete."
            return jsonify(summary)

        except Exception as exc:
            import traceback
            traceback.print_exc()
            return jsonify({"ok": False, "message": str(exc)}), 500


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
    print("  SAF-T Ingestor & Analyzer — Web Interface")
    print("  Open http://127.0.0.1:5000 in your browser")
    print("=" * 60)
    app.run(debug=True, host="127.0.0.1", port=5000)


