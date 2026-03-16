"""
Modèles Pydantic pour les données F1.
Servent à la fois de schémas de validation et de contrats de réponse API.
"""

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
