SAF-T Ingestor & Analyzer — Proof of Concept
=============================================

OVERVIEW
--------
This project demonstrates ingestion and behavioural analysis of SAF-T-like
financial data without using any databases.  All data is stored and processed
using JSON and CSV files.

The pipeline consists of five steps:
  1. Synthetic data generation (generator.py)
  2. XML parsing and normalisation (parser.py)
  3. Behavioural risk scoring (scoring.py)
  4. Transaction network graph construction (graph_builder.py)
  5. Interactive visualisation (visualize.py)

The entry point (main.py) orchestrates all five steps and prints a summary.


REQUIREMENTS
------------
Python 3.10 or higher is required.


SETUP
-----

1. Create a virtual environment:

   python -m venv .venv

2. Activate the virtual environment:

   On Linux / macOS:
       source .venv/bin/activate

   On Windows (Command Prompt):
       .venv\Scripts\activate.bat

   On Windows (PowerShell):
       .venv\Scripts\Activate.ps1

3. Install dependencies:

   pip install -r requirements.txt


RUNNING THE PROJECT
-------------------

From the project root directory, run:

   python main.py

The script will:
  - Generate 30 synthetic SAF-T XML files in data/raw_xml/
  - Parse and normalise the data into JSON and CSV files
  - Compute risk scores for every company
  - Build a transaction network graph
  - Generate an interactive HTML visualisation
  - Print a summary report to the console


OUTPUT FILES
------------

  data/raw_xml/           — One XML file per synthetic company
  data/json/companies.json — Normalised company entities
  data/json/partners.json  — Normalised partner (customer/supplier) entities
  data/json/scores.json    — Risk scores and explanations per company
  data/json/graph.json     — Full graph structure (nodes, edges, metrics)
  data/csv/transactions.csv — All transactions in tabular format
  data/outputs/graph.html  — Interactive network visualisation (open in browser)


UNDERSTANDING THE OUTPUT
------------------------

graph.html
  Open this file in any modern web browser.  Nodes represent companies and
  partners; edges represent transaction flows.  Node colour indicates risk:
    Green  — Healthy (score >= 70)
    Yellow — Watch   (score 40-69)
    Red    — Risky   (score < 40)
    Orange-Red — Node involved in a detected fraud ring cycle

scores.json
  Each entry contains:
    company_id  — identifier
    score       — 0-100 (100 = fully healthy)
    risk_level  — Healthy / Watch / Risky
    explanation — list of penalty reasons applied

graph.json → metrics → cycle_details
  Lists any circular trading loops (fraud rings) detected in the network.


INJECTED BEHAVIOURAL PATTERNS
------------------------------

  Companies COMP0001–COMP0020 : Normal behaviour
  Companies COMP0021–COMP0026 : Risky behaviour
    (high customer concentration, revenue spikes)
  Companies COMP0027–COMP0030 : Fraud ring
    (circular trading: COMP0027 -> COMP0028 -> COMP0029 -> COMP0030 -> COMP0027)


NOTES
-----
  - No database is used at any point; all persistence is file-based.
  - Re-running main.py regenerates all data deterministically (fixed seed).
  - The project is intentionally simple; it is designed for demonstration
    purposes only, not production use.
