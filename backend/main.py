"""
F1 Live Dashboard — Backend API
Point d'entrée FastAPI. Sert aussi la SPA frontend via StaticFiles.
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import httpx

from api_client import get_constructor_standings, get_driver_standings, get_last_race_results, get_next_race
from database import init_db
from models import (
    AllDriversPositionResponse,
    AllTyreStrategiesResponse,
    CarPathResponse,
    ConstructorStandingsResponse,
    DriverStandingsResponse,
    LastRaceResponse,
    NextRaceResponse,
    OpenF1Driver,
    OpenF1Session,
    TelemetryResponse,
    TyreStrategyResponse,
)
from live_mqtt_bridge import TelemetrySessionMqttBridge
from telemetry_service import (
    _get_openf1_bearer_token,
    get_all_tyre_stints,
    get_car_path,
    get_last_positions,
    get_openf1_drivers,
    get_openf1_sessions,
    get_telemetry,
    get_tyre_stints,
)

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="F1 Live Dashboard API",
    description="API backend pour le F1 Live Dashboard — données pilotes, équipes et courses.",
    version="0.4.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_SEASON_QUERY = Query(
    default="current",
    description="Saison F1 (ex: '2025') ou 'current' pour la saison en cours.",
)


def _handle_httpx_errors(exc: Exception) -> None:
    if isinstance(exc, httpx.HTTPStatusError):
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Erreur API F1 : {exc.response.text}",
        ) from exc
    raise HTTPException(
        status_code=503,
        detail=f"Impossible de joindre l'API F1 : {exc}",
    ) from exc


@app.get("/api/status")
def api_status():
    return {"message": "F1 Live Dashboard API", "version": "0.4.0", "docs": "/docs"}


@app.get("/standings/drivers", response_model=DriverStandingsResponse)
def driver_standings(season: str = _SEASON_QUERY):
    try:
        return get_driver_standings(season=season)
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        _handle_httpx_errors(exc)


@app.get("/standings/constructors", response_model=ConstructorStandingsResponse)
def constructor_standings(season: str = _SEASON_QUERY):
    try:
        return get_constructor_standings(season=season)
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        _handle_httpx_errors(exc)


# ── Positions GPS ─────────────────────────────────────────────────────────────

@app.get("/location/{session_key}", response_model=AllDriversPositionResponse)
def last_positions(session_key: int):
    try:
        return get_last_positions(session_key=session_key)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        _handle_httpx_errors(exc)


@app.get("/location/{session_key}/{driver_number}", response_model=CarPathResponse)
def car_path(
    session_key: int,
    driver_number: int,
    sample_size: int = Query(default=800, ge=50, le=2000),
):
    try:
        return get_car_path(session_key=session_key, driver_number=driver_number, sample_size=sample_size)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        _handle_httpx_errors(exc)


# ── Stratégie Pneumatiques ────────────────────────────────────────────────────

@app.get("/tyres/{session_key}/{driver_number}", response_model=TyreStrategyResponse)
def tyre_strategy_single(session_key: int, driver_number: int):
    try:
        return get_tyre_stints(session_key=session_key, driver_number=driver_number)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        _handle_httpx_errors(exc)


@app.get("/tyres/{session_key}", response_model=AllTyreStrategiesResponse)
def tyre_strategy_all(session_key: int):
    try:
        return get_all_tyre_stints(session_key=session_key)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        _handle_httpx_errors(exc)


@app.get("/race/last", response_model=LastRaceResponse)
def last_race_results():
    try:
        result = get_last_race_results()
        if result is None:
            raise HTTPException(status_code=404, detail="Aucun résultat disponible pour la saison en cours.")
        return result
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        _handle_httpx_errors(exc)


# ── Télémétrie OpenF1 ─────────────────────────────────────────────────────────

@app.get("/telemetry/live-capable")
def telemetry_live_capable():
    return {"live_mqtt": bool(_get_openf1_bearer_token())}


@app.websocket("/ws/telemetry/{session_key}/{driver_number}")
async def websocket_telemetry_stream(session_key: int, driver_number: int, websocket: WebSocket):
    await websocket.accept()
    bridge = TelemetrySessionMqttBridge(session_key, driver_number)
    try:
        bridge.start()
    except Exception as exc:
        try:
            await websocket.send_json({"error": str(exc), "type": "mqtt_error"})
        except Exception:
            pass
        await websocket.close(code=4000)
        return
    try:
        while True:
            msg = await asyncio.to_thread(bridge.get_blocking, 0.35)
            if msg is None:
                continue
            await websocket.send_json(msg)
    except WebSocketDisconnect:
        pass
    finally:
        bridge.stop()


@app.get("/telemetry/sessions", response_model=list[OpenF1Session])
def telemetry_sessions(
    year: int | None = Query(default=None),
    session_type: str | None = Query(default=None),
    limit: int = Query(default=150, ge=1, le=500),
):
    try:
        return get_openf1_sessions(year=year, session_type=session_type, limit=limit)
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        _handle_httpx_errors(exc)


@app.get("/telemetry/drivers/{session_key}", response_model=list[OpenF1Driver])
def telemetry_drivers(session_key: int):
    try:
        drivers = get_openf1_drivers(session_key)
        if not drivers:
            raise HTTPException(status_code=404, detail=f"Aucun pilote trouvé pour session_key={session_key}.")
        return drivers
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        _handle_httpx_errors(exc)


@app.get("/telemetry/{session_key}/{driver_number}", response_model=TelemetryResponse)
def telemetry(
    session_key: int,
    driver_number: int,
    sample_size: int = Query(default=500, ge=10, le=2000),
    mode: str = Query(default="uniform"),
):
    try:
        return get_telemetry(
            session_key=session_key,
            driver_number=driver_number,
            sample_size=sample_size,
            mode=mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        _handle_httpx_errors(exc)


@app.get("/race/next", response_model=NextRaceResponse)
def next_race():
    try:
        result = get_next_race()
        if result is None:
            raise HTTPException(status_code=404, detail="Aucune prochaine course trouvée — saison terminée.")
        return result
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        _handle_httpx_errors(exc)


# ── SPA Frontend (doit être monté en dernier) ─────────────────────────────────
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
