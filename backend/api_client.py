"""
Client HTTP pour récupérer les données F1 via l'API Jolpica (compatible Ergast MRE).
Documentation : https://api.jolpi.ca/
"""

import httpx
from typing import Any

BASE_URL = "https://api.jolpi.ca/ergast/f1"
TIMEOUT = 10.0


def _get(url: str) -> dict[str, Any]:
    """Effectue une requête GET et retourne le JSON parsé."""
    with httpx.Client(timeout=TIMEOUT) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()


def get_driver_standings(season: str = "current") -> list[dict[str, Any]]:
    """
    Retourne le classement des pilotes pour une saison donnée.

    Args:
        season: Année de la saison (ex: '2025') ou 'current' pour la saison en cours.

    Returns:
        Liste des standings pilotes avec leurs informations.
    """
    url = f"{BASE_URL}/{season}/driverstandings.json"
    data = _get(url)

    standings_table = data["MRData"]["StandingsTable"]
    standings_lists = standings_table.get("StandingsLists", [])

    if not standings_lists:
        return []

    return standings_lists[0].get("DriverStandings", [])
