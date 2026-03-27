"""
Service de télémétrie — interroge l'API OpenF1 pour les données voiture en temps réel.
Documentation : https://openf1.org/

Stratégies d'échantillonnage disponibles :
  - "uniform" : N points équidistants dans la session complète (vue race overview)
  - "tail"    : N derniers points chronologiques (vue live / fin de session)
"""

from __future__ import annotations

import concurrent.futures
import time
from datetime import datetime, timedelta, timezone

import httpx

from models import (
    AllDriversPositionResponse,
    AllTyreStrategiesResponse,
    CarPathPoint,
    CarPathResponse,
    DriverPosition,
    OpenF1Driver,
    OpenF1Session,
    TelemetryPoint,
    TelemetryResponse,
    TyreStint,
    TyreStrategyResponse,
)

OPENF1_BASE = "https://api.openf1.org/v1"

# Timeout généreux : le payload car_data peut dépasser 30 000 points JSON
TIMEOUT_SMALL = 10.0
TIMEOUT_LARGE = 30.0

# ---------------------------------------------------------------------------
# Palette pneumatiques officielle Pirelli F1
# ---------------------------------------------------------------------------

#: Couleur de fond HEX par composé
COMPOUND_COLORS: dict[str, str] = {
    "SOFT":         "#E8002D",
    "MEDIUM":       "#FFF200",
    "HARD":         "#EBEBEB",
    "INTERMEDIATE": "#39B54A",
    "WET":          "#0067FF",
    "UNKNOWN":      "#555555",
}

#: Couleur du texte selon le fond (lisibilité)
COMPOUND_TEXT_COLORS: dict[str, str] = {
    "SOFT":         "#FFFFFF",
    "MEDIUM":       "#000000",
    "HARD":         "#000000",
    "INTERMEDIATE": "#FFFFFF",
    "WET":          "#FFFFFF",
    "UNKNOWN":      "#CCCCCC",
}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _get(url: str, params: dict, timeout: float = TIMEOUT_SMALL) -> list | dict:
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Sampling strategies
# ---------------------------------------------------------------------------


def _uniform_sample(data: list[dict], n: int) -> list[dict]:
    """
    Prélève N points uniformément répartis sur l'ensemble du dataset.
    Garantit que le premier et le dernier point sont toujours inclus.
    """
    if len(data) <= n:
        return data
    step = (len(data) - 1) / (n - 1)
    indices = sorted({round(i * step) for i in range(n)})
    return [data[i] for i in indices]


def _tail_sample(data: list[dict], n: int) -> list[dict]:
    """Prélève les N derniers points chronologiques (lecture live)."""
    return data[-n:] if len(data) > n else data


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _parse_point(raw: dict) -> TelemetryPoint:
    """Convertit un point brut OpenF1 en TelemetryPoint Pydantic."""
    # OpenF1 peut renvoyer des timestamps avec suffixe 'Z' selon les endpoints/points
    # (Python 3.10 ne le parse pas via fromisoformat)
    date_str = str(raw["date"]).replace("Z", "+00:00")
    # OpenF1 peut fournir des valeurs >100 pour brake/throttle (capteurs/normalisation).
    # On clamp pour garantir un contrat stable 0–100 côté dashboard.
    throttle = int(raw.get("throttle") or 0)
    brake = int(raw.get("brake") or 0)
    throttle = 0 if throttle < 0 else (100 if throttle > 100 else throttle)
    brake = 0 if brake < 0 else (100 if brake > 100 else brake)

    return TelemetryPoint(
        timestamp=datetime.fromisoformat(date_str),
        speed=int(raw.get("speed") or 0),
        rpm=int(raw.get("rpm") or 0),
        n_gear=int(raw.get("n_gear") or 0),
        throttle=throttle,
        brake=brake,
        drs=raw.get("drs"),
    )


def _parse_session(raw: dict) -> OpenF1Session:
    return OpenF1Session(
        meeting_key=raw.get("meeting_key"),
        session_key=raw["session_key"],
        session_type=raw.get("session_type"),
        session_name=raw.get("session_name", raw.get("session_type", "—")),
        date_start=datetime.fromisoformat(str(raw["date_start"]).replace("Z", "+00:00")),
        date_end=(
            datetime.fromisoformat(str(raw["date_end"]).replace("Z", "+00:00"))
            if raw.get("date_end")
            else None
        ),
        circuit_short_name=raw.get("circuit_short_name", "—"),
        country_name=raw.get("country_name", "—"),
        year=int(raw.get("year", 0)),
    )


