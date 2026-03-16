"""
F1 Live Dashboard — Backend API
Point d'entrée FastAPI.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx

from api_client import get_driver_standings

app = FastAPI(
    title="F1 Live Dashboard API",
    description="API backend pour le F1 Live Dashboard — données pilotes, équipes et courses.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "F1 Live Dashboard API", "version": "0.1.0", "docs": "/docs"}


@app.get("/standings/drivers")
def driver_standings(
    season: str = Query(
        default="current",
        description="Saison F1 (ex: '2025') ou 'current' pour la saison en cours.",
    )
):
    """
    Retourne le classement des pilotes pour une saison donnée.
    Données fournies par l'API Jolpica (compatible Ergast MRE).
    """
    try:
        standings = get_driver_standings(season=season)
        return {
            "season": season,
            "total": len(standings),
            "standings": standings,
        }
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Erreur lors de la récupération des données F1 : {exc.response.text}",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Impossible de joindre l'API F1 : {exc}",
        ) from exc
