"""
risk_propagation.py - Risk propagation through the transaction network.

Identifies risky nodes and propagates risk to connected entities:
  - Direct exposure: high transaction volume with risky node
  - Indirect exposure: multi-hop connections to risky entities

Updates graph.json with exposure metrics per node.

Output: updates data/json/graph.json (adds exposure fields to nodes)
"""

import os
import json
from collections import defaultdict

GRAPH_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "graph.json"
)
SCORES_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "scores.json"
)


def propagate_risk(
    graph_path: str = GRAPH_JSON,
    scores_path: str = SCORES_JSON,
) -> dict:
    """
    Propagate risk through the transaction network.

    For each node, computes:
      - exposure_score (0-100): how exposed to risky entities
      - direct_exposure: list of risky entities with direct connections
      - indirect_exposure: list of risky entities reachable in 2 hops

    Updates and saves graph.json.
    Returns the updated graph.
    """
    with open(graph_path, encoding="utf-8") as fh:
        graph = json.load(fh)

    with open(scores_path, encoding="utf-8") as fh:
        scores = json.load(fh)

    score_map = {s["company_id"]: s for s in scores}

    # Identify risky nodes (score < 40)
    risky_nodes = set()
    for s in scores:
        if s["risk_level"] == "Risky":
            risky_nodes.add(s["company_id"])

    # Build adjacency lists (undirected for exposure)
    neighbors: dict = defaultdict(set)
    edge_volume: dict = defaultdict(float)  # (node, neighbor) -> volume

    for edge in graph["edges"]:
        src = edge["source"]
        dst = edge["target"]
        w = edge["weight"]
        neighbors[src].add(dst)
        neighbors[dst].add(src)
        edge_volume[(src, dst)] += w
        edge_volume[(dst, src)] += w

    # Compute total volume per node
    node_total_volume: dict = defaultdict(float)
    for node in graph["nodes"]:
        node_total_volume[node["id"]] = node.get("volume", 0)

    # Compute exposure for each node
    node_exposure = {}

    for node in graph["nodes"]:
        nid = node["id"]
        direct = []
        indirect = []

        # Direct exposure: directly connected to risky nodes
        for neighbor in neighbors.get(nid, set()):
            if neighbor in risky_nodes and neighbor != nid:
                vol = edge_volume.get((nid, neighbor), 0)
                total = node_total_volume.get(nid, 1)
                share = round(vol / total, 4) if total > 0 else 0
                direct.append({
                    "entity": neighbor,
                    "volume": round(vol, 2),
                    "share": share,
                })

        # Indirect exposure: 2-hop connections to risky nodes
        seen = {nid} | neighbors.get(nid, set())
        for neighbor in neighbors.get(nid, set()):
            for hop2 in neighbors.get(neighbor, set()):
                if hop2 in risky_nodes and hop2 != nid and hop2 not in seen:
                    indirect.append({
                        "entity": hop2,
                        "via": neighbor,
                    })
                    seen.add(hop2)

        # Compute exposure score (0-100)
        exposure_score = 0.0

        # Direct exposure contributes up to 60 points
        if direct:
            total_risky_share = sum(d["share"] for d in direct)
            exposure_score += min(60, total_risky_share * 100)

        # Indirect exposure contributes up to 25 points
        if indirect:
            exposure_score += min(25, len(indirect) * 8)

        # Being risky yourself adds 15 points
        if nid in risky_nodes:
            exposure_score += 15

        exposure_score = round(min(100, exposure_score), 1)

        node_exposure[nid] = {
            "exposure_score": exposure_score,
            "direct_exposure": direct,
            "indirect_exposure": indirect,
            "exposure_level": (
                "high" if exposure_score >= 50
                else "medium" if exposure_score >= 20
                else "low"
            ),
        }

    # Update graph nodes with exposure data
    for node in graph["nodes"]:
        nid = node["id"]
        exp = node_exposure.get(nid, {})
        node["exposure_score"] = exp.get("exposure_score", 0)
        node["exposure_level"] = exp.get("exposure_level", "low")
        node["direct_exposure"] = exp.get("direct_exposure", [])
        node["indirect_exposure"] = exp.get("indirect_exposure", [])

    # Save updated graph
    with open(graph_path, "w", encoding="utf-8") as fh:
        json.dump(graph, fh, indent=2, ensure_ascii=False)

    high = sum(1 for e in node_exposure.values() if e["exposure_level"] == "high")
    medium = sum(1 for e in node_exposure.values() if e["exposure_level"] == "medium")
    print(
        f"[risk_propagation] Exposure computed for {len(node_exposure)} nodes → "
        f"high: {high}, medium: {medium}"
    )
    return graph


if __name__ == "__main__":
    propagate_risk()
