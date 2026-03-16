"""F1 Live Dashboard — Frontend Streamlit"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import api as f1_api

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="F1 Live Dashboard",
    page_icon="🏎",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ─────────────────────────────────────────────────────────────────
F1_RED = "#E10600"

TEAM_COLORS: dict[str, str] = {
    "mercedes":      "#00D2BE",
    "ferrari":       "#DC0000",
    "red bull":      "#3671C6",
    "mclaren":       "#FF8000",
    "aston martin":  "#358C75",
    "alpine":        "#0093CC",
    "williams":      "#64C4FF",
    "haas":          "#B6BABD",
    "sauber":        "#52E252",
    "racing bulls":  "#6692FF",
    "rb":            "#6692FF",
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

SESSION_LABELS: dict[str, str] = {
    "Race":             "🔴 Course",
    "Qualifying":       "🔵 Qualifications",
    "Sprint":           "🟠 Sprint",
    "SprintQualifying": "🟡 Sprint Qualifs",
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def team_color(name: str) -> str:
    """Retourne la couleur officielle de l'écurie ou le rouge F1 par défaut."""
    lower = name.lower()
    for key, color in TEAM_COLORS.items():
        if key in lower:
            return color
    return F1_RED


def fmt_dt(iso: str) -> str:
    dt = datetime.fromisoformat(iso)
    return dt.strftime("%a %d %b · %H:%M UTC")


def flag(country: str) -> str:
    return COUNTRY_FLAGS.get(country, "🏁")


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏎 F1 Live Dashboard")
    st.divider()

    view = st.radio(
        "Navigation",
        options=["🏆 Classement Pilotes", "🏭 Classement Constructeurs"],
        label_visibility="collapsed",
    )

    st.divider()

    season = st.text_input(
        "Saison",
        value="current",
        help="Entrez une année (ex: 2024) ou laissez 'current' pour la saison en cours.",
    )

    st.divider()

    if st.button("🔄 Rafraîchir", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.caption("Source : Jolpica API (Ergast MRE)")


# ── Hero : Prochaine course ───────────────────────────────────────────────────
st.markdown("## 🏁 Prochaine Course")

next_race = f1_api.fetch_next_race()

if next_race is None:
    st.warning(
        "Impossible de récupérer la prochaine course. "
        "Vérifiez que le backend FastAPI tourne sur http://localhost:8000.",
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
            country_flag = flag(loc["country"])
            st.markdown(f"### {country_flag} {next_race['race_name']}")
            st.markdown(f"**{circuit['name']}**")
            st.caption(f"📍 {loc['locality']}, {loc['country']}")
            st.caption(
                f"Saison **{next_race['season']}** &nbsp;·&nbsp; Round **{next_race['round']}**"
            )

        with col_sessions:
            st.markdown("**Programme des sessions**")
            sessions_ordered = []
            if next_race.get("sprint_qualifying"):
                sessions_ordered.append(("SprintQualifying", next_race["sprint_qualifying"]["datetime_utc"]))
            if next_race.get("sprint"):
                sessions_ordered.append(("Sprint", next_race["sprint"]["datetime_utc"]))
            sessions_ordered.append(("Qualifying", next_race["qualifying"]["datetime_utc"]))
            sessions_ordered.append(("Race", next_race["race"]["datetime_utc"]))

            for key, dt_iso in sessions_ordered:
                label_icon = SESSION_LABELS.get(key, key)
                st.markdown(f"{label_icon} &nbsp; `{fmt_dt(dt_iso)}`")

        with col_cd:
            st.markdown(f"**Prochain : {session_label}**")
            c1, c2, c3 = st.columns(3)
            c1.metric("Jours",    cd["days"])
            c2.metric("Heures",   cd["hours"])
            c3.metric("Minutes",  cd["minutes"])

st.divider()

# ── Standings section ─────────────────────────────────────────────────────────
is_drivers = "Pilotes" in view

if is_drivers:
    season_label = season if season != "current" else "en cours"
    st.markdown(f"## 🏆 Classement Pilotes — Saison {season_label}")
    data = f1_api.fetch_driver_standings(season)
else:
    season_label = season if season != "current" else "en cours"
    st.markdown(f"## 🏭 Classement Constructeurs — Saison {season_label}")
    data = f1_api.fetch_constructor_standings(season)

if data is None:
    st.error(
        "Impossible de charger les données. "
        "Vérifiez que le backend FastAPI est en cours d'exécution sur **http://localhost:8000**.",
        icon="🚨",
    )
    st.stop()

standings = data.get("standings", [])

if not standings:
    st.warning("Aucune donnée disponible pour cette saison.")
    st.stop()

# ── Layout chart + table ──────────────────────────────────────────────────────
col_chart, col_table = st.columns([6, 4], gap="large")

# --- Plotly bar chart (top 10) ------------------------------------------------
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

    fig = go.Figure(
        go.Bar(
            x=points,
            y=labels,
            orientation="h",
            marker=dict(
                color=colors,
                line=dict(color="rgba(255,255,255,0.08)", width=1),
            ),
            text=[f"  {p} pts" for p in points],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{hovertext}<extra></extra>",
            hovertext=hover,
        )
    )
    fig.update_layout(
        template="plotly_dark",
        title=dict(text=chart_title, font=dict(size=15, color="#F0F0F0"), x=0),
        xaxis=dict(
            title="Points",
            showgrid=True,
            gridcolor="rgba(255,255,255,0.08)",
            zeroline=False,
        ),
        yaxis=dict(
            categoryorder="total ascending",
            tickfont=dict(size=12),
            ticklabelposition="outside left",
        ),
        height=430,
        margin=dict(l=10, r=90, t=50, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        hoverlabel=dict(bgcolor="#1A1A1A", bordercolor="#E10600", font_color="white"),
    )

    st.plotly_chart(fig, use_container_width=True)

# --- Tableau de classement complet --------------------------------------------
with col_table:
    if is_drivers:
        rows = [
            {
                "Pos": s["position"],
                "Code": s["driver"]["code"] or "—",
                "Pilote": f"{s['driver']['first_name']} {s['driver']['last_name']}",
                "Écurie": s["constructor_name"],
                "Pts": s["points"],
                "V": s["wins"],
            }
            for s in standings
        ]
        df = pd.DataFrame(rows).set_index("Pos")
        column_config = {
            "Pts": st.column_config.NumberColumn("Pts", format="%.1f"),
            "V":   st.column_config.NumberColumn("V"),
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
            "V":   st.column_config.NumberColumn("V"),
        }

    st.dataframe(
        df,
        use_container_width=True,
        height=430,
        column_config=column_config,
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    f"Données : Jolpica API · Saison {data.get('season', '—')} · "
    f"Round {data.get('round', '—')} · Cache 5 min"
)
