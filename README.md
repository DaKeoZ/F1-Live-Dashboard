# F1 Live Dashboard

Dashboard en temps réel pour suivre les données de la Formule 1 : classements pilotes, constructeurs, résultats de courses et bien plus.

## Stack technique

| Couche    | Technologie              |
|-----------|--------------------------|
| Backend   | Python · FastAPI · httpx |
| API F1    | Jolpica (Ergast MRE)     |

## Structure du projet

```
F1-Live-Dashboard/
├── backend/
│   ├── main.py          # Application FastAPI & endpoints
│   └── api_client.py    # Client HTTP vers l'API Jolpica
├── requirements.txt
└── README.md
```

## Installation

```bash
# Créer et activer un environnement virtuel
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS

# Installer les dépendances
pip install -r requirements.txt
```

## Démarrage du serveur

```bash
cd backend
uvicorn main:app --reload
```

Le serveur démarre sur **http://localhost:8000**.

## Endpoints disponibles

| Méthode | Route                  | Description                                          |
|---------|------------------------|------------------------------------------------------|
| GET     | `/`                    | Informations générales sur l'API                    |
| GET     | `/standings/drivers`   | Classement des pilotes (saison en cours par défaut) |
| GET     | `/docs`                | Documentation interactive Swagger UI                |

### Exemples

```
GET /standings/drivers
GET /standings/drivers?season=2024
```

## Source des données

Les données F1 sont fournies par **[Jolpica API](https://api.jolpi.ca/)**, implémentation communautaire compatible avec l'API Ergast MRE.
