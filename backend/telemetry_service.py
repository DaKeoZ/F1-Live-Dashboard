"""
Service de télémétrie — interroge l'API OpenF1 pour les données voiture en temps réel.
Documentation : https://openf1.org/

Stratégies d'échantillonnage disponibles :
  - "uniform" : N points équidistants dans la session complète (vue race overview)
  - "tail"    : N derniers points chronologiques (vue live / fin de session)
"""

from __future__ import annotations

from datetime import datetime

import httpx

from models import (
    AllTyreStrategiesResponse,
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
    return TelemetryPoint(
        timestamp=datetime.fromisoformat(raw["date"]),
        speed=int(raw.get("speed") or 0),
        rpm=int(raw.get("rpm") or 0),
        n_gear=int(raw.get("n_gear") or 0),
        throttle=int(raw.get("throttle") or 0),
        brake=int(raw.get("brake") or 0),
        drs=raw.get("drs"),
    )


def _parse_session(raw: dict) -> OpenF1Session:
    return OpenF1Session(
        session_key=raw["session_key"],
        session_name=raw.get("session_name", raw.get("session_type", "—")),
        date_start=datetime.fromisoformat(raw["date_start"]),
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

    raw_data = _get(
        f"{OPENF1_BASE}/car_data",
        params={"session_key": session_key, "driver_number": driver_number},
        timeout=TIMEOUT_LARGE,
    )

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
    session_type: str = "Race",
    limit: int = 20,
) -> list[OpenF1Session]:
    """
    Retourne les sessions OpenF1 disponibles, triées de la plus récente à la plus ancienne.

    Args:
        year:         Filtrer par année (None = toutes années).
        session_type: Type de session ("Race", "Qualifying", "Sprint"…).
        limit:        Nombre maximum de sessions à retourner.
    """
    params: dict = {"session_type": session_type}
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
