/**
 * Page Résultats — sélecteur de course + podium + tableau complet
 */

import { fetchRaceSchedule, fetchRaceResults } from '../api.js';

const TEAM_COLORS = {
  'mercedes':     '#00D2BE', 'ferrari':        '#DC0000', 'red bull':     '#3671C6',
  'mclaren':      '#FF8000', 'aston martin':   '#358C75', 'alpine':       '#0093CC',
  'williams':     '#64C4FF', 'haas':           '#B6BABD', 'racing bulls': '#6692FF',
  'cadillac':     '#C5003E', 'rb':             '#6692FF', 'kick sauber':  '#52E252',
};

function teamColor(name) {
  if (!name) return '#555';
  const k = name.toLowerCase();
  for (const [kw, c] of Object.entries(TEAM_COLORS)) {
    if (k.includes(kw)) return c;
  }
  return '#555';
}

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: 'long', year: 'numeric' });
}

function podCard(p, cls) {
  if (!p) return `<div class="podium-card ${cls}"></div>`;
  const fl = p.fastest_lap_rank === 1 ? '<span class="podium-fastest">⚡ Meilleur tour</span>' : '';
  return `
    <div class="podium-card ${cls}">
      <div class="podium-pos">P${p.position}</div>
      <div class="podium-code">${p.driver_code || p.driver_name?.split(' ').pop() || '—'}</div>
      <div class="podium-name">${p.driver_name || '—'}</div>
      <div class="podium-team">${p.constructor_name || '—'}</div>
      <div class="podium-time">${p.time_or_status || '—'}</div>
      <div class="podium-points">${p.points} pts</div>
      ${fl}
    </div>`;
}

function renderResults(race) {
  if (!race) return `<div class="error-banner">Résultats non disponibles.</div>`;

  const [p1, p2, p3] = [1, 2, 3].map(pos => race.results?.find(r => r.position === pos));

  const podiumHtml = (p1 || p2 || p3) ? `
    <div class="podium-row">
      ${podCard(p2, 'podium-p2')}
      ${podCard(p1, 'podium-p1')}
      ${podCard(p3, 'podium-p3')}
    </div>` : '';

  const tableRows = (race.results || []).map(r => {
    const color = teamColor(r.constructor_name);
    const posClass = r.position <= 3 ? 'top' : '';
    const fl = r.fastest_lap_rank === 1 ? ' ⚡' : '';
    return `
      <tr>
        <td><span class="pos-num ${posClass}">${r.position}</span></td>
        <td>
          <div class="driver-code">${r.driver_code || r.driver_name?.split(' ').pop() || '—'}</div>
          <div class="driver-name">${r.driver_name || '—'}</div>
        </td>
        <td style="color:${color};font-size:12px">${r.constructor_name}</td>
        <td style="color:#888;font-size:12px">${r.grid}</td>
        <td style="color:#888;font-size:12px">${r.laps}</td>
        <td style="font-variant-numeric:tabular-nums">${r.time_or_status}${fl}</td>
        <td class="points-val">${r.points}</td>
      </tr>`;
  }).join('');

  return `
    <div class="card" style="margin-bottom:24px">
      <div class="section-title">Podium</div>
      ${podiumHtml}
    </div>
    <div class="card" style="overflow:auto">
      <div class="section-title">Classement de course</div>
      <table class="standings-table">
        <thead>
          <tr>
            <th>#</th><th>Pilote</th><th>Écurie</th>
            <th>Départ</th><th>Tours</th><th>Temps / Statut</th><th>Points</th>
          </tr>
        </thead>
        <tbody>${tableRows}</tbody>
      </table>
    </div>`;
}

export async function renderResultsPage(container) {
  container.innerHTML = `<div class="loading-screen"><div class="loading-spinner"></div><p>Chargement du calendrier…</p></div>`;

  let schedule;
  try {
    schedule = await fetchRaceSchedule();
  } catch (e) {
    container.innerHTML = `<div class="error-banner">Impossible de charger le calendrier : ${e.message}</div>`;
    return;
  }

  // Only show races that have already taken place (date ≤ today)
  const today = new Date().toISOString().slice(0, 10);
  const pastRaces = (schedule.races || []).filter(r => r.date <= today).reverse(); // most recent first

  if (!pastRaces.length) {
    container.innerHTML = `
      <div class="page-header">
        <div class="page-title">Résultats</div>
        <div class="page-subtitle">Saison ${schedule.season}</div>
      </div>
      <div class="card"><p style="color:var(--text-muted);text-align:center;padding:24px">Aucune course disputée pour l'instant.</p></div>`;
    return;
  }

  const selectorHtml = `
    <select id="racePicker" class="race-picker">
      ${pastRaces.map(r => `<option value="${r.round}">${r.round}. ${r.race_name} — ${fmtDate(r.date)}</option>`).join('')}
    </select>`;

  container.innerHTML = `
    <div class="page-header">
      <div class="page-title">Résultats</div>
      <div class="page-subtitle">Saison ${schedule.season} · ${schedule.total_rounds} manches</div>
    </div>
    ${selectorHtml}
    <div id="resultsContent">
      <div class="loading-screen"><div class="loading-spinner"></div><p>Chargement…</p></div>
    </div>`;

  const picker  = document.getElementById('racePicker');
  const content = document.getElementById('resultsContent');

  async function loadRound(round) {
    content.innerHTML = `<div class="loading-screen"><div class="loading-spinner"></div><p>Chargement des résultats…</p></div>`;
    try {
      const race = await fetchRaceResults(round);
      content.innerHTML = renderResults(race);
    } catch (e) {
      content.innerHTML = `<div class="error-banner">Erreur : ${e.message}</div>`;
    }
  }

  picker.addEventListener('change', () => loadRound(parseInt(picker.value, 10)));

  // Load most recent race by default
  await loadRound(parseInt(picker.value, 10));
}
