"""F1 Live Dashboard — Frontend Streamlit"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

import api as f1_api

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="F1 Live Dashboard",
    page_icon="🏎",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* ── Metric cards ── */
    [data-testid="metric-container"] {
        background: #1A1A1A;
        border-radius: 10px;
        padding: 14px 10px 10px 14px;
        border-bottom: 3px solid #E10600;
    }
    [data-testid="stMetricValue"]  { color: #FFFFFF !important; }
    [data-testid="stMetricLabel"]  { color: #888888 !important; font-size: 0.75em !important; letter-spacing: 1px; text-transform: uppercase; }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] { border-right: 1px solid #2A2A2A; }

    /* ── Dividers ── */
    hr { border-color: #2A2A2A !important; margin: 8px 0 !important; }

    /* ── Containers with border ── */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-color: #2A2A2A !important;
        border-radius: 12px !important;
    }

    /* ── Dataframe ── */
    [data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }

    /* ── Expander ── */
    [data-testid="stExpander"] summary {
        font-weight: 600;
        color: #CCCCCC;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Constants ─────────────────────────────────────────────────────────────────
F1_RED = "#E10600"

TEAM_COLORS: dict[str, str] = {
    "mercedes":     "#00D2BE",
    "ferrari":      "#DC0000",
    "red bull":     "#3671C6",
    "mclaren":      "#FF8000",
    "aston martin": "#358C75",
    "alpine":       "#0093CC",
    "williams":     "#64C4FF",
    "haas":         "#B6BABD",
    "racing bulls": "#6692FF",
    "rb":           "#6692FF",
    "cadillac":     "#C5003E",
    "audi":         "#F50537",
}

# Light teams need dark text on their badge
_LIGHT_TEAMS = {"#64C4FF", "#B6BABD", "#52E252", "#FF8000"}

# Palette officielle Pirelli (doit rester cohérente avec telemetry_service.py)
COMPOUND_COLORS: dict[str, str] = {
    "SOFT":         "#E8002D",
    "MEDIUM":       "#FFF200",
    "HARD":         "#EBEBEB",
    "INTERMEDIATE": "#39B54A",
    "WET":          "#0067FF",
    "UNKNOWN":      "#555555",
}
COMPOUND_TEXT_COLORS: dict[str, str] = {
    "SOFT":         "#FFFFFF",
    "MEDIUM":       "#000000",
    "HARD":         "#000000",
    "INTERMEDIATE": "#FFFFFF",
    "WET":          "#FFFFFF",
    "UNKNOWN":      "#CCCCCC",
}
COMPOUND_ABBREVS: dict[str, str] = {
    "SOFT": "S", "MEDIUM": "M", "HARD": "H",
    "INTERMEDIATE": "I", "WET": "W", "UNKNOWN": "?",
}

PODIUM_STYLES = {
    1: {"color": "#FFD700", "label": "🥇", "margin_top": "0px"},
    2: {"color": "#C0C0C0", "label": "🥈", "margin_top": "32px"},
    3: {"color": "#CD7F32", "label": "🥉", "margin_top": "56px"},
}

COUNTRY_FLAGS: dict[str, str] = {
    "Australia": "🇦🇺", "Austria": "🇦🇹", "Azerbaijan": "🇦🇿",
    "Bahrain": "🇧🇭", "Belgium": "🇧🇪", "Brazil": "🇧🇷",
    "Canada": "🇨🇦", "China": "🇨🇳", "France": "🇫🇷",
    "Germany": "🇩🇪", "Hungary": "🇭🇺", "Italy": "🇮🇹",
    "Japan": "🇯🇵", "Mexico": "🇲🇽", "Monaco": "🇲🇨",
    "Netherlands": "🇳🇱", "Qatar": "🇶🇦", "Saudi Arabia": "🇸🇦",
    "Singapore": "🇸🇬", "Spain": "🇪🇸", "UAE": "🇦🇪",
    "United Kingdom": "🇬🇧", "United States": "🇺🇸",
}

NATIONALITY_FLAGS: dict[str, str] = {
    "British": "🇬🇧", "German": "🇩🇪", "Dutch": "🇳🇱", "Spanish": "🇪🇸",
    "French": "🇫🇷", "Finnish": "🇫🇮", "Australian": "🇦🇺", "Canadian": "🇨🇦",
    "Mexican": "🇲🇽", "Monegasque": "🇲🇨", "Italian": "🇮🇹", "Thai": "🇹🇭",
    "Chinese": "🇨🇳", "Danish": "🇩🇰", "American": "🇺🇸", "Brazilian": "🇧🇷",
    "Argentine": "🇦🇷", "Japanese": "🇯🇵", "Austrian": "🇦🇹", "Belgian": "🇧🇪",
    "Swiss": "🇨🇭", "New Zealander": "🇳🇿", "Russian": "🇷🇺",
}

SESSION_LABELS: dict[str, str] = {
    "FP1":              "🟢 Essais Libres 1",
    "FP2":              "🟢 Essais Libres 2",
    "FP3":              "🟢 Essais Libres 3",
    "Qualifying":       "🔵 Qualifications",
    "SprintQualifying": "🟡 Sprint Qualifs",
    "Sprint":           "🟠 Sprint",
    "Race":             "🔴 Course",
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def team_color(name: str) -> str:
    lower = name.lower()
    for key, color in TEAM_COLORS.items():
        if key in lower:
            return color
    return F1_RED


def team_badge_html(name: str) -> str:
    """Pill HTML avec la couleur officielle de l'écurie."""
    color = team_color(name)
    text_color = "#000000" if color in _LIGHT_TEAMS else "#FFFFFF"
    return (
        f'<span style="background:{color}; color:{text_color}; '
        f'border-radius:20px; padding:2px 10px; font-size:0.75em; '
        f'font-weight:700; display:inline-block; white-space:nowrap;">'
        f"{name}</span>"
    )


def nat_flag(nationality: str) -> str:
    return NATIONALITY_FLAGS.get(nationality, "")


