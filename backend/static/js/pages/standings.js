/**
 * Page classements pilotes & constructeurs
 */

import {
  fetchDriverStandings,
  fetchConstructorStandings,
  fetchNextRace,
  fetchLastRace,
} from '../api.js';

const COUNTRY_FLAGS = {
  british: '🇬🇧', dutch: '🇳🇱', monégasque: '🇲🇨', spanish: '🇪🇸', german: '🇩🇪',
  australian: '🇦🇺', mexican: '🇲🇽', canadian: '🇨🇦', french: '🇫🇷', finnish: '🇫🇮',
  chinese: '🇨🇳', american: '🇺🇸', danish: '🇩🇰', thai: '🇹🇭', japanese: '🇯🇵',
  new_zealander: '🇳🇿', italian: '🇮🇹', austrian: '🇦🇹', argentinian: '🇦🇷',
  swiss: '🇨🇭', swedish: '🇸🇪', polish: '🇵🇱', brazilian: '🇧🇷',
};

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

function flag(nat) {
  return COUNTRY_FLAGS[(nat || '').toLowerCase().replace(/\s/g,'_')] || '🏁';
}

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' });
}

function fmtTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }) + ' UTC';
}

function fmtFullDatetime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', timeZone: 'UTC' })
       + ' · ' + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })
       + ' UTC';
}

function countdown(targetIso) {
  const diff = new Date(targetIso) - Date.now();
  if (diff <= 0) return { d: 0, h: 0, m: 0, s: 0, past: true };
  const s  = Math.floor(diff / 1000);
  const d  = Math.floor(s / 86400);
  const h  = Math.floor((s % 86400) / 3600);
  const m  = Math.floor((s % 3600) / 60);
  return { d, h, m, s: s % 60, past: false };
}

function pad(n) { return String(n).padStart(2, '0'); }

