# F1 Live Dashboard

Dashboard F1 full-stack en temps réel : classements pilotes & constructeurs, calendrier complet avec essais libres, résultats de courses, télémétrie voiture, vue live avec jauge de rapport, stratégie pneumatiques et suivi de position GPS sur circuit.

## Stack technique

| Couche      | Technologie                                      |
|-------------|--------------------------------------------------|
| Backend     | Python · FastAPI · httpx · Pydantic              |
| Frontend    | Streamlit · Plotly · Pandas                      |
| API F1      | Jolpica (Ergast MRE) + OpenF1                    |
| Infra       | Docker · Docker Compose · GitHub Actions · Nginx |

---

## Structure du projet

```
F1-Live-Dashboard/
├── backend/
│   ├── main.py              # Application FastAPI — tous les endpoints
│   ├── api_client.py        # Client HTTP → Jolpica (classements, calendrier, résultats)
│   ├── telemetry_service.py # Client HTTP → OpenF1 (télémétrie, stints, positions GPS)
│   ├── models.py            # Modèles Pydantic (validation & contrats d'API)
│   ├── Dockerfile
│   └── requirements.txt     # Dépendances backend uniquement
├── frontend/
│   ├── app.py               # Application Streamlit (dashboard principal)
│   ├── api.py               # Fonctions d'appel au backend FastAPI (avec cache)
│   ├── Dockerfile
│   └── requirements.txt     # Dépendances frontend uniquement
├── nginx/
│   └── nginx.conf           # Reverse proxy (HTTPS + WebSocket Streamlit)
├── .github/
│   └── workflows/
│       └── docker-publish.yml  # CI/CD → build & push images sur ghcr.io
├── .streamlit/
│   └── config.toml          # Thème sombre F1 (couleurs, font)
├── docker-compose.yml       # Build local
├── docker-compose.prod.yml  # Déploiement VPS (images ghcr.io)
├── .dockerignore
├── requirements.txt         # Toutes les dépendances (dev local)
└── README.md
```

---

## Lancement en local (sans Docker)

### Prérequis

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell
# source .venv/bin/activate     # Linux / macOS

pip install -r requirements.txt
```

### Terminal 1 — Backend FastAPI

```bash
cd backend
uvicorn main:app --reload --port 9797
```

Serveur sur **http://localhost:9797** · Swagger : **http://localhost:9797/docs**

### Terminal 2 — Frontend Streamlit

```bash
cd frontend
streamlit run app.py --server.port 9798
```

Dashboard sur **http://localhost:9798**

---

## Déploiement Docker

### Build & run local

```bash
docker compose up --build
```

- Backend  → **http://localhost:9797**
- Frontend → **http://localhost:9798**

### Production (VPS via ghcr.io)

Chaque `git push main` déclenche GitHub Actions qui build et publie les images sur `ghcr.io`.

**Sur le VPS :**

```bash
mkdir -p /opt/f1-dashboard && cd /opt/f1-dashboard

# Récupérer le compose de prod (remplacer YOUR_GITHUB_USERNAME par votre pseudo GitHub en minuscules)
curl -O https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/F1-Live-Dashboard/main/docker-compose.prod.yml

# Authentification ghcr.io
echo YOUR_GITHUB_TOKEN | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin

# Lancer
docker compose -f docker-compose.prod.yml up -d
```

> Le `docker-compose.prod.yml` référence les images `ghcr.io/YOUR_GITHUB_USERNAME/f1-dashboard-backend:latest` et `ghcr.io/YOUR_GITHUB_USERNAME/f1-dashboard-frontend:latest`. Pensez à adapter les noms d'images à votre dépôt.

**Mise à jour après un push :**

```bash
cd /opt/f1-dashboard
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --remove-orphans
```

### Nginx + HTTPS

```bash
sudo apt install nginx certbot python3-certbot-nginx -y

# Adapter nginx/nginx.conf avec votre domaine, puis :
sudo cp /opt/f1-dashboard/nginx/nginx.conf /etc/nginx/sites-available/f1-dashboard
sudo ln -s /etc/nginx/sites-available/f1-dashboard /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d votre-domaine.example.com
```

---

## Endpoints API

### Classements (Jolpica)

| Méthode | Route                     | Description                                       |
|---------|---------------------------|---------------------------------------------------|
| GET     | `/`                       | Informations générales sur l'API                  |
| GET     | `/standings/drivers`      | Classement pilotes (paramètre `season` optionnel) |
| GET     | `/standings/constructors` | Classement constructeurs                          |

### Calendrier & Résultats (Jolpica)

| Méthode | Route        | Description                                                    |
|---------|--------------|----------------------------------------------------------------|
| GET     | `/race/next` | Prochaine course : FP1/FP2/FP3, qualifs, sprint, course + compte à rebours |
| GET     | `/race/last` | Résultats complets de la dernière course (podium + classement) |

### Télémétrie OpenF1

| Méthode | Route                                      | Description                                                          |
|---------|--------------------------------------------|----------------------------------------------------------------------|
| GET     | `/telemetry/sessions`                      | Sessions disponibles (filtres : `year`, `session_type`)              |
| GET     | `/telemetry/drivers/{session_key}`         | Pilotes d'une session                                                |
| GET     | `/telemetry/{session_key}/{driver_number}` | Données voiture échantillonnées (`sample_size` 10–2000, mode uniform/tail) |

### Stratégie Pneumatiques OpenF1

| Méthode | Route                                  | Description                                             |
|---------|----------------------------------------|---------------------------------------------------------|
| GET     | `/tyres/{session_key}/{driver_number}` | Stints d'un pilote (composé, couleur, tours)            |
| GET     | `/tyres/{session_key}`                 | Stints de tous les pilotes (pour le Gantt multi-pilotes) |

### Positions GPS OpenF1

| Méthode | Route                                     | Description                                                          |
|---------|-------------------------------------------|----------------------------------------------------------------------|
| GET     | `/location/{session_key}`                 | Snapshot de la dernière position GPS de tous les pilotes             |
| GET     | `/location/{session_key}/{driver_number}` | Tracé GPS consécutif (contour circuit, paramètre `sample_size`)      |

### Exemples

```
GET /standings/drivers?season=2026
GET /race/next
GET /telemetry/sessions?year=2026&session_type=Race
GET /telemetry/11234/1?sample_size=1000&mode=uniform
GET /tyres/11234/1
GET /tyres/11234
GET /location/11234
GET /location/11234/1?sample_size=500
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
- Programme complet du weekend : **FP1 · FP2 · FP3** · Qualifications · Sprint (si applicable) · Course
- Compte à rebours vers la session imminente (jours / heures / minutes)

