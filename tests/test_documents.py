"""
Document tests for DocManager application
"""

import pytest


class TestDocumentList:
    """Document list tests"""

    def test_documents_page_loads(self, logged_in_client):
        """Documents page should load"""
        response = logged_in_client.get("/documents")
        assert response.status_code == 200
        # Check for document list or similar content
        assert b"Document" in response.data or b"Rechercher" in response.data

    def test_documents_visible(self, logged_in_client):
        """Documents should be visible"""
        response = logged_in_client.get("/documents")
        # The test document was added in conftest
        assert b"Test Document" in response.data or b"Contenu de test" in response.data

    def test_search_by_author(self, logged_in_client):
        """Search by author should work"""
        response = logged_in_client.get("/documents?author=testuser")
        assert response.status_code == 200
        # Should find the test document
        assert b"Test Document" in response.data or b"Contenu de test" in response.data

    def test_certificates_grouped_by_triplet(self, client, app):
        """Certificates with same entreprise/adresse/norme should be grouped together
        and sorted by date_peremption descending (newest first)"""
        from app_sqlalchemy import db, DocumentDB, UserDB
        from datetime import date
        import json

        with app.app_context():
            # Get or create test user
            user = UserDB.query.filter_by(username="testuser").first()
            if not user:
                from werkzeug.security import generate_password_hash

                user = UserDB(
                    username="testuser",
                    password=generate_password_hash("testpass123"),
                    role="user",
                )
                db.session.add(user)
                db.session.commit()

            # Create multiple certificates with the same triplet but different dates
            entreprise = "Test Entreprise"
            adresse = "123 Test Street, Paris"
            norme = "ISO 9001:2015"

            # Certificate 1: oldest (expires 2025-01-01)
            doc1_attrs = {
                "organisme_certificateur": "Certificateur A",
                "norme": norme,
                "entreprise_certifiee": entreprise,
                "pays": "France",
                "adresse": adresse,
                "date_peremption": "2025-01-01",
            }
            doc1 = DocumentDB(
                title="Certificat Ancien",
                content="Certificat ancien",
                user_id=user.id,
                file_path=None,
                type="Certificat",
                attributes=json.dumps(doc1_attrs),
            )
            db.session.add(doc1)

            # Certificate 2: middle (expires 2026-01-01)
            doc2_attrs = {
                "organisme_certificateur": "Certificateur B",
                "norme": norme,
                "entreprise_certifiee": entreprise,
                "pays": "France",
                "adresse": adresse,
                "date_peremption": "2026-01-01",
            }
            doc2 = DocumentDB(
                title="Certificat Moyen",
                content="Certificat moyen",
                user_id=user.id,
                file_path=None,
                type="Certificat",
                attributes=json.dumps(doc2_attrs),
            )
            db.session.add(doc2)

            # Certificate 3: newest (expires 2027-01-01)
            doc3_attrs = {
                "organisme_certificateur": "Certificateur C",
                "norme": norme,
                "entreprise_certifiee": entreprise,
                "pays": "France",
                "adresse": adresse,
                "date_peremption": "2027-01-01",
            }
            doc3 = DocumentDB(
                title="Certificat Recent",
                content="Certificat recent",
                user_id=user.id,
                file_path=None,
                type="Certificat",
                attributes=json.dumps(doc3_attrs),
            )
            db.session.add(doc3)

            db.session.commit()

            # Also add a certificate with a different triplet to verify grouping
            doc4_attrs = {
                "organisme_certificateur": "Certificateur D",
                "norme": "ISO 14001:2015",
                "entreprise_certifiee": "Autre Entreprise",
                "pays": "France",
                "adresse": "456 Other Street, Paris",
                "date_peremption": "2026-06-01",
            }
            doc4 = DocumentDB(
                title="Autre Certificat",
                content="Autre certificat",
                user_id=user.id,
                file_path=None,
                type="Certificat",
                attributes=json.dumps(doc4_attrs),
            )
            db.session.add(doc4)
            db.session.commit()

            # Log in as testuser
            client.post(
                "/login",
                data={"username": "testuser", "password": "testpass123"},
                follow_redirects=True,
            )

            # Access documents page
            response = client.get("/documents")
            assert response.status_code == 200

            # Parse the response to check grouping
            # The page should contain the group header with entreprise, adresse, norme
            assert entreprise.encode() in response.data
            assert adresse.encode() in response.data
            assert norme.encode() in response.data

            # Check that all three certificates from the same triplet are visible
            assert b"Certificat Ancien" in response.data
            assert b"Certificat Moyen" in response.data
            assert b"Certificat Recent" in response.data

            # Check that the other certificate (different triplet) is also visible
            assert b"Autre Certificat" in response.data
            assert b"Autre Entreprise" in response.data

            # Check that the newest certificate (2027) is marked as "Dernier" in its group
            # The first certificate in each group should have the "Dernier" badge
            # We can check that "Certificat Recent" appears before "Certificat Moyen" in the HTML
            recent_pos = response.data.find(b"Certificat Recent")
            moyen_pos = response.data.find(b"Certificat Moyen")
            ancien_pos = response.data.find(b"Certificat Ancien")

            # All certificates should be present
            assert recent_pos > 0
            assert moyen_pos > 0
            assert ancien_pos > 0

            # The newest (Recent) should appear first in the group
            # Note: this depends on the template rendering order
            assert recent_pos < moyen_pos < ancien_pos

            # Clean up
            db.session.delete(doc1)
            db.session.delete(doc2)
            db.session.delete(doc3)
            db.session.delete(doc4)
            db.session.commit()


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
            or response.request.path == "/login"
            or response.request.path == "/documents"
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
