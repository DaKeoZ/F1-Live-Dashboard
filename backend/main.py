"""
F1 Live Dashboard — Backend API
Point d'entrée FastAPI.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx

from api_client import get_constructor_standings, get_driver_standings
from models import ConstructorStandingsResponse, DriverStandingsResponse

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
