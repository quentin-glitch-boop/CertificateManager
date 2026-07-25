"""Tests for application startup and basic configuration"""

import pytest


def test_app_creation():
    """Test that the Flask app can be created without errors"""
    from app import app

    assert app is not None
    assert hasattr(app, "config")
    assert "UPLOAD_FOLDER" in app.config


def test_app_context_and_db_init():
    """Test that database initialization works within app context"""
    from app import app, init_db

    with app.app_context():
        init_db()

        from app import get_db

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        )
        assert cursor.fetchone() is not None

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='documents'"
        )
        assert cursor.fetchone() is not None

        conn.close()


def test_routes_are_registered():
    """Test that essential routes are registered"""
    from app import app

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
        assert (
            found
        ), f"Route {route} not found in registered routes. Available: {routes}"


def test_upload_folder_exists():
    """Test that the upload folder exists"""
    from app import app, ensure_upload_folder
    import os

    # Ensure upload folder exists (create if needed)
    ensure_upload_folder()

    upload_folder = app.config["UPLOAD_FOLDER"]
    assert os.path.exists(upload_folder)
    assert os.path.isdir(upload_folder)
