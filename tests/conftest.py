import pytest
import os
import sys
import tempfile
from datetime import datetime, timedelta, date

# Add parent directory to path to import app
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app_sqlalchemy import app as _app, db, init_db
from werkzeug.security import generate_password_hash


@pytest.fixture
def app():
    """Flask application in test mode with SQLAlchemy"""
    # Configure app for testing
    _app.config["TESTING"] = True
    _app.config["WTF_CSRF_ENABLED"] = False
    _app.config["SECRET_KEY"] = "test_secret_key_for_testing_only"

    # Use in-memory SQLite database for tests
    _app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    _app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    return _app


@pytest.fixture
def client(app):
    """Test client with application context and database"""
    from app_sqlalchemy import UserDB, DocumentDB, DashboardConfigDB, GeocodeCacheDB

    with app.app_context():
        # Create all tables
        db.create_all()

        # Clear existing data
        db.session.query(DashboardConfigDB).delete()
        db.session.query(GeocodeCacheDB).delete()
        db.session.query(DocumentDB).delete()
        db.session.query(UserDB).delete()
        db.session.commit()

        # Add test users
        user_password = generate_password_hash("testpass123")
        user1 = UserDB(username="testuser", password=user_password, role="user")
        db.session.add(user1)
        db.session.commit()

        admin_password = generate_password_hash("adminpass123")
        user2 = UserDB(username="testadmin", password=admin_password, role="admin")
        db.session.add(user2)
        db.session.commit()

        user3 = UserDB(username="user2", password=generate_password_hash("password123"), role="user")
        db.session.add(user3)
        db.session.commit()

        # Add test document - date_peremption is now in attributes
        import json

        doc_attributes = {
            "organisme_certificateur": "Bureau Veritas",
            "norme": "ISO 9001:2015",
            "date_peremption": "2026-12-31",
            "entreprise_certifiee": "Test Company",
            "pays": "France",
            "adresse": "123 Test Street",
        }
        doc = DocumentDB(
            title="Test Document",
            content="Contenu de test",
            user_id=user1.id,
            file_path=None,
            type="certificat",
            attributes=json.dumps(doc_attributes),
        )
        db.session.add(doc)
        db.session.commit()

    with app.test_client() as client:
        yield client

    # Clean up
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def logged_in_client(client):
    """Client logged in as testuser via actual login"""
    # Perform actual login
    client.post(
        "/login",
        data={"username": "testuser", "password": "testpass123"},
        follow_redirects=True,
    )

    yield client

    # Logout
    client.get("/logout", follow_redirects=True)


@pytest.fixture
def admin_client(client):
    """Client logged in as admin via actual login"""
    # Perform actual login as admin
    client.post(
        "/login",
        data={"username": "testadmin", "password": "adminpass123"},
        follow_redirects=True,
    )

    yield client

    # Logout
    client.get("/logout", follow_redirects=True)


@pytest.fixture
def test_db(app):
    """Temporary database for unit tests"""
    with app.app_context():
        db.create_all()
        yield db
        db.session.remove()
        db.drop_all()
