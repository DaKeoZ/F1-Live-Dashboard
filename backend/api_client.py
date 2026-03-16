"""
Client HTTP pour récupérer les données F1 via l'API Jolpica (compatible Ergast MRE).
Documentation : https://api.jolpi.ca/
"""

from datetime import datetime, timezone

import httpx

from models import (
    Circuit,
    CircuitLocation,
    ConstructorInfo,
    ConstructorStanding,
    ConstructorStandingsResponse,
    Countdown,
    DriverInfo,
    DriverStanding,
    DriverStandingsResponse,
    LastRaceResponse,
    NextRaceResponse,
    RaceResultEntry,
    SessionInfo,
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


def get_next_race() -> NextRaceResponse | None:
    """
    Identifie la prochaine course de la saison courante à partir de la date actuelle
    et retourne ses détails avec un compte à rebours vers la session imminente.

    Returns:
        NextRaceResponse ou None si la saison est terminée.
    """
    url = f"{BASE_URL}/current.json"
    data = _get(url)
    races: list[dict] = data["MRData"]["RaceTable"]["Races"]
    now_utc = datetime.now(timezone.utc)

    next_race_raw = _find_next_race(races, now_utc)
    if next_race_raw is None:
        return None

    return _parse_next_race(next_race_raw, now_utc)


def _find_next_race(races: list[dict], now_utc: datetime) -> dict | None:
    """Retourne la première course dont la date de course est >= aujourd'hui UTC."""
    for race in races:
        race_dt = _parse_session_dt(race["date"], race.get("time", "00:00:00Z"))
        if race_dt >= now_utc:
            return race
    return None


def _parse_session_dt(date_str: str, time_str: str) -> datetime:
    """Combine une date ISO et une heure UTC en datetime aware."""
    raw = f"{date_str}T{time_str.rstrip('Z')}+00:00"
    return datetime.fromisoformat(raw)


def _build_countdown(sessions: dict[str, datetime], now_utc: datetime) -> Countdown:
    """
    Sélectionne la session imminente (la plus proche dans le futur)
    et calcule le compte à rebours.
    """
    future_sessions = {name: dt for name, dt in sessions.items() if dt > now_utc}

    if not future_sessions:
        # Toutes les sessions sont passées — on pointe vers la course par défaut
        target_name = "Race"
        target_dt = sessions["Race"]
    else:
        target_name = min(future_sessions, key=lambda n: future_sessions[n])
        target_dt = future_sessions[target_name]

    delta = target_dt - now_utc
    total_seconds = max(0, int(delta.total_seconds()))
    total_minutes, secs = divmod(total_seconds, 60)
    total_hours, mins = divmod(total_minutes, 60)
    days, hours = divmod(total_hours, 24)

    return Countdown(
        target_session=target_name,
        target_datetime_utc=target_dt,
        days=days,
        hours=hours,
        minutes=mins,
        total_seconds=total_seconds,
    )


def _parse_next_race(raw: dict, now_utc: datetime) -> NextRaceResponse:
    """Convertit une entrée brute de course en NextRaceResponse avec compte à rebours."""
    circuit_raw = raw["Circuit"]
    loc_raw = circuit_raw["Location"]

    circuit = Circuit(
        circuit_id=circuit_raw["circuitId"],
        name=circuit_raw["circuitName"],
        location=CircuitLocation(
            locality=loc_raw["locality"],
            country=loc_raw["country"],
            lat=float(loc_raw["lat"]),
            long=float(loc_raw["long"]),
        ),
    )

    race_dt = _parse_session_dt(raw["date"], raw.get("time", "00:00:00Z"))
    qual_raw = raw["Qualifying"]
    qual_dt = _parse_session_dt(qual_raw["date"], qual_raw.get("time", "00:00:00Z"))

    sessions: dict[str, datetime] = {
        "Qualifying": qual_dt,
        "Race": race_dt,
    }

    sprint: SessionInfo | None = None
    sprint_qualifying: SessionInfo | None = None

    if "Sprint" in raw:
        sprint_dt = _parse_session_dt(raw["Sprint"]["date"], raw["Sprint"].get("time", "00:00:00Z"))
        sprint = SessionInfo(datetime_utc=sprint_dt)
        sessions["Sprint"] = sprint_dt

    if "SprintQualifying" in raw:
        sq_dt = _parse_session_dt(raw["SprintQualifying"]["date"], raw["SprintQualifying"].get("time", "00:00:00Z"))
        sprint_qualifying = SessionInfo(datetime_utc=sq_dt)
        sessions["SprintQualifying"] = sq_dt

    return NextRaceResponse(
        season=raw["season"],
        round=int(raw["round"]),
        race_name=raw["raceName"],
        circuit=circuit,
        race=SessionInfo(datetime_utc=race_dt),
        qualifying=SessionInfo(datetime_utc=qual_dt),
        sprint=sprint,
        sprint_qualifying=sprint_qualifying,
        countdown=_build_countdown(sessions, now_utc),
    )


def get_last_race_results() -> LastRaceResponse | None:
    """
    Retourne les résultats complets de la dernière course disputée.
    Utilise l'alias /current/last de l'API Jolpica.
    """
    url = f"{BASE_URL}/current/last/results.json"
    data = _get(url)
    races: list[dict] = data["MRData"]["RaceTable"].get("Races", [])
    if not races:
        return None
    return _parse_last_race(races[0])


def _parse_result_entry(raw: dict) -> RaceResultEntry:
    driver = raw["Driver"]
    constructor = raw["Constructor"]

    time_raw = raw.get("Time", {})
    time_or_status = time_raw.get("time") or raw.get("status", "—")

    fastest_lap_raw = raw.get("FastestLap")
    fastest_lap_time = fastest_lap_rank = None
    if fastest_lap_raw:
        fastest_lap_time = fastest_lap_raw.get("Time", {}).get("time")
        fastest_lap_rank = int(fastest_lap_raw["rank"]) if fastest_lap_raw.get("rank") else None

    return RaceResultEntry(
        position=int(raw["position"]),
        driver_code=driver.get("code"),
        driver_name=f"{driver['givenName']} {driver['familyName']}",
        constructor_name=constructor["name"],
        grid=int(raw.get("grid", 0)),
        laps=int(raw.get("laps", 0)),
        time_or_status=time_or_status,
        points=float(raw.get("points", 0)),
        fastest_lap_time=fastest_lap_time,
        fastest_lap_rank=fastest_lap_rank,
    )


def _parse_last_race(raw: dict) -> LastRaceResponse:
    circuit_raw = raw["Circuit"]
    loc_raw = circuit_raw["Location"]

    circuit = Circuit(
        circuit_id=circuit_raw["circuitId"],
        name=circuit_raw["circuitName"],
        location=CircuitLocation(
            locality=loc_raw["locality"],
            country=loc_raw["country"],
            lat=float(loc_raw["lat"]),
            long=float(loc_raw["long"]),
        ),
    )

    return LastRaceResponse(
        season=raw["season"],
        round=int(raw["round"]),
        race_name=raw["raceName"],
        circuit=circuit,
        date=raw["date"],
        results=[_parse_result_entry(r) for r in raw.get("Results", [])],
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
