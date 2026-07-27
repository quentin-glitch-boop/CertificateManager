"""Tests for application startup and basic configuration"""

import pytest


def test_app_creation():
    """Test that the Flask app can be created without errors"""
    from app_sqlalchemy import app

    assert app is not None
    assert hasattr(app, "config")
    assert "UPLOAD_FOLDER" in app.config


def test_app_context_and_db_init():
    """Test that database initialization works within app context"""
    from app_sqlalchemy import app, init_db, db, UserDB, DocumentDB

    with app.app_context():
        # Initialize database
        init_db()

        # Check that tables exist by querying them
        # This will raise an exception if tables don't exist
        user_count = UserDB.query.count()
        doc_count = DocumentDB.query.count()

        # Tables exist if we can query them
        assert True


def test_routes_are_registered():
    """Test that essential routes are registered"""
    from app_sqlalchemy import app

    routes = [rule.rule for rule in app.url_map.iter_rules()]

    expected_routes = [
        "/",
        "/login",
        "/logout",
        "/add",
        "/admin/users",
        "/admin/add_user",
    ]

    for route in expected_routes:
        found = any(route in r for r in routes)
        assert found, f"Route {route} not found in registered routes. Available: {routes}"


def test_upload_folder_exists():
    """Test that the upload folder exists"""
    from app_sqlalchemy import app, ensure_upload_folder
    import os

    # Ensure upload folder exists (create if needed)
    ensure_upload_folder()

    upload_folder = app.config["UPLOAD_FOLDER"]
    assert os.path.exists(upload_folder)
    assert os.path.isdir(upload_folder)
