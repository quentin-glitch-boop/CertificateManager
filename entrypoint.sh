#!/bin/sh
set -e

# Appliquer les migrations/initialisation si nécessaire
if [ "$FLASK_ENV" = "production" ]; then
    echo "Initialising database for production..."
    python init_db.py
fi

# Créer le dossier des uploads
mkdir -p "$UPLOAD_FOLDER"

# Lancer la commande passée en argument
exec "$@"