### 🏁 Derniers Résultats
- Podium stylisé (or · argent · bronze) avec couleurs d'équipe
- Tableau complet de la course dans un expandeur

### 📡 Télémétrie (Analyse complète)
- Filtre automatique sur la saison en cours, sélection par défaut sur la course la plus récente
- Mode **Course complète (uniform)** activé automatiquement pour les sessions terminées (défaut 1 000 pts)
- Mode **Temps réel (tail)** pour les sessions en direct
- Graphique Plotly 4 sous-figures : **vitesse** (+ overlay DRS) · **RPM** · **rapport** · **accélérateur / frein**
- Statistiques rapides : vitesse max/moy, RPM max, rapport max, points DRS actifs

### 🔴 Vue Live — Jauge & Temps Réel
- **Rafraîchissement automatique toutes les 5 secondes** (`@st.fragment`) activable via toggle
- Graphique bi-axe **Vitesse (km/h) / RPM** avec marqueurs DRS
- **Jauge circulaire** du rapport de boîte actuel (0–8), colorée par écurie
- **Badge pneu** : cercle coloré Pirelli avec abréviation (S/M/H/I/W) et effet glow
- Bande de valeurs instantanées : vitesse · RPM · gaz · frein · DRS

### 🗺 Positions sur le Circuit
- Snapshot de la dernière position GPS des 22 pilotes, colorés par écurie
- Tracé du circuit en arrière-plan (points GPS **consécutifs** d'un même tour, pas d'interpolation)
- Cache 24 h pour le tracé circuit (données statiques)
- Tableau expandable des coordonnées complètes

### 🛞 Stratégie Pneumatiques
- Stints individuels du pilote sélectionné (composé, tours effectués, âge pneu)
- Gantt multi-pilotes : tous les drivers en un seul graphique
- Couleurs officielles Pirelli : Soft (rouge) · Medium (jaune) · Hard (blanc) · Inter (vert) · Wet (bleu)

---

## Sources des données

| Données                            | Source                                                  |
|------------------------------------|---------------------------------------------------------|
| Classements, calendrier, résultats | [Jolpica API](https://api.jolpi.ca/) (fork Ergast MRE) |
| Télémétrie, positions, stints      | [OpenF1 API](https://openf1.org/)                       |

---

## Notes techniques

- **OpenF1 — authentification (live)** : l’API OpenF1 peut répondre **401 Unauthorized** sans jeton (notamment pendant une session en direct). Configurez le **backend** avec l’un des deux modes documentés sur [openf1.org/auth](https://openf1.org/auth.html) :
  - **`OPENF1_USERNAME` + `OPENF1_PASSWORD`** : le backend obtient un jeton OAuth2 sur `https://api.openf1.org/token` et le renouvelle avant expiration (environ 1 h).
  - **`OPENF1_ACCESS_TOKEN`** : jeton Bearer fixe (à renouveler manuellement ou par script lorsque OpenF1 expire le token).
  - Avec Docker Compose, définissez ces variables dans un fichier `.env` à côté du `docker-compose*.yml` ou exportez-les avant `docker compose up`.
- **Ports** : backend sur `9797`, frontend sur `9798`. En Docker, la variable `API_BASE_URL=http://backend:9797` est injectée dans le conteneur frontend via docker-compose.
- **Rate-limiting OpenF1** : `/location` refuse les requêtes sans `driver_number`. Le backend effectue jusqu'à 21 appels en parallèle (max 3 workers) avec 3 passes de retry automatique.
- **Volumes de données** : `/car_data` et `/location` retournent ~32 000 points par pilote par session. Les données sont sous-échantillonnées avant renvoi (télémétrie : 10–2 000 pts ; tracé circuit : points consécutifs d'un tour).
- **Cache Streamlit** : tracé circuit 24 h · télémétrie 60 s · positions GPS 2 min · classements 5 min. Le bouton "Charger" n'invalide que les caches de télémétrie (pas le tracé circuit).
- **Vue Live** : utilise `@st.fragment(run_every="5s")` (Streamlit ≥ 1.37) — seul le fragment se recharge, pas la page entière. Cache `fetch_live_telemetry` TTL = 5 s.
- **CI/CD** : GitHub Actions build les images Docker et les publie sur `ghcr.io` à chaque push sur `main`. Les noms d'images sont normalisés en minuscules (contrainte Docker).
