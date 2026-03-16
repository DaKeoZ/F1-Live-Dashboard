# Le contexte de build doit être la racine du projet (docker-compose le gère)
# afin de pouvoir copier .streamlit/config.toml
FROM python:3.11-slim

WORKDIR /app

# Dépendances
COPY frontend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code source frontend
COPY frontend/ .

# Thème Streamlit (situé à la racine du repo)
COPY .streamlit/ .streamlit/

EXPOSE 9798

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9798/_stcore/health')"

CMD ["streamlit", "run", "app.py", \
     "--server.port=9798", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
