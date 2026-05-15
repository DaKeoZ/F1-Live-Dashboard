/**
 * Page Télémétrie — sélection session/pilote, charts, circuit, stratégie pneus, live WebSocket
 */

import {
  fetchSessions,
  fetchDrivers,
  fetchTelemetry,
  fetchLastPositions,
  fetchCarPath,
  fetchTyreStints,
  TelemetryWS,
} from '../api.js';

import { CircuitRenderer } from '../components/circuit.js';
import {
  createSpeedChart,
  createRPMChart,
  createGearChart,
  createThrottleBrakeChart,
  pushPoint,
  renderTyreStrategy,
} from '../components/charts.js';

// Module-level state — survives re-renders, cleaned up by destroyTelemetry()
let _ws       = null;
let _circuit  = null;
let _posTimer = null;
let _charts   = {};

const COMPOUND_COLORS = {
  SOFT: '#E8002D', MEDIUM: '#FFF200', HARD: '#EBEBEB',
  INTERMEDIATE: '#39B54A', WET: '#0067FF', UNKNOWN: '#555',
};
const COMPOUND_TEXT = {
  SOFT: '#fff', MEDIUM: '#000', HARD: '#000',
  INTERMEDIATE: '#fff', WET: '#fff', UNKNOWN: '#aaa',
};

function isSessionEnded(session) {
  if (!session?.date_end) return false;
  return new Date(session.date_end) < new Date(Date.now() - 60 * 60 * 1000);
}

function groupByMeeting(sessions) {
  const meetings = {};
  for (const s of sessions) {
    const mk = s.meeting_key || s.session_key;
    if (!meetings[mk]) {
      meetings[mk] = { key: mk, name: s.circuit_short_name, country: s.country_name, year: s.year, sessions: [] };
    }
    meetings[mk].sessions.push(s);
  }
  return Object.values(meetings).sort((a, b) => {
    const aDate = a.sessions[0]?.date_start || '';
    const bDate = b.sessions[0]?.date_start || '';
    return bDate.localeCompare(aDate);
  });
}

const SESSION_LABELS = {
  Race: 'Course', Qualifying: 'Qualifications', Sprint: 'Sprint',
  'Sprint Qualifying': 'Sprint Q.', 'Practice 1': 'EL1', 'Practice 2': 'EL2', 'Practice 3': 'EL3',
};

function fmtSessionLabel(s) {
  return SESSION_LABELS[s.session_name] || SESSION_LABELS[s.session_type] || s.session_name || s.session_type || '—';
}

export function destroyTelemetry() {
  _ws?.close(); _ws = null;
  _circuit?.destroy(); _circuit = null;
  if (_posTimer) { clearInterval(_posTimer); _posTimer = null; }
  Object.values(_charts).forEach(c => c?.destroy?.());
  _charts = {};
  document.dispatchEvent(new CustomEvent('f1:live', { detail: false }));
}

