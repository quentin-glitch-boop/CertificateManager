"""
WSGI entry point for Railway deployment.
Handles database initialization before starting the app.
"""
import os
import time
from app_sqlalchemy import app, db, init_db

# Ensure upload folder exists
def ensure_upload_folder():
    """Create upload folder if it doesn't exist"""
    upload_folder = os.environ.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(__file__), 'static', 'uploads'))
    try:
        os.makedirs(upload_folder, exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create upload folder: {e}")

# Initialize database on startup
with app.app_context():
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            print(f"[{retry_count + 1}/{max_retries}] Attempting to initialize database...")
            init_db()
            print("✓ Database initialized successfully")
            break
        except Exception as e:
            retry_count += 1
            print(f"✗ Database initialization failed: {e}")
            if retry_count < max_retries:
                wait_time = 2 ** retry_count  # Exponential backoff
                print(f"  Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print("✗ Failed to initialize database after all retries")
                raise

# Ensure upload folder exists
ensure_upload_folder()

# Export the app for Gunicorn
app = app
