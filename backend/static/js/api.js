/**
 * API client — fetch wrappers + WebSocket manager
 */

const BASE = '';  // même origine que la SPA

async function get(path) {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new Error(`HTTP ${res.status} — ${path}`);
  return res.json();
}

export async function fetchDriverStandings(season = 'current') {
  return get(`/standings/drivers?season=${season}`);
}

export async function fetchConstructorStandings(season = 'current') {
  return get(`/standings/constructors?season=${season}`);
}

export async function fetchNextRace() {
  return get('/race/next');
}

export async function fetchLastRace() {
  return get('/race/last');
}

export async function fetchSessions(year) {
  return get(`/telemetry/sessions?year=${year}&limit=200`);
}

export async function fetchDrivers(sessionKey) {
  return get(`/telemetry/drivers/${sessionKey}`);
}

export async function fetchTelemetry(sessionKey, driverNumber, sampleSize = 500, mode = 'uniform') {
  return get(`/telemetry/${sessionKey}/${driverNumber}?sample_size=${sampleSize}&mode=${mode}`);
}

export async function fetchLastPositions(sessionKey) {
  return get(`/location/${sessionKey}`);
}

export async function fetchCarPath(sessionKey, driverNumber) {
  return get(`/location/${sessionKey}/${driverNumber}?sample_size=800`);
}

export async function fetchTyreStints(sessionKey) {
  return get(`/tyres/${sessionKey}`);
}

export async function fetchRaceSchedule(season = 'current') {
  return get(`/race/schedule?season=${season}`);
}

export async function fetchRaceResults(round, season = 'current') {
  return get(`/race/${round}?season=${season}`);
}

export async function fetchLiveCapable() {
  try { return get('/telemetry/live-capable'); }
  catch { return { live_mqtt: false }; }
}

/**
 * WebSocket manager — single connection, auto-reconnect
 */
export class TelemetryWS {
  constructor(sessionKey, driverNumber, onMessage) {
    this._key = sessionKey;
    this._drv = driverNumber;
    this._cb  = onMessage;
    this._ws  = null;
    this._dead = false;
  }

  connect() {
    if (this._dead) return;
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const url   = `${proto}://${location.host}/ws/telemetry/${this._key}/${this._drv}`;
    this._ws = new WebSocket(url);

    this._ws.onmessage = (e) => {
      try { this._cb(JSON.parse(e.data)); } catch {}
    };

    this._ws.onclose = () => {
      if (!this._dead) setTimeout(() => this.connect(), 3000);
    };

    this._ws.onerror = () => this._ws.close();
  }

  close() {
    this._dead = true;
    this._ws?.close();
  }
}