/* ── Main render ── */
export async function renderTelemetry(container) {
  destroyTelemetry();

  container.innerHTML = `
    <div class="page-header">
      <div class="page-title">Télémétrie</div>
      <div class="page-subtitle">Données voiture en temps réel ou historiques via OpenF1</div>
    </div>
    <div class="tel-controls">
      <div class="control-group">
        <label class="control-label">Année</label>
        <select class="control-select" id="yearSel"></select>
      </div>
      <div class="control-group" style="min-width:200px">
        <label class="control-label">Grand Prix</label>
        <select class="control-select" id="meetingSel"><option value="">— Choisir —</option></select>
      </div>
      <div class="control-group">
        <label class="control-label">Session</label>
        <select class="control-select" id="sessionSel"><option value="">— Choisir —</option></select>
      </div>
      <div class="control-group">
        <label class="control-label">Pilote</label>
        <select class="control-select" id="driverSel"><option value="">— Choisir —</option></select>
      </div>
      <div id="modeBadge" style="margin-left:auto"></div>
    </div>
    <div id="telContent">
      <div class="empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
        </svg>
        <p>Sélectionnez une session et un pilote</p>
      </div>
    </div>
  `;

  // Populate year selector
  const currentYear = new Date().getFullYear();
  const yearSel = document.getElementById('yearSel');
  for (let y = currentYear; y >= 2023; y--) {
    const opt = document.createElement('option');
    opt.value = y; opt.textContent = y;
    if (y === currentYear) opt.selected = true;
    yearSel.appendChild(opt);
  }

  let allSessions = [];
  let meetings    = [];
  let driverMap   = {};

  async function loadSessions(year) {
    try {
      allSessions = await fetchSessions(year);
    } catch {
      allSessions = [];
    }
    meetings = groupByMeeting(allSessions);
    const meetingSel = document.getElementById('meetingSel');
    meetingSel.innerHTML = '<option value="">— Choisir —</option>';
    meetings.forEach((m, i) => {
      const opt = document.createElement('option');
      opt.value = i;
      opt.textContent = `${m.country} — ${m.name} (${m.year})`;
      meetingSel.appendChild(opt);
    });
    // Auto-select most recent past meeting
    const nowIso = new Date().toISOString();
    const pastIdx = meetings.findIndex(m => m.sessions.some(s => s.date_end && s.date_end < nowIso));
    if (pastIdx >= 0) {
      meetingSel.value = pastIdx;
      await onMeetingChange(pastIdx, true);
    }
  }

  async function onMeetingChange(idx, autoSession = false) {
    const m = meetings[idx];
    if (!m) return;
    const sessionSel = document.getElementById('sessionSel');
    sessionSel.innerHTML = '<option value="">— Choisir —</option>';
    m.sessions.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.session_key;
      opt.textContent = fmtSessionLabel(s);
      sessionSel.appendChild(opt);
    });
    if (autoSession) {
      // Pick Race, else last session
      const raceSess = m.sessions.find(s => s.session_type === 'Race' || s.session_name === 'Race');
      const target = raceSess || m.sessions[m.sessions.length - 1];
      if (target) {
        sessionSel.value = target.session_key;
        await onSessionChange(target.session_key);
      }
    }
  }

  async function onSessionChange(sessionKey) {
    if (!sessionKey) return;
    const driverSel = document.getElementById('driverSel');
    driverSel.innerHTML = '<option value="">Chargement…</option>';
    try {
      const drivers = await fetchDrivers(sessionKey);
      driverSel.innerHTML = '<option value="">— Choisir —</option>';
      driverMap = {};
      drivers.forEach(d => {
        driverMap[d.driver_number] = d;
        const opt = document.createElement('option');
        opt.value = d.driver_number;
        opt.textContent = `${d.name_acronym} — ${d.full_name}`;
        driverSel.appendChild(opt);
      });
    } catch {
      driverSel.innerHTML = '<option value="">Erreur</option>';
    }
  }

  // Event listeners
  yearSel.addEventListener('change', () => loadSessions(yearSel.value));

  document.getElementById('meetingSel').addEventListener('change', e => {
    const idx = parseInt(e.target.value, 10);
    if (!isNaN(idx)) onMeetingChange(idx);
  });

  document.getElementById('sessionSel').addEventListener('change', e => {
    onSessionChange(e.target.value);
  });

  document.getElementById('driverSel').addEventListener('change', e => {
    const sk  = parseInt(document.getElementById('sessionSel').value, 10);
    const drv = parseInt(e.target.value, 10);
    const sess = allSessions.find(s => s.session_key === sk);
    if (sk && drv) loadTelemetryView(sk, drv, sess, driverMap);
  });

  await loadSessions(currentYear);
}