def _parse_dt(iso: str) -> datetime:
    """Parse une chaîne ISO 8601 en datetime — compatible Python 3.10 (gère le suffixe 'Z')."""
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """Convertit une couleur HEX (#RRGGBB) en chaîne rgba() acceptée par Plotly."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def fmt_dt(iso: str) -> str:
    return _parse_dt(iso).strftime("%a %d %b · %H:%M UTC")


def flag(country: str) -> str:
    return COUNTRY_FLAGS.get(country, "🏁")


def _podium_card_html(result: dict, position: int) -> str:
    """Génère le HTML d'une carte podium avec les couleurs F1."""
    style = PODIUM_STYLES[position]
    medal_color = style["color"]
    margin_top = style["margin_top"]
    t_color = team_color(result["constructor_name"])
    badge_text_color = "#000" if t_color in _LIGHT_TEAMS else "#fff"
    nat_f = nat_flag(result.get("driver_nationality", ""))

    return f"""
    <div style="
        margin-top: {margin_top};
        background: linear-gradient(160deg, #1e1e1e 0%, #141414 100%);
        border: 1px solid {medal_color}50;
        border-top: 4px solid {medal_color};
        border-radius: 14px;
        padding: 22px 16px 18px;
        text-align: center;
        min-height: 220px;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
    ">
        <div style="font-size:2.6em; font-weight:900; color:{medal_color}; line-height:1;">
            {position}
        </div>
        <div style="font-size:1.6em; font-weight:800; color:#FFFFFF; letter-spacing:3px; margin-top:4px;">
            {result["driver_code"] or "—"}
        </div>
        <div style="font-size:0.88em; color:#AAAAAA; margin-bottom:4px;">
            {nat_f} {result["driver_name"]}
        </div>
        <span style="
            background:{t_color}; color:{badge_text_color};
            border-radius:20px; padding:3px 12px;
            font-size:0.72em; font-weight:700;
            display:inline-block; margin-bottom:6px;
        ">{result["constructor_name"]}</span>
        <div style="font-size:0.9em; color:#CCCCCC; font-family:monospace; letter-spacing:1px;">
            {result["time_or_status"]}
        </div>
        <div style="font-size:0.95em; color:{F1_RED}; font-weight:700; margin-top:2px;">
            +{result["points"]:.0f} pts
        </div>
        {"<div style='font-size:0.75em; color:#FFD700; margin-top:4px;'>⚡ Meilleur tour</div>" if result.get("fastest_lap_rank") == 1 else ""}
    </div>
    """


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f"<h2 style='color:#FFFFFF; margin-bottom:0;'>🏎 F1 Live</h2>"
        f"<p style='color:{F1_RED}; font-weight:700; margin-top:0; letter-spacing:1px;'>DASHBOARD</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    view = st.radio(
        "Navigation",
        options=["🏆 Classement Pilotes", "🏭 Classement Constructeurs", "📡 Télémétrie"],
        label_visibility="collapsed",
    )

    st.divider()

    season = st.text_input(
        "Saison",
        value="current",
        help="Entrez une année (ex: 2024) ou laissez 'current' pour la saison en cours.",
    )

    st.divider()

    if st.button("🔄 Rafraîchir les données", width="stretch"):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.markdown("**Couleurs des écuries**")
    for team, color in TEAM_COLORS.items():
        if team in ("rb",):
            continue
        text_c = "#000" if color in _LIGHT_TEAMS else "#fff"
        label = team.title()
        st.markdown(
            f'<div style="display:flex; align-items:center; gap:8px; margin:3px 0;">'
            f'<div style="width:12px; height:12px; border-radius:50%; background:{color}; flex-shrink:0;"></div>'
            f'<span style="font-size:0.82em; color:#CCCCCC;">{label}</span>'
            f"</div>",
            unsafe_allow_html=True,
        )

    st.divider()
    st.caption("Source : Jolpica API (Ergast MRE)")


# ── Telemetry rendering (function) ───────────────────────────────────────────