def _parse_driver(raw: dict) -> OpenF1Driver:
    colour = raw.get("team_colour")
    if colour and not colour.startswith("#"):
        colour = f"#{colour}"
    return OpenF1Driver(
        driver_number=int(raw["driver_number"]),
        name_acronym=raw.get("name_acronym", "—"),
        full_name=raw.get("full_name", "—"),
        team_name=raw.get("team_name", "—"),
        team_colour=colour,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_telemetry(
    session_key: int,
    driver_number: int,
    sample_size: int = 100,
    mode: str = "uniform",
) -> TelemetryResponse:
    """
    Retourne les données de télémétrie échantillonnées pour un pilote donné.

    Args:
        session_key:   Clé de session OpenF1 (ex: 11234 pour Melbourne 2026).
        driver_number: Numéro de voiture du pilote.
        sample_size:   Nombre de points à retourner (10–500).
        mode:          "uniform" — points répartis sur toute la session.
                       "tail"    — N derniers points (mode live).

    Returns:
        TelemetryResponse avec métadonnées de sampling et liste de TelemetryPoint.

    Raises:
        httpx.HTTPStatusError: Erreur HTTP depuis OpenF1.
        ValueError:            Réponse API non conforme ou mode invalide.
    """
    if mode not in ("uniform", "tail"):
        raise ValueError(f"Mode inconnu : '{mode}'. Choisir 'uniform' ou 'tail'.")

    # OpenF1 peut renvoyer 404 "No results found." si aucune donnée n'existe
    # (ex: session future, session sans car_data publié, etc.)
    with httpx.Client(timeout=TIMEOUT_LARGE) as client:
        resp = client.get(
            f"{OPENF1_BASE}/car_data",
            params={"session_key": session_key, "driver_number": driver_number},
        )
        if resp.status_code == 404:
            raw_data = []
        else:
            resp.raise_for_status()
            raw_data = resp.json()

    if not isinstance(raw_data, list):
        raise ValueError(
            f"Réponse inattendue de l'API OpenF1 (type={type(raw_data).__name__}). "
            "Vérifiez session_key et driver_number."
        )

    total = len(raw_data)

    if mode == "tail":
        sampled = _tail_sample(raw_data, sample_size)
    else:
        sampled = _uniform_sample(raw_data, sample_size)

    return TelemetryResponse(
        session_key=session_key,
        driver_number=driver_number,
        total_raw_points=total,
        sample_size=len(sampled),
        sample_method=mode,
        points=[_parse_point(p) for p in sampled],
    )


def get_openf1_sessions(
    year: int | None = None,
    session_type: str | None = "Race",
    limit: int = 20,
) -> list[OpenF1Session]:
    """
    Retourne les sessions OpenF1 disponibles, triées de la plus récente à la plus ancienne.

    Args:
        year:         Filtrer par année (None = toutes années).
        session_type: Type de session ("Race", "Qualifying", "Sprint"…).
        limit:        Nombre maximum de sessions à retourner.
    """
    params: dict = {}
    if session_type:
        params["session_type"] = session_type
    if year is not None:
        params["year"] = year

    raw = _get(f"{OPENF1_BASE}/sessions", params=params)
    if not isinstance(raw, list):
        return []

    sessions = [_parse_session(s) for s in raw]
    # Tri décroissant par date
    sessions.sort(key=lambda s: s.date_start, reverse=True)
    return sessions[:limit]


def get_openf1_drivers(session_key: int) -> list[OpenF1Driver]:
    """
    Retourne la liste des pilotes présents dans une session OpenF1.
    Triée par numéro de voiture.
    """
    raw = _get(f"{OPENF1_BASE}/drivers", params={"session_key": session_key})
    if not isinstance(raw, list):
        return []

    drivers = [_parse_driver(d) for d in raw]
    drivers.sort(key=lambda d: d.driver_number)
    return drivers


# ---------------------------------------------------------------------------
# Stints / Stratégie pneumatiques
# ---------------------------------------------------------------------------


def _normalise_compound(compound: str | None) -> str:
    """Normalise le composé en majuscule, remplace None par 'UNKNOWN'."""
    if not compound:
        return "UNKNOWN"
    return compound.strip().upper()


def _parse_stint(raw: dict) -> TyreStint:
    compound_key = _normalise_compound(raw.get("compound"))
    lap_start = int(raw.get("lap_start") or 1)
    lap_end   = int(raw["lap_end"]) if raw.get("lap_end") is not None else None

    return TyreStint(
        stint_number=int(raw.get("stint_number") or 1),
        lap_start=lap_start,
        lap_end=lap_end,
        compound=raw.get("compound"),
        tyre_age_at_start=int(raw.get("tyre_age_at_start") or 0),
        laps_in_stint=(lap_end - lap_start + 1) if lap_end is not None else None,
        compound_color=COMPOUND_COLORS.get(compound_key, COMPOUND_COLORS["UNKNOWN"]),
        compound_text_color=COMPOUND_TEXT_COLORS.get(compound_key, COMPOUND_TEXT_COLORS["UNKNOWN"]),
    )


def get_tyre_stints(session_key: int, driver_number: int) -> TyreStrategyResponse:
    """
    Retourne la stratégie pneumatiques complète d'un pilote sur une session.

    Args:
        session_key:   Clé de session OpenF1.
        driver_number: Numéro de voiture.

    Returns:
        TyreStrategyResponse avec la liste des stints triés chronologiquement.
    """
    raw = _get(
        f"{OPENF1_BASE}/stints",
        params={"session_key": session_key, "driver_number": driver_number},
    )
    if not isinstance(raw, list):
        raise ValueError(f"Réponse inattendue de l'API OpenF1 stints : {type(raw).__name__}")

    stints = sorted([_parse_stint(s) for s in raw], key=lambda s: s.stint_number)

    return TyreStrategyResponse(
        session_key=session_key,
        driver_number=driver_number,
        total_stints=len(stints),
        stints=stints,
    )


def get_all_tyre_stints(session_key: int) -> AllTyreStrategiesResponse:
    """
    Retourne la stratégie pneumatiques de TOUS les pilotes d'une session en un seul appel API.
    Utile pour le Gantt de stratégie multi-pilotes.

    Args:
        session_key: Clé de session OpenF1.

    Returns:
        AllTyreStrategiesResponse contenant la stratégie de chaque pilote.
    """
    raw = _get(f"{OPENF1_BASE}/stints", params={"session_key": session_key})
    if not isinstance(raw, list):
        raise ValueError(f"Réponse inattendue de l'API OpenF1 stints : {type(raw).__name__}")

    # Regrouper par pilote
    by_driver: dict[int, list[dict]] = {}
    for entry in raw:
        dn = int(entry["driver_number"])
        by_driver.setdefault(dn, []).append(entry)

    strategies = [
        TyreStrategyResponse(
            session_key=session_key,
            driver_number=dn,
            total_stints=len(stints_raw),
            stints=sorted([_parse_stint(s) for s in stints_raw], key=lambda s: s.stint_number),
        )
        for dn, stints_raw in sorted(by_driver.items())
    ]

    return AllTyreStrategiesResponse(
        session_key=session_key,
        total_drivers=len(strategies),
        strategies=strategies,
    )


# ---------------------------------------------------------------------------
# Positions GPS — suivi en temps réel
# ---------------------------------------------------------------------------

# Nombre maximum de workers concurrents pour éviter le rate-limiting d'OpenF1
_LOCATION_MAX_WORKERS = 3
# Délai (secondes) entre les passes de retry
_RETRY_DELAY = 0.6
# Nombre maximum de tentatives par pilote
_MAX_RETRIES = 3


def _get_session_info(session_key: int) -> dict:
    """Récupère les infos de session depuis OpenF1 (date_start, date_end…)."""
    raw = _get(f"{OPENF1_BASE}/sessions", params={"session_key": session_key})
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"Session introuvable : session_key={session_key}")
    return raw[0]