/* ── Load full telemetry view ── */
async function loadTelemetryView(sessionKey, driverNumber, session, driverMap) {
  destroyTelemetry();

  const content = document.getElementById('telContent');
  content.innerHTML = `<div class="loading-screen"><div class="loading-spinner"></div><p>Chargement des données…</p></div>`;

  const ended = isSessionEnded(session);
  const driver = driverMap?.[driverNumber];
  const teamColor = driver?.team_colour
    ? (driver.team_colour.startsWith('#') ? driver.team_colour : '#' + driver.team_colour)
    : '#60a5fa';

  // Render the page skeleton
  content.innerHTML = `
    <div class="live-stats" id="liveStats">
      <div class="live-stat-card">
        <div class="live-stat-label">Vitesse</div>
        <div class="live-stat-value" id="lsSpeed" style="color:${teamColor}">—</div>
        <div class="live-stat-unit">km/h</div>
      </div>
      <div class="live-stat-card">
        <div class="live-stat-label">Régime</div>
        <div class="live-stat-value" id="lsRpm" style="color:#f97316">—</div>
        <div class="live-stat-unit">rpm</div>
      </div>
      <div class="live-stat-card">
        <div class="live-stat-label">Rapport</div>
        <div class="live-stat-value" id="lsGear" style="color:#a78bfa">—</div>
        <div class="live-stat-unit">ième</div>
      </div>
      <div class="live-stat-card">
        <div class="live-stat-label">Pneu actuel</div>
        <div style="display:flex;justify-content:center;padding:4px 0" id="lsTyre">
          <div class="tyre-badge" style="background:#555;color:#aaa">?</div>
        </div>
      </div>
    </div>

    <div class="tel-grid">
      <div class="tel-charts-col">
        <div class="tel-chart-card">
          <div class="tel-chart-label">Vitesse <span id="lblSpeed"></span></div>
          <div class="chart-wrap" style="height:100px"><canvas id="chartSpeed"></canvas></div>
        </div>
        <div class="tel-chart-card">
          <div class="tel-chart-label">Régime moteur <span id="lblRpm"></span></div>
          <div class="chart-wrap" style="height:80px"><canvas id="chartRpm"></canvas></div>
        </div>
        <div class="tel-chart-card">
          <div class="tel-chart-label">Rapport <span id="lblGear"></span></div>
          <div class="chart-wrap" style="height:70px"><canvas id="chartGear"></canvas></div>
        </div>
        <div class="tel-chart-card">
          <div class="tel-chart-label">Gaz / Frein</div>
          <div class="chart-wrap" style="height:80px"><canvas id="chartThBr"></canvas></div>
        </div>
      </div>

      <div class="circuit-card">
        <div class="circuit-title">Position en piste</div>
        <div class="circuit-canvas-wrap">
          <canvas id="circuitCanvas"></canvas>
        </div>
        <div class="circuit-legend" id="circuitLegend"></div>
      </div>
    </div>

    <div class="section">
      <div class="section-title">Stratégie pneus</div>
      <div class="card">
        <div id="strategyContainer"></div>
      </div>
    </div>

    <div id="modeBadge2" style="text-align:center;margin-top:-16px;margin-bottom:24px"></div>
  `;

  // Mode badge
  const badge = ended
    ? `<span class="mode-badge history"><span class="mode-dot"></span> Historique</span>`
    : `<span class="mode-badge live"><span class="mode-dot"></span> Temps réel</span>`;
  document.getElementById('modeBadge').innerHTML  = badge;
  document.getElementById('modeBadge2').innerHTML = badge;

  document.dispatchEvent(new CustomEvent('f1:live', { detail: !ended }));

  // Initialize circuit
  const circuitCanvas = document.getElementById('circuitCanvas');
  _circuit = new CircuitRenderer(circuitCanvas);

  // Load data concurrently
  const [telResult, pathResult, tyreResult] = await Promise.allSettled([
    fetchTelemetry(sessionKey, driverNumber, 500, ended ? 'uniform' : 'tail'),
    fetchCarPath(sessionKey, driverNumber),
    fetchTyreStints(sessionKey),
  ]);

  // Circuit path
  if (pathResult.status === 'fulfilled') {
    _circuit.setPath(pathResult.value.path || []);
  }

  // Tyre strategy
  if (tyreResult.status === 'fulfilled') {
    const strategies = tyreResult.value.strategies || [];
    renderTyreStrategy(document.getElementById('strategyContainer'), strategies, driverMap);
    // Update tyre badge for current driver
    const myStints = strategies.find(s => s.driver_number === driverNumber)?.stints || [];
    updateTyreBadge(myStints);
  }

  // Telemetry charts
  if (telResult.status === 'fulfilled') {
    const pts = telResult.value.points || [];
    renderCharts(pts, teamColor);
  } else {
    content.querySelector('.tel-charts-col').innerHTML = `
      <div class="error-banner">Impossible de charger la télémétrie : ${telResult.reason?.message || 'Erreur'}</div>`;
  }

  // Load positions
  await loadPositions(sessionKey, driverMap);

  // If live session → start WebSocket
  if (!ended) {
    startLive(sessionKey, driverNumber, teamColor, driverMap);
  } else {
    // Poll positions every 10s for historical (display snapshot)
    _posTimer = setInterval(() => loadPositions(sessionKey, driverMap), 10000);
  }
}

