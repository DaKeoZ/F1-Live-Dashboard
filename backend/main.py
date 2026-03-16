"""
F1 Live Dashboard — Backend API
Point d'entrée FastAPI.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx

from api_client import get_constructor_standings, get_driver_standings, get_last_race_results, get_next_race
from models import ConstructorStandingsResponse, DriverStandingsResponse, LastRaceResponse, NextRaceResponse

app = FastAPI(
    title="F1 Live Dashboard API",
    description="API backend pour le F1 Live Dashboard — données pilotes, équipes et courses.",
    version="0.2.0",
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
