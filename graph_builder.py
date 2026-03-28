"""
graph_builder.py - Transaction network graph construction, analysis, and risk propagation.

Builds a directed graph where:
  - Nodes  = companies + partners
  - Edges  = transaction flows
  - Weight = total transaction value

Computes per-node metrics, detects cycles (fraud rings), and propagates
risk to connected nodes based on exposure.

Output: data/json/graph.json
"""

import os
import json
import csv
from collections import defaultdict

TRANSACTIONS_CSV = os.path.join(
    os.path.dirname(__file__), "data", "csv", "transactions.csv"
)
COMPANIES_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "companies.json"
)
PARTNERS_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "partners.json"
)
SCORES_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "scores.json"
)
GRAPH_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "graph.json"
)


def _load_json(path: str) -> list:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _load_transactions(path: str) -> list:
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                row["amount"] = float(row["amount"])
            except ValueError:
                row["amount"] = 0.0
            rows.append(row)
    return rows


def _find_cycles(adj: dict) -> list:
    """
    Detect simple cycles in a directed graph using DFS (Johnson-like approach
    simplified for small graphs).  Returns a list of cycles, each cycle being
    a list of node IDs.
    """
    visited = set()
    rec_stack = []
    rec_set = set()
    cycles = []

    def dfs(node):
        visited.add(node)
        rec_stack.append(node)
        rec_set.add(node)

        for neighbor in adj.get(node, []):
            if neighbor not in visited:
                dfs(neighbor)
            elif neighbor in rec_set:
                # Found a cycle - extract it from the stack
                idx = rec_stack.index(neighbor)
                cycle = rec_stack[idx:]
                cycles.append(list(cycle))

        rec_stack.pop()
        rec_set.discard(node)

    for node in list(adj.keys()):
        if node not in visited:
            dfs(node)

    # Deduplicate cycles (canonical form: start from min node)
    unique = []
    seen_sigs = set()
    for cycle in cycles:
        canonical = tuple(sorted(cycle))
        if canonical not in seen_sigs:
            seen_sigs.add(canonical)
            unique.append(cycle)

    return unique


def _propagate_risk(
    nodes_by_id: dict,
    edge_weight: dict,
    score_map: dict,
    company_ids: set,
) -> dict:
    """
    Propagate risk through the network.

    For each company, compute an exposure_score based on:
      - Direct exposure: high transaction volume with risky nodes
      - Indirect exposure: multi-hop connections to risky nodes (2 hops)

    Returns dict: company_id -> {exposure_score, direct_risky_partners, indirect_exposure}
    """
    # Build adjacency with weights (both directions)
    neighbors: dict = defaultdict(dict)  # node -> {neighbor -> total_weight}
    for (src, dst), weight in edge_weight.items():
        neighbors[src][dst] = weight
        neighbors[dst][src] = neighbors[dst].get(src, 0) + weight

    # Identify risky nodes (score < 40)
    risky_nodes = set()
    for cid, s in score_map.items():
        if s.get("score", 100) < 40:
            risky_nodes.add(cid)

    exposure = {}

    for cid in company_ids:
        if cid not in neighbors:
            exposure[cid] = {
                "exposure_score": 0,
                "direct_risky_partners": [],
                "indirect_exposure": False,
            }
            continue

        company_volume = sum(neighbors[cid].values())
        if company_volume == 0:
            exposure[cid] = {
                "exposure_score": 0,
                "direct_risky_partners": [],
                "indirect_exposure": False,
            }
            continue

        # Direct exposure: what % of volume is with risky nodes
        direct_risky_volume = 0
        direct_risky_partners = []
        for neighbor, weight in neighbors[cid].items():
            if neighbor in risky_nodes and neighbor != cid:
                direct_risky_volume += weight
                direct_risky_partners.append(neighbor)

        direct_ratio = direct_risky_volume / company_volume if company_volume > 0 else 0

        # Indirect exposure: 2-hop connections to risky nodes
        indirect_exposure = False
        for neighbor in neighbors[cid]:
            if neighbor == cid or neighbor in risky_nodes:
                continue
            for hop2 in neighbors.get(neighbor, {}):
                if hop2 in risky_nodes and hop2 != cid:
                    indirect_exposure = True
                    break
            if indirect_exposure:
                break

        # Exposure score: 0-100 scale
        exposure_score = round(min(100, direct_ratio * 100 + (15 if indirect_exposure else 0)), 1)

        exposure[cid] = {
            "exposure_score": exposure_score,
            "direct_risky_partners": direct_risky_partners,
            "indirect_exposure": indirect_exposure,
        }

    return exposure


