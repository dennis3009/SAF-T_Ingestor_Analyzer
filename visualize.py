"""
visualize.py - Enhanced transaction network graph visualization.

Generates a standalone interactive HTML file using vis-network JS library
with filtering, highlighting, and detailed node inspection capabilities.

Output: data/outputs/graph.html
"""

import os
import json

GRAPH_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "graph.json"
)
SCORES_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "scores.json"
)
DECISIONS_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "decisions.json"
)
MONTHLY_METRICS_JSON = os.path.join(
    os.path.dirname(__file__), "data", "json", "monthly_metrics.json"
)
OUTPUT_HTML = os.path.join(
    os.path.dirname(__file__), "data", "outputs", "graph.html"
)


def _node_color(risk_level, in_cycle):
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


def _node_size(volume):
    """Return vis-network node size proportional to transaction volume."""
    return 12 + min(int(volume / 400_000), 38)


def _build_html(graph, scores_map, decisions_map, metrics_map):
    """Build the complete standalone HTML visualization string."""
    nodes_list = []
    for node in graph["nodes"]:
        color = _node_color(node.get("risk_level"), node.get("in_cycle", False))
        size = _node_size(node.get("volume", 0))
        nid = node["id"]
        score_data = scores_map.get(nid, {})
        decision_data = decisions_map.get(nid, {})
        metric_data = metrics_map.get(nid, {})

        score_str = (f"Score: {node['score']}" if node.get("score") is not None
                     else "External partner")
        risk_str = node.get("risk_level") or "Partner"
        trend = score_data.get("trend", "")
        decision = decision_data.get("decision", "")
        cycle_badge = " FRAUD RING" if node.get("in_cycle") else ""
        exposure = node.get("exposure_level", "")

        tooltip = (
            f"<div style='font-family:Inter,sans-serif;padding:8px;'>"
            f"<b style='font-size:13px'>{node['label']}</b><br>"
            f"<span style='color:#6b7280'>ID: {nid}</span><br>"
            f"Type: {node.get('type','unknown')}<br>"
            f"{score_str} | {risk_str}{cycle_badge}<br>"
            f"Volume: {node.get('volume', 0):,.0f} RON<br>"
        )
        if trend:
            tooltip += f"Trend: {trend}<br>"
        if decision:
            tooltip += f"Decision: {decision}<br>"
        if exposure:
            tooltip += f"Exposure: {exposure}<br>"
        tooltip += (
            f"Out: {node.get('degree_out', 0)} &nbsp; In: {node.get('degree_in', 0)}"
            f"</div>"
        )

        nodes_list.append({
            "id": nid,
            "label": node["label"][:22],
            "title": tooltip,
            "color": color,
            "size": size,
            "borderWidth": 3 if node.get("in_cycle") else 1,
            "font": {"color": "#1e293b", "size": 11},
            "shape": "dot" if node.get("type") == "company" else "diamond",
            # Store metadata for filtering
            "_risk": node.get("risk_level", ""),
            "_type": node.get("type", ""),
            "_cycle": node.get("in_cycle", False),
            "_score": node.get("score"),
            "_trend": score_data.get("trend", ""),
            "_decision": decision_data.get("decision", ""),
            "_exposure": node.get("exposure_level", ""),
            "_volume": node.get("volume", 0),
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
            "_weight": w,
            "title": f"Value: {w:,.0f} RON ({edge['count']} txs)",
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.5}},
            "color": {"color": "#cbd5e1", "highlight": "#6366f1"},
            "smooth": {"type": "dynamic"},
        })

    metrics = graph.get("metrics", {})
    cycles = metrics.get("cycle_details", [])
    cycle_nodes = set(metrics.get("cycle_node_ids", []))

    # Count risk levels
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

    # Build scores data for detail panel
    scores_json = json.dumps(scores_map, ensure_ascii=False)
    decisions_json = json.dumps(decisions_map, ensure_ascii=False)
    metrics_json_str = json.dumps(metrics_map, ensure_ascii=False)

    cycle_html = ""
    if cycles:
        items = "".join(
            f'<li class="text-xs text-slate-600 py-0.5">'
            f'<span class="font-mono">{" -> ".join(c)} -> {c[0]}</span></li>'
            for c in cycles
        )
        cycle_html = (
            f'<div class="bg-orange-50 border border-orange-200 rounded-lg p-3">'
            f'<p class="text-xs font-semibold text-orange-700 mb-1">'
            f'{len(cycles)} Fraud Ring(s) Detected</p>'
            f'<ul class="list-none space-y-0">{items}</ul>'
            f'</div>'
        )
    else:
        cycle_html = (
            '<div class="bg-emerald-50 border border-emerald-200 rounded-lg p-3">'
            '<p class="text-xs text-emerald-700">No circular trading patterns</p>'
            '</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>SAF-T Transaction Network - Risk Analyzer</title>
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
      max-width: 280px;
    }}
    .vis-tooltip b {{ color: #e2e8f0; }}
    .vis-tooltip span {{ color: #94a3b8; }}
    ::-webkit-scrollbar {{ width: 4px; }}
    ::-webkit-scrollbar-track {{ background: #f1f5f9; }}
    ::-webkit-scrollbar-thumb {{ background: #cbd5e1; border-radius: 2px; }}
    .filter-btn {{ transition: all 0.2s; }}
    .filter-btn.active {{ background: #4f46e5; color: white; border-color: #4f46e5; }}
  </style>
</head>
<body class="bg-slate-100 overflow-hidden" style="height:100vh;">
  <div class="flex h-screen">

    <!-- LEFT PANEL -->
    <aside class="w-80 bg-white shadow-xl flex flex-col overflow-hidden border-r border-slate-200">

      <!-- Header -->
      <div class="bg-gradient-to-br from-indigo-600 to-indigo-800 px-4 py-4 flex-shrink-0">
        <div class="flex items-center gap-2 mb-1">
          <svg class="w-5 h-5 text-indigo-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
          </svg>
          <h1 class="text-white font-bold text-base leading-tight">SAF-T Network</h1>
        </div>
        <p class="text-indigo-200 text-xs">Investigation &amp; Risk Analysis Tool</p>
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
              <div class="flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-full bg-emerald-500"></span><span class="text-xs text-slate-600">Healthy</span></div>
              <span class="text-xs font-semibold text-slate-700 bg-emerald-100 px-1.5 py-0.5 rounded">{healthy}</span>
            </div>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-full bg-amber-500"></span><span class="text-xs text-slate-600">Watch</span></div>
              <span class="text-xs font-semibold text-slate-700 bg-amber-100 px-1.5 py-0.5 rounded">{watch}</span>
            </div>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-full bg-red-500"></span><span class="text-xs text-slate-600">Risky</span></div>
              <span class="text-xs font-semibold text-slate-700 bg-red-100 px-1.5 py-0.5 rounded">{risky}</span>
            </div>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-full bg-orange-500"></span><span class="text-xs text-slate-600">Fraud Ring</span></div>
              <span class="text-xs font-semibold text-slate-700 bg-orange-100 px-1.5 py-0.5 rounded">{len(cycle_nodes)}</span>
            </div>
          </div>
        </div>

        <!-- Filters -->
        <div class="bg-slate-50 rounded-lg p-3 border border-slate-100">
          <p class="text-xs font-semibold text-slate-700 mb-2 uppercase tracking-wide">Filters</p>
          <div class="flex flex-wrap gap-1.5">
            <button onclick="filterRisky()" class="filter-btn text-xs px-2.5 py-1 rounded-full border border-slate-300 text-slate-600 hover:border-red-400 hover:text-red-600" id="btn-filter-risky">Risky Only</button>
            <button onclick="filterHighValue()" class="filter-btn text-xs px-2.5 py-1 rounded-full border border-slate-300 text-slate-600 hover:border-indigo-400 hover:text-indigo-600" id="btn-filter-hv">High-Value Edges</button>
            <button onclick="highlightCycles()" class="filter-btn text-xs px-2.5 py-1 rounded-full border border-slate-300 text-slate-600 hover:border-orange-400 hover:text-orange-600" id="btn-filter-cycles">Highlight Cycles</button>
            <button onclick="resetFilters()" class="filter-btn text-xs px-2.5 py-1 rounded-full border border-slate-300 text-slate-600 hover:border-emerald-400 hover:text-emerald-600">Reset</button>
          </div>
        </div>

        <!-- Fraud rings -->
        {cycle_html}

        <!-- Node detail (populated by JS on click) -->
        <div id="node-detail" class="hidden bg-indigo-50 border border-indigo-200 rounded-lg p-3">
          <p class="text-xs font-semibold text-indigo-700 mb-2">Selected Node</p>
          <div id="node-detail-content" class="text-xs text-slate-700 space-y-1"></div>
        </div>

      </div>
    </aside>

    <!-- MAIN CANVAS -->
    <main class="flex-1 relative">
      <!-- Toolbar -->
      <div class="absolute top-3 right-3 z-10 flex gap-2">
        <button onclick="network.fit({{animation:true}})"
          class="bg-white shadow text-xs text-slate-600 px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-indigo-50 hover:border-indigo-300 hover:text-indigo-700 transition-colors">
          Fit View
        </button>
        <button id="physics-btn" onclick="togglePhysics()"
          class="bg-white shadow text-xs text-slate-600 px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-indigo-50 hover:border-indigo-300 hover:text-indigo-700 transition-colors">
          Physics: ON
        </button>
      </div>
      <div id="network" class="w-full h-full"></div>
    </main>
  </div>

  <script>
    // Graph data
    const allNodesData = {nodes_json};
    const allEdgesData = {edges_json};
    const scoresData = {scores_json};
    const decisionsData = {decisions_json};
    const metricsData = {metrics_json_str};

    const nodes = new vis.DataSet(allNodesData);
    const edges = new vis.DataSet(allEdgesData);

    // vis-network options
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

    // Physics toggle
    let physicsOn = true;
    function togglePhysics() {{
      physicsOn = !physicsOn;
      network.setOptions({{ physics: {{ enabled: physicsOn }} }});
      document.getElementById("physics-btn").textContent = physicsOn ? "Physics: ON" : "Physics: OFF";
    }}

    network.once("stabilizationIterationsDone", () => {{
      network.setOptions({{ physics: {{ enabled: false }} }});
      physicsOn = false;
      document.getElementById("physics-btn").textContent = "Physics: OFF";
    }});

    // Filter functions
    let activeFilter = null;

    function clearFilterBtns() {{
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    }}

    function filterRisky() {{
      clearFilterBtns();
      if (activeFilter === 'risky') {{ resetFilters(); return; }}
      activeFilter = 'risky';
      document.getElementById('btn-filter-risky').classList.add('active');

      const riskyIds = new Set(allNodesData.filter(n => n._risk === 'Risky' || n._cycle).map(n => n.id));
      // Show risky nodes and their direct connections
      const connectedEdges = allEdgesData.filter(e => riskyIds.has(e.from) || riskyIds.has(e.to));
      const connectedNodeIds = new Set();
      connectedEdges.forEach(e => {{ connectedNodeIds.add(e.from); connectedNodeIds.add(e.to); }});

      const hiddenNodes = allNodesData.filter(n => !connectedNodeIds.has(n.id)).map(n => ({{ ...n, hidden: true }}));
      const visibleNodes = allNodesData.filter(n => connectedNodeIds.has(n.id)).map(n => ({{ ...n, hidden: false }}));
      nodes.update([...hiddenNodes, ...visibleNodes]);
    }}

    function filterHighValue() {{
      clearFilterBtns();
      if (activeFilter === 'hv') {{ resetFilters(); return; }}
      activeFilter = 'hv';
      document.getElementById('btn-filter-hv').classList.add('active');

      const maxW = Math.max(...allEdgesData.map(e => e._weight));
      const threshold = maxW * 0.3;
      const hvEdges = allEdgesData.filter(e => e._weight >= threshold);
      const hvNodeIds = new Set();
      hvEdges.forEach(e => {{ hvNodeIds.add(e.from); hvNodeIds.add(e.to); }});

      // Dim low-value edges
      edges.update(allEdgesData.map(e => ({{
        ...e,
        color: e._weight >= threshold
          ? {{ color: '#6366f1', highlight: '#4f46e5' }}
          : {{ color: '#e2e8f0', highlight: '#cbd5e1' }},
        width: e._weight >= threshold ? Math.max(2, e.value) : 0.5,
      }})));

      nodes.update(allNodesData.map(n => ({{ ...n, hidden: !hvNodeIds.has(n.id) }})));
    }}

    function highlightCycles() {{
      clearFilterBtns();
      if (activeFilter === 'cycles') {{ resetFilters(); return; }}
      activeFilter = 'cycles';
      document.getElementById('btn-filter-cycles').classList.add('active');

      const cycleIds = new Set(allNodesData.filter(n => n._cycle).map(n => n.id));
      nodes.update(allNodesData.map(n => ({{
        ...n,
        hidden: false,
        opacity: cycleIds.has(n.id) ? 1.0 : 0.15,
        borderWidth: cycleIds.has(n.id) ? 4 : 1,
      }})));
      edges.update(allEdgesData.map(e => ({{
        ...e,
        color: (cycleIds.has(e.from) && cycleIds.has(e.to))
          ? {{ color: '#f97316', highlight: '#ea580c' }}
          : {{ color: '#f1f5f9', highlight: '#e2e8f0' }},
      }})));
    }}

    function resetFilters() {{
      clearFilterBtns();
      activeFilter = null;
      nodes.update(allNodesData.map(n => ({{ ...n, hidden: false, opacity: 1.0, borderWidth: n._cycle ? 3 : 1 }})));
      edges.update(allEdgesData.map(e => ({{ ...e, color: {{ color: '#cbd5e1', highlight: '#6366f1' }}, width: undefined }})));
      network.fit({{ animation: true }});
    }}

    // Helper: escape HTML to prevent injection
    function esc(s) {{
      const d = document.createElement('div');
      d.textContent = String(s);
      return d.innerHTML;
    }}

    // Node click: show detail panel
    network.on("click", (params) => {{
      const panel = document.getElementById("node-detail");
      const content = document.getElementById("node-detail-content");
      if (!params.nodes.length) {{ panel.classList.add("hidden"); return; }}

      const nid = params.nodes[0];
      const node = allNodesData.find(n => n.id === nid);
      if (!node) return;

      const scoreInfo = scoresData[nid] || {{}};
      const decisionInfo = decisionsData[nid] || {{}};
      const metricInfo = metricsData[nid] || {{}};

      let html = `<p class="font-semibold text-sm text-slate-800">${{esc(node.label)}}</p>`;
      html += `<p class="text-slate-500">ID: ${{esc(nid)}}</p>`;

      if (node._score !== null && node._score !== undefined) {{
        const riskColor = node._risk === 'Risky' ? 'text-red-600' : node._risk === 'Watch' ? 'text-amber-600' : 'text-emerald-600';
        html += `<p>Score: <b class="${{riskColor}}">${{node._score}}</b> / 100</p>`;
        html += `<p>Risk: <span class="${{riskColor}} font-medium">${{esc(node._risk)}}</span></p>`;
      }}

      if (node._trend) {{
        const trendIcon = node._trend === 'improving' ? '&#x2191;' : node._trend === 'deteriorating' ? '&#x2193;' : '&#x2192;';
        const trendColor = node._trend === 'improving' ? 'text-emerald-600' : node._trend === 'deteriorating' ? 'text-red-600' : 'text-slate-600';
        html += `<p>Trend: <span class="${{trendColor}} font-medium">${{trendIcon}} ${{esc(node._trend)}}</span></p>`;
      }}

      if (node._decision) {{
        const decColor = node._decision === 'approve' ? 'bg-emerald-100 text-emerald-700' : node._decision === 'reject' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700';
        html += `<p>Decision: <span class="px-1.5 py-0.5 rounded ${{decColor}} text-xs font-medium">${{esc(node._decision.toUpperCase())}}</span></p>`;
      }}

      if (node._exposure) {{
        html += `<p>Exposure: <span class="font-medium">${{esc(node._exposure)}}</span></p>`;
      }}

      html += `<p>Volume: ${{Number(node._volume || 0).toLocaleString()}} RON</p>`;

      if (node._cycle) {{
        html += `<p class="text-orange-600 font-semibold mt-1">FRAUD RING MEMBER</p>`;
      }}

      // Show explanations
      if (scoreInfo.explanation && scoreInfo.explanation.length) {{
        html += `<div class="mt-2 pt-2 border-t border-indigo-200"><p class="font-semibold text-xs text-indigo-700 mb-1">Risk Factors:</p>`;
        scoreInfo.explanation.forEach(r => {{
          html += `<p class="text-xs text-slate-600 pl-2">- ${{esc(r)}}</p>`;
        }});
        html += `</div>`;
      }}

      // Show top partners (connected edges)
      const connected = allEdgesData
        .filter(e => e.from === nid || e.to === nid)
        .map(e => ({{ partner: e.from === nid ? e.to : e.from, volume: e._weight }}))
        .sort((a, b) => b.volume - a.volume)
        .slice(0, 5);

      if (connected.length) {{
        html += `<div class="mt-2 pt-2 border-t border-indigo-200"><p class="font-semibold text-xs text-indigo-700 mb-1">Top Partners:</p>`;
        connected.forEach(p => {{
          const pNode = allNodesData.find(n => n.id === p.partner);
          const pLabel = pNode ? pNode.label : p.partner;
          html += `<p class="text-xs text-slate-600 pl-2">${{esc(pLabel)}}: ${{Number(p.volume).toLocaleString()}} RON</p>`;
        }});
        html += `</div>`;
      }}

      content.innerHTML = html;
      panel.classList.remove("hidden");
      panel.scrollIntoView({{ behavior: "smooth", block: "nearest" }});
    }});
  </script>
</body>
</html>"""


def visualize(
    graph_path=GRAPH_JSON,
    scores_path=SCORES_JSON,
    decisions_path=DECISIONS_JSON,
    metrics_path=MONTHLY_METRICS_JSON,
    output_html=OUTPUT_HTML,
):
    """Load data and produce an enhanced vis-network visualization."""
    with open(graph_path, encoding="utf-8") as fh:
        graph = json.load(fh)

    # Load auxiliary data for enriched display
    scores_map = {}
    if os.path.exists(scores_path):
        with open(scores_path, encoding="utf-8") as fh:
            for s in json.load(fh):
                scores_map[s["company_id"]] = s

    decisions_map = {}
    if os.path.exists(decisions_path):
        with open(decisions_path, encoding="utf-8") as fh:
            for d in json.load(fh):
                decisions_map[d["company_id"]] = d

    metrics_map = {}
    if os.path.exists(metrics_path):
        with open(metrics_path, encoding="utf-8") as fh:
            for m in json.load(fh):
                metrics_map[m["company_id"]] = m

    os.makedirs(os.path.dirname(output_html), exist_ok=True)
    html = _build_html(graph, scores_map, decisions_map, metrics_map)
    with open(output_html, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"[visualize] Interactive graph saved -> {output_html}")


if __name__ == "__main__":
    visualize()
