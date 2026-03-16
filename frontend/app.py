"""F1 Live Dashboard — Frontend Streamlit"""

from __future__ import annotations

from datetime import datetime

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
    "sauber":       "#52E252",
    "racing bulls": "#6692FF",
    "rb":           "#6692FF",
}

# Light teams need dark text on their badge
_LIGHT_TEAMS = {"#64C4FF", "#B6BABD", "#52E252", "#FF8000"}

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
    "Race":             "🔴 Course",
    "Qualifying":       "🔵 Qualifications",
    "Sprint":           "🟠 Sprint",
    "SprintQualifying": "🟡 Sprint Qualifs",
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


def fmt_dt(iso: str) -> str:
    dt = datetime.fromisoformat(iso)
    return dt.strftime("%a %d %b · %H:%M UTC")


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

    if st.button("🔄 Rafraîchir les données", use_container_width=True):
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
    col_sess, col_drv, col_opts = st.columns([3, 3, 2], gap="medium")

    with col_sess:
        sessions = f1_api.fetch_openf1_sessions()
        if not sessions:
            st.error("Impossible de récupérer les sessions OpenF1.", icon="🚨")
            return

        session_options = {
            f"{s['circuit_short_name']} {s['date_start'][:10]} ({s['session_name']})": s["session_key"]
            for s in sessions
        }
        selected_session_label = st.selectbox("Session", list(session_options.keys()))
        selected_session_key   = session_options[selected_session_label]

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
        sample_size = st.slider("Points", min_value=50, max_value=400, value=150, step=50)
        mode = st.radio(
            "Mode",
            options=["uniform", "tail"],
            format_func=lambda m: "Race overview" if m == "uniform" else "Live (fin session)",
            horizontal=True,
        )

    # ── Fetch & affichage ────────────────────────────────────────────────────
    if st.button("⚡ Charger la télémétrie", type="primary", use_container_width=True):
        st.cache_data.clear()

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
    times     = [datetime.fromisoformat(p["timestamp"]) for p in points]
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
            fillcolor=f"{drv_colour}18",
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

    st.plotly_chart(fig, use_container_width=True)


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
            sessions_ordered: list[tuple[str, str]] = []
            if next_race.get("sprint_qualifying"):
                sessions_ordered.append(("SprintQualifying", next_race["sprint_qualifying"]["datetime_utc"]))
            if next_race.get("sprint"):
                sessions_ordered.append(("Sprint", next_race["sprint"]["datetime_utc"]))
            sessions_ordered.append(("Qualifying", next_race["qualifying"]["datetime_utc"]))
            sessions_ordered.append(("Race", next_race["race"]["datetime_utc"]))

            for key, dt_iso in sessions_ordered:
                icon = SESSION_LABELS.get(key, key)
                st.markdown(f"{icon} &nbsp; `{fmt_dt(dt_iso)}`")

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
            use_container_width=True,
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
        "Impossible de charger les données — backend indisponible sur **http://localhost:8000**.",
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
    st.plotly_chart(fig, use_container_width=True)

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
        use_container_width=True,
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
