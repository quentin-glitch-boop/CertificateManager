"""
WSGI entry point for Railway deployment.
"""
from app_sqlalchemy import app


# Ensure upload folder exists
def ensure_upload_folder():
    """Create upload folder if it doesn't exist"""
    import os
    upload_folder = os.environ.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(__file__), 'static', 'uploads'))
    try:
        os.makedirs(upload_folder, exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create upload folder: {e}")


# Ensure upload folder exists at startup
ensure_upload_folder()


# Export the app for Gunicorn
app = app
