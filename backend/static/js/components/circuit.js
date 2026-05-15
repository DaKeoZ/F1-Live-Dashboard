/**
 * Circuit canvas renderer
 * Normalise correctement les coordonnées OpenF1 en préservant le ratio d'aspect.
 * Y est inversé (canvas Y↓, OpenF1 Y↑).
 */

// Chargement du référentiel de virages — import dynamique pour ne pas bloquer
// le graphe de modules si le fichier est absent (graceful degradation)
let CIRCUIT_TURN_COUNTS = {};
try {
  const mod = await import('../data/circuit_turns.js');
  CIRCUIT_TURN_COUNTS = mod.CIRCUIT_TURN_COUNTS ?? {};
} catch {
  // Sans données : la détection tourne sans contrainte de comptage officiel
}

export class CircuitRenderer {
  constructor(canvas) {
    this._canvas = canvas;
    this._ctx    = canvas.getContext('2d');
    this._path   = [];   // [{cx, cy}] canvas coords (full multi-lap path)
    this._drivers = [];  // [{x, y, code, color}] raw GPS
    this._minX = 0; this._maxX = 1;
    this._minY = 0; this._maxY = 1;
    this._scale = 1;
    this._offX = 0;  this._offY = 0;
    this._animFrame = null;
    this._circuitName = null;
    this._turns = [];  // [{num, idx}] — idx into this._path (first lap slice)

    const ro = new ResizeObserver(() => this._resize());
    ro.observe(canvas.parentElement);
    this._resize();
  }

  _resize() {
    const parent = this._canvas.parentElement;
    const w = parent.clientWidth || 400;
    const h = Math.min(w, 460);
    this._canvas.width  = w;
    this._canvas.height = h;
    this._computeTransform();
    this.draw();
  }

  setPath(rawPoints) {
    if (!rawPoints?.length) return;
    this._rawPath = rawPoints;
    this._computeBounds(rawPoints);
    this._computeTransform();
    this._turns = this._detectTurns();
    this.draw();
  }

  setCircuit(name) {
    this._circuitName = name || null;
    if (this._path.length) {
      this._turns = this._detectTurns();
      this.draw();
    }
  }

  updateDrivers(driversArray) {
    this._drivers = driversArray;
    this.draw();
  }

  _computeBounds(points) {
    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;
    for (const p of points) {
      if (p.x < minX) minX = p.x;
      if (p.x > maxX) maxX = p.x;
      if (p.y < minY) minY = p.y;
      if (p.y > maxY) maxY = p.y;
    }
    this._minX = minX; this._maxX = maxX;
    this._minY = minY; this._maxY = maxY;
  }

  _computeTransform() {
    if (!this._rawPath?.length) return;
    const PAD = 40;
    const W   = this._canvas.width  - PAD * 2;
    const H   = this._canvas.height - PAD * 2;
    const rangeX = (this._maxX - this._minX) || 1;
    const rangeY = (this._maxY - this._minY) || 1;

    const scale = Math.min(W / rangeX, H / rangeY);
    this._scale = scale;
    this._offX = PAD + (W - rangeX * scale) / 2;
    this._offY = PAD + (H - rangeY * scale) / 2;

    this._path = (this._rawPath || []).map(p => ({
      cx: this._toCanvasX(p.x),
      cy: this._toCanvasY(p.y),
    }));
  }

  _toCanvasX(x) {
    return (x - this._minX) * this._scale + this._offX;
  }

  _toCanvasY(y) {
    return (this._maxY - y) * this._scale + this._offY;
  }

  /* ── Find where the multi-lap path completes its first lap ── */
  _findFirstLapEnd() {
    const path = this._path;
    const n    = path.length;
    const p0   = path[0];

    // 8% of canvas diagonal as proximity threshold
    const diagLen   = Math.sqrt(this._canvas.width ** 2 + this._canvas.height ** 2);
    const threshold = diagLen * 0.08;
    const minStart  = Math.floor(n * 0.10); // must advance at least 10% first

    for (let i = minStart; i < n; i++) {
      const dx = path[i].cx - p0.cx;
      const dy = path[i].cy - p0.cy;
      if (Math.sqrt(dx * dx + dy * dy) < threshold) {
        return i;
      }
    }
    return n; // single-lap path or no return found
  }

