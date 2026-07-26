#!/bin/sh
set -e

# Appliquer les migrations/initialisation si nécessaire
if [ "$RAILWAY_ENVIRONMENT" = "production" ] || [ "$FLASK_ENV" = "production" ]; then
    echo "Initialising database for production..."
    python -c "from app_sqlalchemy import app, db; with app.app_context(): db.create_all()"
fi

# Créer le dossier des uploads
mkdir -p "$UPLOAD_FOLDER"

# Lancer la commande passée en argument
exec "$@"
