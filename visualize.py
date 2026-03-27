"""
visualize.py - Transaction network graph visualization.

Generates an interactive HTML file using pyvis (falls back to a static
NetworkX/matplotlib PNG if pyvis is unavailable).

Output: data/outputs/graph.html  (and optionally graph.png)
"""

import os
import json

GRAPH_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "graph.json"
)
OUTPUT_HTML = os.path.join(
    os.path.dirname(__file__), "data", "outputs", "graph.html"
)
OUTPUT_PNG = os.path.join(
    os.path.dirname(__file__), "data", "outputs", "graph.png"
)


def _risk_color(risk_level: str | None, in_cycle: bool) -> str:
    """Return a hex color string based on risk level."""
    if in_cycle:
        return "#FF4500"  # orange-red for fraud ring nodes
    mapping = {
        "Healthy": "#2ECC71",   # green
        "Watch": "#F39C12",     # yellow/orange
        "Risky": "#E74C3C",     # red
    }
    return mapping.get(risk_level or "", "#95A5A6")  # grey for external partners


def _node_size(volume: float, min_size: int = 10, max_size: int = 60) -> int:
    """Scale node size proportionally to transaction volume."""
    return min_size + min(int(volume / 2_000_000), max_size - min_size)


def visualize_pyvis(graph: dict, output_path: str = OUTPUT_HTML) -> None:
    """Generate interactive HTML with pyvis."""
    from pyvis.network import Network  # type: ignore

    net = Network(
        height="800px",
        width="100%",
        bgcolor="#1a1a2e",
        font_color="#ffffff",
        directed=True,
        notebook=False,
    )
    net.toggle_physics(True)
    net.set_options(
        """{
          "physics": {
            "barnesHut": {
              "gravitationalConstant": -8000,
              "springLength": 150,
              "springConstant": 0.04
            },
            "stabilization": {"iterations": 150}
          },
          "edges": {
            "smooth": {"type": "dynamic"},
            "arrows": {"to": {"enabled": true, "scaleFactor": 0.5}}
          }
        }"""
    )

    # Map node id -> volume for edge scaling
    volume_map = {n["id"]: n.get("volume", 0) for n in graph["nodes"]}
    max_volume = max(volume_map.values(), default=1)

    for node in graph["nodes"]:
        nid = node["id"]
        color = _risk_color(node.get("risk_level"), node.get("in_cycle", False))
        size = _node_size(node.get("volume", 0))

        score_str = (
            f"Score: {node['score']}" if node.get("score") is not None else "External"
        )
        risk_str = node.get("risk_level") or "Partner"
        cycle_str = " ⚠ IN FRAUD RING" if node.get("in_cycle") else ""

        title = (
            f"<b>{node['label']}</b><br>"
            f"ID: {nid}<br>"
            f"Type: {node.get('type', 'unknown')}<br>"
            f"{score_str} | {risk_str}{cycle_str}<br>"
            f"Volume: {node.get('volume', 0):,.0f}<br>"
            f"Out-degree: {node.get('degree_out', 0)} | "
            f"In-degree: {node.get('degree_in', 0)}"
        )

        net.add_node(
            nid,
            label=node["label"][:25],
            color=color,
            size=size,
            title=title,
            borderWidth=3 if node.get("in_cycle") else 1,
            borderWidthSelected=5,
        )

    # Determine max edge weight for scaling
    max_weight = max((e["weight"] for e in graph["edges"]), default=1)

    for edge in graph["edges"]:
        w = edge["weight"]
        thickness = max(1, int(w / max_weight * 10))
        net.add_edge(
            edge["source"],
            edge["target"],
            value=thickness,
            title=f"Value: {w:,.0f} ({edge['count']} txs)",
            color="#888888",
        )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    net.save_graph(output_path)
    print(f"[visualize] Interactive graph saved → {output_path}")


def visualize_matplotlib(graph: dict, output_path: str = OUTPUT_PNG) -> None:
    """Fallback: static PNG using networkx + matplotlib."""
    import networkx as nx
    import matplotlib.pyplot as plt

    G = nx.DiGraph()
    for node in graph["nodes"]:
        G.add_node(node["id"], **node)
    for edge in graph["edges"]:
        G.add_edge(edge["source"], edge["target"], weight=edge["weight"])

    pos = nx.spring_layout(G, seed=42, k=2)
    colors = [
        _risk_color(
            G.nodes[n].get("risk_level"), G.nodes[n].get("in_cycle", False)
        )
        for n in G.nodes
    ]
    sizes = [_node_size(G.nodes[n].get("volume", 0)) * 20 for n in G.nodes]

    plt.figure(figsize=(16, 12))
    nx.draw_networkx(
        G,
        pos,
        node_color=colors,
        node_size=sizes,
        font_size=6,
        arrows=True,
        edge_color="#888888",
        alpha=0.8,
    )
    plt.title("SAF-T Transaction Network", fontsize=16)
    plt.axis("off")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[visualize] Static graph image saved → {output_path}")


def visualize(
    graph_path: str = GRAPH_JSON,
    output_html: str = OUTPUT_HTML,
) -> None:
    """Load graph JSON and produce visualization."""
    with open(graph_path, encoding="utf-8") as fh:
        graph = json.load(fh)

    try:
        visualize_pyvis(graph, output_html)
    except ImportError:
        print("[visualize] pyvis not available, falling back to matplotlib PNG")
        visualize_matplotlib(graph)


if __name__ == "__main__":
    visualize()
