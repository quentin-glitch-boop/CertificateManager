"""
WSGI entry point for Railway deployment.
"""
import os
import sys


print("=== Starting WSGI ===", file=sys.stderr)
print(f"PORT: {os.environ.get('PORT', 'not set')}", file=sys.stderr)
print(f"DATABASE_URL: {os.environ.get('DATABASE_URL', 'not set')}", file=sys.stderr)


from app_sqlalchemy import app


# Ensure upload folder exists
def ensure_upload_folder():
    """Create upload folder if it doesn't exist"""
    upload_folder = os.environ.get('UPLOAD_FOLDER', '/app/static/uploads')
    try:
        os.makedirs(upload_folder, exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create upload folder: {e}", file=sys.stderr)


# Ensure upload folder exists at startup
ensure_upload_folder()


print("=== WSGI ready ===", file=sys.stderr)


# Export the app for Gunicorn
app = app
