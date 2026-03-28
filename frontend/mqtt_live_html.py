"""
HTML + JS : WebSocket vers le backend (relai MQTT OpenF1) — graphique Plotly mis à jour en continu.
"""

from __future__ import annotations

import json


def build_mqtt_live_embed(ws_url: str) -> str:
    """Composant iframe-friendly : Plotly.js + WebSocket, aucun jeton côté client."""
    ws_js = json.dumps(ws_url)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  body {{ margin:0; padding:8px; background:#0e0e0e; color:#ddd; font-family:system-ui,sans-serif; font-size:13px; }}
  #st {{ color:#888; margin-bottom:8px; min-height:1.2em; }}
  #kv {{ display:flex; flex-wrap:wrap; gap:12px; margin:10px 0; }}
  #kv span {{ background:#1a1a1a; padding:8px 12px; border-radius:8px; border-left:3px solid #E10600; }}
  #chart {{ width:100%; height:320px; }}
</style></head><body>
<div id="st">Connexion au flux MQTT…</div>
<div id="kv"></div>
<div id="chart"></div>
<script>
const WS_URL = {ws_js};
let ws = null;
let xs = [], ys = [], yr = [];
const layout = {{
  paper_bgcolor: '#0e0e0e',
  plot_bgcolor: '#161616',
  font: {{ color: '#ccc' }},
  margin: {{ t: 28, r: 55, b: 40, l: 55 }},
  xaxis: {{ title: 'Temps', gridcolor: '#333' }},
  yaxis: {{ title: 'km/h', side: 'left', range: [0, 380], gridcolor: '#333' }},
  yaxis2: {{ title: 'RPM', overlaying: 'y', side: 'right', range: [0, 20000], showgrid: false }},
  showlegend: true,
  legend: {{ orientation: 'h', y: 1.12 }}
}};
const traces = [
  {{ x: [], y: [], name: 'Vitesse', line: {{ color: '#E10600', width: 2 }}, yaxis: 'y' }},
  {{ x: [], y: [], name: 'RPM', line: {{ color: '#FF8000', width: 1.5 }}, yaxis: 'y2' }}
];
Plotly.newPlot('chart', traces, layout, {{ responsive: true, displayModeBar: false }});

function setStatus(t, ok) {{
  const el = document.getElementById('st');
  el.textContent = t;
  el.style.color = ok ? '#6c6' : '#e66';
}}

function updateKv(d) {{
  const g = d.n_gear != null ? d.n_gear : '—';
  const drs = (d.drs != null && Number(d.drs) >= 8) ? 'ouvert' : 'fermé';
  document.getElementById('kv').innerHTML =
    '<span><b>Vitesse</b> ' + (d.speed ?? '—') + ' km/h</span>' +
    '<span><b>RPM</b> ' + (d.rpm ?? '—') + '</span>' +
    '<span><b>R</b> ' + g + '</span>' +
    '<span><b>Gaz</b> ' + (d.throttle ?? '—') + ' %</span>' +
    '<span><b>Frein</b> ' + (d.brake ?? '—') + ' %</span>' +
    '<span><b>DRS</b> ' + drs + '</span>';
}}

function push(d) {{
  if (!d.date) return;
  const t = new Date(d.date.replace('Z', '+00:00'));
  xs.push(t); ys.push(Number(d.speed)||0); yr.push(Number(d.rpm)||0);
  const max = 400;
  while (xs.length > max) {{ xs.shift(); ys.shift(); yr.shift(); }}
  Plotly.react('chart', [
    {{ x: xs.slice(), y: ys.slice(), name: 'Vitesse', line: {{ color: '#E10600', width: 2 }}, yaxis: 'y' }},
    {{ x: xs.slice(), y: yr.slice(), name: 'RPM', line: {{ color: '#FF8000', width: 1.5 }}, yaxis: 'y2' }}
  ], layout, {{ responsive: true, displayModeBar: false }});
  updateKv(d);
}}

function connect() {{
  try {{
    ws = new WebSocket(WS_URL);
  }} catch (e) {{
    setStatus('WebSocket impossible : ' + e, false);
    return;
  }}
  ws.onopen = () => setStatus('Flux MQTT actif — données poussées par OpenF1', true);
  ws.onclose = () => setStatus('Connexion fermée', false);
  ws.onerror = () => setStatus('Erreur WebSocket (vérifiez PUBLIC_API_BASE_URL / pare-feu)', false);
  ws.onmessage = (ev) => {{
    try {{
      const d = JSON.parse(ev.data);
      if (d.error) {{
        setStatus('Erreur : ' + d.error, false);
        return;
      }}
      push(d);
    }} catch (e) {{}}
  }};
}}
connect();
</script>
</body></html>"""
