"""
Client HTTP vers le backend FastAPI.
Les appels sont mis en cache 5 minutes via st.cache_data pour éviter
de solliciter l'API Jolpica à chaque rerender Streamlit.
"""

from __future__ import annotations

import httpx
import streamlit as st

API_BASE = "http://localhost:8000"
TIMEOUT = 10.0


@st.cache_data(ttl=300, show_spinner=False)
def fetch_next_race() -> dict | None:
    """Retourne la prochaine course ou None si saison terminée / backend indisponible."""
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.get(f"{API_BASE}/race/next")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_driver_standings(season: str = "current") -> dict | None:
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.get(f"{API_BASE}/standings/drivers", params={"season": season})
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_constructor_standings(season: str = "current") -> dict | None:
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.get(f"{API_BASE}/standings/constructors", params={"season": season})
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_last_race() -> dict | None:
    """Retourne les résultats de la dernière course ou None si indisponible."""
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.get(f"{API_BASE}/race/last")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


@st.cache_data(ttl=600, show_spinner=False)
def fetch_openf1_sessions(year: int | None = None, session_type: str = "Race") -> list[dict]:
    """Retourne les sessions OpenF1 disponibles."""
    try:
        params: dict = {"session_type": session_type, "limit": 20}
        if year:
            params["year"] = year
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.get(f"{API_BASE}/telemetry/sessions", params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return []


@st.cache_data(ttl=600, show_spinner=False)
def fetch_openf1_drivers(session_key: int) -> list[dict]:
    """Retourne les pilotes d'une session OpenF1."""
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.get(f"{API_BASE}/telemetry/drivers/{session_key}")
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def fetch_telemetry(
    session_key: int,
    driver_number: int,
    sample_size: int = 100,
    mode: str = "uniform",
) -> dict | None:
    """Retourne les données de télémétrie échantillonnées pour un pilote."""
    try:
        with httpx.Client(timeout=35.0) as client:
            resp = client.get(
                f"{API_BASE}/telemetry/{session_key}/{driver_number}",
                params={"sample_size": sample_size, "mode": mode},
            )
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None
