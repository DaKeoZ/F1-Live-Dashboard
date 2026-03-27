"""
Modèles Pydantic pour les données F1.
Servent à la fois de schémas de validation et de contrats de réponse API.
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pilotes
# ---------------------------------------------------------------------------


class DriverInfo(BaseModel):
    """Informations d'identité d'un pilote."""

    driver_id: str = Field(..., description="Identifiant unique Ergast/Jolpica")
    code: str | None = Field(None, description="Code 3 lettres (ex: VER, HAM)")
    number: str | None = Field(None, description="Numéro de course")
    first_name: str
    last_name: str
    nationality: str


class DriverStanding(BaseModel):
    """Entrée du classement pilotes."""

    position: int = Field(..., ge=1, description="Position au classement")
    points: float = Field(..., ge=0)
    wins: int = Field(..., ge=0)
    driver: DriverInfo
    constructor_name: str = Field(..., description="Nom de l'écurie actuelle")


class DriverStandingsResponse(BaseModel):
    """Réponse complète de l'endpoint /standings/drivers."""

    season: str
    round: int | None = Field(None, description="Dernier round inclus dans le classement")
    total: int
    standings: list[DriverStanding]


# ---------------------------------------------------------------------------
# Constructeurs
# ---------------------------------------------------------------------------


class ConstructorInfo(BaseModel):
    """Informations d'identité d'un constructeur."""

    constructor_id: str = Field(..., description="Identifiant unique Ergast/Jolpica")
    name: str
    nationality: str


class ConstructorStanding(BaseModel):
    """Entrée du classement constructeurs."""

    position: int = Field(..., ge=1)
    points: float = Field(..., ge=0)
    wins: int = Field(..., ge=0)
    constructor: ConstructorInfo


class ConstructorStandingsResponse(BaseModel):
    """Réponse complète de l'endpoint /standings/constructors."""

    season: str
    round: int | None = Field(None, description="Dernier round inclus dans le classement")
    total: int
    standings: list[ConstructorStanding]


# ---------------------------------------------------------------------------
# Calendrier & prochaine course
# ---------------------------------------------------------------------------


class CircuitLocation(BaseModel):
    locality: str
    country: str
    lat: float
    long: float


class Circuit(BaseModel):
    circuit_id: str
    name: str
    location: CircuitLocation


class SessionInfo(BaseModel):
    """Date et heure UTC d'une session (qualifs, course, sprint…)."""

    datetime_utc: datetime = Field(..., description="Date et heure UTC de la session")


class Countdown(BaseModel):
    """Compte à rebours calculé jusqu'à la prochaine session imminente."""

    target_session: str = Field(..., description="Nom de la session visée (ex: 'Qualifying', 'Race')")
    target_datetime_utc: datetime
    days: int = Field(..., ge=0)
    hours: int = Field(..., ge=0, le=23)
    minutes: int = Field(..., ge=0, le=59)
    total_seconds: int = Field(..., ge=0)


class NextRaceResponse(BaseModel):
    """Réponse complète de l'endpoint /race/next."""

    season: str
    round: int
    race_name: str
    circuit: Circuit
    fp1: SessionInfo | None = Field(None, description="Essais libres 1")
    fp2: SessionInfo | None = Field(None, description="Essais libres 2")
    fp3: SessionInfo | None = Field(None, description="Essais libres 3 (absent sur sprint weekend)")
    qualifying: SessionInfo
    sprint: SessionInfo | None = Field(None, description="Présent uniquement lors d'un sprint weekend")
    sprint_qualifying: SessionInfo | None = Field(None, description="Qualifications sprint")
    race: SessionInfo
    countdown: Countdown


# ---------------------------------------------------------------------------
# Résultats de course
# ---------------------------------------------------------------------------


class RaceResultEntry(BaseModel):
    """Résultat individuel d'un pilote pour une course donnée."""

    position: int
    driver_code: str | None = Field(None, description="Code 3 lettres du pilote")
    driver_name: str
    constructor_name: str
    grid: int = Field(..., description="Position de départ")
    laps: int
    time_or_status: str = Field(..., description="Temps de course ou statut (DNF, +Xm Xs…)")
    points: float = Field(..., ge=0)
    fastest_lap_time: str | None = None
    fastest_lap_rank: int | None = None


class LastRaceResponse(BaseModel):
    """Réponse complète de l'endpoint /race/last."""

    season: str
    round: int
    race_name: str
    circuit: Circuit
    date: str
    results: list[RaceResultEntry]


# ---------------------------------------------------------------------------
# Télémétrie OpenF1
# ---------------------------------------------------------------------------


