"""
visualize.py - Transaction network graph visualization.

Generates a standalone interactive HTML file using the vis-network JS library
styled with a Syncfusion-inspired Tailwind color palette.

Output: data/outputs/graph.html
"""

import os
import json

GRAPH_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "graph.json"
)
OUTPUT_HTML = os.path.join(
    os.path.dirname(__file__), "data", "outputs", "graph.html"
)


def _node_color(risk_level: str | None, in_cycle: bool) -> dict:
    """Return a vis-network color object based on risk level."""
    if in_cycle:
        return {
            "background": "#f97316", "border": "#ea580c",
            "highlight": {"background": "#fb923c", "border": "#f97316"},
        }
    palette = {
        "Healthy": {
            "background": "#10b981", "border": "#059669",
            "highlight": {"background": "#34d399", "border": "#10b981"},
        },
        "Watch": {
            "background": "#f59e0b", "border": "#d97706",
            "highlight": {"background": "#fbbf24", "border": "#f59e0b"},
        },
        "Risky": {
            "background": "#ef4444", "border": "#dc2626",
            "highlight": {"background": "#f87171", "border": "#ef4444"},
        },
    }
    return palette.get(risk_level or "", {
        "background": "#94a3b8", "border": "#64748b",
        "highlight": {"background": "#cbd5e1", "border": "#94a3b8"},
    })


def _node_size(volume: float) -> int:
    """Return vis-network node size proportional to transaction volume."""
    return 12 + min(int(volume / 400_000), 38)


