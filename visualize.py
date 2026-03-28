"""
visualize.py - Multi-page SPA dashboard for SAF-T risk analysis.

Generates a single standalone HTML file embedding all analysis data as an
interactive Single-Page Application with four views: Dashboard, Company
List / Detail, and Network Graph.

Uses Tailwind CSS (CDN) for styling and vis-network (CDN) for the graph.

Output: data/outputs/index.html
"""

import html as html_mod
import json
import os

_BASE = os.path.dirname(__file__)
_JSON = os.path.join(_BASE, "data", "json")

GRAPH_JSON = os.path.join(_JSON, "graph.json")
SCORES_JSON = os.path.join(_JSON, "scores.json")
PORTFOLIO_JSON = os.path.join(_JSON, "portfolio.json")
DECISIONS_JSON = os.path.join(_JSON, "decisions.json")
MONTHLY_JSON = os.path.join(_JSON, "monthly_metrics.json")
CASHFLOW_JSON = os.path.join(_JSON, "cash_flow.json")
COMPANIES_JSON = os.path.join(_JSON, "companies.json")

OUTPUT_HTML = os.path.join(_BASE, "data", "outputs", "index.html")


def _load(path: str, default=None):
    """Load a JSON file, returning *default* on missing file."""
    if not os.path.isfile(path):
        return default if default is not None else {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _build_html(
    graph: dict,
    scores: list,
    portfolio: dict,
    decisions: list,
    monthly: dict,
    cash_flow: dict,
    companies: list,
) -> str:
    """Build a complete standalone SPA HTML string."""

    # Embed data safely as JS literals
    def _js(obj):
        return json.dumps(obj, ensure_ascii=False, default=str)

    data_block = (
        f"const DATA_GRAPH={_js(graph)};\n"
        f"const DATA_SCORES={_js(scores)};\n"
        f"const DATA_PORTFOLIO={_js(portfolio)};\n"
        f"const DATA_DECISIONS={_js(decisions)};\n"
        f"const DATA_MONTHLY={_js(monthly)};\n"
        f"const DATA_CASHFLOW={_js(cash_flow)};\n"
        f"const DATA_COMPANIES={_js(companies)};\n"
    )

    # Use str.replace for template markers instead of f-string for the
    # giant HTML blob — avoids having to double every JS brace.
    html = _HTML_TEMPLATE.replace("/* __DATA_BLOCK__ */", data_block)
    return html


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------
# We store the template as a plain string constant so that JavaScript's
# curly braces do not need escaping.  The single token /* __DATA_BLOCK__ */
# is replaced at build time with the embedded JSON variables.
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>SAF-T Risk Analyzer — Dashboard</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
*{font-family:'Inter',system-ui,-apple-system,sans-serif;margin:0;padding:0;box-sizing:border-box}
body{background:#f1f5f9;color:#1e293b}
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:#f1f5f9}
::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:3px}
.page{display:none}.page.active{display:block}
.nav-tab{cursor:pointer;padding:0.5rem 1.25rem;font-size:0.875rem;font-weight:500;border-bottom:2px solid transparent;transition:all 0.15s}
.nav-tab:hover{color:#6366f1;border-color:#c7d2fe}
.nav-tab.active{color:#4f46e5;border-color:#4f46e5;font-weight:600}
.kpi-card{background:#fff;border-radius:0.75rem;padding:1.25rem 1.5rem;border:1px solid #e2e8f0;transition:box-shadow 0.15s}
.kpi-card:hover{box-shadow:0 4px 12px rgba(0,0,0,0.06)}
.badge{display:inline-flex;align-items:center;padding:0.125rem 0.625rem;border-radius:9999px;font-size:0.75rem;font-weight:600}
.badge-healthy{background:#d1fae5;color:#065f46}
.badge-watch{background:#fef3c7;color:#92400e}
.badge-risky{background:#fee2e2;color:#991b1b}
.badge-approve{background:#d1fae5;color:#065f46}
.badge-review{background:#fef3c7;color:#92400e}
.badge-reject{background:#fee2e2;color:#991b1b}
.bar-segment{height:20px;display:inline-block;transition:width 0.4s ease}
table.data-table{width:100%;border-collapse:separate;border-spacing:0}
table.data-table thead th{position:sticky;top:0;background:#f8fafc;padding:0.625rem 0.75rem;text-align:left;font-size:0.75rem;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:#64748b;border-bottom:2px solid #e2e8f0;cursor:pointer;user-select:none}
table.data-table thead th:hover{color:#4f46e5}
table.data-table tbody tr{cursor:pointer;transition:background 0.1s}
table.data-table tbody tr:hover{background:#eef2ff}
table.data-table tbody td{padding:0.625rem 0.75rem;font-size:0.8125rem;border-bottom:1px solid #f1f5f9}
.sort-arrow{margin-left:4px;opacity:0.4;font-size:10px}
th.sorted .sort-arrow{opacity:1;color:#4f46e5}
#vis-network{width:100%;height:100%;background:#f8fafc}
.vis-tooltip{background:#1e293b!important;border:1px solid #334155!important;border-radius:8px!important;color:#f1f5f9!important;padding:0!important;font-family:'Inter',sans-serif!important;box-shadow:0 10px 25px rgba(0,0,0,0.3)!important;max-width:260px}
.gauge-ring{transition:stroke-dashoffset 0.6s ease}
.trend-up{color:#10b981}.trend-down{color:#ef4444}.trend-flat{color:#64748b}
.alert-danger{background:#fef2f2;border-left:4px solid #ef4444;color:#991b1b}
.alert-warning{background:#fffbeb;border-left:4px solid #f59e0b;color:#92400e}
.alert-info{background:#eff6ff;border-left:4px solid #3b82f6;color:#1e40af}
.fade-in{animation:fadeIn 0.2s ease}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
</style>
</head>
<body>

<!-- ═══════════════════  TOP NAV  ═══════════════════ -->
<nav class="bg-white border-b border-slate-200 shadow-sm sticky top-0 z-50">
  <div class="max-w-[1440px] mx-auto px-4 flex items-center justify-between h-14">
    <div class="flex items-center gap-3">
      <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-600 to-indigo-800 flex items-center justify-center">
        <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
        </svg>
      </div>
      <div>
        <span class="font-bold text-sm text-slate-800">SAF-T Risk Analyzer</span>
        <span class="text-xs text-slate-400 ml-2">ANAF Compliance Suite</span>
      </div>
    </div>
    <div class="flex items-center gap-0" id="nav-tabs">
      <div class="nav-tab active" data-page="dashboard">
        <span class="mr-1">📊</span> Dashboard
      </div>
      <div class="nav-tab" data-page="companies">
        <span class="mr-1">🏢</span> Companies
      </div>
      <div class="nav-tab" data-page="network">
        <span class="mr-1">🔗</span> Network
      </div>
    </div>
    <div class="text-xs text-slate-400">v2.0</div>
  </div>
</nav>

<div class="max-w-[1440px] mx-auto px-4 py-5">

<!-- ═══════════════════  PAGE: DASHBOARD  ═══════════════════ -->
<div id="page-dashboard" class="page active fade-in">

  <!-- KPI Row -->
  <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6" id="kpi-row"></div>

  <!-- Distribution Bars -->
  <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
    <div class="bg-white rounded-xl p-5 border border-slate-200">
      <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Risk Distribution</h3>
      <div id="risk-bar" class="rounded-full overflow-hidden flex h-5 mb-3"></div>
      <div id="risk-legend" class="flex gap-4 text-xs text-slate-600"></div>
    </div>
    <div class="bg-white rounded-xl p-5 border border-slate-200">
      <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Decision Distribution</h3>
      <div id="decision-bar" class="rounded-full overflow-hidden flex h-5 mb-3"></div>
      <div id="decision-legend" class="flex gap-4 text-xs text-slate-600"></div>
    </div>
    <div class="bg-white rounded-xl p-5 border border-slate-200">
      <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Trend Distribution</h3>
      <div id="trend-bar" class="rounded-full overflow-hidden flex h-5 mb-3"></div>
      <div id="trend-legend" class="flex gap-4 text-xs text-slate-600"></div>
    </div>
  </div>

  <!-- Alerts + Top Risky -->
  <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
    <div class="bg-white rounded-xl p-5 border border-slate-200">
      <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">⚡ Alerts</h3>
      <div id="alerts-list" class="space-y-2"></div>
    </div>
    <div class="bg-white rounded-xl p-5 border border-slate-200">
      <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">🔴 Top 10 Risky Companies</h3>
      <div id="top-risky" class="space-y-1.5"></div>
    </div>
  </div>
</div>

<!-- ═══════════════════  PAGE: COMPANIES (LIST + DETAIL)  ═══════════════════ -->
<div id="page-companies" class="page fade-in">

  <!-- LIST VIEW -->
  <div id="company-list-view">
    <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
      <h2 class="text-lg font-bold text-slate-800">Company Directory</h2>
      <div class="flex items-center gap-2">
        <input id="company-search" type="text" placeholder="Search name or ID…"
          class="text-sm border border-slate-300 rounded-lg px-3 py-1.5 w-56 focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400"/>
        <select id="risk-filter" class="text-sm border border-slate-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-300">
          <option value="">All Risks</option>
          <option value="Healthy">Healthy</option>
          <option value="Watch">Watch</option>
          <option value="Risky">Risky</option>
        </select>
      </div>
    </div>
    <div class="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div class="overflow-x-auto max-h-[calc(100vh-220px)] overflow-y-auto">
        <table class="data-table" id="companies-table">
          <thead>
            <tr>
              <th data-key="name">Name <span class="sort-arrow">▲</span></th>
              <th data-key="company_id">ID <span class="sort-arrow">▲</span></th>
              <th data-key="score">Score <span class="sort-arrow">▲</span></th>
              <th data-key="risk_level">Risk <span class="sort-arrow">▲</span></th>
              <th data-key="trend">Trend <span class="sort-arrow">▲</span></th>
              <th data-key="decision">Decision <span class="sort-arrow">▲</span></th>
              <th data-key="recommended_credit_limit">Credit Limit <span class="sort-arrow">▲</span></th>
            </tr>
          </thead>
          <tbody id="companies-tbody"></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- DETAIL VIEW -->
  <div id="company-detail-view" class="hidden fade-in">
    <button id="back-to-list" class="mb-4 text-sm text-indigo-600 hover:text-indigo-800 font-medium flex items-center gap-1">
      ← Back to Companies
    </button>
    <div id="company-detail-content"></div>
  </div>
</div>

<!-- ═══════════════════  PAGE: NETWORK  ═══════════════════ -->
<div id="page-network" class="page fade-in">
  <div class="flex gap-4" style="height:calc(100vh - 130px)">
    <!-- Graph -->
    <div class="flex-1 bg-white rounded-xl border border-slate-200 overflow-hidden relative">
      <!-- Toolbar -->
      <div class="absolute top-3 left-3 z-10 flex flex-wrap gap-2">
        <button onclick="netFit()" class="bg-white/90 backdrop-blur shadow text-xs text-slate-600 px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-indigo-50 hover:border-indigo-300 hover:text-indigo-700 transition-colors">⊕ Fit</button>
        <button id="physics-btn" onclick="netTogglePhysics()" class="bg-white/90 backdrop-blur shadow text-xs text-slate-600 px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-indigo-50 hover:border-indigo-300 hover:text-indigo-700 transition-colors">⚙ Physics: ON</button>
        <label class="flex items-center gap-1.5 bg-white/90 backdrop-blur shadow text-xs text-slate-600 px-3 py-1.5 rounded-lg border border-slate-200">
          <input type="checkbox" id="filter-risky" class="accent-indigo-600"/> Risky only
        </label>
        <label class="flex items-center gap-1.5 bg-white/90 backdrop-blur shadow text-xs text-slate-600 px-3 py-1.5 rounded-lg border border-slate-200">
          <input type="checkbox" id="filter-high-value" class="accent-indigo-600"/> High-value edges
        </label>
        <label class="flex items-center gap-1.5 bg-white/90 backdrop-blur shadow text-xs text-slate-600 px-3 py-1.5 rounded-lg border border-slate-200">
          <input type="checkbox" id="filter-cycles" class="accent-indigo-600"/> Highlight cycles
        </label>
      </div>
      <div id="vis-network" class="w-full h-full"></div>
    </div>
    <!-- Side panel -->
    <aside id="net-side-panel" class="w-80 bg-white rounded-xl border border-slate-200 overflow-y-auto p-4 hidden flex-shrink-0">
      <div id="net-panel-content"></div>
    </aside>
  </div>
  <!-- Legend bar -->
  <div class="mt-3 flex flex-wrap items-center gap-4 text-xs text-slate-500">
    <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-emerald-500 inline-block"></span> Healthy</span>
    <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-amber-500 inline-block"></span> Watch</span>
    <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-red-500 inline-block"></span> Risky</span>
    <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-orange-500 inline-block"></span> Fraud Ring</span>
    <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-slate-400 inline-block"></span> Partner</span>
    <span class="text-slate-300">|</span>
    <span>● Company &nbsp; ◆ Partner &nbsp; Edge thickness = transaction value</span>
  </div>
</div>

</div><!-- end container -->

<!-- ═══════════════════  JAVASCRIPT  ═══════════════════ -->
<script>
/* __DATA_BLOCK__ */

// ── Helpers ─────────────────────────────────────────────────────────────
function esc(s){
  if(s==null) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function fmt(n){
  if(n==null) return '—';
  return Number(n).toLocaleString('en',{maximumFractionDigits:0});
}
function fmtScore(n){
  if(n==null) return '—';
  return Number(n).toFixed(1);
}
function pct(part,total){return total?((part/total)*100).toFixed(1):0;}

function badgeClass(level){
  const m={'Healthy':'badge-healthy','Watch':'badge-watch','Risky':'badge-risky','approve':'badge-approve','review':'badge-review','reject':'badge-reject'};
  return m[level]||'';
}
function trendIcon(t){
  if(!t) return '';
  if(t==='improving') return '<span class="trend-up font-bold">▲</span>';
  if(t==='deteriorating') return '<span class="trend-down font-bold">▼</span>';
  return '<span class="trend-flat font-bold">●</span>';
}

// Build lookup maps
const companyMap={};
DATA_COMPANIES.forEach(c=>{companyMap[c.company_id]=c;});
const scoreMap={};
DATA_SCORES.forEach(s=>{scoreMap[s.company_id]=s;});
const decisionMap={};
DATA_DECISIONS.forEach(d=>{decisionMap[d.company_id]=d;});

// Merged company rows for the table
const companyRows = DATA_COMPANIES.map(c=>{
  const s = scoreMap[c.company_id]||{};
  const d = decisionMap[c.company_id]||{};
  return {
    company_id: c.company_id,
    name: c.name,
    tax_id: c.tax_id,
    score: s.score!=null?s.score:null,
    risk_level: s.risk_level||'—',
    trend: s.trend||d.trend||'',
    explanation: s.explanation||[],
    decision: d.decision||'—',
    recommended_credit_limit: d.recommended_credit_limit!=null?d.recommended_credit_limit:null,
    decision_explanation: d.explanation||[]
  };
});

// ── Navigation ──────────────────────────────────────────────────────────
let currentPage = 'dashboard';
let networkInitialised = false;

document.getElementById('nav-tabs').addEventListener('click', e=>{
  const tab = e.target.closest('.nav-tab');
  if(!tab) return;
  navigateTo(tab.dataset.page);
});

function navigateTo(page){
  currentPage = page;
  document.querySelectorAll('.nav-tab').forEach(t=>t.classList.toggle('active',t.dataset.page===page));
  document.querySelectorAll('.page').forEach(p=>p.classList.toggle('active',p.id==='page-'+page));
  if(page==='network' && !networkInitialised) initNetwork();
  if(page==='companies'){
    document.getElementById('company-list-view').classList.remove('hidden');
    document.getElementById('company-detail-view').classList.add('hidden');
  }
}

// ══════════════════════════════════════════════════════════════════════════
//  DASHBOARD
// ══════════════════════════════════════════════════════════════════════════
(function renderDashboard(){
  const p = DATA_PORTFOLIO;
  const kpis = [
    {label:'Companies',value:p.total_companies||DATA_COMPANIES.length,color:'indigo'},
    {label:'Avg Score',value:fmtScore(p.average_score),color:'slate'},
    {label:'Portfolio Revenue',value:fmt(p.total_portfolio_revenue),color:'emerald'},
    {label:'Cycles Detected',value:p.cycles_detected||0,color:(p.cycles_detected?'orange':'slate')},
  ];
  const kpiRow = document.getElementById('kpi-row');
  kpiRow.innerHTML = kpis.map(k=>`
    <div class="kpi-card">
      <p class="text-xs font-semibold text-slate-500 uppercase tracking-wide">${esc(k.label)}</p>
      <p class="text-2xl font-extrabold text-${k.color}-600 mt-1">${esc(String(k.value))}</p>
    </div>`).join('');

  // Distribution bars helper
  function distBar(containerId, legendId, dist, palette){
    const bar = document.getElementById(containerId);
    const legend = document.getElementById(legendId);
    const total = Object.values(dist||{}).reduce((a,b)=>a+b,0)||1;
    let barH='', legH='';
    for(const [key,count] of Object.entries(dist||{})){
      const w = (count/total*100).toFixed(1);
      const col = palette[key]||'#94a3b8';
      barH+=`<div class="bar-segment" style="width:${w}%;background:${col}" title="${esc(key)}: ${count}"></div>`;
      legH+=`<span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-full inline-block" style="background:${col}"></span>${esc(key)} (${count})</span>`;
    }
    bar.innerHTML=barH; legend.innerHTML=legH;
  }

  distBar('risk-bar','risk-legend', p.risk_distribution, {Healthy:'#10b981',Watch:'#f59e0b',Risky:'#ef4444'});
  distBar('decision-bar','decision-legend', p.decision_distribution, {approve:'#10b981',review:'#f59e0b',reject:'#ef4444'});
  distBar('trend-bar','trend-legend', p.trend_distribution, {improving:'#10b981',stable:'#64748b',deteriorating:'#ef4444'});

  // Alerts
  const alertList = document.getElementById('alerts-list');
  const alerts = p.alerts||[];
  if(alerts.length){
    alertList.innerHTML = alerts.map(a=>`
      <div class="alert-${a.type||'info'} rounded-lg px-4 py-2.5 text-sm">${esc(a.message)}</div>
    `).join('');
  } else {
    alertList.innerHTML='<p class="text-sm text-slate-400">No alerts.</p>';
  }

  // Top 10 risky
  const topRisky = document.getElementById('top-risky');
  const risky = p.top_10_risky||[];
  if(risky.length){
    topRisky.innerHTML = risky.map((r,i)=>{
      const name = companyMap[r.company_id]?esc(companyMap[r.company_id].name):esc(r.company_id);
      return `<div class="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-red-50 cursor-pointer" data-company="${esc(r.company_id)}">
        <div class="flex items-center gap-2">
          <span class="text-xs font-bold text-slate-400 w-5">${i+1}</span>
          <span class="text-sm font-medium text-slate-700">${name}</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-sm font-bold text-red-600">${fmtScore(r.score)}</span>
          <span class="badge ${badgeClass(r.risk_level)}">${esc(r.risk_level)}</span>
        </div>
      </div>`;
    }).join('');
  } else {
    topRisky.innerHTML='<p class="text-sm text-slate-400">No risky companies.</p>';
  }

  // Event delegation for top-risky clicks
  topRisky.addEventListener('click',e=>{
    const el = e.target.closest('[data-company]');
    if(el) showCompanyDetail(el.dataset.company);
  });
})();

// ══════════════════════════════════════════════════════════════════════════
//  COMPANIES LIST
// ══════════════════════════════════════════════════════════════════════════
let sortKey='score', sortDir='asc';

function renderCompanyTable(){
  let rows = [...companyRows];
  // Filter
  const q = (document.getElementById('company-search').value||'').toLowerCase();
  const rf = document.getElementById('risk-filter').value;
  if(q) rows=rows.filter(r=>(r.name||'').toLowerCase().includes(q)||(r.company_id||'').toLowerCase().includes(q));
  if(rf) rows=rows.filter(r=>r.risk_level===rf);
  // Sort
  rows.sort((a,b)=>{
    let va=a[sortKey], vb=b[sortKey];
    if(typeof va==='string') va=(va||'').toLowerCase();
    if(typeof vb==='string') vb=(vb||'').toLowerCase();
    if(va==null) va = sortDir==='asc'?Infinity:-Infinity;
    if(vb==null) vb = sortDir==='asc'?Infinity:-Infinity;
    if(va<vb) return sortDir==='asc'?-1:1;
    if(va>vb) return sortDir==='asc'?1:-1;
    return 0;
  });
  const tbody = document.getElementById('companies-tbody');
  tbody.innerHTML = rows.map(r=>`
    <tr data-company="${esc(r.company_id)}">
      <td class="font-medium text-slate-800">${esc(r.name)}</td>
      <td class="font-mono text-xs text-slate-500">${esc(r.company_id)}</td>
      <td><span class="font-bold ${r.score!=null?(r.score>=70?'text-emerald-600':r.score>=40?'text-amber-600':'text-red-600'):'text-slate-400'}">${fmtScore(r.score)}</span></td>
      <td><span class="badge ${badgeClass(r.risk_level)}">${esc(r.risk_level)}</span></td>
      <td>${trendIcon(r.trend)} <span class="text-xs">${esc(r.trend)}</span></td>
      <td><span class="badge ${badgeClass(r.decision)}">${esc(r.decision)}</span></td>
      <td class="text-right font-mono">${r.recommended_credit_limit!=null?fmt(r.recommended_credit_limit):'—'}</td>
    </tr>`).join('');

  // Update sort arrows
  document.querySelectorAll('#companies-table thead th').forEach(th=>{
    th.classList.toggle('sorted', th.dataset.key===sortKey);
    const arrow = th.querySelector('.sort-arrow');
    if(arrow) arrow.textContent = (th.dataset.key===sortKey)?(sortDir==='asc'?'▲':'▼'):'▲';
  });
}

document.querySelectorAll('#companies-table thead th').forEach(th=>{
  th.addEventListener('click',()=>{
    const key = th.dataset.key;
    if(!key) return;
    if(sortKey===key) sortDir = sortDir==='asc'?'desc':'asc';
    else { sortKey=key; sortDir='asc'; }
    renderCompanyTable();
  });
});
// Event delegation for table row clicks
document.getElementById('companies-tbody').addEventListener('click',e=>{
  const tr = e.target.closest('tr[data-company]');
  if(tr) showCompanyDetail(tr.dataset.company);
});
document.getElementById('company-search').addEventListener('input', renderCompanyTable);
document.getElementById('risk-filter').addEventListener('change', renderCompanyTable);
renderCompanyTable();

// ══════════════════════════════════════════════════════════════════════════
//  COMPANY DETAIL
// ══════════════════════════════════════════════════════════════════════════
function showCompanyDetail(companyId){
  navigateTo('companies');
  document.getElementById('company-list-view').classList.add('hidden');
  const detailView = document.getElementById('company-detail-view');
  detailView.classList.remove('hidden');

  const c = companyMap[companyId]||{};
  const s = scoreMap[companyId]||{};
  const d = decisionMap[companyId]||{};
  const m = DATA_MONTHLY[companyId]||{};
  const cf = DATA_CASHFLOW[companyId]||{};
  const gNode = (DATA_GRAPH.nodes||[]).find(n=>n.id===companyId)||{};
  const metrics = DATA_GRAPH.metrics||{};
  const topPartners = (metrics.top_partners||{})[companyId]||[];

  const score = s.score!=null?s.score:0;
  const riskLevel = s.risk_level||'—';
  const trend = s.trend||d.trend||'';
  const explanations = s.explanation||[];
  const decisionExplanations = d.explanation||[];
  const monthly = m.monthly||[];

  // Score gauge SVG
  const gaugeAngle = (score/100)*251.2;  // circumference = 2*PI*40
  const gaugeColor = score>=70?'#10b981':score>=40?'#f59e0b':'#ef4444';

  // Revenue chart
  const maxRev = Math.max(...monthly.map(r=>Math.max(r.revenue||0,r.expenses||0)),1);
  let revenueChart = '';
  if(monthly.length){
    revenueChart = monthly.map(r=>{
      const revH = ((r.revenue||0)/maxRev*100).toFixed(1);
      const expH = ((r.expenses||0)/maxRev*100).toFixed(1);
      return `<div class="flex flex-col items-center gap-1" style="flex:1;min-width:36px">
        <div class="w-full flex gap-0.5 items-end" style="height:80px">
          <div class="flex-1 rounded-t" style="height:${revH}%;background:#6366f1" title="Revenue: ${fmt(r.revenue)}"></div>
          <div class="flex-1 rounded-t" style="height:${expH}%;background:#f59e0b" title="Expenses: ${fmt(r.expenses)}"></div>
        </div>
        <span class="text-[10px] text-slate-400">${esc((r.month||'').slice(5))}</span>
      </div>`;
    }).join('');
  }

  // Cash flow bars
  let cashFlowChart = '';
  const cfMonthly = cf.monthly||[];
  if(cfMonthly.length){
    const maxCf = Math.max(...cfMonthly.map(r=>Math.max(Math.abs(r.inflow||0),Math.abs(r.outflow||0))),1);
    cashFlowChart = cfMonthly.map(r=>{
      const inH = ((r.inflow||0)/maxCf*100).toFixed(1);
      const outH = ((r.outflow||0)/maxCf*100).toFixed(1);
      return `<div class="flex flex-col items-center gap-1" style="flex:1;min-width:36px">
        <div class="w-full flex gap-0.5 items-end" style="height:60px">
          <div class="flex-1 rounded-t" style="height:${inH}%;background:#10b981" title="Inflow: ${fmt(r.inflow)}"></div>
          <div class="flex-1 rounded-t" style="height:${outH}%;background:#ef4444" title="Outflow: ${fmt(r.outflow)}"></div>
        </div>
        <span class="text-[10px] text-slate-400">${esc((r.month||'').slice(5))}</span>
      </div>`;
    }).join('');
  }

  const liqColor = {'stable':'emerald','warning':'amber','critical':'red'}[cf.liquidity_indicator]||'slate';

  document.getElementById('company-detail-content').innerHTML = `
    <!-- Header -->
    <div class="bg-white rounded-xl border border-slate-200 p-6 mb-4">
      <div class="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <h2 class="text-xl font-bold text-slate-800">${esc(c.name||companyId)}</h2>
          <p class="text-sm text-slate-500 font-mono">${esc(companyId)} · Tax ID: ${esc(c.tax_id||'—')}</p>
        </div>
        <div class="flex items-center gap-4">
          <!-- Gauge -->
          <div class="relative" style="width:80px;height:80px">
            <svg viewBox="0 0 100 100" class="w-full h-full -rotate-90">
              <circle cx="50" cy="50" r="40" fill="none" stroke="#e2e8f0" stroke-width="8"/>
              <circle cx="50" cy="50" r="40" fill="none" stroke="${gaugeColor}" stroke-width="8"
                stroke-dasharray="251.2" stroke-dashoffset="${251.2-gaugeAngle}" stroke-linecap="round" class="gauge-ring"/>
            </svg>
            <div class="absolute inset-0 flex items-center justify-center">
              <span class="text-lg font-extrabold" style="color:${gaugeColor}">${fmtScore(score)}</span>
            </div>
          </div>
          <div class="flex flex-col gap-1">
            <span class="badge ${badgeClass(riskLevel)} text-sm px-3 py-1">${esc(riskLevel)}</span>
            <span class="text-sm">${trendIcon(trend)} ${esc(trend)}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
      <!-- Explanations -->
      <div class="bg-white rounded-xl border border-slate-200 p-5">
        <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Risk Factors</h3>
        ${explanations.length?
          '<ul class="space-y-1.5">'+explanations.map(e=>'<li class="text-sm text-slate-700 flex items-start gap-2"><span class="text-red-400 mt-0.5">•</span><span>'+esc(e)+'</span></li>').join('')+'</ul>'
          :'<p class="text-sm text-slate-400">No penalties detected.</p>'}
      </div>
      <!-- Decision -->
      <div class="bg-white rounded-xl border border-slate-200 p-5">
        <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Credit Decision</h3>
        <div class="flex items-center gap-3 mb-3">
          <span class="badge ${badgeClass(d.decision||'')} text-sm px-3 py-1">${esc(d.decision||'—')}</span>
          <span class="text-slate-500 text-sm">Limit:</span>
          <span class="font-bold text-slate-800">${d.recommended_credit_limit!=null?fmt(d.recommended_credit_limit)+' RON':'—'}</span>
        </div>
        ${decisionExplanations.length?
          '<ul class="space-y-1">'+decisionExplanations.map(e=>'<li class="text-sm text-slate-600">'+esc(e)+'</li>').join('')+'</ul>'
          :''}
      </div>
    </div>

    <!-- Revenue Chart -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
      <div class="bg-white rounded-xl border border-slate-200 p-5">
        <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Monthly Revenue vs Expenses</h3>
        <div class="flex items-center gap-4 mb-3 text-xs text-slate-500">
          <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded bg-indigo-500 inline-block"></span> Revenue</span>
          <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded bg-amber-500 inline-block"></span> Expenses</span>
        </div>
        ${revenueChart?
          '<div class="flex gap-1 items-end">'+revenueChart+'</div>'
          :'<p class="text-sm text-slate-400">No monthly data.</p>'}
        <div class="mt-3 grid grid-cols-3 gap-3 text-center">
          <div><p class="text-xs text-slate-500">Total Revenue</p><p class="font-bold text-indigo-600">${fmt(m.total_revenue)}</p></div>
          <div><p class="text-xs text-slate-500">Total Expenses</p><p class="font-bold text-amber-600">${fmt(m.total_expenses)}</p></div>
          <div><p class="text-xs text-slate-500">Trend</p><p class="font-medium">${trendIcon(m.revenue_trend||m.trend)} ${esc(m.revenue_trend||m.trend||'—')}</p></div>
        </div>
      </div>

      <!-- Cash Flow Chart -->
      <div class="bg-white rounded-xl border border-slate-200 p-5">
        <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Cash Flow (Inflow vs Outflow)</h3>
        <div class="flex items-center gap-4 mb-3 text-xs text-slate-500">
          <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded bg-emerald-500 inline-block"></span> Inflow</span>
          <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded bg-red-500 inline-block"></span> Outflow</span>
        </div>
        ${cashFlowChart?
          '<div class="flex gap-1 items-end">'+cashFlowChart+'</div>'
          :'<p class="text-sm text-slate-400">No cash flow data.</p>'}
        <div class="mt-3 grid grid-cols-3 gap-3 text-center">
          <div><p class="text-xs text-slate-500">Total Inflow</p><p class="font-bold text-emerald-600">${fmt(cf.total_inflow)}</p></div>
          <div><p class="text-xs text-slate-500">Total Outflow</p><p class="font-bold text-red-600">${fmt(cf.total_outflow)}</p></div>
          <div><p class="text-xs text-slate-500">Liquidity</p><p class="font-bold text-${liqColor}-600">${esc(cf.liquidity_indicator||'—')}</p></div>
        </div>
      </div>
    </div>

    <!-- Top Partners -->
    <div class="bg-white rounded-xl border border-slate-200 p-5">
      <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Top Trading Partners</h3>
      ${topPartners.length?`
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          ${topPartners.map((tp,i)=>{
            const pNode = (DATA_GRAPH.nodes||[]).find(n=>n.id===tp.partner_id);
            const pName = pNode?pNode.label:tp.partner_id;
            return '<div class="flex items-center justify-between bg-slate-50 rounded-lg px-3 py-2 border border-slate-100"><div class="flex items-center gap-2"><span class="text-xs font-bold text-slate-400">'+(i+1)+'</span><span class="text-sm text-slate-700">'+esc(pName)+'</span></div><span class="text-sm font-mono font-bold text-slate-600">'+fmt(tp.amount)+'</span></div>';
          }).join('')}
        </div>`
        :'<p class="text-sm text-slate-400">No partner data available.</p>'}
    </div>
  `;
}

document.getElementById('back-to-list').addEventListener('click',()=>{
  document.getElementById('company-detail-view').classList.add('hidden');
  document.getElementById('company-list-view').classList.remove('hidden');
});

// ══════════════════════════════════════════════════════════════════════════
//  NETWORK GRAPH
// ══════════════════════════════════════════════════════════════════════════
let visNetwork = null;
let visNodes = null;
let visEdges = null;
let allVisNodes = [];
let allVisEdges = [];
let physicsOn = true;

function nodeColor(riskLevel, inCycle){
  if(inCycle) return {background:'#f97316',border:'#ea580c',highlight:{background:'#fb923c',border:'#f97316'}};
  const pal = {
    Healthy:{background:'#10b981',border:'#059669',highlight:{background:'#34d399',border:'#10b981'}},
    Watch:{background:'#f59e0b',border:'#d97706',highlight:{background:'#fbbf24',border:'#f59e0b'}},
    Risky:{background:'#ef4444',border:'#dc2626',highlight:{background:'#f87171',border:'#ef4444'}},
  };
  return pal[riskLevel]||{background:'#94a3b8',border:'#64748b',highlight:{background:'#cbd5e1',border:'#94a3b8'}};
}

function buildVisData(){
  const nodes = DATA_GRAPH.nodes||[];
  const edges = DATA_GRAPH.edges||[];
  const maxW = Math.max(...edges.map(e=>e.weight),1);
  const cycleIds = new Set((DATA_GRAPH.metrics||{}).cycle_node_ids||[]);

  allVisNodes = nodes.map(n=>{
    const col = nodeColor(n.risk_level, n.in_cycle);
    const sz = 12 + Math.min(Math.floor((n.volume||0)/400000),38);
    const scoreStr = n.score!=null?'Score: '+n.score:'External partner';
    const riskStr = n.risk_level||'Partner';
    const cycleBadge = n.in_cycle?' ⚠ FRAUD RING':'';
    return {
      id:n.id, label:(n.label||'').substring(0,22), color:col, size:sz,
      borderWidth:n.in_cycle?3:1, font:{color:'#1e293b',size:11},
      shape:n.type==='company'?'dot':'diamond',
      title:`<div style="font-family:Inter,sans-serif;padding:8px"><b style="font-size:13px">${esc(n.label)}</b><br><span style="color:#6b7280">ID: ${esc(n.id)}</span><br>Type: ${esc(n.type||'unknown')}<br>${esc(scoreStr)} | ${esc(riskStr)}${esc(cycleBadge)}<br>Volume: ${fmt(n.volume)} RON<br>Out: ${n.degree_out||0} &nbsp; In: ${n.degree_in||0}</div>`,
      _risk:n.risk_level, _type:n.type, _inCycle:n.in_cycle, _volume:n.volume, _score:n.score
    };
  });

  allVisEdges = edges.map(e=>{
    const w = Math.max(1, Math.round(e.weight/maxW*10));
    return {
      from:e.source, to:e.target, value:w,
      title:'Value: '+fmt(e.weight)+' RON ('+e.count+' txs)',
      arrows:{to:{enabled:true,scaleFactor:0.5}},
      color:{color:'#cbd5e1',highlight:'#6366f1'},
      smooth:{type:'dynamic'},
      _weight:e.weight, _source:e.source, _target:e.target
    };
  });
}

function applyFilters(){
  if(!visNetwork) return;
  const riskyOnly = document.getElementById('filter-risky').checked;
  const highValue = document.getElementById('filter-high-value').checked;
  const showCycles = document.getElementById('filter-cycles').checked;
  const cycleIds = new Set((DATA_GRAPH.metrics||{}).cycle_node_ids||[]);

  let filteredNodes = [...allVisNodes];
  let filteredEdges = [...allVisEdges];

  if(riskyOnly){
    const riskyIds = new Set(filteredNodes.filter(n=>n._risk==='Risky'||n._risk==='Watch'||n._inCycle).map(n=>n.id));
    // Also include nodes connected to risky ones
    filteredEdges.forEach(e=>{
      if(riskyIds.has(e.from)) riskyIds.add(e.to);
      if(riskyIds.has(e.to)) riskyIds.add(e.from);
    });
    filteredNodes = filteredNodes.filter(n=>riskyIds.has(n.id));
    filteredEdges = filteredEdges.filter(e=>riskyIds.has(e.from)&&riskyIds.has(e.to));
  }

  if(highValue){
    const weights = allVisEdges.map(e=>e._weight);
    const threshold = weights.sort((a,b)=>b-a)[Math.floor(weights.length*0.25)]||0;
    const hvEdges = filteredEdges.filter(e=>e._weight>=threshold);
    const hvNodeIds = new Set();
    hvEdges.forEach(e=>{hvNodeIds.add(e.from);hvNodeIds.add(e.to);});
    filteredNodes = filteredNodes.filter(n=>hvNodeIds.has(n.id));
    filteredEdges = hvEdges;
  }

  if(showCycles){
    filteredNodes = filteredNodes.map(n=>{
      if(cycleIds.has(n.id)){
        return {...n, borderWidth:4, color:{background:'#f97316',border:'#ea580c',highlight:{background:'#fb923c',border:'#f97316'}}};
      }
      return n;
    });
    filteredEdges = filteredEdges.map(e=>{
      if(cycleIds.has(e.from)&&cycleIds.has(e.to)){
        return {...e, color:{color:'#f97316',highlight:'#ea580c'}, width:3};
      }
      return e;
    });
  }

  visNodes.clear();
  visEdges.clear();
  visNodes.add(filteredNodes);
  visEdges.add(filteredEdges);
}

function initNetwork(){
  buildVisData();
  visNodes = new vis.DataSet(allVisNodes);
  visEdges = new vis.DataSet(allVisEdges);

  const container = document.getElementById('vis-network');
  const options = {
    physics:{enabled:true,barnesHut:{gravitationalConstant:-12000,centralGravity:0.3,springLength:160,springConstant:0.04,damping:0.09},stabilization:{iterations:200,updateInterval:25}},
    interaction:{hover:true,tooltipDelay:150,hideEdgesOnDrag:true,keyboard:{enabled:true,speed:{x:10,y:10,zoom:0.02}}},
    edges:{smooth:{type:'dynamic'},scaling:{min:1,max:10},selectionWidth:2,hoverWidth:1.5},
    nodes:{scaling:{min:10,max:50},shadow:{enabled:true,color:'rgba(0,0,0,0.10)',size:8,x:2,y:2}},
  };

  visNetwork = new vis.Network(container,{nodes:visNodes,edges:visEdges},options);
  networkInitialised = true;

  visNetwork.once('stabilizationIterationsDone',()=>{
    visNetwork.setOptions({physics:{enabled:false}});
    physicsOn=false;
    document.getElementById('physics-btn').textContent='⚙ Physics: OFF';
  });

  // Click handler
  visNetwork.on('click',(params)=>{
    const panel = document.getElementById('net-side-panel');
    const content = document.getElementById('net-panel-content');
    if(!params.nodes.length){panel.classList.add('hidden');return;}

    const nid = params.nodes[0];
    const gNode = (DATA_GRAPH.nodes||[]).find(n=>n.id===nid);
    if(!gNode){panel.classList.add('hidden');return;}

    panel.classList.remove('hidden');

    const sc = scoreMap[nid];
    const dc = decisionMap[nid];
    const co = companyMap[nid];
    const cf = DATA_CASHFLOW[nid];
    const isCompany = gNode.type==='company';
    const score = sc?sc.score:gNode.score;
    const riskLevel = sc?sc.risk_level:gNode.risk_level;
    const gaugeAngle = score!=null?(score/100*251.2):0;
    const gaugeColor = score>=70?'#10b981':score>=40?'#f59e0b':'#ef4444';

    let html = `<h3 class="font-bold text-base text-slate-800 mb-1">${esc(gNode.label)}</h3>
      <p class="text-xs text-slate-500 font-mono mb-3">${esc(nid)} · ${esc(gNode.type)}</p>`;

    if(isCompany && score!=null){
      html += `<div class="flex items-center gap-3 mb-3">
        <div class="relative" style="width:56px;height:56px">
          <svg viewBox="0 0 100 100" class="w-full h-full -rotate-90">
            <circle cx="50" cy="50" r="40" fill="none" stroke="#e2e8f0" stroke-width="10"/>
            <circle cx="50" cy="50" r="40" fill="none" stroke="${gaugeColor}" stroke-width="10"
              stroke-dasharray="251.2" stroke-dashoffset="${251.2-gaugeAngle}" stroke-linecap="round"/>
          </svg>
          <div class="absolute inset-0 flex items-center justify-center">
            <span class="text-sm font-extrabold" style="color:${gaugeColor}">${fmtScore(score)}</span>
          </div>
        </div>
        <div>
          <span class="badge ${badgeClass(riskLevel)}">${esc(riskLevel||'')}</span>
          ${gNode.in_cycle?'<span class="badge bg-orange-100 text-orange-700 ml-1">⚠ Fraud Ring</span>':''}
        </div>
      </div>`;
    }

    html += `<div class="space-y-1.5 text-xs text-slate-600 mb-3">
      <p>Volume: <b>${fmt(gNode.volume)}</b> RON</p>
      <p>Connections: Out ${gNode.degree_out||0} / In ${gNode.degree_in||0}</p>
      ${cf?'<p>Liquidity: <b class="text-'+({'stable':'emerald','warning':'amber','critical':'red'}[cf.liquidity_indicator]||'slate')+'-600">'+esc(cf.liquidity_indicator||'—')+'</b></p>':''}
      ${dc?'<p>Decision: <span class="badge '+badgeClass(dc.decision)+'">'+esc(dc.decision)+'</span></p>':''}
    </div>`;

    if(isCompany){
      html += `<button data-company="${esc(nid)}" class="net-detail-btn w-full text-center text-xs font-semibold text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 rounded-lg py-2 transition-colors">View Full Detail →</button>`;
    }

    content.innerHTML = html;

    // Bind the detail button via event listener
    const detailBtn = content.querySelector('.net-detail-btn');
    if(detailBtn){
      detailBtn.addEventListener('click',()=>showCompanyDetail(detailBtn.dataset.company));
    }
  });

  // Filter listeners
  document.getElementById('filter-risky').addEventListener('change', applyFilters);
  document.getElementById('filter-high-value').addEventListener('change', applyFilters);
  document.getElementById('filter-cycles').addEventListener('change', applyFilters);
}

function netFit(){if(visNetwork) visNetwork.fit({animation:true});}
function netTogglePhysics(){
  if(!visNetwork) return;
  physicsOn=!physicsOn;
  visNetwork.setOptions({physics:{enabled:physicsOn}});
  document.getElementById('physics-btn').textContent=physicsOn?'⚙ Physics: ON':'⚙ Physics: OFF';
}
</script>
</body>
</html>"""


def visualize(output_html: str = OUTPUT_HTML) -> None:
    """Load all analysis JSON files and produce a multi-page SPA dashboard."""
    graph = _load(GRAPH_JSON, default={"nodes": [], "edges": [], "metrics": {}})
    scores = _load(SCORES_JSON, default=[])
    portfolio = _load(PORTFOLIO_JSON, default={})
    decisions = _load(DECISIONS_JSON, default=[])
    monthly = _load(MONTHLY_JSON, default={})
    cash_flow = _load(CASHFLOW_JSON, default={})
    companies = _load(COMPANIES_JSON, default=[])

    os.makedirs(os.path.dirname(output_html), exist_ok=True)
    html = _build_html(graph, scores, portfolio, decisions, monthly,
                       cash_flow, companies)
    with open(output_html, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"[visualize] SPA dashboard saved → {output_html}")


if __name__ == "__main__":
    visualize()
