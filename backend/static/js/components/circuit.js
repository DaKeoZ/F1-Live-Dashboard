/**
 * Circuit canvas renderer
 * Normalise correctement les coordonnées OpenF1 en préservant le ratio d'aspect.
 * Y est inversé (canvas Y↓, OpenF1 Y↑).
 */
export class CircuitRenderer {
  constructor(canvas) {
    this._canvas = canvas;
    this._ctx    = canvas.getContext('2d');
    this._path   = [];   // [{x, y}] normalized to [0,1]
    this._drivers = [];  // [{x, y, code, color}] normalized
    this._minX = 0; this._maxX = 1;
    this._minY = 0; this._maxY = 1;
    this._scaleX = 1; this._scaleY = 1;
    this._offX = 0;  this._offY = 0;
    this._animFrame = null;

    // Resize observer
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
    this.draw();
  }

  updateDrivers(driversArray) {
    // driversArray: [{x, y, code, color}]
    this._drivers = driversArray.map(d => ({
      ...d,
      cx: this._toCanvasX(d.x),
      cy: this._toCanvasY(d.y),
    }));
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

    // Uniform scale to preserve aspect ratio
    const scale = Math.min(W / rangeX, H / rangeY);
    this._scale = scale;

    // Center in canvas
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
    // Flip Y: OpenF1 Y increases upward, canvas Y increases downward
    return (this._maxY - y) * this._scale + this._offY;
  }

  draw() {
    const ctx = this._ctx;
    const W   = this._canvas.width;
    const H   = this._canvas.height;

    ctx.clearRect(0, 0, W, H);

    // Background
    ctx.fillStyle = '#0d0d0d';
    ctx.fillRect(0, 0, W, H);

    if (!this._path.length) {
      ctx.fillStyle = '#444';
      ctx.font = '13px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Circuit en cours de chargement…', W / 2, H / 2);
      return;
    }

    // Draw circuit outline (thick grey)
    ctx.beginPath();
    ctx.moveTo(this._path[0].cx, this._path[0].cy);
    for (const p of this._path) ctx.lineTo(p.cx, p.cy);
    ctx.closePath();
    ctx.strokeStyle = 'rgba(255,255,255,0.18)';
    ctx.lineWidth = 8;
    ctx.lineJoin = 'round';
    ctx.lineCap  = 'round';
    ctx.stroke();

    // Inner white line
    ctx.beginPath();
    ctx.moveTo(this._path[0].cx, this._path[0].cy);
    for (const p of this._path) ctx.lineTo(p.cx, p.cy);
    ctx.closePath();
    ctx.strokeStyle = 'rgba(255,255,255,0.55)';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Draw drivers
    for (const d of this._drivers) {
      const cx = this._toCanvasX(d.x);
      const cy = this._toCanvasY(d.y);
      const color = d.color || '#888';

      // Glow halo
      ctx.beginPath();
      ctx.arc(cx, cy, 10, 0, Math.PI * 2);
      ctx.fillStyle = color + '33';
      ctx.fill();

      // Dot
      ctx.beginPath();
      ctx.arc(cx, cy, 7, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = 'rgba(0,0,0,0.6)';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Label
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
