"""
Page télémétrie « tail » unifiée : WebSocket multiplexé (car_data + location + stints)
→ graphiques Plotly.js, carte live, bloc pneus, vue Live (jauge + badge).
"""

from __future__ import annotations

import json


def build_telemetry_tail_full_embed(
    ws_url: str,
    drivers_json: str,
    drv_colour: str,
    selected_driver_number: int,
    circuit_path_json: str,
) -> str:
    """drivers_json : liste [{driver_number, name_acronym, team_name, team_colour}, ...]."""
    ws_js = json.dumps(ws_url)
    drivers_js = drivers_json  # déjà JSON valide
    drv_col = json.dumps(drv_colour)
    sel_dn = int(selected_driver_number)
    path_js = circuit_path_json  # "null" ou JSON array de [x,y]

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  body {{ margin:0; padding:10px; background:#0a0a0a; color:#ddd; font-family:system-ui,sans-serif; font-size:13px; }}
  h3 {{ color:#E10600; font-size:15px; margin:16px 0 8px; border-bottom:1px solid #2a2a2a; padding-bottom:4px; }}
  #st {{ color:#888; margin-bottom:8px; min-height:1.2em; }}
  .row {{ display:flex; flex-wrap:wrap; gap:12px; margin:8px 0; }}
  .kv span {{ background:#1a1a1a; padding:8px 12px; border-radius:8px; border-left:3px solid #E10600; }}
  #g1 {{ width:100%; height:200px; }}
  #g2 {{ width:100%; height:160px; }}
  #g3 {{ width:100%; height:140px; }}
  #g4 {{ width:100%; height:200px; }}
  #map {{ width:100%; height:520px; }}
  #liveRow {{ display:flex; flex-wrap:wrap; gap:12px; align-items:stretch; margin-top:8px; }}
  #liveChart {{ flex:3; min-width:280px; height:260px; }}
  #liveGauge {{ flex:1; min-width:200px; height:240px; }}
  #liveTyre {{ flex:1; min-width:160px; text-align:center; padding-top:12px; }}
  #stintSolo {{ background:#141414; border-radius:10px; padding:14px; border:1px solid #333; min-height:80px; }}
  .tyreCircle {{
    width:88px; height:88px; border-radius:50%; display:flex; align-items:center; justify-content:center;
    font-size:34px; font-weight:900; margin:8px auto; border:3px solid rgba(255,255,255,0.2);
  }}
</style></head><body>
<div id="st">Connexion au flux MQTT (car_data + location + stints)…</div>
<h3>📈 Télémétrie — pilote sélectionné</h3>
<div class="row" id="kv"></div>
<div id="g1"></div><div id="g2"></div><div id="g3"></div><div id="g4"></div>
<h3>🗺 Positions sur le circuit (live)</h3>
<div id="map"></div>
<h3>🏎 Stratégie pneumatiques (live MQTT)</h3>
<div id="stintSolo">En attente de messages <code>v1/stints</code>…</div>
<h3>🔴 Vue Live — jauge &amp; dernier composé</h3>
<div id="liveRow">
  <div id="liveChart"></div>
  <div id="liveGauge"></div>
  <div id="liveTyre"></div>
</div>
<script>
const WS_URL = {ws_js};
const DRIVERS = {drivers_js};
const DRV_COLOR = {drv_col};
const SEL_DN = {sel_dn};
const CIRCUIT_PATH = {path_js};

const MAX_P = 450;
let xs = [], sp = [], rp = [], gr = [], th = [], br = [], drs = [];

function setStatus(t, ok) {{
  const el = document.getElementById('st');
  el.textContent = t;
  el.style.color = ok ? '#6c6' : '#e66';
}}

const COMPOUND_COLORS = {{
  SOFT:'#E8002D', MEDIUM:'#FFF200', HARD:'#EBEBEB', INTERMEDIATE:'#39B54A', WET:'#0067FF', UNKNOWN:'#555555'
}};
const COMPOUND_TEXT = {{
  SOFT:'#FFF', MEDIUM:'#000', HARD:'#000', INTERMEDIATE:'#FFF', WET:'#FFF', UNKNOWN:'#CCC'
}};
const COMPOUND_ABBR = {{ SOFT:'S', MEDIUM:'M', HARD:'H', INTERMEDIATE:'I', WET:'W', UNKNOWN:'?' }};

function updateKv(d) {{
  const g = d.n_gear != null ? d.n_gear : '—';
  const drsOk = (d.drs != null && Number(d.drs) >= 8);
  document.getElementById('kv').innerHTML =
    '<span><b>Vitesse</b> ' + (d.speed ?? '—') + ' km/h</span>' +
    '<span><b>RPM</b> ' + (d.rpm ?? '—') + '</span>' +
    '<span><b>R</b> ' + g + '</span>' +
    '<span><b>Gaz</b> ' + (d.throttle ?? '—') + ' %</span>' +
    '<span><b>Frein</b> ' + (d.brake ?? '—') + ' %</span>' +
    '<span><b>DRS</b> ' + (drsOk ? 'ouvert' : 'fermé') + '</span>';
}}

const baseLayout = (title, ytitle, yrange, extra) => ({{
  paper_bgcolor: '#0e0e0e',
  plot_bgcolor: '#121212',
  font: {{ color: '#ccc', size: 11 }},
  margin: {{ l: 52, r: 12, t: 28, b: 28 }},
  showlegend: false,
  title: {{ text: title, font: {{ size: 12, color: '#888' }} }},
  xaxis: {{ showgrid: false, tickfont: {{ color: '#888' }} }},
  yaxis: {{ title: ytitle, range: yrange, gridcolor: '#333' }},
  ...extra
}});

Plotly.newPlot('g1', [
  {{ type:'scatter', mode:'lines', x:[], y:[], name:'V', line:{{ color: DRV_COLOR, width: 2 }}, fill:'tozeroy', fillcolor: 'rgba(200,200,200,0.06)' }},
  {{ type:'scatter', mode:'lines', x:[], y:[], name:'DRS', line:{{ color:'#00FF88', width:2, dash:'dot' }} }},
], baseLayout('Vitesse (km/h)', 'km/h', [0, 380], {{}}), {{ responsive: true, displayModeBar: false }});

Plotly.newPlot('g2', [
  {{ type:'scatter', mode:'lines', x:[], y:[], line:{{ color:'#FF8000', width:1.5 }} }},
], baseLayout('RPM', 'RPM', [0, 20000], {{}}), {{ responsive: true, displayModeBar: false }});

Plotly.newPlot('g3', [
  {{ type:'scatter', mode:'lines', x:[], y:[], line:{{ color:'#CCC', width:2, shape:'hv' }} }},
], baseLayout('Rapport', 'R', [0, 8], {{ yaxis: {{ dtick: 1 }} }}), {{ responsive: true, displayModeBar: false }});

Plotly.newPlot('g4', [
  {{ type:'scatter', mode:'lines', x:[], y:[], name:'Gaz', line:{{ color:'#00CC44', width:1.5 }}, fill:'tozeroy', fillcolor:'rgba(0,204,68,0.12)' }},
  {{ type:'scatter', mode:'lines', x:[], y:[], name:'Frein', line:{{ color:'#E10600', width:1.5 }}, fill:'tozeroy', fillcolor:'rgba(225,6,0,0.12)' }},
], baseLayout('Gaz / Frein (%)', '%', [0, 105], {{ showlegend: true, legend: {{ orientation:'h', y:1.15 }} }}), {{ responsive: true, displayModeBar: false }});

function pushCar(d) {{
  if (!d.date) return;
  const t = new Date(d.date.replace('Z', '+00:00'));
  const dr = (d.drs != null && Number(d.drs) >= 8) ? Number(d.speed) || 0 : null;
  xs.push(t); sp.push(Number(d.speed)||0); rp.push(Number(d.rpm)||0);
  gr.push(Number(d.n_gear)||0); th.push(Number(d.throttle)||0); br.push(Number(d.brake)||0); drs.push(dr);
  while (xs.length > MAX_P) {{
    xs.shift(); sp.shift(); rp.shift(); gr.shift(); th.shift(); br.shift(); drs.shift();
  }}
  updateKv(d);
  const X = xs.slice();
  const Drs = drs.slice();
  Plotly.react('g1', [
    {{ type:'scatter', mode:'lines', x: X, y: sp.slice(), line:{{ color: DRV_COLOR, width: 2 }}, fill:'tozeroy', fillcolor: 'rgba(200,200,200,0.06)' }},
    {{ type:'scatter', mode:'lines', x: X, y: Drs, line:{{ color:'#00FF88', width:2, dash:'dot' }} }},
  ], baseLayout('Vitesse (km/h)', 'km/h', [0, 380], {{}}), {{ responsive: true, displayModeBar: false }});
  Plotly.react('g2', [{{ type:'scatter', mode:'lines', x: X, y: rp.slice(), line:{{ color:'#FF8000', width:1.5 }} }}],
    baseLayout('RPM', 'RPM', [0, 20000], {{}}), {{ responsive: true, displayModeBar: false }});
  Plotly.react('g3', [{{ type:'scatter', mode:'lines', x: X, y: gr.slice(), line:{{ color:'#CCC', width:2, shape:'hv' }} }}],
    baseLayout('Rapport', 'R', [0, 8], {{ yaxis: {{ dtick: 1 }} }}), {{ responsive: true, displayModeBar: false }});
  Plotly.react('g4', [
    {{ type:'scatter', mode:'lines', x: X, y: th.slice(), name:'Gaz', line:{{ color:'#00CC44', width:1.5 }}, fill:'tozeroy', fillcolor:'rgba(0,204,68,0.12)' }},
    {{ type:'scatter', mode:'lines', x: X, y: br.slice(), name:'Frein', line:{{ color:'#E10600', width:1.5 }}, fill:'tozeroy', fillcolor:'rgba(225,6,0,0.12)' }},
  ], baseLayout('Gaz / Frein (%)', '%', [0, 105], {{ showlegend: true, legend: {{ orientation:'h', y:1.15 }} }}), {{ responsive: true, displayModeBar: false }});

  // Vue Live mini (bi-axe)
  const layoutL = {{
    paper_bgcolor:'#0e0e0e', plot_bgcolor:'#121212', font:{{color:'#ccc'}},
    margin:{{l:45,r:45,t:28,b:30}},
    xaxis:{{showgrid:false}},
    yaxis:{{title:'km/h', range:[0,380], gridcolor:'rgba(255,255,255,0.07)'}},
    yaxis2:{{title:'RPM', overlaying:'y', side:'right', range:[0,20000], showgrid:false}},
    legend:{{orientation:'h', y:1.12}},
    hoverlabel:{{bgcolor:'#1a1a1a'}}
  }};
  const drsX = [], drsY = [];
  for (let i=0;i<X.length;i++) if (drs[i]!=null) {{ drsX.push(X[i]); drsY.push(sp[i]); }}
  Plotly.react('liveChart', [
    {{ x:X, y:sp.slice(), name:'Vitesse', line:{{color:DRV_COLOR,width:2}}, fill:'tozeroy', fillcolor:'rgba(200,200,200,0.06)', yaxis:'y' }},
    {{ x:X, y:rp.slice(), name:'RPM', line:{{color:'#FF8000',width:1.5,dash:'dot'}}, yaxis:'y2' }},
    {{ x:drsX, y:drsY, name:'DRS', mode:'markers', marker:{{color:'#00FF88',size:6}}, yaxis:'y' }},
  ], layoutL, {{ responsive: true, displayModeBar: false }});

  const g = Number(d.n_gear)||0;
  Plotly.react('liveGauge', [{{
    type:'indicator', mode:'gauge+number', value:g,
    title:{{text:'Rapport', font:{{color:'#ccc', size:13}}}},
    number:{{font:{{size:52, color: DRV_COLOR}}}},
    gauge:{{
      axis:{{range:[0,8], tickvals:[0,1,2,3,4,5,6,7,8]}},
      bar:{{color: DRV_COLOR, thickness:0.28}},
      bgcolor:'#181818', borderwidth:1, bordercolor:'#333',
    }}
  }}], {{ height:240, margin:{{t:40,b:10}}, paper_bgcolor:'#0e0e0e' }}, {{displayModeBar:false}});
}}

// ── Carte ───────────────────────────────────────────────────────────────────
const locByDn = {{}};
DRIVERS.forEach(d => {{
  locByDn[d.driver_number] = {{ ...d, x: null, y: null }};
}});

const mapTraces = [];
if (CIRCUIT_PATH && Array.isArray(CIRCUIT_PATH) && CIRCUIT_PATH.length > 1) {{
  const px = CIRCUIT_PATH.map(p => p[0]);
  const py = CIRCUIT_PATH.map(p => p[1]);
  mapTraces.push({{
    type:'scatter', mode:'lines', x: px, y: py, name:'Circuit',
    line:{{ color:'rgba(255,255,255,0.2)', width:6 }}, hoverinfo:'skip', showlegend:false
  }});
}}

DRIVERS.forEach(d => {{
  const c = d.team_colour || '#E10600';
  const big = d.driver_number === SEL_DN ? 16 : 11;
  mapTraces.push({{
    type:'scatter', mode:'markers+text', x:[], y:[], name: d.name_acronym || ('#'+d.driver_number),
    text: [d.name_acronym || ('#'+d.driver_number)], textposition:'top center',
    marker:{{ size: big, color: c, line:{{color:'white', width:1.5}} }},
    textfont:{{ color:'white', size: 10 }},
    customdata: [d.driver_number],
    hovertemplate: '<b>%{{text}}</b><br>x=%{{x:.0f}} y=%{{y:.0f}}<extra></extra>'
  }});
}});

const layoutMap = {{
  paper_bgcolor:'#0e0e0e', plot_bgcolor:'#0e0e0e',
  xaxis:{{ showgrid:false, zeroline:false, showticklabels:false, scaleanchor:'y' }},
  yaxis:{{ showgrid:false, zeroline:false, showticklabels:false }},
  margin:{{l:0,r:0,t:36,b:0}},
  height: 520,
  title:{{ text:'<b>Positions live</b> <span style="font-size:12px;color:#888">MQTT location</span>', font:{{size:14}} }}
}};
Plotly.newPlot('map', mapTraces, layoutMap, {{ responsive: true, displayModeBar: false }});

const pathOffset = (CIRCUIT_PATH && CIRCUIT_PATH.length) ? 1 : 0;
function traceIndexForDn(dn) {{
  for (let i = pathOffset; i < mapTraces.length; i++) {{
    const t = mapTraces[i];
    if (t.customdata && t.customdata[0] === dn) return i;
  }}
  return -1;
}}

function pushLoc(d) {{
  const dn = Number(d.driver_number);
  if (!locByDn[dn]) return;
  locByDn[dn].x = d.x; locByDn[dn].y = d.y;
  const ti = traceIndexForDn(dn);
  if (ti < 0) return;
  Plotly.restyle('map', {{ x: [[d.x]], y: [[d.y]] }}, [ti]);
}}

let lastStintByDriver = {{}};
function pushStint(d) {{
  const dn = Number(d.driver_number);
  if (!isFinite(dn)) return;
  lastStintByDriver[dn] = d;
  const c = (d.compound || 'UNKNOWN').toUpperCase();
  const bg = COMPOUND_COLORS[c] || '#555';
  const tx = COMPOUND_TEXT[c] || '#fff';
  const ab = COMPOUND_ABBR[c] || '?';
  const solo = document.getElementById('stintSolo');
  if (dn === SEL_DN) {{
    solo.innerHTML =
      '<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;">' +
      '<div style="background:'+bg+';color:'+tx+';border-radius:20px;padding:6px 18px;font-size:1.4em;font-weight:900;">'+ab+'</div>' +
      '<div><div style="color:#fff;font-weight:700">Stint '+(d.stint_number ?? '—')+' · '+c+'</div>' +
      '<div style="color:#888;font-size:0.9em;margin-top:4px">Tours '+(d.lap_start ?? '?')+' → '+(d.lap_end ?? '?')+
      ' · Âge pneu : '+(d.tyre_age_at_start ?? '—')+'</div></div></div>';
  }}
  const tyreDiv = document.getElementById('liveTyre');
  if (dn === SEL_DN) {{
    tyreDiv.innerHTML =
      '<div class="tyreCircle" style="background:'+bg+';color:'+tx+';box-shadow:0 0 20px '+bg+'55">'+ab+'</div>' +
      '<div style="color:#ccc;font-weight:600;margin-top:6px">'+c.charAt(0)+c.slice(1).toLowerCase()+'</div>' +
      '<div style="color:#777;font-size:0.8em">Stint '+(d.stint_number ?? '?')+'</div>';
  }}
}}

function onWsMessage(ev) {{
  try {{
    const msg = JSON.parse(ev.data);
    if (msg.error) {{ setStatus('Erreur : ' + msg.error, false); return; }}
    if (msg.ch) {{
      if (msg.ch === 'car_data') pushCar(msg.d);
      else if (msg.ch === 'location') pushLoc(msg.d);
      else if (msg.ch === 'stint') pushStint(msg.d);
    }} else {{
      pushCar(msg);
    }}
  }} catch (e) {{}}
}}

function connect() {{
  let ws;
  try {{ ws = new WebSocket(WS_URL); }}
  catch (e) {{ setStatus('WebSocket impossible : ' + e, false); return; }}
  ws.onopen = () => setStatus('Flux MQTT actif — car_data + location + stints', true);
  ws.onclose = () => setStatus('Connexion fermée', false);
  ws.onerror = () => setStatus('Erreur WebSocket (PUBLIC_API_BASE_URL / pare-feu)', false);
  ws.onmessage = onWsMessage;
}}
connect();
</script>
</body></html>"""

