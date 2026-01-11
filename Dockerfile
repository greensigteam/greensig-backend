# Dockerfile pour Django + GDAL/PostGIS sur Fly.io
FROM python:3.12-slim-bookworm

# Variables d'environnement
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Installer les dépendances système pour GDAL/GEOS/PostGIS
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    postgresql-client \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Définir les variables GDAL pour Python
ENV GDAL_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/libgdal.so
ENV GEOS_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/libgeos_c.so

# Créer le répertoire de travail
WORKDIR /app

# Copier et installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn whitenoise

# Copier le code de l'application
COPY . .

# Copier et rendre exécutable le script d'entrypoint
COPY entrypoint.sh /entrypoint.sh
# Convertir les fins de ligne Windows (CRLF) en Unix (LF) et rendre exécutable
RUN apt-get update && apt-get install -y dos2unix && \
    dos2unix /entrypoint.sh && \
    chmod +x /entrypoint.sh && \
    rm -rf /var/lib/apt/lists/*

# Collecter les fichiers statiques (variables temporaires pour le build uniquement)
RUN SECRET_KEY=build-secret-key-not-for-production \
    DEBUG=False \
    DB_NAME=dummy \
    DB_USER=dummy \
    DB_PASSWORD=dummy \
    DB_HOST=localhost \
    python manage.py collectstatic --noinput

# Exposer le port
EXPOSE 8000

# Script d'entrypoint qui gère les migrations et démarre Daphne
ENTRYPOINT ["/entrypoint.sh"]