def build_graph(
    tx_path: str = TRANSACTIONS_CSV,
    companies_path: str = COMPANIES_JSON,
    partners_path: str = PARTNERS_JSON,
    scores_path: str = SCORES_JSON,
    output_path: str = GRAPH_JSON,
) -> dict:
    """
    Build and persist the transaction network graph.

    Returns a graph dict with keys: nodes, edges, metrics.
    """
    transactions = _load_transactions(tx_path)
    companies_list = _load_json(companies_path)
    partners_list = _load_json(partners_path)
    scores_list = _load_json(scores_path)

    score_map = {s["company_id"]: s for s in scores_list}
    company_ids = {c["company_id"] for c in companies_list}
    partner_ids = {p["partner_id"] for p in partners_list}

    # --- Aggregate edge weights ---
    # For sales: edge from company -> partner (company sells to customer)
    # For purchases: edge from partner -> company (supplier sends to company)
    edge_weight: dict = defaultdict(float)  # (src, dst) -> total amount
    edge_count: dict = defaultdict(int)

    node_volume: dict = defaultdict(float)  # total value touching node
    node_degree_out: dict = defaultdict(set)
    node_degree_in: dict = defaultdict(set)

    for tx in transactions:
        cid = tx["company_id"]
        pid = tx["partner_id"]
        amt = tx["amount"]

        if tx["type"] == "sale":
            src, dst = cid, pid
        else:  # purchase
            src, dst = pid, cid

        edge_weight[(src, dst)] += amt
        edge_count[(src, dst)] += 1
        node_volume[src] += amt
        node_volume[dst] += amt
        node_degree_out[src].add(dst)
        node_degree_in[dst].add(src)

    # --- Build adjacency list for cycle detection (company-to-company only) ---
    adj: dict = defaultdict(set)
    for (src, dst) in edge_weight.keys():
        if src in company_ids and dst in company_ids:
            adj[src].add(dst)

    cycles = _find_cycles(adj)
    cycle_nodes: set = set()
    for cycle in cycles:
        cycle_nodes.update(cycle)

    # --- Risk propagation ---
    exposure_map = _propagate_risk(
        {}, edge_weight, score_map, company_ids
    )

    # --- Build nodes list ---
    nodes = []
    all_node_ids = (
        {c["company_id"] for c in companies_list}
        | {p["partner_id"] for p in partners_list}
    )

    # Only include nodes that actually appear in transactions
    active_nodes = set()
    for (src, dst) in edge_weight.keys():
        active_nodes.add(src)
        active_nodes.add(dst)

    node_id_lookup = {}
    for c in companies_list:
        node_id_lookup[c["company_id"]] = c.get("name", c["company_id"])
    for p in partners_list:
        node_id_lookup[p["partner_id"]] = p.get("name", p["partner_id"])

    for nid in active_nodes:
        s = score_map.get(nid, {})
        exp = exposure_map.get(nid, {})
        node = {
            "id": nid,
            "label": node_id_lookup.get(nid, nid),
            "type": "company" if nid in company_ids else "partner",
            "volume": round(node_volume[nid], 2),
            "degree_out": len(node_degree_out[nid]),
            "degree_in": len(node_degree_in[nid]),
            "in_cycle": nid in cycle_nodes,
            "score": s.get("score", None),
            "risk_level": s.get("risk_level", None),
            "trend": s.get("trend", None),
            "exposure_score": exp.get("exposure_score", 0),
            "direct_risky_partners": exp.get("direct_risky_partners", []),
            "indirect_exposure": exp.get("indirect_exposure", False),
        }
        nodes.append(node)

    # --- Build edges list ---
    edges = []
    for (src, dst), weight in edge_weight.items():
        edges.append(
            {
                "source": src,
                "target": dst,
                "weight": round(weight, 2),
                "count": edge_count[(src, dst)],
            }
        )

    # --- Per-company partner concentration metric ---
    partner_concentration: dict = {}
    revenue_by_company_partner: dict = defaultdict(lambda: defaultdict(float))
    for tx in transactions:
        if tx["type"] == "sale":
            revenue_by_company_partner[tx["company_id"]][tx["partner_id"]] += tx["amount"]

    for cid, rev_map in revenue_by_company_partner.items():
        total = sum(rev_map.values())
        if total > 0:
            top = max(rev_map.values())
            partner_concentration[cid] = round(top / total, 4)

    # --- Top partners per company ---
    top_partners: dict = {}
    for cid, rev_map in revenue_by_company_partner.items():
        sorted_partners = sorted(rev_map.items(), key=lambda x: -x[1])[:5]
        top_partners[cid] = [
            {"partner_id": pid, "amount": round(amt, 2)}
            for pid, amt in sorted_partners
        ]

    metrics = {
        "num_nodes": len(nodes),
        "num_edges": len(edges),
        "cycles_detected": len(cycles),
        "cycle_details": cycles,
        "cycle_node_ids": list(cycle_nodes),
        "partner_concentration": partner_concentration,
        "top_partners": top_partners,
    }

    graph = {"nodes": nodes, "edges": edges, "metrics": metrics}

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(graph, fh, indent=2, ensure_ascii=False)

    exposed = sum(1 for n in nodes if n.get("exposure_score", 0) > 0 and n["type"] == "company")
    print(
        f"[graph_builder] Graph: {len(nodes)} nodes, {len(edges)} edges, "
        f"{len(cycles)} cycle(s) detected, {exposed} companies with risk exposure"
    )
    return graph


if __name__ == "__main__":
    build_graph()
