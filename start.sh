#!/bin/sh
set -e

# Use default port if PORT is not set
PORT=${PORT:-8080}

echo "Starting application..."
echo "PORT: $PORT"
echo "DATABASE_URL: $DATABASE_URL"

# Start Gunicorn with Railway's PORT
exec gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 120 wsgi:app