def _calc_filter_date(session_info: dict) -> str:
    """
    Calcule la date de filtre pour n'obtenir que la dernière partie de la session
    (60 % du temps écoulé depuis le début).
    Pour une course de 2h, cela correspond aux 48 dernières minutes.
    """
    date_start = datetime.fromisoformat(session_info["date_start"])
    date_end   = datetime.fromisoformat(session_info["date_end"])
    duration   = (date_end - date_start).total_seconds()
    filter_dt  = date_start.replace(tzinfo=None) + timedelta(seconds=duration * 0.60)
    return filter_dt.strftime("%Y-%m-%dT%H:%M:%S")


def _fetch_location_last(
    session_key: int,
    driver_number: int,
    filter_date: str,
) -> tuple[int, dict | None]:
    """
    Récupère le DERNIER point de position GPS d'un pilote.
    Retourne (driver_number, last_point_dict) ou (driver_number, None) si indisponible.
    """
    try:
        raw = _get(
            f"{OPENF1_BASE}/location",
            params={
                "session_key":   session_key,
                "driver_number": driver_number,
                "date>":         filter_date,
            },
            timeout=TIMEOUT_LARGE,
        )
        if isinstance(raw, list) and raw:
            return driver_number, raw[-1]
        return driver_number, None
    except Exception:
        return driver_number, None


