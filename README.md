# F1 Live Dashboard

Dashboard F1 full-stack en temps réel : classements pilotes & constructeurs, résultats de toutes les courses de la saison, calendrier avec compte à rebours, télémétrie voiture, stratégie pneumatiques et suivi de position GPS sur le tracé du circuit — avec numéros de virages officiels.

## Stack technique

| Couche      | Technologie                                             |
|-------------|---------------------------------------------------------|
| Backend     | Python · FastAPI · httpx · Pydantic · SQLite (cache)    |
| Frontend    | SPA vanilla JS (ES modules) · Chart.js v4 · Canvas 2D  |
| API F1      | Jolpica (Ergast MRE) + OpenF1                           |
| Infra       | Docker · Docker Compose · GitHub Actions · Nginx        |

> Le frontend est une SPA (Single Page Application) HTML/CSS/JS servie directement par FastAPI via `StaticFiles`. Il n'y a pas de framework JS ni de serveur frontend séparé.

---

## Structure du projet

```
F1-Live-Dashboard/
├── backend/
│   ├── main.py              # Application FastAPI — tous les endpoints + montage SPA
│   ├── api_client.py        # Client HTTP → Jolpica (classements, calendrier, résultats)
│   ├── telemetry_service.py # Client HTTP → OpenF1 (télémétrie, stints, positions GPS)
│   ├── live_mqtt_bridge.py  # Bridge MQTT → WebSocket pour sessions en direct
│   ├── models.py            # Modèles Pydantic (validation & contrats d'API)
│   ├── database.py          # Cache SQLite (télémétrie, tracé circuit, stints)
│   ├── static/
│   │   ├── index.html       # Shell SPA (sidebar + pageContainer)
│   │   ├── css/
│   │   │   └── style.css    # Thème sombre F1
│   │   └── js/
│   │       ├── app.js       # Routeur hash-based + navigation
│   │       ├── api.js       # Fetch wrappers + WebSocket manager
│   │       ├── pages/
│   │       │   ├── standings.js  # Pilotes & Constructeurs (podium, KPIs, tableau)
│   │       │   ├── results.js    # Résultats de courses (sélecteur + podium + tableau)
│   │       │   └── telemetry.js  # Télémétrie, circuit, stints
│   │       ├── components/
│   │       │   ├── circuit.js    # Canvas 2D — tracé circuit + numéros de virages
│   │       │   └── charts.js     # Chart.js wrappers
│   │       └── data/
│   │           └── circuit_turns.js  # Comptages officiels de virages (calendrier 2025)
│   ├── Dockerfile
│   └── requirements.txt
├── data/                    # Volume Docker — base SQLite persistante
├── nginx/
│   └── nginx.conf           # Reverse proxy (HTTPS + WebSocket)
├── .github/
│   └── workflows/
│       └── docker-publish.yml  # CI/CD → build & push images sur ghcr.io
├── docker-compose.yml       # Build local
├── docker-compose.prod.yml  # Déploiement VPS (images ghcr.io)
└── README.md
```

---

## Lancement en local (sans Docker)

### Prérequis

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell
# source .venv/bin/activate     # Linux / macOS

pip install -r backend/requirements.txt
```

### Lancer le serveur

```bash
cd backend
uvicorn main:app --reload --port 9797
```

- Dashboard → **http://localhost:9797**
- Swagger API → **http://localhost:9797/docs**

Le frontend SPA est servi automatiquement par FastAPI depuis `backend/static/`.

---

## Déploiement Docker

### Build & run local

```bash
docker compose up --build
```

Dashboard sur **http://localhost:9797**

### Production (VPS via ghcr.io)

Chaque `git push main` déclenche GitHub Actions qui build et publie l'image sur `ghcr.io`.

**Sur le VPS :**

```bash
mkdir -p /opt/f1-dashboard && cd /opt/f1-dashboard

# Récupérer le compose de prod (remplacer YOUR_GITHUB_USERNAME)
curl -O https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/F1-Live-Dashboard/main/docker-compose.prod.yml

# Authentification ghcr.io
echo YOUR_GITHUB_TOKEN | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin

# Lancer
docker compose -f docker-compose.prod.yml up -d
```

**Mise à jour après un push :**

```bash
cd /opt/f1-dashboard
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --remove-orphans
```

### Nginx + HTTPS

```bash
sudo apt install nginx certbot python3-certbot-nginx -y
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
| GET     | `/standings/drivers`      | Classement pilotes (paramètre `season` optionnel) |
| GET     | `/standings/constructors` | Classement constructeurs                          |

### Calendrier & Résultats (Jolpica)

| Méthode | Route                | Description                                                              |
|---------|----------------------|--------------------------------------------------------------------------|
| GET     | `/race/next`         | Prochaine course : sessions, compte à rebours, total manches saison      |
| GET     | `/race/last`         | Résultats de la dernière course disputée                                 |
| GET     | `/race/schedule`     | Calendrier complet de la saison (toutes les courses, passées et futures) |
| GET     | `/race/{round}`      | Résultats d'une manche spécifique (ex: `/race/5`)                        |

### Télémétrie OpenF1

| Méthode | Route                                      | Description                                                              |
|---------|--------------------------------------------|--------------------------------------------------------------------------|
| GET     | `/telemetry/sessions`                      | Sessions disponibles (filtres : `year`, `session_type`)                  |
| GET     | `/telemetry/drivers/{session_key}`         | Pilotes d'une session                                                    |
| GET     | `/telemetry/{session_key}/{driver_number}` | Données voiture (`sample_size` 10–2000, mode `uniform` ou `tail`)        |
| WS      | `/ws/telemetry/{session_key}/{driver_number}` | Flux WebSocket temps réel (sessions en cours)                         |