class TelemetryPoint(BaseModel):
    """Un point de données de télémétrie voiture à un instant T."""

    timestamp: datetime
    speed: int = Field(..., ge=0, description="Vitesse en km/h")
    rpm: int = Field(..., ge=0, description="Tours/minute moteur")
    n_gear: int = Field(..., ge=0, le=8, description="Rapport de boîte engagé (0 = neutre)")
    throttle: int = Field(..., ge=0, le=100, description="Ouverture des gaz en %")
    brake: int = Field(..., ge=0, le=100, description="Pression de frein en %")
    drs: int | None = Field(None, description="Statut DRS (0=fermé, 14=ouvert)")


class TelemetryResponse(BaseModel):
    """Réponse de l'endpoint /telemetry — données voiture échantillonnées."""

    session_key: int
    driver_number: int
    total_raw_points: int = Field(..., description="Nombre total de points bruts dans la session")
    sample_size: int = Field(..., description="Nombre de points retournés après échantillonnage")
    sample_method: str = Field(..., description="Méthode d'échantillonnage : 'uniform' ou 'tail'")
    points: list[TelemetryPoint]


class OpenF1Session(BaseModel):
    """Session de course provenant de l'API OpenF1."""

    meeting_key: int | None = Field(None, description="Identifiant weekend (meeting) OpenF1")
    session_key: int
    session_type: str | None = Field(None, description="Type OpenF1 (Practice/Qualifying/Race…)")
    session_name: str
    date_start: datetime
    date_end: datetime | None = Field(None, description="Fin de session si disponible")
    circuit_short_name: str
    country_name: str
    year: int


class OpenF1Driver(BaseModel):
    """Pilote dans une session OpenF1."""

    driver_number: int
    name_acronym: str
    full_name: str
    team_name: str
    team_colour: str | None = Field(None, description="Couleur HEX sans #")


# ---------------------------------------------------------------------------
# Stratégie Pneumatiques OpenF1
# ---------------------------------------------------------------------------


class TyreStint(BaseModel):
    """Un stint (séquence de tours sur un même jeu de pneus)."""

    stint_number: int = Field(..., ge=1)
    lap_start: int = Field(..., ge=1, description="Tour de début du stint")
    lap_end: int | None = Field(None, description="Tour de fin du stint (None si course en cours)")
    compound: str | None = Field(
        None,
        description="Composé : SOFT | MEDIUM | HARD | INTERMEDIATE | WET | None",
    )
    tyre_age_at_start: int = Field(..., ge=0, description="Âge des pneus en tours au début du stint")
    laps_in_stint: int | None = Field(None, description="Nombre de tours effectués sur ce jeu")
    compound_color: str = Field(..., description="Couleur HEX officielle du composé")
    compound_text_color: str = Field(..., description="Couleur HEX pour le texte sur fond composé")


class TyreStrategyResponse(BaseModel):
    """Réponse de l'endpoint /tyres — stratégie pneus d'un pilote."""

    session_key: int
    driver_number: int
    total_stints: int
    stints: list[TyreStint]


class AllTyreStrategiesResponse(BaseModel):
    """Réponse de l'endpoint /tyres/{session_key} — stratégie de tous les pilotes."""

    session_key: int
    total_drivers: int
    strategies: list[TyreStrategyResponse]


# ---------------------------------------------------------------------------
# Positions GPS OpenF1
# ---------------------------------------------------------------------------


class DriverPosition(BaseModel):
    """Dernière position GPS connue d'un pilote."""

    driver_number: int
    x: float = Field(..., description="Coordonnée X dans le repère circuit")
    y: float = Field(..., description="Coordonnée Y dans le repère circuit")
    z: float = Field(..., description="Altitude normalisée")
    timestamp: datetime = Field(..., description="Horodatage UTC de ce point")
    driver_code: str | None = None
    team_name: str | None = None
    team_colour: str | None = Field(None, description="Couleur HEX de l'écurie (avec #)")


class AllDriversPositionResponse(BaseModel):
    """Snapshot de la dernière position GPS de tous les pilotes d'une session."""

    session_key: int
    captured_at: datetime = Field(..., description="Heure UTC de la requête API")
    reference_timestamp: datetime = Field(..., description="Timestamp du point de données le plus récent")
    total_drivers: int
    positions: list[DriverPosition]


class CarPathPoint(BaseModel):
    """Un point du tracé GPS d'une voiture (vue circuit top-down)."""

    x: float
    y: float
    z: float


class CarPathResponse(BaseModel):
    """Tracé GPS sous-échantillonné d'un pilote — sert à dessiner le contour du circuit."""

    session_key: int
    driver_number: int
    total_raw_points: int
    sample_size: int
    path: list[CarPathPoint]
