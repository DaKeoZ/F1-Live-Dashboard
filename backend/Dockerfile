FROM python:3.11-slim

WORKDIR /app

# Installer les dépendances en premier (couche cachée par Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code source
COPY . .

EXPOSE 9797

# Pas de --reload en prod
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9797"]
