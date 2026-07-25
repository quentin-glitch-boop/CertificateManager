"""
REST API tests for DocManager application
"""

import pytest
import json
import base64


class TestAPILogin:
    """API login tests"""

    def test_api_login_success(self, client):
        """API login should return JWT token"""
        response = client.post(
            "/api/login",
            data=json.dumps({"username": "testuser", "password": "testpass123"}),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "token" in data
        assert "user" in data
        assert data["user"]["username"] == "testuser"

    def test_api_login_failure(self, client):
        """API login with wrong credentials should fail"""
        response = client.post(
            "/api/login",
            data=json.dumps({"username": "testuser", "password": "wrongpass"}),
            content_type="application/json",
        )

        assert response.status_code == 401
        data = json.loads(response.data)
        assert "error" in data

    def test_api_login_missing_data(self, client):
        """API login without data should fail"""
        response = client.post(
            "/api/login", data=json.dumps({}), content_type="application/json"
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data

    def test_api_login_admin(self, client):
        """API login as admin should return admin role"""
        response = client.post(
            "/api/login",
            data=json.dumps({"username": "testadmin", "password": "adminpass123"}),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["user"]["role"] == "admin"


class TestAPILogout:
    """API logout tests"""

    def test_api_logout(self, client):
        """API logout should succeed"""
        # First, login
        login_response = client.post(
            "/api/login",
            data=json.dumps({"username": "testuser", "password": "testpass123"}),
            content_type="application/json",
        )

        token = json.loads(login_response.data)["token"]

        # Then, logout
        response = client.post(
            "/api/logout", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "message" in data


class TestAPIDocuments:
    """API documents tests"""

    def get_auth_header(self, client, username="testuser", password="testpass123"):
        """Get auth header with JWT token"""
        response = client.post(
            "/api/login",
            data=json.dumps({"username": username, "password": password}),
            content_type="application/json",
        )
        token = json.loads(response.data)["token"]
        return {"Authorization": f"Bearer {token}"}

    def test_api_get_documents(self, client):
        """Get documents via API"""
        headers = self.get_auth_header(client)
        response = client.get("/api/documents", headers=headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "documents" in data
        assert isinstance(data["documents"], list)

    def test_api_get_documents_unauthorized(self, client):
        """Get documents without token should fail"""
        response = client.get("/api/documents")
        assert response.status_code == 401

    def test_api_add_document(self, client):
        """Add document via API"""
        headers = self.get_auth_header(client)

        # Create PDF content in base64
        pdf_content = b"%PDF-1.4\nTest PDF content"
        pdf_base64 = base64.b64encode(pdf_content).decode("utf-8")

        response = client.post(
            "/api/documents",
            data=json.dumps(
                {
                    "title": "Document API",
                    "content": "Contenu via API",
                    "validity_date": "2026-12-31",
                    "file": pdf_base64,
                }
            ),
            headers=headers,
            content_type="application/json",
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert "message" in data

    def test_api_delete_nonexistent_document(self, client):
        """Delete non-existent document should fail"""
        headers = self.get_auth_header(client)
        response = client.delete("/api/documents/99999", headers=headers)
        assert response.status_code == 404


class TestAPIUsers:
    """API users management tests"""

    def get_token(self, client, username, password):
        """Get JWT token"""
        response = client.post(
            "/api/login",
            data=json.dumps({"username": username, "password": password}),
            content_type="application/json",
        )
        return json.loads(response.data)["token"]

    def test_api_get_users_as_admin(self, client):
        """Admin can get users list via API"""
        headers = {
            "Authorization": f'Bearer {self.get_token(client, "testadmin", "adminpass123")}'
        }
        response = client.get("/api/users", headers=headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "users" in data
        assert isinstance(data["users"], list)

    def test_api_get_users_unauthorized(self, client):
        """Non-admin cannot get users list"""
        headers = {
            "Authorization": f'Bearer {self.get_token(client, "testuser", "testpass123")}'
        }
        response = client.get("/api/users", headers=headers)

        assert response.status_code == 403


class TestAPITokenValidation:
    """JWT token validation tests"""

    def test_invalid_token(self, client):
        """Invalid token should be rejected"""
        response = client.get(
            "/api/documents", headers={"Authorization": "Bearer invalidtoken"}
        )
        assert response.status_code == 401

    def test_missing_token(self, client):
        """Missing token should be rejected"""
        response = client.get("/api/documents")
        assert response.status_code == 401