  /* ── Turn detection on one lap ── */
  _detectTurns() {
    const full = this._path;
    if (full.length < 20) return [];

    // Extract first lap only (the path covers ~6 laps — avoid duplicate detections)
    const lapEnd = this._findFirstLapEnd();
    const path   = full.slice(0, lapEnd);
    const m      = path.length;
    if (m < 20) return [];

    // 1. Angular change at each point (scale is uniform → angles preserved in canvas space)
    const curv = new Array(m).fill(0);
    for (let i = 1; i < m - 1; i++) {
      const dx1 = path[i].cx   - path[i-1].cx;
      const dy1 = path[i].cy   - path[i-1].cy;
      const dx2 = path[i+1].cx - path[i].cx;
      const dy2 = path[i+1].cy - path[i].cy;
      const cross = Math.abs(dx1 * dy2 - dy1 * dx2);
      const dot   = dx1 * dx2 + dy1 * dy2;
      curv[i] = Math.atan2(cross, Math.max(dot, 0));
    }

    // 2. Smooth (window ±7)
    const W = 7;
    const smooth = curv.map((_, i) => {
      let s = 0, c = 0;
      for (let j = Math.max(0, i - W); j <= Math.min(m - 1, i + W); j++) {
        s += curv[j]; c++;
      }
      return s / c;
    });

    // 3. Local maxima above threshold
    const THRESH  = 0.05;
    const MIN_SEP = Math.max(4, Math.floor(m / 120));
    const peaks   = [];
    for (let i = 1; i < m - 1; i++) {
      if (smooth[i] >= THRESH && smooth[i] >= smooth[i - 1] && smooth[i] > smooth[i + 1]) {
        peaks.push({ idx: i, val: smooth[i] });
      }
    }
    if (!peaks.length) return [];

    // 4. Cluster nearby peaks, keep sharpest per cluster
    const clustered = [];
    let cluster = [peaks[0]];
    for (let i = 1; i < peaks.length; i++) {
      if (peaks[i].idx - cluster[cluster.length - 1].idx < MIN_SEP) {
        cluster.push(peaks[i]);
      } else {
        clustered.push(cluster.reduce((m, p) => (p.val > m.val ? p : m)));
        cluster = [peaks[i]];
      }
    }
    clustered.push(cluster.reduce((m, p) => (p.val > m.val ? p : m)));

    // 5. Trim to expected count (keep highest-curvature peaks)
    const name     = (this._circuitName || '').toLowerCase().trim();
    const expected = CIRCUIT_TURN_COUNTS[name];
    let selected   = clustered;
    if (expected && clustered.length > expected) {
      selected = [...clustered]
        .sort((a, b) => b.val - a.val)
        .slice(0, expected)
        .sort((a, b) => a.idx - b.idx);
    }
    if (!selected.length) return [];

    // 6. Find the longest gap between consecutive peaks → approximates S/F straight
    let maxGap = 0;
    let sfAfter = 0;
    for (let i = 0; i < selected.length; i++) {
      const curr = selected[i].idx;
      const next = selected[(i + 1) % selected.length].idx;
      const gap  = i < selected.length - 1
        ? next - curr
        : (m - curr) + selected[0].idx;
      if (gap > maxGap) { maxGap = gap; sfAfter = (i + 1) % selected.length; }
    }

    // 7. T1 = selected[sfAfter], T2 = next, ...
    return selected.map((p, i) => ({
      num: ((i - sfAfter + selected.length) % selected.length) + 1,
      idx: p.idx,  // index into the single-lap slice (valid as-is in this._path)
    })).sort((a, b) => a.num - b.num);
  }

  draw() {
    const ctx = this._ctx;
    const W   = this._canvas.width;
    const H   = this._canvas.height;

    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#0d0d0d';
    ctx.fillRect(0, 0, W, H);

    if (!this._path.length) {
      ctx.fillStyle = '#444';
      ctx.font = '13px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Circuit en cours de chargement…', W / 2, H / 2);
      return;
    }

    // Outer stroke
    ctx.beginPath();
    ctx.moveTo(this._path[0].cx, this._path[0].cy);
    for (const p of this._path) ctx.lineTo(p.cx, p.cy);
    ctx.strokeStyle = 'rgba(255,255,255,0.18)';
    ctx.lineWidth = 8;
    ctx.lineJoin = 'round';
    ctx.lineCap  = 'round';
    ctx.stroke();

    // Inner white line
    ctx.beginPath();
    ctx.moveTo(this._path[0].cx, this._path[0].cy);
    for (const p of this._path) ctx.lineTo(p.cx, p.cy);
    ctx.strokeStyle = 'rgba(255,255,255,0.55)';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Turn numbers (use first-lap indices — same GPS coordinates as later laps)
    for (const turn of this._turns) {
      const p = this._path[turn.idx];
      if (!p) continue;
      ctx.beginPath();
      ctx.arc(p.cx, p.cy, 9, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(0,0,0,0.78)';
      ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,0.55)';
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 7px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(String(turn.num), p.cx, p.cy);
    }

    // Drivers
    for (const d of this._drivers) {
      const cx = this._toCanvasX(d.x);
      const cy = this._toCanvasY(d.y);
      const color = d.color || '#888';

      ctx.beginPath();
      ctx.arc(cx, cy, 10, 0, Math.PI * 2);
      ctx.fillStyle = color + '33';
      ctx.fill();

      ctx.beginPath();
      ctx.arc(cx, cy, 7, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = 'rgba(0,0,0,0.6)';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      ctx.fillStyle = '#fff';
      ctx.font = 'bold 8px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(d.code || '?', cx, cy);
    }
  }

  destroy() {
    if (this._animFrame) cancelAnimationFrame(this._animFrame);
  }
}
