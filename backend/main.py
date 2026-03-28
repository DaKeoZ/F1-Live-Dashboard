"""
F1 Live Dashboard — Backend API
Point d'entrée FastAPI.
"""

import asyncio

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import httpx

from api_client import get_constructor_standings, get_driver_standings, get_last_race_results, get_next_race
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
from live_mqtt_bridge import CarDataMqttBridge
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

app = FastAPI(
    title="F1 Live Dashboard API",
    description="API backend pour le F1 Live Dashboard — données pilotes, équipes et courses.",
    version="0.3.0",
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
    """Convertit les erreurs httpx en HTTPException FastAPI."""
    if isinstance(exc, httpx.HTTPStatusError):
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Erreur API F1 : {exc.response.text}",
        ) from exc
    raise HTTPException(
        status_code=503,
        detail=f"Impossible de joindre l'API F1 : {exc}",
    ) from exc


@app.get("/")
def root():
    return {"message": "F1 Live Dashboard API", "version": "0.2.0", "docs": "/docs"}


@app.get("/standings/drivers", response_model=DriverStandingsResponse)
def driver_standings(season: str = _SEASON_QUERY):
    """
    Classement des pilotes pour une saison donnée.
    Données validées et structurées via Pydantic.
    """
    try:
        return get_driver_standings(season=season)
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        _handle_httpx_errors(exc)


@app.get("/standings/constructors", response_model=ConstructorStandingsResponse)
def constructor_standings(season: str = _SEASON_QUERY):
    """
    Classement des constructeurs pour une saison donnée.
    Données validées et structurées via Pydantic.
    """
    try:
        return get_constructor_standings(season=season)
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        _handle_httpx_errors(exc)


# ── Positions GPS ─────────────────────────────────────────────────────────────

@app.get("/location/{session_key}", response_model=AllDriversPositionResponse)
def last_positions(session_key: int):
    """
    Retourne la dernière position GPS connue de tous les pilotes d'une session.

    Les coordonnées x, y sont dans le référentiel du circuit (unités arbitraires OpenF1).
    La coordonnée z représente l'altitude normalisée.

    Stratégie d'acquisition :
    - Fenêtre temporelle = 60 % de la durée de session (évite de charger la totalité des données).
    - Requêtes concurrentes (max 3 workers) avec 3 passes de retry pour contourner le rate-limiting.
    - Cache côté client recommandé : 60 s (données quasi-statiques pour une session terminée).
    """
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
    sample_size: int = Query(
        default=500,
        ge=50,
        le=2000,
        description="Nombre de points du tracé retournés (pour dessiner le contour du circuit).",
    ),
):
    """
    Retourne le tracé GPS sous-échantillonné d'un pilote sur l'ensemble de la session.
    Utile pour dessiner le contour du circuit en fond de la carte de positions.
    """
    try:
        return get_car_path(session_key=session_key, driver_number=driver_number, sample_size=sample_size)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        _handle_httpx_errors(exc)


# ── Stratégie Pneumatiques ────────────────────────────────────────────────────

@app.get("/tyres/{session_key}/{driver_number}", response_model=TyreStrategyResponse)
def tyre_strategy_single(session_key: int, driver_number: int):
    """
    Retourne la stratégie pneumatiques d'un pilote pour une session OpenF1.

    Chaque stint contient : compound, couleur officielle, tour de départ/fin,
    âge des pneus au départ et nombre de tours effectués.
    """
    try:
        return get_tyre_stints(session_key=session_key, driver_number=driver_number)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        _handle_httpx_errors(exc)


@app.get("/tyres/{session_key}", response_model=AllTyreStrategiesResponse)
def tyre_strategy_all(session_key: int):
    """
    Retourne la stratégie pneumatiques de TOUS les pilotes d'une session en un seul appel API.
    Conçu pour alimenter le Gantt de stratégie multi-pilotes.
    """
    try:
        return get_all_tyre_stints(session_key=session_key)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        _handle_httpx_errors(exc)


@app.get("/race/last", response_model=LastRaceResponse)
def last_race_results():
    """
    Retourne les résultats complets de la dernière course disputée.
    Inclut le classement complet, les temps, statuts et meilleurs tours.
    """
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
    """Indique si un jeton OpenF1 est disponible (MQTT / REST authentifiés)."""
    return {"live_mqtt": bool(_get_openf1_bearer_token())}


@app.websocket("/ws/telemetry/{session_key}/{driver_number}")
async def websocket_telemetry_stream(session_key: int, driver_number: int, websocket: WebSocket):
    """
    Relai temps réel : souscription MQTT OpenF1 (v1/car_data) filtrée → messages JSON vers le navigateur.
    Le jeton OAuth2 ne quitte jamais le backend.
    """
    await websocket.accept()
    bridge = CarDataMqttBridge(session_key, driver_number)
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
    year: int | None = Query(default=None, description="Filtrer par année (ex: 2026)"),
    session_type: str | None = Query(default=None, description="Type de session OpenF1 (None = toutes)"),
    limit: int = Query(default=150, ge=1, le=500),
):
    """
    Liste les sessions OpenF1 disponibles, triées de la plus récente à la plus ancienne.
    Utilisé pour alimenter le sélecteur de session dans l'interface.
    """
    try:
        return get_openf1_sessions(year=year, session_type=session_type, limit=limit)
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        _handle_httpx_errors(exc)


@app.get("/telemetry/drivers/{session_key}", response_model=list[OpenF1Driver])
def telemetry_drivers(session_key: int):
    """
    Retourne la liste des pilotes dans une session OpenF1 (triés par numéro de voiture).
    """
    try:
        drivers = get_openf1_drivers(session_key)
        if not drivers:
            raise HTTPException(
                status_code=404,
                detail=f"Aucun pilote trouvé pour session_key={session_key}.",
            )
        return drivers
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        _handle_httpx_errors(exc)


@app.get("/telemetry/{session_key}/{driver_number}", response_model=TelemetryResponse)
def telemetry(
    session_key: int,
    driver_number: int,
    sample_size: int = Query(
        default=200,
        ge=10,
        le=2000,
        description="Nombre de points retournés après échantillonnage.",
    ),
    mode: str = Query(
        default="uniform",
        description=(
            "Stratégie d'échantillonnage :\n"
            "  'uniform' — points équidistants sur toute la session (race overview).\n"
            "  'tail'    — N derniers points chronologiques (lecture live)."
        ),
    ),
):
    """
    Retourne les données de télémétrie voiture (speed, rpm, n_gear, throttle, brake, drs)
    pour un pilote donné sur une session OpenF1, sous-échantillonnées pour la visualisation.

    Les données brutes d'OpenF1 peuvent dépasser 30 000 points par session (≈ 3.7 Hz).
    Le paramètre `sample_size` contrôle le nombre de points retournés (défaut : 100).
    """
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
    """
    Retourne la prochaine course de la saison en cours avec :
    - Nom du Grand Prix, circuit et localisation
    - Horaires UTC de la qualification et de la course (+ sprint si applicable)
    - Compte à rebours (jours / heures / minutes) vers la session imminente
    """
    try:
        result = get_next_race()
        if result is None:
            raise HTTPException(status_code=404, detail="Aucune prochaine course trouvée — saison terminée.")
        return result
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        _handle_httpx_errors(exc)
