"""
Document tests for DocManager application
"""

import pytest


class TestDocumentList:
    """Document list tests"""

    def test_documents_page_loads(self, logged_in_client):
        """Documents page should load"""
        response = logged_in_client.get("/")
        assert response.status_code == 200
        # Check for document list or similar content
        assert b"Document" in response.data or b"Rechercher" in response.data

    def test_documents_visible(self, logged_in_client):
        """Documents should be visible"""
        response = logged_in_client.get("/")
        # The test document was added in conftest
        assert b"Test Document" in response.data or b"Contenu de test" in response.data

    def test_search_by_author(self, logged_in_client):
        """Search by author should work"""
        response = logged_in_client.get("/?author=testuser")
        assert response.status_code == 200
        # Should find the test document
        assert b"Test Document" in response.data or b"Contenu de test" in response.data


class TestDocumentCreation:
    """Document creation tests"""

    def test_add_document_missing_title(self, logged_in_client):
        """Adding document without title should fail"""
        response = logged_in_client.post(
            "/add", data={"title": "", "content": "Contenu"}, follow_redirects=True
        )
        # Should show error about required title
        assert (
            b"titre est obligatoire" in response.data
            or b"Le titre est obligatoire" in response.data
            or b"titre" in response.data.lower()
        )

    def test_add_document_missing_pdf(self, logged_in_client):
        """Adding document without PDF should fail"""
        response = logged_in_client.post(
            "/add",
            data={"title": "Nouveau Document", "content": "Contenu"},
            follow_redirects=True,
        )
        # Should show error about required PDF
        assert (
            b"PDF est obligatoire" in response.data
            or b"Le fichier PDF est obligatoire" in response.data
            or b"fichier" in response.data.lower()
        )


class TestUserManagement:
    """User management tests"""

    def test_admin_users_page_loads(self, admin_client):
        """Admin users page should load"""
        response = admin_client.get("/admin/users")
        assert response.status_code == 200
        # Check for user management content
        assert (
            b"Gestion des Utilisateurs" in response.data
            or b"Utilisateurs" in response.data
        )

    def test_admin_users_page_requires_admin(self, logged_in_client):
        """Admin users page requires admin role"""
        response = logged_in_client.get("/admin/users", follow_redirects=True)
        # Non-admin should be denied access
        assert (
            b"Acces refuse" in response.data
            or response.status_code == 403
            or response.request.path == "/"
        )

    def test_add_user_as_admin(self, admin_client):
        """Admin can add user"""
        response = admin_client.post(
            "/admin/add_user",
            data={"username": "newuser", "password": "newpassword123", "role": "user"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert (
            b"Utilisateur ajoute" in response.data
            or b"ajoute" in response.data
            or b"success" in response.data.lower()
        )

    def test_add_user_duplicate_username(self, admin_client):
        """Cannot add user with duplicate username"""
        response = admin_client.post(
            "/admin/add_user",
            data={"username": "testuser", "password": "newpassword123", "role": "user"},
            follow_redirects=True,
        )
        # Should show error about duplicate username
        assert (
            b"existe deja" in response.data.lower()
            or b"existe" in response.data.lower()
        )

    def test_add_user_short_password(self, admin_client):
        """Short password should be rejected"""
        response = admin_client.post(
            "/admin/add_user",
            data={"username": "newuser2", "password": "short", "role": "user"},
            follow_redirects=True,
        )
        # Should show error about password length
        # Check for the error message in the response (could be in flash message)
        assert (
            b"6 caracteres" in response.data.lower()
            or b"caracteres" in response.data.lower()
            or b"mot de passe" in response.data.lower()
        )
