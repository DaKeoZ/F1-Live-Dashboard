"""
Client HTTP pour récupérer les données F1 via l'API Jolpica (compatible Ergast MRE).
Documentation : https://api.jolpi.ca/
"""

import httpx

from models import (
    ConstructorInfo,
    ConstructorStanding,
    ConstructorStandingsResponse,
    DriverInfo,
    DriverStanding,
    DriverStandingsResponse,
)

BASE_URL = "https://api.jolpi.ca/ergast/f1"
TIMEOUT = 10.0


def _get(url: str) -> dict:
    """Effectue une requête GET et retourne le JSON parsé."""
    with httpx.Client(timeout=TIMEOUT) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()


# ---------------------------------------------------------------------------
# Parsers — transforment le JSON brut en objets Pydantic
# ---------------------------------------------------------------------------


def _parse_driver_standing(raw: dict) -> DriverStanding:
    """Convertit une entrée brute DriverStandings en modèle Pydantic."""
    driver_raw = raw["Driver"]
    constructors = raw.get("Constructors", [])
    constructor_name = constructors[0]["name"] if constructors else "Unknown"

    return DriverStanding(
        position=int(raw["position"]),
        points=float(raw["points"]),
        wins=int(raw["wins"]),
        constructor_name=constructor_name,
        driver=DriverInfo(
            driver_id=driver_raw["driverId"],
            code=driver_raw.get("code"),
            number=driver_raw.get("permanentNumber"),
            first_name=driver_raw["givenName"],
            last_name=driver_raw["familyName"],
            nationality=driver_raw["nationality"],
        ),
    )


def _parse_constructor_standing(raw: dict) -> ConstructorStanding:
    """Convertit une entrée brute ConstructorStandings en modèle Pydantic."""
    constructor_raw = raw["Constructor"]

    return ConstructorStanding(
        position=int(raw["position"]),
        points=float(raw["points"]),
        wins=int(raw["wins"]),
        constructor=ConstructorInfo(
            constructor_id=constructor_raw["constructorId"],
            name=constructor_raw["name"],
            nationality=constructor_raw["nationality"],
        ),
    )


# ---------------------------------------------------------------------------
# Fonctions publiques
# ---------------------------------------------------------------------------


def get_driver_standings(season: str = "current") -> DriverStandingsResponse:
    """
    Retourne le classement des pilotes pour une saison donnée.

    Args:
        season: Année de la saison (ex: '2025') ou 'current' pour la saison en cours.
    """
    url = f"{BASE_URL}/{season}/driverstandings.json"
    data = _get(url)

    standings_table = data["MRData"]["StandingsTable"]
    standings_lists = standings_table.get("StandingsLists", [])

    if not standings_lists:
        return DriverStandingsResponse(
            season=standings_table.get("season", season),
            round=None,
            total=0,
            standings=[],
        )

    standings_list = standings_lists[0]
    parsed = [_parse_driver_standing(entry) for entry in standings_list.get("DriverStandings", [])]

    return DriverStandingsResponse(
        season=standings_list.get("season", season),
        round=int(standings_list["round"]) if standings_list.get("round") else None,
        total=len(parsed),
        standings=parsed,
    )


def get_constructor_standings(season: str = "current") -> ConstructorStandingsResponse:
    """
    Retourne le classement des constructeurs pour une saison donnée.

    Args:
        season: Année de la saison (ex: '2025') ou 'current' pour la saison en cours.
    """
    url = f"{BASE_URL}/{season}/constructorstandings.json"
    data = _get(url)

    standings_table = data["MRData"]["StandingsTable"]
    standings_lists = standings_table.get("StandingsLists", [])

    if not standings_lists:
        return ConstructorStandingsResponse(
            season=standings_table.get("season", season),
            round=None,
            total=0,
            standings=[],
        )

    standings_list = standings_lists[0]
    parsed = [_parse_constructor_standing(entry) for entry in standings_list.get("ConstructorStandings", [])]

    return ConstructorStandingsResponse(
        season=standings_list.get("season", season),
        round=int(standings_list["round"]) if standings_list.get("round") else None,
        total=len(parsed),
        standings=parsed,
    )
