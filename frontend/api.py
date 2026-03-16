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