def _build_html(graph: dict) -> str:
    """Build the complete standalone HTML visualization string."""
    nodes_list = []
    for node in graph["nodes"]:
        color = _node_color(node.get("risk_level"), node.get("in_cycle", False))
        size = _node_size(node.get("volume", 0))
        score_str = (f"Score: {node['score']}" if node.get("score") is not None
                     else "External partner")
        risk_str = node.get("risk_level") or "Partner"
        cycle_badge = " ⚠ FRAUD RING" if node.get("in_cycle") else ""
        tooltip = (
            f"<div style='font-family:Inter,sans-serif;padding:8px;'>"
            f"<b style='font-size:13px'>{node['label']}</b><br>"
            f"<span style='color:#6b7280'>ID: {node['id']}</span><br>"
            f"Type: {node.get('type','unknown')}<br>"
            f"{score_str} | {risk_str}{cycle_badge}<br>"
            f"Volume: {node.get('volume', 0):,.0f} RON<br>"
            f"Out: {node.get('degree_out', 0)} &nbsp; In: {node.get('degree_in', 0)}"
            f"</div>"
        )
        nodes_list.append({
            "id": node["id"],
            "label": node["label"][:22],
            "title": tooltip,
            "color": color,
            "size": size,
            "borderWidth": 3 if node.get("in_cycle") else 1,
            "font": {"color": "#1e293b", "size": 11},
            "shape": "dot" if node.get("type") == "company" else "diamond",
        })

    max_weight = max((e["weight"] for e in graph["edges"]), default=1)
    edges_list = []
    for edge in graph["edges"]:
        w = edge["weight"]
        width = max(1.0, round(w / max_weight * 10, 1))
        edges_list.append({
            "from": edge["source"],
            "to": edge["target"],
            "value": width,
            "title": f"Value: {w:,.0f} RON ({edge['count']} txs)",
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.5}},
            "color": {"color": "#cbd5e1", "highlight": "#6366f1"},
            "smooth": {"type": "dynamic"},
        })

    metrics = graph.get("metrics", {})
    cycles = metrics.get("cycle_details", [])
    cycle_nodes = set(metrics.get("cycle_node_ids", []))

    # Count risk levels in a single pass over nodes
    healthy = watch = risky = companies = num_partners = 0
    for n in graph["nodes"]:
        ntype = n.get("type")
        if ntype == "company":
            companies += 1
            rl = n.get("risk_level")
            if rl == "Healthy":
                healthy += 1
            elif rl == "Watch":
                watch += 1
            elif rl == "Risky":
                risky += 1
        elif ntype == "partner":
            num_partners += 1

    nodes_json = json.dumps(nodes_list, ensure_ascii=False)
    edges_json = json.dumps(edges_list, ensure_ascii=False)

    cycle_html = ""
    if cycles:
        items = "".join(
            f'<li class="text-xs text-slate-600 py-0.5">'
            f'<span class="font-mono">{" → ".join(c)} → {c[0]}</span></li>'
            for c in cycles
        )
        cycle_html = (
            f'<div class="bg-orange-50 border border-orange-200 rounded-lg p-3">'
            f'<p class="text-xs font-semibold text-orange-700 mb-1">'
            f'⚠ {len(cycles)} Fraud Ring(s) Detected</p>'
            f'<ul class="list-none space-y-0">{items}</ul>'
            f'</div>'
        )
    else:
        cycle_html = (
            '<div class="bg-emerald-50 border border-emerald-200 rounded-lg p-3">'
            '<p class="text-xs text-emerald-700">✓ No circular trading patterns</p>'
            '</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>SAF-T Transaction Network — ANAF Risk Analyzer</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    * {{ font-family: 'Inter', system-ui, -apple-system, sans-serif; }}
    #network {{ width: 100%; height: 100%; background: #f8fafc; }}
    .vis-tooltip {{
      background: #1e293b !important;
      border: 1px solid #334155 !important;
      border-radius: 8px !important;
      color: #f1f5f9 !important;
      padding: 0 !important;
      font-family: 'Inter', sans-serif !important;
      box-shadow: 0 10px 25px rgba(0,0,0,0.3) !important;
      max-width: 260px;
    }}
    .vis-tooltip b {{ color: #e2e8f0; }}
    .vis-tooltip span {{ color: #94a3b8; }}
    ::-webkit-scrollbar {{ width: 4px; }}
    ::-webkit-scrollbar-track {{ background: #f1f5f9; }}
    ::-webkit-scrollbar-thumb {{ background: #cbd5e1; border-radius: 2px; }}
  </style>
</head>
<body class="bg-slate-100 overflow-hidden" style="height:100vh;">
  <div class="flex h-screen">

    <!-- ==================  LEFT PANEL  ================== -->
    <aside class="w-72 bg-white shadow-xl flex flex-col overflow-hidden border-r border-slate-200">

      <!-- Header -->
      <div class="bg-gradient-to-br from-indigo-600 to-indigo-800 px-4 py-5 flex-shrink-0">
        <div class="flex items-center gap-2 mb-1">
          <svg class="w-5 h-5 text-indigo-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
          </svg>
          <h1 class="text-white font-bold text-base leading-tight">SAF-T Network</h1>
        </div>
        <p class="text-indigo-200 text-xs">ANAF Transaction Risk Analyzer</p>
      </div>

      <!-- Scrollable content -->
      <div class="flex-1 overflow-y-auto px-3 py-3 space-y-3">

        <!-- Stats grid -->
        <div class="grid grid-cols-2 gap-2">
          <div class="bg-slate-50 rounded-lg p-2.5 border border-slate-100">
            <p class="text-2xl font-bold text-slate-800">{companies}</p>
            <p class="text-xs text-slate-500 mt-0.5">Companies</p>
          </div>
          <div class="bg-slate-50 rounded-lg p-2.5 border border-slate-100">
            <p class="text-2xl font-bold text-slate-800">{num_partners}</p>
            <p class="text-xs text-slate-500 mt-0.5">Partners</p>
          </div>
          <div class="bg-slate-50 rounded-lg p-2.5 border border-slate-100">
            <p class="text-2xl font-bold text-slate-800">{metrics.get('num_edges', 0)}</p>
            <p class="text-xs text-slate-500 mt-0.5">Edges</p>
          </div>
          <div class="bg-slate-50 rounded-lg p-2.5 border border-slate-100">
            <p class="text-2xl font-bold text-{'orange' if cycles else 'slate'}-600">{len(cycles)}</p>
            <p class="text-xs text-slate-500 mt-0.5">Cycles</p>
          </div>
        </div>

        <!-- Risk breakdown -->
        <div class="bg-slate-50 rounded-lg p-3 border border-slate-100">
          <p class="text-xs font-semibold text-slate-700 mb-2 uppercase tracking-wide">Risk Breakdown</p>
          <div class="space-y-1.5">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-emerald-500 flex-shrink-0"></span>
                <span class="text-xs text-slate-600">Healthy</span>
              </div>
              <span class="text-xs font-semibold text-slate-700 bg-emerald-100 px-1.5 py-0.5 rounded">{healthy}</span>
            </div>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-amber-500 flex-shrink-0"></span>
                <span class="text-xs text-slate-600">Watch</span>
              </div>
              <span class="text-xs font-semibold text-slate-700 bg-amber-100 px-1.5 py-0.5 rounded">{watch}</span>
            </div>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-red-500 flex-shrink-0"></span>
                <span class="text-xs text-slate-600">Risky</span>
              </div>
              <span class="text-xs font-semibold text-slate-700 bg-red-100 px-1.5 py-0.5 rounded">{risky}</span>
            </div>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-orange-500 flex-shrink-0"></span>
                <span class="text-xs text-slate-600">Fraud Ring</span>
              </div>
              <span class="text-xs font-semibold text-slate-700 bg-orange-100 px-1.5 py-0.5 rounded">{len(cycle_nodes)}</span>
            </div>
          </div>
        </div>

        <!-- Legend -->
        <div class="bg-slate-50 rounded-lg p-3 border border-slate-100">
          <p class="text-xs font-semibold text-slate-700 mb-2 uppercase tracking-wide">Legend</p>
          <div class="space-y-1.5 text-xs text-slate-600">
            <div class="flex items-center gap-2">
              <svg width="14" height="14" viewBox="0 0 14 14">
                <circle cx="7" cy="7" r="6" fill="#10b981"/>
              </svg>Healthy company
            </div>
            <div class="flex items-center gap-2">
              <svg width="14" height="14" viewBox="0 0 14 14">
                <circle cx="7" cy="7" r="6" fill="#f59e0b"/>
              </svg>Watch company
            </div>
            <div class="flex items-center gap-2">
              <svg width="14" height="14" viewBox="0 0 14 14">
                <circle cx="7" cy="7" r="6" fill="#ef4444"/>
              </svg>Risky company
            </div>
            <div class="flex items-center gap-2">
              <svg width="14" height="14" viewBox="0 0 14 14">
                <circle cx="7" cy="7" r="6" fill="#f97316"/>
              </svg>Fraud ring node
            </div>
            <div class="flex items-center gap-2">
              <svg width="14" height="14" viewBox="0 0 14 14">
                <polygon points="7,1 13,13 1,13" fill="#94a3b8"/>
              </svg>External partner ◆
            </div>
            <div class="flex items-center gap-2 pt-1 border-t border-slate-200">
              <svg width="20" height="6" viewBox="0 0 20 6">
                <line x1="0" y1="3" x2="20" y2="3" stroke="#cbd5e1" stroke-width="3"/>
              </svg>Transaction flow (→)
            </div>
          </div>
        </div>

        <!-- Fraud rings summary -->
        {cycle_html}

        <!-- Node detail (populated by JS on click) -->
        <div id="node-detail" class="hidden bg-indigo-50 border border-indigo-200 rounded-lg p-3">
          <p class="text-xs font-semibold text-indigo-700 mb-2">Selected Node</p>
          <div id="node-detail-content" class="text-xs text-slate-700 space-y-1"></div>
        </div>

      </div><!-- end scrollable -->
    </aside>

    <!-- ==================  MAIN CANVAS  ================== -->
    <main class="flex-1 relative">
      <!-- Toolbar -->
      <div class="absolute top-3 right-3 z-10 flex gap-2">
        <button onclick="network.fit({{animation:true}})"
          class="bg-white shadow text-xs text-slate-600 px-3 py-1.5 rounded-lg border border-slate-200
                 hover:bg-indigo-50 hover:border-indigo-300 hover:text-indigo-700 transition-colors">
          ⊕ Fit View
        </button>
        <button id="physics-btn" onclick="togglePhysics()"
          class="bg-white shadow text-xs text-slate-600 px-3 py-1.5 rounded-lg border border-slate-200
                 hover:bg-indigo-50 hover:border-indigo-300 hover:text-indigo-700 transition-colors">
          ⚙ Physics: ON
        </button>
      </div>
      <div id="network" class="w-full h-full"></div>
    </main>
  </div>

  <script>
    // ── Graph data ──────────────────────────────────────────────────────
    const nodesData = {nodes_json};
    const edgesData = {edges_json};

    const nodes = new vis.DataSet(nodesData);
    const edges = new vis.DataSet(edgesData);

    // ── vis-network options (Syncfusion Tailwind aesthetic) ─────────────
    const options = {{
      physics: {{
        enabled: true,
        barnesHut: {{
          gravitationalConstant: -12000,
          centralGravity: 0.3,
          springLength: 160,
          springConstant: 0.04,
          damping: 0.09,
        }},
        stabilization: {{ iterations: 200, updateInterval: 25 }},
      }},
      interaction: {{
        hover: true,
        tooltipDelay: 150,
        hideEdgesOnDrag: true,
        navigationButtons: false,
        keyboard: {{ enabled: true, speed: {{ x: 10, y: 10, zoom: 0.02 }} }},
      }},
      edges: {{
        smooth: {{ type: "dynamic" }},
        scaling: {{ min: 1, max: 10 }},
        selectionWidth: 2,
        hoverWidth: 1.5,
      }},
      nodes: {{
        scaling: {{ min: 10, max: 50 }},
        shadow: {{ enabled: true, color: "rgba(0,0,0,0.10)", size: 8, x: 2, y: 2 }},
      }},
    }};

    const container = document.getElementById("network");
    const network = new vis.Network(container, {{ nodes, edges }}, options);

    // ── Physics toggle ──────────────────────────────────────────────────
    let physicsOn = true;
    function togglePhysics() {{
      physicsOn = !physicsOn;
      network.setOptions({{ physics: {{ enabled: physicsOn }} }});
      document.getElementById("physics-btn").textContent =
        physicsOn ? "⚙ Physics: ON" : "⚙ Physics: OFF";
    }}

    // Disable physics after initial stabilisation to keep layout stable
    network.once("stabilizationIterationsDone", () => {{
      network.setOptions({{ physics: {{ enabled: false }} }});
      physicsOn = false;
      document.getElementById("physics-btn").textContent = "⚙ Physics: OFF";
    }});

    // ── Node click: show detail panel ───────────────────────────────────
    network.on("click", (params) => {{
      const panel = document.getElementById("node-detail");
      const content = document.getElementById("node-detail-content");
      if (!params.nodes.length) {{ panel.classList.add("hidden"); return; }}

      const nid = params.nodes[0];
      const node = nodesData.find(n => n.id === nid);
      if (!node) return;

      // Extract plain text from tooltip HTML for the side panel
      const tmp = document.createElement("div");
      tmp.innerHTML = node.title || "";
      const lines = tmp.innerText.split("\\n").filter(l => l.trim());

      // Escape text before inserting into innerHTML to prevent XSS
      content.innerHTML = lines.map(l => {{
        const escaped = l.trim()
          .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        return `<p class="leading-5">${{escaped}}</p>`;
      }}).join("");
      panel.classList.remove("hidden");
      panel.scrollIntoView({{ behavior: "smooth", block: "nearest" }});
    }});
  </script>
</body>
</html>"""


def visualize(
    graph_path: str = GRAPH_JSON,
    output_html: str = OUTPUT_HTML,
) -> None:
    """Load graph JSON and produce a vis-network visualization."""
    with open(graph_path, encoding="utf-8") as fh:
        graph = json.load(fh)

    os.makedirs(os.path.dirname(output_html), exist_ok=True)
    html = _build_html(graph)
    with open(output_html, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"[visualize] Interactive graph saved → {output_html}")


if __name__ == "__main__":
    visualize()
