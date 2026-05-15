/**
 * Chart.js wrappers for telemetry charts
 */

Chart.defaults.color = '#666';
Chart.defaults.borderColor = 'rgba(255,255,255,0.05)';

const COMMON_SCALE = {
  grid: { color: 'rgba(255,255,255,0.05)' },
  ticks: { color: '#555', font: { size: 10 } },
  border: { color: 'rgba(255,255,255,0.06)' },
};

function makeTimeScale(showLabels = true) {
  return {
    type: 'category',
    grid: { color: 'rgba(255,255,255,0.04)' },
    ticks: {
      color: '#555',
      font: { size: 9 },
      display: showLabels,
      maxTicksLimit: 8,
      maxRotation: 0,
      callback(val) {
        // val is a timestamp string — show HH:MM:SS
        try {
          const d = new Date(val);
          return d.toISOString().slice(11, 19);
        } catch { return val; }
      },
    },
    border: { color: 'rgba(255,255,255,0.06)' },
  };
}

function destroyChart(canvas) {
  const existing = Chart.getChart(canvas);
  if (existing) existing.destroy();
}

export function createSpeedChart(canvas, labels, speedData, drsData) {
  destroyChart(canvas);
  return new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Vitesse',
          data: speedData,
          borderColor: '#60a5fa',
          backgroundColor: 'rgba(96,165,250,0.06)',
          fill: true,
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0.2,
          yAxisID: 'y',
        },
        {
          label: 'DRS',
          data: drsData.map((v, i) => v >= 10 ? speedData[i] : null),
          borderColor: '#22c55e',
          backgroundColor: 'transparent',
          borderWidth: 0,
          pointRadius: 3,
          pointBackgroundColor: '#22c55e',
          showLine: false,
          yAxisID: 'y',
        },
      ],
    },
    options: _lineOptions(false, 'km/h', [0, 380]),
  });
}

export function createRPMChart(canvas, labels, data) {
  destroyChart(canvas);
  return new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'RPM',
        data,
        borderColor: '#f97316',
        backgroundColor: 'rgba(249,115,22,0.06)',
        fill: true,
        borderWidth: 1.5,
        pointRadius: 0,
        tension: 0.2,
      }],
    },
    options: _lineOptions(false, 'rpm', [0, 18000]),
  });
}

export function createGearChart(canvas, labels, data) {
  destroyChart(canvas);
  return new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Rapport',
        data,
        borderColor: '#a78bfa',
        backgroundColor: 'rgba(167,139,250,0.06)',
        fill: true,
        borderWidth: 1.5,
        pointRadius: 0,
        stepped: 'before',
      }],
    },
    options: _lineOptions(false, '', [0, 8]),
  });
}

export function createThrottleBrakeChart(canvas, labels, throttleData, brakeData) {
  destroyChart(canvas);
  return new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Gaz',
          data: throttleData,
          borderColor: '#22c55e',
          backgroundColor: 'rgba(34,197,94,0.12)',
          fill: true,
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0.1,
        },
        {
          label: 'Frein',
          data: brakeData,
          borderColor: '#ef4444',
          backgroundColor: 'rgba(239,68,68,0.12)',
          fill: true,
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0.1,
        },
      ],
    },
    options: _lineOptions(true, '%', [0, 100]),
  });
}

function _lineOptions(showXLabels, unit, suggestedRange) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        mode: 'index',
        intersect: false,
        backgroundColor: 'rgba(17,17,17,0.95)',
        borderColor: 'rgba(255,255,255,0.1)',
        borderWidth: 1,
        titleFont: { size: 10 },
        bodyFont: { size: 11 },
        callbacks: {
          title: items => {
            try { return new Date(items[0].label).toISOString().slice(11, 19); } catch { return items[0].label; }
          },
          label: ctx => ` ${ctx.dataset.label}: ${ctx.raw}${unit ? ' ' + unit : ''}`,
        },
      },
    },
    scales: {
      x: makeTimeScale(showXLabels),
      y: {
        ...COMMON_SCALE,
        min: suggestedRange?.[0],
        max: suggestedRange?.[1],
        ticks: { ...COMMON_SCALE.ticks, maxTicksLimit: 4 },
      },
    },
  };
}

/* ── Live chart update ── */
export function pushPoint(chart, label, ...values) {
  const MAX = 300;
  chart.data.labels.push(label);
  if (chart.data.labels.length > MAX) chart.data.labels.shift();
  chart.data.datasets.forEach((ds, i) => {
    ds.data.push(values[i] ?? null);
    if (ds.data.length > MAX) ds.data.shift();
  });
  chart.update('none');
}

/* ── Tyre strategy (SVG-based Gantt) ── */
export function renderTyreStrategy(container, strategies, driverMap) {
  if (!strategies?.length) {
    container.innerHTML = '<div class="empty-state"><p>Pas de données pneus disponibles</p></div>';
    return;
  }

  const ROW_H  = 26;
  const LABEL_W = 52;
  const PAD    = 8;

  // Find total laps
  let maxLap = 1;
  for (const s of strategies) {
    for (const st of s.stints) {
      if (st.lap_end && st.lap_end > maxLap) maxLap = st.lap_end;
    }
  }

  const W = container.clientWidth || 600;
  const chartW = W - LABEL_W - PAD * 2;
  const H = strategies.length * ROW_H + 28;

  const lapToX = lap => LABEL_W + PAD + ((lap - 1) / Math.max(maxLap - 1, 1)) * chartW;

  let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" style="font-family:Inter,sans-serif;display:block">`;

  // Background
  svg += `<rect width="${W}" height="${H}" fill="#111"/>`;

  // Lap axis labels
  for (let l = 1; l <= maxLap; l += Math.ceil(maxLap / 10)) {
    const x = lapToX(l);
    svg += `<text x="${x}" y="${H - 6}" fill="#555" font-size="10" text-anchor="middle">${l}</text>`;
    svg += `<line x1="${x}" y1="0" x2="${x}" y2="${H - 16}" stroke="rgba(255,255,255,0.04)"/>`;
  }

  // Rows
  strategies.forEach((s, row) => {
    const y    = row * ROW_H + 4;
    const code = driverMap?.[s.driver_number]?.name_acronym || `#${s.driver_number}`;

    svg += `<text x="${LABEL_W - 4}" y="${y + ROW_H / 2 + 4}" fill="#888" font-size="10"
      text-anchor="end" font-weight="600">${code}</text>`;

    for (const st of s.stints) {
      if (!st.lap_start) continue;
      const x1 = lapToX(st.lap_start);
      const x2 = lapToX((st.lap_end || maxLap) + 1);
      const w  = Math.max(x2 - x1, 2);
      const abbr = (st.compound || '?')[0];

      svg += `<rect x="${x1}" y="${y + 2}" width="${w}" height="${ROW_H - 6}"
        rx="3" fill="${st.compound_color || '#555'}" opacity="0.9"/>`;

      if (w > 20) {
        svg += `<text x="${x1 + w / 2}" y="${y + ROW_H / 2 + 4}" fill="${st.compound_text_color || '#fff'}"
          font-size="9" font-weight="700" text-anchor="middle">${abbr}</text>`;
      }
    }
  });

  svg += '</svg>';
  container.innerHTML = svg;
}
