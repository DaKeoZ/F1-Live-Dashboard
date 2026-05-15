/**
 * SPA router & global state
 */

import { renderStandings } from './pages/standings.js';
import { renderTelemetry, destroyTelemetry } from './pages/telemetry.js';

const PAGES = ['standings', 'constructors', 'telemetry'];

const state = {
  page: 'standings',
  season: 'current',
};

function setLiveIndicator(active, label) {
  const dot = document.querySelector('.live-dot');
  const lbl = document.querySelector('.live-label');
  if (dot) dot.classList.toggle('active', active);
  if (lbl) lbl.textContent = label;
}

// Écoute les événements live depuis la page télémétrie (évite la dépendance circulaire)
document.addEventListener('f1:live', e => {
  const active = e.detail;
  setLiveIndicator(active, active ? 'Session en cours' : 'Hors session');
});

async function navigate(page) {
  if (!PAGES.includes(page)) page = 'standings';

  // Cleanup telemetry when leaving
  if (state.page === 'telemetry' && page !== 'telemetry') {
    destroyTelemetry();
  }

  state.page = page;

  // Update nav
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.page === page);
  });

  // Fade out → render → fade in
  const container = document.getElementById('pageContainer');
  container.style.opacity = '0';
  container.style.transform = 'translateY(6px)';

  await new Promise(r => setTimeout(r, 120));

  if (page === 'telemetry') {
    await renderTelemetry(container);
  } else {
    await renderStandings(container, page === 'constructors' ? 'constructors' : 'drivers');
  }

  container.style.transition = 'opacity 0.18s ease, transform 0.18s ease';
  container.style.opacity = '1';
  container.style.transform = 'translateY(0)';
}

function init() {
  // Wire nav buttons
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => navigate(btn.dataset.page));
  });

  // Hash-based routing
  const pageFromHash = location.hash.slice(1);
  navigate(PAGES.includes(pageFromHash) ? pageFromHash : 'standings');

  window.addEventListener('hashchange', () => {
    const p = location.hash.slice(1);
    if (PAGES.includes(p) && p !== state.page) navigate(p);
  });
}

init();