def _fetch_all_last_positions_concurrent(
    session_key: int,
    driver_numbers: list[int],
    filter_date: str,
) -> dict[int, dict]:
    """
    Récupère la dernière position GPS de tous les pilotes en parallèle.
    Gère le rate-limiting d'OpenF1 via un nombre limité de workers et des passes de retry.

    Returns:
        dict mapping driver_number → last_position_dict
    """
    results: dict[int, dict] = {}
    remaining = list(driver_numbers)

    for attempt in range(_MAX_RETRIES):
        if not remaining:
            break
        if attempt > 0:
            time.sleep(_RETRY_DELAY * attempt)

        with concurrent.futures.ThreadPoolExecutor(max_workers=_LOCATION_MAX_WORKERS) as executor:
            futures = {
                executor.submit(_fetch_location_last, session_key, dn, filter_date): dn
                for dn in remaining
            }
            for future in concurrent.futures.as_completed(futures):
                dn, point = future.result()
                if point is not None:
                    results[dn] = point

        remaining = [dn for dn in remaining if dn not in results]

    return results


def get_last_positions(session_key: int) -> AllDriversPositionResponse:
    """
    Retourne la dernière position GPS connue de tous les pilotes d'une session.

    Stratégie :
    1. Récupère la liste des pilotes de la session.
    2. Calcule une fenêtre temporelle (60 % de la durée de session) pour limiter les données.
    3. Effectue les requêtes en parallèle (max 3 workers) avec retry automatique.
    4. Enrichit chaque position avec le code pilote et la couleur d'écurie.
    """
    session_info   = _get_session_info(session_key)
    filter_date    = _calc_filter_date(session_info)
    drivers        = get_openf1_drivers(session_key)
    driver_numbers = [d.driver_number for d in drivers]

    raw_positions  = _fetch_all_last_positions_concurrent(session_key, driver_numbers, filter_date)

    # Enrichissement : code pilote + couleur équipe
    drv_map: dict[int, OpenF1Driver] = {d.driver_number: d for d in drivers}

    positions: list[DriverPosition] = []
    for dn, pt in raw_positions.items():
        drv = drv_map.get(dn)
        colour = drv.team_colour if drv else None

        positions.append(DriverPosition(
            driver_number=dn,
            x=float(pt["x"]),
            y=float(pt["y"]),
            z=float(pt.get("z") or 0),
            timestamp=datetime.fromisoformat(pt["date"]),
            driver_code=drv.name_acronym if drv else None,
            team_name=drv.team_name if drv else None,
            team_colour=colour,
        ))

    # Tri par driver_number pour une réponse déterministe
    positions.sort(key=lambda p: p.driver_number)

    ref_ts = max((p.timestamp for p in positions), default=datetime.now(timezone.utc))

    return AllDriversPositionResponse(
        session_key=session_key,
        captured_at=datetime.now(timezone.utc),
        reference_timestamp=ref_ts,
        total_drivers=len(positions),
        positions=positions,
    )


def get_car_path(
    session_key: int,
    driver_number: int,
    sample_size: int = 500,
) -> CarPathResponse:
    """
    Retourne le tracé GPS CONSÉCUTIF d'un pilote pour dessiner le contour du circuit.

    Stratégie anti-429 : au lieu de charger les 32 000+ points de la session entière,
    on utilise un filtre de DATE pour ne récupérer que les 12 premières minutes
    de la session (tour de formation + 1-2 tours de course ≈ 400 points max).

    On saute ensuite les 35 % du début (tour de formation) pour ne conserver que
    des points correspondant à des tours de course propres.
    """
    # Récupérer l'heure de début de session pour construire la fenêtre temporelle
    session_info = _get_session_info(session_key)
    date_start_str = session_info.get("date_start", "")
    date_start = datetime.fromisoformat(date_start_str.replace("Z", "+00:00"))
    # Travailler en UTC naïf pour correspondre au format attendu par OpenF1
    window_start = date_start.replace(tzinfo=None)
    window_end   = window_start + timedelta(minutes=12)

    raw = _get(
        f"{OPENF1_BASE}/location",
        params={
            "session_key":   session_key,
            "driver_number": driver_number,
            "date>":         window_start.strftime("%Y-%m-%dT%H:%M:%S"),
            "date<":         window_end.strftime("%Y-%m-%dT%H:%M:%S"),
        },
        timeout=TIMEOUT_SMALL,   # Données légères — timeout court suffisant
    )

    if not isinstance(raw, list) or not raw:
        raise ValueError(
            f"Aucune donnée GPS dans les 12 premières minutes pour "
            f"session_key={session_key}, driver={driver_number}."
        )

    total = len(raw)

    # Sauter le tour de formation (~35 % du début de la fenêtre ≈ 4 min)
    skip   = min(int(total * 0.35), max(0, total - sample_size))
    window = raw[skip: skip + sample_size]
    if len(window) < min(50, sample_size // 4):
        window = raw[:sample_size]

    path = [
        CarPathPoint(
            x=float(pt["x"]),
            y=float(pt["y"]),
            z=float(pt.get("z") or 0),
        )
        for pt in window
    ]

    return CarPathResponse(
        session_key=session_key,
        driver_number=driver_number,
        total_raw_points=total,
        sample_size=len(path),
        path=path,
    )
