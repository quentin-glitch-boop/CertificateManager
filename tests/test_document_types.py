"""Tests for document types functionality"""
import pytest
import json


class TestDocumentTypes:
    """Tests for the document types system"""
    
    def test_document_types_are_registered(self):
        """Test that document types are properly registered"""
        from app import DOCUMENT_TYPES, get_document_types, get_document_type
        
        doc_types = get_document_types()
        
        # Should have at least the certificat type
        assert 'certificat' in doc_types
        assert 'certificat' in DOCUMENT_TYPES
        
        # Check certificat structure
        certificat = get_document_type('certificat')
        assert certificat is not None
        assert 'name' in certificat
        assert 'description' in certificat
        assert 'attributes' in certificat
        
    def test_certificat_attributes_structure(self):
        """Test that certificat has the expected attributes"""
        from app import get_document_type
        
        certificat = get_document_type('certificat')
        attrs = certificat['attributes']
        
        # Check all expected attributes exist
        expected_attrs = ['nom_societe_certifiee', 'societe_certificatrice', 'adresse', 'date_peremption', 'url_telechargement']
        for attr in expected_attrs:
            assert attr in attrs, f"Attribute {attr} not found in certificat"
        
        # Check url_telechargement is optional
        assert attrs['url_telechargement']['required'] == False
        assert attrs['url_telechargement']['type'] == 'string'
        
        # Check attribute properties
        assert attrs['nom_societe_certifiee']['type'] == 'string'
        assert attrs['nom_societe_certifiee']['required'] == True
        assert attrs['nom_societe_certifiee']['form_type'] == 'text'
        
        assert attrs['date_peremption']['type'] == 'date'
        assert attrs['date_peremption']['required'] == True
        assert attrs['date_peremption']['form_type'] == 'date'
        
    def test_validate_document_attributes_valid(self):
        """Test validation with valid attributes"""
        from app import validate_document_attributes
        
        attributes = {
            'nom_societe_certifiee': 'Societe A',
            'societe_certificatrice': 'Certificateur B',
            'adresse': '123 Rue Test',
            'date_peremption': '2026-12-31'
        }
        
        is_valid, errors = validate_document_attributes('certificat', attributes)
        assert is_valid == True
        assert errors == []
        
    def test_validate_document_attributes_missing_required(self):
        """Test validation with missing required attributes"""
        from app import validate_document_attributes
        
        # Missing nom_societe_certifiee
        attributes = {
            'societe_certificatrice': 'Certificateur B',
            'date_peremption': '2026-12-31'
        }
        
        is_valid, errors = validate_document_attributes('certificat', attributes)
        assert is_valid == False
        assert len(errors) > 0
        assert any('obligatoire' in error for error in errors)
        
    def test_validate_document_attributes_invalid_date(self):
        """Test validation with invalid date format"""
        from app import validate_document_attributes
        
        attributes = {
            'nom_societe_certifiee': 'Societe A',
            'societe_certificatrice': 'Certificateur B',
            'date_peremption': 'invalid-date'
        }
        
        is_valid, errors = validate_document_attributes('certificat', attributes)
        assert is_valid == False
        assert any('date valide' in error for error in errors)
        
    def test_validate_unknown_document_type(self):
        """Test validation with unknown document type"""
        from app import validate_document_attributes
        
        is_valid, errors = validate_document_attributes('unknown_type', {})
        assert is_valid == False
        assert any('inconnu' in error for error in errors)
    
    def test_register_new_document_type(self):
        """Test registering a new document type"""
        from app import register_document_type, get_document_type
        
        new_type = {
            'name': 'Contrat',
            'description': 'Contrat commercial',
            'attributes': {
                'partie_a': {
                    'type': 'string',
                    'label': 'Partie A',
                    'required': True,
                    'form_type': 'text'
                },
                'montant': {
                    'type': 'number',
                    'label': 'Montant',
                    'required': False,
                    'form_type': 'number'
                }
            }
        }
        
        register_document_type('contrat', new_type)
        
        # Verify it was registered
        contrat = get_document_type('contrat')
        assert contrat is not None
        assert contrat['name'] == 'Contrat'
        assert 'partie_a' in contrat['attributes']
        
    def test_add_document_with_type_and_attributes(self, logged_in_client):
        """Test adding a document with type and attributes via web interface"""
        # Test adding a certificat document (without file for now, just testing type/attributes)
        response = logged_in_client.post('/add', data={
            'title': 'Certificat Test',
            'content': 'Test certificat',
            'doc_type': 'certificat',
            'doc_attr_nom_societe_certifiee': 'Societe Test',
            'doc_attr_societe_certificatrice': 'Certificateur Test',
            'doc_attr_adresse': '123 Rue Test',
            'doc_attr_date_peremption': '2026-12-31'
        }, content_type='multipart/form-data', follow_redirects=True)
        
        # Should have error about missing PDF
        assert response.status_code == 200
        assert b'PDF est obligatoire' in response.data or b'PDF' in response.data
        
    def test_add_document_missing_required_attribute(self, logged_in_client):
        """Test that adding a document with missing required attribute fails"""
        response = logged_in_client.post('/add', data={
            'title': 'Certificat Incomplet',
            'doc_type': 'certificat',
            'doc_attr_societe_certificatrice': 'Certificateur Test',
        }, content_type='multipart/form-data', follow_redirects=True)
        
        # Should stay on page with error message
        assert response.status_code == 200
        assert b'est obligatoire' in response.data
        
    def test_document_type_filter(self, logged_in_client):
        """Test filtering documents by type"""
        # Access index with type filter
        response = logged_in_client.get('/?doc_type=certificat')
        assert response.status_code == 200