/* ── Standings bar chart ── */
function drawStandingsChart(canvas, items, labelKey, valueKey, colorFn) {
  const existing = Chart.getChart(canvas);
  if (existing) existing.destroy();

  const labels = items.slice(0, 10).map(i => labelKey(i));
  const data   = items.slice(0, 10).map(i => i[valueKey]);
  const colors = items.slice(0, 10).map(i => colorFn(i));

  new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: colors.map(c => c + '99'),
        borderColor:     colors,
        borderWidth: 1,
        borderRadius: 4,
        borderSkipped: false,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.raw} pts`,
          },
        },
      },
      scales: {
        x: {
          grid: { color: 'rgba(255,255,255,0.05)' },
          ticks: { color: '#666', font: { size: 11 } },
          border: { color: 'rgba(255,255,255,0.08)' },
        },
        y: {
          grid: { display: false },
          ticks: { color: '#ccc', font: { size: 12, weight: '600' } },
        },
      },
    },
  });
}

/* ── Render ── */
export async function renderStandings(container, type = 'drivers') {
  container.innerHTML = `<div class="loading-screen"><div class="loading-spinner"></div><p>Chargement…</p></div>`;

  let standings, nextRace, lastRace;
  try {
    const [s, nr, lr] = await Promise.allSettled([
      type === 'drivers' ? fetchDriverStandings() : fetchConstructorStandings(),
      fetchNextRace(),
      fetchLastRace(),
    ]);
    standings = s.status === 'fulfilled' ? s.value : null;
    nextRace  = nr.status === 'fulfilled' ? nr.value : null;
    lastRace  = lr.status === 'fulfilled' ? lr.value : null;
  } catch (e) {
    container.innerHTML = `<div class="error-banner">Erreur de chargement : ${e.message}</div>`;
    return;
  }

  const isDrivers = type === 'drivers';
  const title = isDrivers ? 'Classement Pilotes' : 'Classement Constructeurs';
  const subtitle = standings
    ? `Saison ${standings.season} · Manche ${standings.round ?? '—'} · ${standings.total} ${isDrivers ? 'pilotes' : 'constructeurs'}`
    : '';

  const leader = standings?.standings?.[0];
  const leaderName = isDrivers
    ? (leader?.driver?.code || leader?.driver?.last_name || '—')
    : (leader?.constructor?.name || '—');

  /* ── KPI ── */
  const kpis = `
    <div class="kpi-row">
      <div class="kpi-card">
        <div class="kpi-label">Saison</div>
        <div class="kpi-value">${standings?.season ?? '—'}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Manche</div>
        <div class="kpi-value">${standings?.round ?? '—'}/${nextRace?.total_rounds ?? '?'}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Leader</div>
        <div class="kpi-value" style="font-size:18px">${leaderName}</div>
        <div class="kpi-sub">${leader?.points ?? 0} pts · ${leader?.wins ?? 0} victoires</div>
      </div>
      ${nextRace ? `
      <div class="kpi-card">
        <div class="kpi-label">Prochain GP</div>
        <div class="kpi-value" style="font-size:14px">${nextRace.race_name}</div>
        <div class="kpi-sub">${fmtDate(nextRace.race?.datetime_utc)}</div>
      </div>` : ''}
    </div>
  `;

  /* ── Next race ── */
  let nextRaceHtml = '';
  if (nextRace) {
    const ct = countdown(nextRace.countdown?.target_datetime_utc);
    const sessions = [
      { label: 'Essais Libres 1', dt: nextRace.fp1?.datetime_utc },
      { label: 'Essais Libres 2', dt: nextRace.fp2?.datetime_utc },
      { label: 'Essais Libres 3', dt: nextRace.fp3?.datetime_utc },
      { label: 'Sprint Q.',        dt: nextRace.sprint_qualifying?.datetime_utc },
      { label: 'Sprint',           dt: nextRace.sprint?.datetime_utc },
      { label: 'Qualifications',   dt: nextRace.qualifying?.datetime_utc },
      { label: 'Course',           dt: nextRace.race?.datetime_utc },
    ].filter(s => s.dt);

    nextRaceHtml = `
      <div class="next-race-card">
        <div>
          <div class="race-name">${nextRace.race_name}</div>
          <div class="race-meta">
            ${nextRace.circuit?.location?.locality || ''}, ${nextRace.circuit?.location?.country || ''}
            · ${nextRace.circuit?.name || ''}
          </div>
          <div class="race-sessions">
            ${sessions.map(s => `
              <div class="race-session-row">
                <span class="race-session-label">${s.label}</span>
                <span class="race-session-time">${fmtFullDatetime(s.dt)}</span>
              </div>
            `).join('')}
          </div>
        </div>
        <div class="countdown-block">
          <div class="countdown-title">Prochain : ${nextRace.countdown?.target_session ?? 'Course'}</div>
          <div class="countdown-digits" id="countdownDigits">
            <div class="countdown-unit">
              <span class="countdown-num" id="cdDays">${pad(ct.d)}</span>
              <span class="countdown-label">jours</span>
            </div>
            <div class="countdown-unit">
              <span class="countdown-num" id="cdHours">${pad(ct.h)}</span>
              <span class="countdown-label">heures</span>
            </div>
            <div class="countdown-unit">
              <span class="countdown-num" id="cdMins">${pad(ct.m)}</span>
              <span class="countdown-label">min</span>
            </div>
            <div class="countdown-unit">
              <span class="countdown-num" id="cdSecs">${pad(ct.s ?? 0)}</span>
              <span class="countdown-label">sec</span>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  /* ── Podium ── */
  let podiumHtml = '';
  if (lastRace?.results?.length >= 3) {
    const r = lastRace.results;
    const [p1, p2, p3] = [r.find(x => x.position === 1), r.find(x => x.position === 2), r.find(x => x.position === 3)];
    function podCard(p, cls) {
      if (!p) return '<div class="podium-card"></div>';
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
    podiumHtml = `
      <div class="section-title">Résultats : ${lastRace.race_name}</div>
      <div class="podium-row">
        ${podCard(p2, 'podium-p2')}
        ${podCard(p1, 'podium-p1')}
        ${podCard(p3, 'podium-p3')}
      </div>
    `;
  }

  /* ── Standings table & chart ── */
  const rows = standings?.standings ?? [];

  const tableRows = rows.map((s, i) => {
    const posClass = i < 3 ? 'top' : '';
    if (isDrivers) {
      const color = teamColor(s.constructor_name);
      return `
        <tr>
          <td><span class="pos-num ${posClass}">${s.position}</span></td>
          <td>
            <div style="display:flex;align-items:center">
              <span class="team-badge" style="background:${color}"></span>
              <div>
                <div class="driver-code">${flag(s.driver.nationality)} ${s.driver.code || s.driver.last_name}</div>
                <div class="driver-name">${s.driver.first_name} ${s.driver.last_name}</div>
              </div>
            </div>
          </td>
          <td style="color:${color};font-size:12px">${s.constructor_name}</td>
          <td class="points-val">${s.points}</td>
          <td style="color:#777">${s.wins}</td>
        </tr>`;
    } else {
      const color = teamColor(s.constructor.name);
      return `
        <tr>
          <td><span class="pos-num ${posClass}">${s.position}</span></td>
          <td>
            <div style="display:flex;align-items:center">
              <span class="team-badge" style="background:${color}"></span>
              <div>
                <div class="driver-code">${flag(s.constructor.nationality)} ${s.constructor.name}</div>
              </div>
            </div>
          </td>
          <td class="points-val">${s.points}</td>
          <td style="color:#777">${s.wins}</td>
        </tr>`;
    }
  }).join('');

  const tableHeaders = isDrivers
    ? '<th>#</th><th>Pilote</th><th>Écurie</th><th>Points</th><th>Victoires</th>'
    : '<th>#</th><th>Constructeur</th><th>Points</th><th>Victoires</th>';

  container.innerHTML = `
    <div class="page-header">
      <div class="page-title">${title}</div>
      <div class="page-subtitle">${subtitle}</div>
    </div>
    ${kpis}
    ${nextRaceHtml}
    ${podiumHtml}
    <div class="two-col">
      <div class="card">
        <div class="section-title">Top 10</div>
        <div class="chart-wrap" style="height:280px">
          <canvas id="standingsChart"></canvas>
        </div>
      </div>
      <div class="card" style="overflow:auto">
        <div class="section-title">Classement complet</div>
        <table class="standings-table">
          <thead><tr>${tableHeaders}</tr></thead>
          <tbody>${tableRows}</tbody>
        </table>
      </div>
    </div>
  `;

  /* ── Chart ── */
  const canvas = document.getElementById('standingsChart');
  if (canvas && rows.length) {
    if (isDrivers) {
      drawStandingsChart(
        canvas,
        rows,
        i => i.driver.code || i.driver.last_name,
        'points',
        i => teamColor(i.constructor_name),
      );
    } else {
      drawStandingsChart(
        canvas,
        rows,
        i => i.constructor.name,
        'points',
        i => teamColor(i.constructor.name),
      );
    }
  }

  /* ── Countdown ticker ── */
  if (nextRace?.countdown?.target_datetime_utc) {
    const target = nextRace.countdown.target_datetime_utc;
    const tick = () => {
      const ct = countdown(target);
      const d  = document.getElementById('cdDays');
      if (!d) return; // page was navigated away
      document.getElementById('cdDays').textContent  = pad(ct.d);
      document.getElementById('cdHours').textContent = pad(ct.h);
      document.getElementById('cdMins').textContent  = pad(ct.m);
      document.getElementById('cdSecs').textContent  = pad(ct.s ?? 0);
    };
    tick();
    const id = setInterval(() => {
      if (!document.getElementById('cdDays')) { clearInterval(id); return; }
      tick();
    }, 1000);
  }
}
