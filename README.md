# F1 Live Dashboard

Dashboard F1 full-stack en temps réel : classements pilotes & constructeurs, calendrier, résultats, télémétrie voiture, stratégie pneumatiques et suivi de position GPS sur circuit.

## Stack technique

| Couche     | Technologie                          |
|------------|--------------------------------------|
| Backend    | Python · FastAPI · httpx · Pydantic  |
| Frontend   | Streamlit · Plotly · Pandas          |
| API F1     | Jolpica (Ergast MRE) + OpenF1        |

---

## Structure du projet

```
F1-Live-Dashboard/
├── backend/
│   ├── main.py              # Application FastAPI — tous les endpoints
│   ├── api_client.py        # Client HTTP → Jolpica (classements, calendrier, résultats)
│   ├── telemetry_service.py # Client HTTP → OpenF1 (télémétrie, stints, positions GPS)
│   └── models.py            # Modèles Pydantic (validation & contrats d'API)
├── frontend/
│   ├── app.py               # Application Streamlit (dashboard principal)
│   └── api.py               # Fonctions d'appel au backend FastAPI (avec cache)
├── .streamlit/
│   └── config.toml          # Thème sombre F1 (couleurs, font)
├── requirements.txt
└── README.md
```

---

## Installation

```bash
# 1. Créer et activer un environnement virtuel
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell
# source .venv/bin/activate     # Linux / macOS

# 2. Installer toutes les dépendances (backend + frontend)
pip install -r requirements.txt
```

---

## Démarrage de l'application

L'application comporte deux processus à lancer dans **deux terminaux séparés**.

### Terminal 1 — Backend FastAPI

```bash
cd backend
uvicorn main:app --reload
```

Le serveur démarre sur **http://localhost:8000**.  
La documentation interactive Swagger est disponible sur **http://localhost:8000/docs**.

### Terminal 2 — Frontend Streamlit

```bash
cd frontend
streamlit run app.py
```

Le dashboard s'ouvre automatiquement sur **http://localhost:8501**.

---

## Endpoints API

### Classements (Jolpica)

| Méthode | Route                        | Description                                       |
|---------|------------------------------|---------------------------------------------------|
| GET     | `/`                          | Informations générales sur l'API                  |
| GET     | `/standings/drivers`         | Classement pilotes (paramètre `season` optionnel) |
| GET     | `/standings/constructors`    | Classement constructeurs                          |

### Calendrier & Résultats (Jolpica)

| Méthode | Route         | Description                                                    |
|---------|---------------|----------------------------------------------------------------|
| GET     | `/race/next`  | Prochaine course : circuit, horaires, compte à rebours         |
| GET     | `/race/last`  | Résultats complets de la dernière course (podium + classement) |

### Télémétrie OpenF1

| Méthode | Route                                      | Description                                                         |
|---------|--------------------------------------------|---------------------------------------------------------------------|
| GET     | `/telemetry/sessions`                      | Liste des sessions disponibles (filtres : `year`, `session_type`)   |
| GET     | `/telemetry/drivers/{session_key}`         | Pilotes d'une session                                               |
| GET     | `/telemetry/{session_key}/{driver_number}` | Données voiture échantillonnées (speed, rpm, gear, throttle, brake) |

### Stratégie Pneumatiques OpenF1

| Méthode | Route                                  | Description                                           |
|---------|----------------------------------------|-------------------------------------------------------|
| GET     | `/tyres/{session_key}/{driver_number}` | Stints d'un pilote (composé, couleur, tours)          |
| GET     | `/tyres/{session_key}`                 | Stints de tous les pilotes (pour le Gantt de stratégie) |

### Positions GPS OpenF1

| Méthode | Route                                    | Description                                                         |
|---------|------------------------------------------|---------------------------------------------------------------------|
| GET     | `/location/{session_key}`                | Snapshot de la dernière position GPS de tous les pilotes            |
| GET     | `/location/{session_key}/{driver_number}`| Tracé GPS complet sous-échantillonné (contour circuit, `sample_size` optionnel) |

### Exemples d'appels

```
GET /standings/drivers?season=2025
GET /race/next
GET /telemetry/sessions?year=2026&session_type=Race
GET /telemetry/11234/1?sample_size=200&mode=uniform
GET /tyres/11234/1
GET /tyres/11234
GET /location/11234
GET /location/11234/1?sample_size=600
```

---

## Fonctionnalités du Dashboard

### 🏆 Classement Pilotes
- Graphique Plotly horizontal : top 10 pilotes avec couleurs officielles des écuries
- Tableau complet du classement saison

### 🏗 Classement Constructeurs
- Graphique Plotly horizontal avec couleurs équipes
- Tableau complet

### 📅 Prochaine Course (Hero section)
- Nom du Grand Prix, circuit, pays
- Horaires UTC de la qualification, de la course (et sprint si applicable)
- Compte à rebours jusqu'à la prochaine session imminente

### 🏁 Derniers Résultats
- Podium stylisé (or · argent · bronze) avec couleurs d'équipe
- Tableau complet de la course dans un expandeur

### 📡 Télémétrie
- Sélection de session et de pilote via menus déroulants
- Paramètres : taille d'échantillon (10–500 pts) et mode (uniform / tail)
- Graphique Plotly 4 sous-figures : **vitesse** (+ overlay DRS) · **RPM** · **rapport** · **accélérateur / frein**
- Statistiques rapides : vitesse max/moy, RPM max, rapport max, points DRS actifs

### 🗺 Positions sur le Circuit
- Snapshot de la dernière position GPS des 22 pilotes, colorés par écurie
- Tracé du circuit en arrière-plan (contour dessiné depuis le GPS d'un pilote)
- Tooltip : code pilote, équipe, coordonnées x/y/z
- Tableau expandable des coordonnées complètes

### 🛞 Stratégie Pneumatiques
- Stints individuels du pilote sélectionné (composé, tours, âge pneu)
- Gantt multi-pilotes (tous les drivers en un seul graphique)
- Couleurs officielles Pirelli : Soft (rouge) · Medium (jaune) · Hard (blanc) · Inter (vert) · Wet (bleu)

---

## Sources des données

| Données                         | Source                                                  |
|---------------------------------|---------------------------------------------------------|
| Classements, calendrier, résultats | [Jolpica API](https://api.jolpi.ca/) (fork Ergast MRE) |
| Télémétrie, positions, stints   | [OpenF1 API](https://openf1.org/)                       |

---

## Notes techniques

- **Rate-limiting OpenF1** : l'endpoint `/location` ne supporte pas les requêtes globales (sans `driver_number`). Le backend effectue jusqu'à 21 appels en parallèle (max 3 workers) avec 3 passes de retry automatique pour contourner les limites.
- **Volumes de données** : `/car_data` et `/location` retournent ~32 000 points par pilote par session. Les données sont sous-échantillonnées (par défaut 100–500 pts) avant d'être renvoyées au frontend.
- **Cache Streamlit** : les données coûteuses (tracé circuit, télémétrie) sont mises en cache 1 h ; les positions GPS 2 min ; les classements 5 min.