function renderCharts(points, teamColor) {
  if (!points.length) return;
  const labels    = points.map(p => p.timestamp);
  const speed     = points.map(p => p.speed);
  const rpm       = points.map(p => p.rpm);
  const gear      = points.map(p => p.n_gear);
  const throttle  = points.map(p => p.throttle);
  const brake     = points.map(p => p.brake);
  const drs       = points.map(p => p.drs ?? 0);

  // Update latest stat indicators
  const last = points[points.length - 1];
  if (last) updateLiveStats(last);

  _charts.speed = createSpeedChart(
    document.getElementById('chartSpeed'), labels, speed, drs
  );
  _charts.rpm   = createRPMChart(document.getElementById('chartRpm'), labels, rpm);
  _charts.gear  = createGearChart(document.getElementById('chartGear'), labels, gear);
  _charts.thbr  = createThrottleBrakeChart(
    document.getElementById('chartThBr'), labels, throttle, brake
  );

  // Max speed label
  const maxSpd = Math.max(...speed);
  if (maxSpd) document.getElementById('lblSpeed').textContent = `max ${maxSpd} km/h`;
}

function updateLiveStats(pt) {
  const el = id => document.getElementById(id);
  if (el('lsSpeed')) el('lsSpeed').textContent = pt.speed ?? '—';
  if (el('lsRpm'))   el('lsRpm').textContent   = pt.rpm   ?? '—';
  if (el('lsGear'))  el('lsGear').textContent  = pt.n_gear ?? '—';
}

function updateTyreBadge(stints) {
  const el = document.getElementById('lsTyre');
  if (!el || !stints.length) return;
  const last = stints[stints.length - 1];
  const compound = (last.compound || 'UNKNOWN').toUpperCase();
  const bg  = last.compound_color  || COMPOUND_COLORS[compound] || '#555';
  const txt = last.compound_text_color || COMPOUND_TEXT[compound] || '#fff';
  const abbr = compound[0] || '?';
  el.innerHTML = `<div class="tyre-badge" style="background:${bg};color:${txt}">${abbr}</div>`;
}

async function loadPositions(sessionKey, driverMap) {
  try {
    const data = await fetchLastPositions(sessionKey);
    const positions = (data.positions || []).map(p => ({
      x: p.x, y: p.y,
      code:  p.driver_code || `#${p.driver_number}`,
      color: p.team_colour || '#888',
    }));
    _circuit?.updateDrivers(positions);

    // Update legend
    const legend = document.getElementById('circuitLegend');
    if (legend) {
      legend.innerHTML = positions.map(p => `
        <div class="circuit-legend-item">
          <span class="legend-dot" style="background:${p.color}"></span>
          <span>${p.code}</span>
        </div>`).join('');
    }
  } catch {}
}

function startLive(sessionKey, driverNumber, teamColor, driverMap) {
  let liveBuffer = { labels: [], speed: [], rpm: [], gear: [], throttle: [], brake: [], drs: [] };
  let lastPosTick = 0;

  _ws = new TelemetryWS(sessionKey, driverNumber, msg => {
    const ch = msg.ch;
    const d  = msg.d;

    if (ch === 'car_data') {
      const ts = d.date || d.timestamp || new Date().toISOString();
      updateLiveStats({ speed: d.speed, rpm: d.rpm, n_gear: d.n_gear });

      if (_charts.speed) {
        pushPoint(_charts.speed, ts, d.speed, d.drs >= 10 ? d.speed : null);
      }
      if (_charts.rpm)  pushPoint(_charts.rpm, ts, d.rpm);
      if (_charts.gear) pushPoint(_charts.gear, ts, d.n_gear);
      if (_charts.thbr) {
        pushPoint(_charts.thbr, ts,
          Math.min(100, Math.max(0, d.throttle || 0)),
          Math.min(100, Math.max(0, d.brake || 0)),
        );
      }
    }

    if (ch === 'location') {
      const now = Date.now();
      if (now - lastPosTick > 1500) {
        lastPosTick = now;
        // d is the enriched position object from the backend
        const positions = Array.isArray(d) ? d : [d];
        const mapped = positions.map(p => ({
          x: p.x, y: p.y,
          code:  p.driver_code || `#${p.driver_number}`,
          color: p.team_colour || '#888',
        }));
        if (mapped.length) _circuit?.updateDrivers(mapped);
      }
    }
  });

  _ws.connect();
}