def _render_telemetry_page() -> None:
    """Affiche la page complète de télémétrie OpenF1."""
    st.markdown("## 📡 Télémétrie OpenF1")
    st.caption("Données voiture en temps réel : vitesse, régime, rapport de boîte, gaz, frein, DRS.")

    # ── Sélecteurs ────────────────────────────────────────────────────────────
    col_weekend, col_sess, col_drv, col_opts = st.columns([3, 3, 3, 2], gap="medium")

    current_year = datetime.now().year
    sessions_all = f1_api.fetch_openf1_sessions(year=current_year, session_type=None, limit=500)
    if not sessions_all:
        st.error("Impossible de récupérer les sessions OpenF1.", icon="🚨")
        return

    # Weekend (meeting) → sessions
    by_meeting: dict[int, list[dict]] = defaultdict(list)
    for s in sessions_all:
        mk = s.get("meeting_key")
        if mk is None:
            continue
        by_meeting[int(mk)].append(s)

    def _meeting_anchor_dt(items: list[dict]) -> datetime:
        # On prend la date du Race (si dispo), sinon la dernière session du weekend
        race = next((x for x in items if (x.get("session_name") or "").strip().lower() == "race"), None)
        if race:
            return _parse_dt(race["date_start"])
        return max((_parse_dt(x["date_start"]) for x in items), default=datetime(1970, 1, 1, tzinfo=timezone.utc))

    meetings_sorted = sorted(by_meeting.items(), key=lambda kv: _meeting_anchor_dt(kv[1]), reverse=True)

    now_utc = datetime.now(timezone.utc)
    default_meeting_idx = 0
    for i, (_mk, items) in enumerate(meetings_sorted):
        if _meeting_anchor_dt(items) <= now_utc:
            default_meeting_idx = i
            break

    def _meeting_label(items: list[dict]) -> str:
        any_s = items[0]
        country = any_s.get("country_name", "—")
        circuit = any_s.get("circuit_short_name", "—")
        dt = _meeting_anchor_dt(items)
        return f"{circuit} · {country} · {dt.strftime('%Y-%m-%d')}"

    meeting_labels = [_meeting_label(items) for _mk, items in meetings_sorted]

    with col_weekend:
        selected_meeting_label = st.selectbox(
            f"Weekend ({current_year})",
            meeting_labels,
            index=min(default_meeting_idx, len(meeting_labels) - 1),
        )
        selected_meeting_key = meetings_sorted[meeting_labels.index(selected_meeting_label)][0]

    meeting_sessions = by_meeting[selected_meeting_key]
    meeting_sessions_sorted = sorted(meeting_sessions, key=lambda s: _parse_dt(s["date_start"]))

    def _session_key(s: dict) -> str:
        stype = (s.get("session_type") or "").strip()
        sname = (s.get("session_name") or "").strip()

        if stype.lower() == "practice":
            if "1" in sname:
                return "FP1"
            if "2" in sname:
                return "FP2"
            if "3" in sname:
                return "FP3"
            return "Practice"
        if sname.lower() == "sprint qualifying":
            return "SprintQualifying"
        if sname.lower() == "sprint":
            return "Sprint"
        if stype.lower() == "qualifying":
            return "Qualifying"
        if sname.lower() == "race":
            return "Race"
        return sname or stype or "Session"

    with col_sess:
        session_options: dict[str, int] = {}
        for s in meeting_sessions_sorted:
            key = _session_key(s)
            label = SESSION_LABELS.get(key, key)
            dt = _parse_dt(s["date_start"]).strftime("%a %d %b · %H:%M UTC")
            session_options[f"{label} — {dt}"] = int(s["session_key"])

        session_labels = list(session_options.keys())
        default_idx = 0
        for i, s in enumerate(meeting_sessions_sorted):
            if _parse_dt(s["date_start"]) <= now_utc:
                default_idx = i
                break

        selected_session_label = st.selectbox("Session", session_labels, index=min(default_idx, len(session_labels) - 1))
        selected_session_key = session_options[selected_session_label]

    with col_drv:
        drivers = f1_api.fetch_openf1_drivers(selected_session_key)
        if not drivers:
            st.warning("Aucun pilote trouvé pour cette session.")
            return

        driver_options = {
            f"{d['name_acronym']} — {d['full_name']} ({d['team_name']})": d["driver_number"]
            for d in drivers
        }
        selected_driver_label  = st.selectbox("Pilote", list(driver_options.keys()))
        selected_driver_number = driver_options[selected_driver_label]

    with col_opts:
        # Détecter si la session est terminée pour proposer un mode adapté
        _sel_session = next((s for s in meeting_sessions_sorted if s["session_key"] == selected_session_key), None)
        _session_ended = (
            _sel_session is not None
            and _parse_dt(_sel_session["date_start"]) < now_utc - __import__("datetime").timedelta(hours=3)
        )
        default_mode  = "uniform" if _session_ended else "tail"
        default_pts   = 1000     if _session_ended else 150

        sample_size = st.slider(
            "Points",
            min_value=50,
            max_value=2000,
            value=default_pts,
            step=50,
            help="Session terminée : 1000+ pts pour la vue course complète. Live : 100-200 pts.",
        )
        mode = st.radio(
            "Mode",
            options=["uniform", "tail"],
            index=0 if default_mode == "uniform" else 1,
            format_func=lambda m: "Course complète (uniform)" if m == "uniform" else "Temps réel (tail)",
            horizontal=True,
        )

    # ── Fetch & affichage ────────────────────────────────────────────────────
    if st.button("⚡ Charger la télémétrie", type="primary", width="stretch"):
        # Invalider uniquement les caches de télémétrie et stints (pas le tracé circuit)
        f1_api.fetch_telemetry.clear()
        f1_api.fetch_tyre_stints.clear()
        f1_api.fetch_all_tyre_stints.clear()

    with st.spinner("Récupération des données OpenF1… (peut prendre 5-15 s)"):
        telem = f1_api.fetch_telemetry(
            session_key=selected_session_key,
            driver_number=selected_driver_number,
            sample_size=sample_size,
            mode=mode,
        )

    if telem is None:
        st.error(
            "Impossible de récupérer la télémétrie. "
            "Vérifiez que le backend tourne et que la session contient des données.",
            icon="🚨",
        )
        return

    points = telem["points"]
    if not points:
        st.warning("Aucune donnée de télémétrie disponible pour ce pilote / cette session.")
        return

    # ── Metadata banner ───────────────────────────────────────────────────────
    raw_pts  = telem["total_raw_points"]
    samp_pts = telem["sample_size"]
    ratio    = raw_pts / samp_pts if samp_pts else 0
    info_col1, info_col2, info_col3, info_col4 = st.columns(4)
    info_col1.metric("Points bruts", f"{raw_pts:,}")
    info_col2.metric("Points affichés", samp_pts)
    info_col3.metric("Facteur compression", f"1 / {ratio:.0f}×")
    info_col4.metric("Mode", telem["sample_method"].upper())

    # ── Préparation des séries ────────────────────────────────────────────────
    times     = [_parse_dt(p["timestamp"]) for p in points]
    speeds    = [p["speed"]    for p in points]
    rpms      = [p["rpm"]      for p in points]
    gears     = [p["n_gear"]   for p in points]
    throttles = [p["throttle"] for p in points]
    brakes    = [p["brake"]    for p in points]
    drs_vals  = [1 if (p.get("drs") or 0) >= 10 else 0 for p in points]

    # Couleur de l'écurie du pilote sélectionné
    drv_data   = next((d for d in drivers if d["driver_number"] == selected_driver_number), None)
    drv_colour = f"#{drv_data['team_colour'].lstrip('#')}" if drv_data and drv_data.get("team_colour") else "#E10600"

    # ── Stats rapides ─────────────────────────────────────────────────────────
    st.markdown("---")
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Vitesse max",   f"{max(speeds)} km/h")
    s2.metric("Vitesse moy",   f"{sum(speeds)//len(speeds)} km/h")
    s3.metric("RPM max",       f"{max(rpms):,}")
    s4.metric("Rapport max",   f"R{max(gears)}")
    s5.metric("DRS actif",     f"{sum(drs_vals)} pts")

    # ── Plotly subplots ───────────────────────────────────────────────────────
    fig = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        subplot_titles=("Vitesse (km/h)", "Régime moteur (RPM)", "Rapport de boîte", "Gaz / Frein (%)"),
        row_heights=[0.35, 0.25, 0.15, 0.25],
    )

    # Row 1 — Speed + DRS background shading
    fig.add_trace(
        go.Scatter(
            x=times, y=speeds,
            mode="lines",
            name="Vitesse",
            line=dict(color=drv_colour, width=2),
            fill="tozeroy",
            fillcolor=_hex_to_rgba(drv_colour, 0.09),
            hovertemplate="<b>%{y} km/h</b><br>%{x|%H:%M:%S}<extra></extra>",
        ),
        row=1, col=1,
    )
    # DRS actif en surimpression
    fig.add_trace(
        go.Scatter(
            x=times, y=[s if d else None for s, d in zip(speeds, drs_vals)],
            mode="lines",
            name="DRS ouvert",
            line=dict(color="#00FF88", width=3, dash="dot"),
            hovertemplate="DRS actif — %{y} km/h<extra></extra>",
        ),
        row=1, col=1,
    )

    # Row 2 — RPM
    fig.add_trace(
        go.Scatter(
            x=times, y=rpms,
            mode="lines",
            name="RPM",
            line=dict(color="#FF8000", width=1.5),
            hovertemplate="<b>%{y:,} RPM</b><br>%{x|%H:%M:%S}<extra></extra>",
        ),
        row=2, col=1,
    )

    # Row 3 — Gear (stepped)
    fig.add_trace(
        go.Scatter(
            x=times, y=gears,
            mode="lines",
            name="Rapport",
            line=dict(color="#CCCCCC", width=2, shape="hv"),
            hovertemplate="<b>Rapport %{y}</b><br>%{x|%H:%M:%S}<extra></extra>",
        ),
        row=3, col=1,
    )

    # Row 4 — Throttle + Brake
    fig.add_trace(
        go.Scatter(
            x=times, y=throttles,
            mode="lines",
            name="Gaz",
            line=dict(color="#00CC44", width=1.5),
            fill="tozeroy",
            fillcolor="rgba(0,204,68,0.12)",
            hovertemplate="Gaz : <b>%{y}%%</b><extra></extra>",
        ),
        row=4, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=times, y=brakes,
            mode="lines",
            name="Frein",
            line=dict(color="#E10600", width=1.5),
            fill="tozeroy",
            fillcolor="rgba(225,6,0,0.12)",
            hovertemplate="Frein : <b>%{y}%%</b><extra></extra>",
        ),
        row=4, col=1,
    )

    # ── Layout global ─────────────────────────────────────────────────────────
    fig.update_layout(
        template="plotly_dark",
        height=680,
        margin=dict(l=10, r=10, t=60, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.01,
            xanchor="right",  x=1,
            font=dict(size=11),
        ),
        hoverlabel=dict(bgcolor="#1A1A1A", bordercolor=drv_colour, font_color="white"),
        hovermode="x unified",
    )
    # Axes Y
    fig.update_yaxes(row=1, gridcolor="rgba(255,255,255,0.06)", range=[0, 380])
    fig.update_yaxes(row=2, gridcolor="rgba(255,255,255,0.06)", range=[0, 20000])
    fig.update_yaxes(row=3, gridcolor="rgba(255,255,255,0.06)", range=[0, 9], dtick=1)
    fig.update_yaxes(row=4, gridcolor="rgba(255,255,255,0.06)", range=[0, 105])
    # Axes X (partagés)
    for row in range(1, 5):
        fig.update_xaxes(row=row, showgrid=False, tickfont=dict(color="#888"))

    st.plotly_chart(fig, width="stretch")

    # ── Section Carte Circuit ─────────────────────────────────────────────────
    st.divider()
    st.markdown("### 🗺 Positions sur le Circuit")

    map_col_opts, map_col_info = st.columns([3, 1], gap="large")
    with map_col_opts:
        show_path = st.checkbox(
            "Afficher le tracé du circuit (contour)",
            value=True,
            help="Charge le tracé GPS complet d'un pilote pour dessiner le contour du circuit (~5-10 s).",
        )
    with map_col_info:
        st.caption(
            "Données : OpenF1 /location\n"
            "Les positions sont figées en fin de session.\n"
            "Cache 2 min."
        )

    with st.spinner("Récupération des dernières positions… (jusqu'à 10 s, retry anti rate-limit)"):
        positions_data = f1_api.fetch_last_positions(selected_session_key)

    if positions_data is None or not positions_data.get("positions"):
        st.warning("Impossible de récupérer les positions GPS pour cette session.", icon="⚠️")
    else:
        positions = positions_data["positions"]

        # ── Tracé du circuit en arrière-plan ──────────────────────────────
        circuit_fig = go.Figure()

        if show_path:
            with st.spinner("Chargement du tracé du circuit…"):
                path_data = f1_api.fetch_car_path(
                    selected_session_key,
                    selected_driver_number,
                    sample_size=600,
                )
            if path_data and path_data.get("path"):
                pts = path_data["path"]
                circuit_fig.add_trace(go.Scatter(
                    x=[p["x"] for p in pts],
                    y=[p["y"] for p in pts],
                    mode="lines",
                    name="Circuit",
                    line=dict(color="rgba(255,255,255,0.15)", width=8),
                    hoverinfo="skip",
                ))

        # ── Points de position des pilotes ────────────────────────────────
        for pos in positions:
            colour = pos.get("team_colour") or "#E10600"
            if not colour.startswith("#"):
                colour = f"#{colour}"
            code = pos.get("driver_code") or f"#{pos['driver_number']}"
            team = pos.get("team_name") or "—"

            circuit_fig.add_trace(go.Scatter(
                x=[pos["x"]],
                y=[pos["y"]],
                mode="markers+text",
                name=code,
                marker=dict(
                    color=colour,
                    size=14,
                    line=dict(color="white", width=1.5),
                    symbol="circle",
                ),
                text=[code],
                textposition="top center",
                textfont=dict(color="white", size=9),
                hovertemplate=(
                    f"<b>{code}</b><br>"
                    f"Équipe : {team}<br>"
                    f"x = {pos['x']:.0f}<br>"
                    f"y = {pos['y']:.0f}<br>"
                    f"z = {pos['z']:.0f}<br>"
                    f"<extra></extra>"
                ),
                showlegend=False,
            ))

        # ── Annotations timestamp ─────────────────────────────────────────
        ref_ts = positions_data.get("reference_timestamp", "")
        if ref_ts:
            ref_dt = _parse_dt(ref_ts)
            ts_label = ref_dt.strftime("%d %b %Y · %H:%M:%S UTC")
        else:
            ts_label = "—"

        circuit_fig.update_layout(
            template="plotly_dark",
            title=dict(
                text=f"<b>Positions — {positions_data.get('total_drivers', '?')} pilotes</b>"
                     f"  <span style='font-size:12px; color:#888;'>{ts_label}</span>",
                font=dict(size=14),
                x=0,
            ),
            xaxis=dict(
                showgrid=False, zeroline=False,
                showticklabels=False, scaleanchor="y",
            ),
            yaxis=dict(
                showgrid=False, zeroline=False,
                showticklabels=False,
            ),
            height=560,
            margin=dict(l=0, r=0, t=60, b=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            hoverlabel=dict(bgcolor="#1A1A1A", bordercolor="#E10600", font_color="white"),
        )
        st.plotly_chart(circuit_fig, width="stretch")

        # Tableau des positions
        with st.expander("📋 Tableau des positions"):
            rows_pos = [
                {
                    "N°":    p["driver_number"],
                    "Code":  p.get("driver_code") or "—",
                    "Équipe": p.get("team_name") or "—",
                    "X":     round(p["x"], 1),
                    "Y":     round(p["y"], 1),
                    "Z":     round(p["z"], 1),
                    "Timestamp": p["timestamp"][:19].replace("T", " "),
                }
                for p in positions
            ]
            df_pos = pd.DataFrame(rows_pos).set_index("N°")
            st.dataframe(df_pos, width="stretch", height=350)

    # ── Section Stratégie Pneumatiques ────────────────────────────────────────
    st.divider()
    st.markdown("### 🏎 Stratégie Pneumatiques")

    # Légende des composés
    legend_html = " &nbsp; ".join(
        f'<span style="background:{COMPOUND_COLORS[c]}; color:{COMPOUND_TEXT_COLORS[c]}; '
        f'border-radius:4px; padding:2px 10px; font-size:0.8em; font-weight:700;">'
        f'{COMPOUND_ABBREVS[c]} {c.title()}</span>'
        for c in ["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"]
    )
    st.markdown(legend_html, unsafe_allow_html=True)
    st.write("")

    tab_solo, tab_all = st.tabs(["Pilote sélectionné", "Tous les pilotes — Gantt"])

    # ── Tab 1 : Stints du pilote courant ──────────────────────────────────────
    with tab_solo:
        solo_data = f1_api.fetch_tyre_stints(selected_session_key, selected_driver_number)

        if not solo_data or not solo_data.get("stints"):
            st.info("Aucune donnée de stints disponible pour ce pilote.")
        else:
            stints = solo_data["stints"]
            stint_cols = st.columns(len(stints))
            for col, stint in zip(stint_cols, stints):
                c = (stint.get("compound") or "UNKNOWN").upper()
                bg  = COMPOUND_COLORS.get(c, "#555")
                txt = COMPOUND_TEXT_COLORS.get(c, "#fff")
                abbr = COMPOUND_ABBREVS.get(c, "?")
                lap_start = stint["lap_start"]
                lap_end   = stint.get("lap_end") or "?"
                n_laps    = stint.get("laps_in_stint") or "?"
                age       = stint.get("tyre_age_at_start", 0)

                col.markdown(
                    f"""
                    <div style="background:#1A1A1A; border:1px solid {bg}; border-top:4px solid {bg};
                                border-radius:10px; padding:12px; text-align:center;">
                        <div style="background:{bg}; color:{txt}; border-radius:20px;
                                    padding:4px 14px; font-size:1.3em; font-weight:900;
                                    display:inline-block; margin-bottom:8px;">{abbr}</div>
                        <div style="font-size:0.8em; color:#AAA;">Stint {stint['stint_number']}</div>
                        <div style="font-size:1em; color:#FFF; font-weight:700; margin:4px 0;">
                            Tours {lap_start} → {lap_end}
                        </div>
                        <div style="font-size:0.85em; color:#CCC;">{n_laps} tours</div>
                        <div style="font-size:0.75em; color:#888; margin-top:4px;">
                            Âge : {age} tour{"s" if age != 1 else ""}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # ── Tab 2 : Gantt multi-pilotes ───────────────────────────────────────────
    with tab_all:
        with st.spinner("Récupération des stratégies de tous les pilotes…"):
            all_data = f1_api.fetch_all_tyre_stints(selected_session_key)

        if not all_data or not all_data.get("strategies"):
            st.info("Aucune donnée de stratégie disponible pour cette session.")
        else:
            # Construire un mapping driver_number → label
            drv_map = {d["driver_number"]: f"#{d['driver_number']} {d['name_acronym']}" for d in drivers}

            # Regrouper les stints par composé pour les traces Plotly
            compound_data: dict[str, dict] = defaultdict(lambda: {"y": [], "x": [], "base": [], "hover": []})

            for strategy in all_data["strategies"]:
                dn = strategy["driver_number"]
                label = drv_map.get(dn, f"#{dn}")
                for stint in strategy["stints"]:
                    c = (stint.get("compound") or "UNKNOWN").upper()
                    lap_s = stint["lap_start"]
                    lap_e = stint.get("lap_end") or lap_s
                    width = max(lap_e - lap_s + 1, 1)
                    age   = stint.get("tyre_age_at_start", 0)
                    compound_data[c]["y"].append(label)
                    compound_data[c]["x"].append(width)
                    compound_data[c]["base"].append(lap_s)
                    compound_data[c]["hover"].append(
                        f"<b>{label}</b><br>"
                        f"Composé : {c.title()}<br>"
                        f"Tours : {lap_s} → {lap_e} ({width} tours)<br>"
                        f"Âge pneu : {age} tour{'s' if age != 1 else ''}"
                    )

            gantt = go.Figure()
            for c, d in compound_data.items():
                color    = COMPOUND_COLORS.get(c, "#555")
                txt_col  = COMPOUND_TEXT_COLORS.get(c, "#fff")
                abbr     = COMPOUND_ABBREVS.get(c, "?")
                gantt.add_trace(go.Bar(
                    name=c.title(),
                    x=d["x"],
                    y=d["y"],
                    orientation="h",
                    base=d["base"],
                    marker=dict(
                        color=color,
                        line=dict(color="rgba(0,0,0,0.4)", width=1),
                    ),
                    text=[abbr] * len(d["x"]),
                    textposition="inside",
                    textfont=dict(color=txt_col, size=10, family="monospace"),
                    hovertemplate="%{hovertext}<extra></extra>",
                    hovertext=d["hover"],
                ))

            n_drivers = all_data["total_drivers"]
            gantt.update_layout(
                template="plotly_dark",
                title=dict(text="<b>Stratégie pneumatiques — vue d'ensemble</b>", font=dict(size=14), x=0),
                barmode="stack",
                xaxis=dict(title="Tour", showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
                yaxis=dict(
                    categoryorder="category ascending",
                    tickfont=dict(size=11),
                    autorange="reversed",
                ),
                height=max(350, n_drivers * 28 + 80),
                margin=dict(l=10, r=10, t=50, b=10),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.01,
                    xanchor="right", x=1, font=dict(size=11),
                ),
                hoverlabel=dict(bgcolor="#1A1A1A", bordercolor="#E10600", font_color="white"),
            )
            st.plotly_chart(gantt, width="stretch")

    # ── Vue Live ──────────────────────────────────────────────────────────────
    st.divider()
    st.markdown("### 🔴 Vue Live — Jauge & Télémétrie Temps Réel")

    live_col_info, live_col_toggle = st.columns([3, 1])
    with live_col_info:
        st.caption(
            "Graphe bi-axe vitesse/RPM · Jauge rapport · Badge pneu actuel. "
            "Active le rafraîchissement pour simuler le direct (session en cours uniquement)."
        )
    with live_col_toggle:
        live_enabled = st.toggle("⟳ Auto-refresh 5 s", value=False)

    @st.fragment(run_every="5s" if live_enabled else None)
    def _live_fragment() -> None:
        live_data = f1_api.fetch_live_telemetry(selected_session_key, selected_driver_number)

        if not live_data or not live_data.get("points"):
            st.info("Aucune donnée disponible pour cette session.", icon="ℹ️")
            return

        points = live_data["points"]
        last   = points[-1]
        times  = [_parse_dt(p["timestamp"]) for p in points]
        speeds = [p["speed"]    for p in points]
        rpms   = [p["rpm"]      for p in points]
        drs_vals = [bool((p.get("drs") or 0) >= 8) for p in points]

        # ── Tyre compound (stints cache TTL=300 s, pas de surcharge) ─────────
        stints_data   = f1_api.fetch_tyre_stints(selected_session_key, selected_driver_number)
        current_stint = (stints_data or {}).get("stints", [{}])[-1] if stints_data else {}
        compound      = ((current_stint.get("compound") or "UNKNOWN")).upper()
        c_color = COMPOUND_COLORS.get(compound, "#555555")
        c_text  = COMPOUND_TEXT_COLORS.get(compound, "#CCCCCC")
        c_abbr  = COMPOUND_ABBREVS.get(compound, "?")
        stint_no   = current_stint.get("stint_number", "?")
        stint_lap  = current_stint.get("lap_start", "?")

        # ── Layout ────────────────────────────────────────────────────────────
        col_chart, col_gear, col_tyre = st.columns([5, 2, 2], gap="medium")

        # ── Graphe dual-axe Speed + RPM ───────────────────────────────────────
        with col_chart:
            fig_live = make_subplots(specs=[[{"secondary_y": True}]])

            fig_live.add_trace(
                go.Scatter(
                    x=times, y=speeds,
                    name="Vitesse (km/h)",
                    line=dict(color=drv_colour, width=2.5),
                    fill="tozeroy",
                    fillcolor=_hex_to_rgba(drv_colour, 0.08),
                    hovertemplate="<b>%{y} km/h</b> · %{x|%H:%M:%S}<extra></extra>",
                ),
                secondary_y=False,
            )
            fig_live.add_trace(
                go.Scatter(
                    x=times, y=rpms,
                    name="RPM",
                    line=dict(color="#FF8000", width=1.5, dash="dot"),
                    hovertemplate="<b>%{y:,} RPM</b> · %{x|%H:%M:%S}<extra></extra>",
                ),
                secondary_y=True,
            )
            # Points DRS actifs en surimpression
            fig_live.add_trace(
                go.Scatter(
                    x=[t for t, d in zip(times, drs_vals) if d],
                    y=[s for s, d in zip(speeds, drs_vals) if d],
                    name="DRS actif",
                    mode="markers",
                    marker=dict(color="#00FF88", size=7, symbol="diamond"),
                    hovertemplate="DRS — %{y} km/h<extra></extra>",
                ),
                secondary_y=False,
            )
            fig_live.update_yaxes(title_text="Vitesse (km/h)", secondary_y=False,
                                  gridcolor="rgba(255,255,255,0.07)")
            fig_live.update_yaxes(title_text="RPM", secondary_y=True,
                                  gridcolor="rgba(255,255,255,0.03)")
            fig_live.update_layout(
                template="plotly_dark",
                height=260,
                margin=dict(l=0, r=0, t=30, b=0),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=False),
                legend=dict(orientation="h", y=1.14, font=dict(size=10)),
                hoverlabel=dict(bgcolor="#1A1A1A", font_color="white"),
            )
            st.plotly_chart(fig_live, width="stretch")

        # ── Jauge Rapport de boîte ─────────────────────────────────────────────
        with col_gear:
            current_gear = int(last.get("n_gear") or 0)
            fig_gear = go.Figure(go.Indicator(
                mode="gauge+number",
                value=current_gear,
                title=dict(text="Rapport", font=dict(color="#CCCCCC", size=13)),
                number=dict(font=dict(size=60, color=drv_colour)),
                gauge=dict(
                    axis=dict(
                        range=[0, 8],
                        tickvals=list(range(9)),
                        tickfont=dict(color="#AAAAAA", size=9),
                        tickcolor="#555",
                    ),
                    bar=dict(color=drv_colour, thickness=0.28),
                    bgcolor="#181818",
                    borderwidth=1,
                    bordercolor="#333",
                    steps=[
                        dict(range=[i, i + 1], color="#242424" if i % 2 == 0 else "#1C1C1C")
                        for i in range(8)
                    ],
                    threshold=dict(
                        line=dict(color="white", width=2),
                        thickness=0.75,
                        value=current_gear,
                    ),
                ),
            ))
            fig_gear.update_layout(
                height=220,
                margin=dict(l=10, r=10, t=40, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="white"),
            )
            st.plotly_chart(fig_gear, width="stretch")

        # ── Badge Pneu ────────────────────────────────────────────────────────
        with col_tyre:
            st.markdown(
                f"""
                <div style="display:flex; flex-direction:column; align-items:center;
                            padding-top:28px;">
                    <div style="
                        width:90px; height:90px; border-radius:50%;
                        background:{c_color};
                        display:flex; align-items:center; justify-content:center;
                        font-size:38px; font-weight:900; color:{c_text};
                        border:3px solid rgba(255,255,255,0.25);
                        box-shadow:0 0 22px {c_color}55;
                    ">{c_abbr}</div>
                    <p style="color:#CCC; margin:10px 0 2px; font-size:0.9em;
                              font-weight:600; text-align:center;">
                        {compound.title()}
                    </p>
                    <p style="color:#777; font-size:0.75em; text-align:center; margin:0;">
                        Stint {stint_no} · Tour {stint_lap}+
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # ── Bande valeurs instantanées ─────────────────────────────────────────
        st.markdown(
            "<hr style='border:1px solid #222; margin:6px 0 10px;'>",
            unsafe_allow_html=True,
        )
        cv1, cv2, cv3, cv4, cv5 = st.columns(5)
        cv1.metric("🚀 Vitesse",  f"{last['speed']} km/h")
        cv2.metric("⚙️ RPM",      f"{int(last['rpm']):,}")
        cv3.metric("🟢 Gaz",      f"{last['throttle']} %")
        cv4.metric("🔴 Frein",    f"{last['brake']} %")
        cv5.metric("DRS",         "Ouvert ✅" if drs_vals[-1] else "Fermé")

    _live_fragment()


# ── Data fetch ────────────────────────────────────────────────────────────────
with st.spinner("Chargement des données F1…"):
    next_race  = f1_api.fetch_next_race()
    last_race  = f1_api.fetch_last_race()
    is_drivers = "Pilotes" in view
    standings_data = (
        f1_api.fetch_driver_standings(season)
        if is_drivers
        else f1_api.fetch_constructor_standings(season)
    )

# ── Mode Télémétrie : rendu dédié puis sortie ─────────────────────────────────
if "Télémétrie" in view:
    st.markdown(
        "<h1 style='margin-bottom:0;'>🏎 F1 Live Dashboard</h1>",
        unsafe_allow_html=True,
    )
    st.divider()
    _render_telemetry_page()
    st.divider()
    st.markdown(
        "<p style='color:#555; font-size:0.78em; text-align:center;'>"
        "Données télémétrie : OpenF1 API &nbsp;·&nbsp; Cache 60 s &nbsp;·&nbsp; F1 Live Dashboard</p>",
        unsafe_allow_html=True,
    )
    st.stop()

# ── Page header ───────────────────────────────────────────────────────────────
st.markdown(
    "<h1 style='margin-bottom:0;'>🏎 F1 Live Dashboard</h1>",
    unsafe_allow_html=True,
)
if standings_data:
    season_display = standings_data.get("season", "—")
    round_display  = standings_data.get("round", "—")
    leader = standings_data["standings"][0] if standings_data.get("standings") else None
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Saison", season_display)
    kpi2.metric("Dernier Round", f"Round {round_display}")
    if leader:
        if is_drivers:
            kpi3.metric("Leader Pilotes", leader["driver"]["code"] or leader["driver"]["last_name"])
            kpi4.metric("Points leader", f"{leader['points']:.0f} pts")
        else:
            kpi3.metric("Leader Constructeurs", leader["constructor"]["name"])
            kpi4.metric("Points leader", f"{leader['points']:.0f} pts")

st.divider()

# ── Hero : Prochaine course ───────────────────────────────────────────────────
st.markdown("## 🏁 Prochaine Course")

if next_race is None:
    st.warning(
        "Impossible de récupérer la prochaine course — backend indisponible ou saison terminée.",
        icon="⚠️",
    )
else:
    circuit = next_race["circuit"]
    loc     = circuit["location"]
    cd      = next_race["countdown"]
    session_label = SESSION_LABELS.get(cd["target_session"], cd["target_session"])

    with st.container(border=True):
        col_info, col_sessions, col_cd = st.columns([3, 3, 2], gap="large")

        with col_info:
            st.markdown(
                f"<h3 style='margin-bottom:4px;'>{flag(loc['country'])} {next_race['race_name']}</h3>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<p style='color:#CCCCCC; margin:0;'><b>{circuit['name']}</b></p>"
                f"<p style='color:#888; font-size:0.85em; margin:2px 0;'>📍 {loc['locality']}, {loc['country']}</p>"
                f"<p style='color:#888; font-size:0.85em; margin:2px 0;'>Saison <b style='color:#fff'>{next_race['season']}</b>"
                f" &nbsp;·&nbsp; Round <b style='color:{F1_RED}'>{next_race['round']}</b></p>",
                unsafe_allow_html=True,
            )

        with col_sessions:
            st.markdown("**Programme des sessions**")
            # Toutes les sessions possibles dans l'ordre chronologique naturel du weekend
            _session_map = [
                ("FP1",              next_race.get("fp1")),
                ("FP2",              next_race.get("fp2")),
                ("FP3",              next_race.get("fp3")),
                ("SprintQualifying", next_race.get("sprint_qualifying")),
                ("Sprint",           next_race.get("sprint")),
                ("Qualifying",       next_race.get("qualifying")),
                ("Race",             next_race.get("race")),
            ]
            for key, session_obj in _session_map:
                if session_obj is None:
                    continue
                dt_iso = session_obj["datetime_utc"]
                label  = SESSION_LABELS.get(key, key)
                st.markdown(f"{label} &nbsp; `{fmt_dt(dt_iso)}`")

        with col_cd:
            st.markdown(
                f"<p style='font-weight:600; color:#CCCCCC; margin-bottom:10px;'>"
                f"Prochain : {session_label}</p>",
                unsafe_allow_html=True,
            )
            c1, c2, c3 = st.columns(3)
            c1.metric("Jours",   cd["days"])
            c2.metric("Heures",  cd["hours"])
            c3.metric("Min",     cd["minutes"])

st.divider()

# ── Derniers Résultats — Podium ───────────────────────────────────────────────
st.markdown("## 🏆 Derniers Résultats")

if last_race is None:
    st.info("Aucun résultat de course disponible pour le moment.", icon="ℹ️")
else:
    results = last_race.get("results", [])
    last_circuit = last_race["circuit"]
    last_loc     = last_circuit["location"]

    st.markdown(
        f"<p style='color:#888; margin-top:-8px;'>"
        f"{flag(last_loc['country'])} <b style='color:#fff'>{last_race['race_name']}</b>"
        f" &nbsp;·&nbsp; Round {last_race['round']}"
        f" &nbsp;·&nbsp; {last_race['date']}"
        f"</p>",
        unsafe_allow_html=True,
    )

    # ── Podium (P1 au centre, P2 à gauche, P3 à droite) ──────────────────────
    if len(results) >= 3:
        gap_l, col_p2, col_p1, col_p3, gap_r = st.columns([0.2, 1, 1.15, 1, 0.2], gap="medium")

        with col_p2:
            st.markdown(_podium_card_html(results[1], position=2), unsafe_allow_html=True)
        with col_p1:
            st.markdown(_podium_card_html(results[0], position=1), unsafe_allow_html=True)
        with col_p3:
            st.markdown(_podium_card_html(results[2], position=3), unsafe_allow_html=True)

    # ── Classement complet (expander) ─────────────────────────────────────────
    with st.expander("📋 Voir le classement complet de la course"):
        rows = [
            {
                "Pos":    r["position"],
                "Code":   r["driver_code"] or "—",
                "Pilote": r["driver_name"],
                "Écurie": r["constructor_name"],
                "Grille": r["grid"],
                "Tours":  r["laps"],
                "Temps":  r["time_or_status"],
                "Pts":    r["points"],
                "⚡":     r["fastest_lap_time"] or "",
            }
            for r in results
        ]
        df_last = pd.DataFrame(rows).set_index("Pos")
            st.dataframe(
                df_last,
                width="stretch",
                height=420,
                column_config={
                "Pts": st.column_config.NumberColumn("Pts", format="%.0f"),
                "⚡":  st.column_config.TextColumn("⚡ FL", help="Meilleur tour en course"),
            },
        )

st.divider()

# ── Standings : Classement + Graphique ───────────────────────────────────────
season_label = season if season != "current" else "en cours"
title_icon = "🏆" if is_drivers else "🏭"
title_text = "Classement Pilotes" if is_drivers else "Classement Constructeurs"
st.markdown(f"## {title_icon} {title_text} — Saison {season_label}")

if standings_data is None:
    st.error(
        f"Impossible de charger les données — backend indisponible sur **{f1_api.API_BASE}**.",
        icon="🚨",
    )
    st.stop()

standings = standings_data.get("standings", [])
if not standings:
    st.warning("Aucune donnée disponible pour cette saison.")
    st.stop()

col_chart, col_table = st.columns([6, 4], gap="large")

# ── Plotly chart (top 10) ─────────────────────────────────────────────────────
with col_chart:
    top10 = standings[:10]

    if is_drivers:
        labels = [
            f"P{s['position']}  {s['driver']['code'] or s['driver']['last_name']}"
            for s in top10
        ]
        points = [s["points"] for s in top10]
        colors = [team_color(s["constructor_name"]) for s in top10]
        hover  = [
            (
                f"<b>{s['driver']['first_name']} {s['driver']['last_name']}</b><br>"
                f"Écurie : {s['constructor_name']}<br>"
                f"Points : {s['points']}<br>"
                f"Victoires : {s['wins']}"
            )
            for s in top10
        ]
        chart_title = "Points — Top 10 Pilotes"
    else:
        labels = [f"P{s['position']}  {s['constructor']['name']}" for s in top10]
        points = [s["points"] for s in top10]
        colors = [team_color(s["constructor"]["name"]) for s in top10]
        hover  = [
            (
                f"<b>{s['constructor']['name']}</b><br>"
                f"Nationalité : {s['constructor']['nationality']}<br>"
                f"Points : {s['points']}<br>"
                f"Victoires : {s['wins']}"
            )
            for s in top10
        ]
        chart_title = "Points — Constructeurs"

    # Barres avec dégradé : couleur pleine → version plus sombre
    bar_colors_gradient = [
        f"rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.90)"
        for c in colors
    ]

    fig = go.Figure(
        go.Bar(
            x=points,
            y=labels,
            orientation="h",
            marker=dict(
                color=bar_colors_gradient,
                line=dict(color="rgba(255,255,255,0.06)", width=1),
                opacity=0.92,
            ),
            text=[f" {p:.0f}" for p in points],
            textposition="outside",
            textfont=dict(color="#CCCCCC", size=12),
            cliponaxis=False,
            hovertemplate="%{hovertext}<extra></extra>",
            hovertext=hover,
        )
    )
    fig.update_layout(
        template="plotly_dark",
        title=dict(
            text=f"<b>{chart_title}</b>",
            font=dict(size=14, color="#F0F0F0"),
            x=0,
        ),
        xaxis=dict(
            title="Points",
            showgrid=True,
            gridcolor="rgba(255,255,255,0.06)",
            zeroline=False,
            tickfont=dict(color="#888"),
        ),
        yaxis=dict(
            categoryorder="total ascending",
            tickfont=dict(size=12, color="#DDDDDD"),
        ),
        height=430,
        margin=dict(l=10, r=70, t=50, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        hoverlabel=dict(
            bgcolor="#1A1A1A",
            bordercolor=F1_RED,
            font_color="white",
            font_size=13,
        ),
    )
    st.plotly_chart(fig, width="stretch")

# ── Tableau complet du classement ────────────────────────────────────────────
with col_table:
    if is_drivers:
        rows = []
        for s in standings:
            nat_f = nat_flag(s["driver"].get("nationality", ""))
            rows.append({
                "Pos":    s["position"],
                "":       nat_f,
                "Code":   s["driver"]["code"] or "—",
                "Pilote": f"{s['driver']['first_name']} {s['driver']['last_name']}",
                "Écurie": s["constructor_name"],
                "Pts":    s["points"],
                "V":      s["wins"],
            })
        df = pd.DataFrame(rows).set_index("Pos")
        column_config = {
            "":    st.column_config.TextColumn("", width="small"),
            "Pts": st.column_config.NumberColumn("Pts", format="%.1f"),
            "V":   st.column_config.NumberColumn("V",   width="small"),
        }
    else:
        rows = [
            {
                "Pos":          s["position"],
                "Constructeur": s["constructor"]["name"],
                "Nat.":         s["constructor"]["nationality"],
                "Pts":          s["points"],
                "V":            s["wins"],
            }
            for s in standings
        ]
        df = pd.DataFrame(rows).set_index("Pos")
        column_config = {
            "Pts": st.column_config.NumberColumn("Pts", format="%.1f"),
            "V":   st.column_config.NumberColumn("V",   width="small"),
        }

    st.dataframe(
        df,
        width="stretch",
        height=430,
        column_config=column_config,
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    f"<p style='color:#555; font-size:0.78em; text-align:center;'>"
    f"Données : Jolpica API (Ergast MRE) &nbsp;·&nbsp; "
    f"Saison {standings_data.get('season','—')} Round {standings_data.get('round','—')} &nbsp;·&nbsp; "
    f"Cache 5 min &nbsp;·&nbsp; F1 Live Dashboard</p>",
    unsafe_allow_html=True,
)
