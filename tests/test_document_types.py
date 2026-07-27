"""Tests for document types functionality"""

import pytest
import json
import io


class TestDocumentTypes:
    """Tests for the document types system"""

    def test_document_types_are_registered(self):
        """Test that document types are properly registered"""
        from app_sqlalchemy import DOCUMENT_TYPES, get_document_types, get_document_type

        doc_types = get_document_types()

        # Should have at least the certificat type
        assert "certificat" in doc_types
        assert "certificat" in DOCUMENT_TYPES

        # Check certificat structure
        certificat = get_document_type("certificat")
        assert certificat is not None
        assert "name" in certificat
        assert "description" in certificat
        assert "attributes" in certificat

    def test_certificat_attributes_structure(self):
        """Test that certificat has the expected attributes"""
        from app_sqlalchemy import get_document_type

        certificat = get_document_type("certificat")
        attrs = certificat["attributes"]

        # Check all expected attributes exist
        expected_attrs = [
            "nom_societe_certifiee",
            "societe_certificatrice",
            "adresse",
            "date_peremption",
            "url_telechargement",
        ]
        for attr in expected_attrs:
            assert attr in attrs, f"Attribute {attr} not found in certificat"

        # Check attribute properties
        assert attrs["nom_societe_certifiee"]["type"] == "string"
        assert attrs["nom_societe_certifiee"]["required"] == True
        assert attrs["nom_societe_certifiee"]["form_type"] == "text"

        assert attrs["date_peremption"]["type"] == "date"
        assert attrs["date_peremption"]["required"] == True
        assert attrs["date_peremption"]["form_type"] == "date"

        # Check url_telechargement is optional
        assert attrs["url_telechargement"]["required"] == False
        assert attrs["url_telechargement"]["type"] == "string"

    def test_validate_document_attributes_valid(self):
        """Test validation with valid attributes"""
        from app_sqlalchemy import validate_document_attributes

        attributes = {
            "nom_societe_certifiee": "Societe A",
            "societe_certificatrice": "Certificateur B",
            "adresse": "123 Rue Test",
            "date_peremption": "2026-12-31",
        }

        is_valid, errors = validate_document_attributes("certificat", attributes)
        assert is_valid == True
        assert errors == []

    def test_add_document_with_type_and_pdf(self, logged_in_client):
        """Test complete document submission with type, attributes, and PDF file"""
        # Create a valid minimal PDF
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF"

        data = {
            "title": "Test Certificate Full",
            "content": "Test content",
            "doc_type": "certificat",
            "doc_attr_nom_societe_certifiee": "Test Company",
            "doc_attr_societe_certificatrice": "Test Certifier",
            "doc_attr_adresse": "123 Test Street",
            "doc_attr_date_peremption": "2026-12-31",
            "doc_attr_url_telechargement": "https://example.com/cert.pdf",
            "file": (io.BytesIO(pdf_content), "test_cert.pdf"),
        }

        response = logged_in_client.post("/add", data=data, content_type="multipart/form-data", follow_redirects=True)

        assert response.status_code == 200
        assert b"Document" in response.data and b"succ" in response.data.lower()

        # Verify in database using SQLAlchemy
        from app_sqlalchemy import db, DocumentDB
        from flask import current_app

        with current_app.app_context():
            doc = DocumentDB.query.filter_by(title="Test Certificate Full").first()

            assert doc is not None
            assert doc.type == "certificat"
            attrs = json.loads(doc.attributes) if doc.attributes else {}
            assert attrs.get("nom_societe_certifiee") == "Test Company"
            assert attrs.get("url_telechargement") == "https://example.com/cert.pdf"