### Stratégie Pneumatiques

| Méthode | Route                                  | Description                                               |
|---------|----------------------------------------|-----------------------------------------------------------|
| GET     | `/tyres/{session_key}/{driver_number}` | Stints d'un pilote (composé, tours, âge pneu)             |
| GET     | `/tyres/{session_key}`                 | Stints de tous les pilotes (Gantt multi-pilotes)           |

### Positions GPS

| Méthode | Route                                     | Description                                               |
|---------|-------------------------------------------|-----------------------------------------------------------|
| GET     | `/location/{session_key}`                 | Snapshot dernière position GPS de tous les pilotes        |
| GET     | `/location/{session_key}/{driver_number}` | Tracé GPS (contour circuit, paramètre `sample_size`)      |

### Exemples

```
GET /standings/drivers?season=2025
GET /race/schedule
GET /race/7
GET /race/next
GET /telemetry/sessions?year=2025&session_type=Race
GET /telemetry/11234/1?sample_size=1000&mode=uniform
GET /tyres/11234
GET /location/11234/1?sample_size=800
```

---

## Fonctionnalités du Dashboard

### Classement Pilotes & Constructeurs
- KPIs : saison, manche actuelle / total de la saison, leader, prochain GP
- Compte à rebours vers la prochaine session (FP1 / Qualifs / Sprint / Course)
- Podium stylisé de la dernière course (or · argent · bronze) avec effet de marche
- Graphique horizontal top 10 (Chart.js) avec couleurs officielles des écuries
- Tableau complet du classement saison

### Résultats de Courses
- Sélecteur de course : toutes les manches disputées de la saison
- Podium et tableau complet pour chaque course sélectionnée
- Informations : position de départ, tours, temps / statut, points, meilleur tour

### Télémétrie
- Sélection par année → meeting → session → pilote
- Mode **Historique** (uniform) pour les sessions terminées
- Mode **Temps réel** (WebSocket) pour les sessions en cours
- Graphiques Chart.js : vitesse · RPM · rapport · gaz / frein
- Badge pneu actuel mis à jour en temps réel
- Stratégie pneumatiques : stints individuels + Gantt multi-pilotes

### Circuit GPS
- Tracé canvas 2D normalisé (ratio d'aspect préservé, Y inversé)
- Numéros de virages officiels auto-détectés depuis la courbure du tracé GPS, calibrés sur les comptages officiels du calendrier 2025 (23 circuits)
- Position en temps réel de tous les pilotes (points colorés par écurie)
- Cache SQLite pour le tracé (données statiques par session)

---

## Cache SQLite

| Table             | Contenu                                             | Invalidation               |
|-------------------|-----------------------------------------------------|----------------------------|
| `telemetry_cache` | Métadonnées des télémétries mises en cache          | Si dernier point < 2 h     |
| `telemetry_points`| Points voiture (speed, rpm, gear, throttle, brake)  | Avec le cache parent       |
| `car_path_cache`  | Métadonnées du tracé circuit                        | Jamais (données statiques) |
| `car_path_points` | Coordonnées GPS (x, y, z)                           | Jamais                     |
| `stints_cache`    | Métadonnées des stints                              | Après complétion session    |
| `tyre_stints`     | Stints individuels (composé, tours, âge)            | Avec le cache parent       |

Volume Docker : `./data:/app/data` (dev) ou volume nommé `f1_data` (prod).

---

## Sources des données

| Données                            | Source                                                  |
|------------------------------------|---------------------------------------------------------|
| Classements, calendrier, résultats | [Jolpica API](https://api.jolpi.ca/) (fork Ergast MRE) |
| Télémétrie, positions, stints      | [OpenF1 API](https://openf1.org/)                       |

---

## Notes techniques

- **Authentification OpenF1 (live)** : sans jeton, l'API OpenF1 renvoie 401 pendant les sessions en direct. Configurez le backend via variables d'environnement :
  - `OPENF1_USERNAME` + `OPENF1_PASSWORD` — le backend obtient un token OAuth2 et le renouvelle automatiquement (~1 h)
  - `OPENF1_ACCESS_TOKEN` — token Bearer fixe
  - Avec Docker Compose, définissez-les dans un fichier `.env` à côté du `docker-compose*.yml`

- **WebSocket live** : le bridge MQTT (`live_mqtt_bridge.py`) relaye les données OpenF1 temps réel vers le client via `/ws/telemetry/{session_key}/{driver_number}`.

- **Numéros de virages** : extraits automatiquement depuis le tracé GPS multi-tours (premier tour isolé par détection de retour au point de départ). Les comptages officiels par circuit (`circuit_turns.js`) permettent de calibrer la détection et d'assurer le bon nombre de virages numérotés. Le virage T1 est positionné après la plus longue ligne droite (approximation de la ligne droite principale).

- **Tracé circuit** : le tracé GPS couvre ~6 tours des 15 premières minutes de session. Le `closePath()` a été supprimé pour éviter la ligne droite parasite entre le dernier point GPS et le premier.

- **Ports** : uniquement le port `9797` (backend + SPA). Plus de service frontend séparé.

- **CI/CD** : GitHub Actions build l'image Docker du backend et la publie sur `ghcr.io` à chaque push sur `main`.
