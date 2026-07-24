"""
Authentication tests for DocManager application
"""
import pytest


class TestLogin:
    """Login page tests"""
    
    def test_login_page_loads(self, client):
        """Login page should load"""
        response = client.get('/login')
        assert response.status_code == 200
        assert b'Nom d' in response.data
        assert b'Mot de passe' in response.data
    
    def test_login_success(self, client):
        """Successful login should redirect to index"""
        response = client.post('/login', data={
            'username': 'testuser',
            'password': 'testpass123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert response.request.path == '/'
        assert b'Connexion' in response.data
    
    def test_login_wrong_password(self, client):
        """Wrong password should show error"""
        response = client.post('/login', data={
            'username': 'testuser',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        
        assert b'mot de passe incorrect' in response.data
    
    def test_login_wrong_username(self, client):
        """Wrong username should show error"""
        response = client.post('/login', data={
            'username': 'nonexistent',
            'password': 'testpass123'
        }, follow_redirects=True)
        
        assert b'mot de passe incorrect' in response.data
    
    def test_logout(self, logged_in_client):
        """Logout should redirect to login"""
        response = logged_in_client.get('/logout', follow_redirects=True)
        
        assert response.status_code == 200
        assert response.request.path == '/login'
        assert b'Deconnexion reussie' in response.data or b'Se connecter' in response.data or b'connexion' in response.data.lower()


class TestProtectedRoutes:
    """Protected routes tests"""
    
    def test_index_requires_login(self, client):
        """Index page requires login"""
        response = client.get('/', follow_redirects=True)
        assert response.request.path == '/login'
    
    def test_admin_route_requires_admin(self, client):
        """Admin route requires admin role"""
        response = client.get('/admin/users', follow_redirects=True)
        # Should redirect to login or show access denied
        assert b'Acces refuse' in response.data or response.request.path == '/login' or response.status_code == 403


class TestPasswordHashing:
    """Password hashing tests"""
    
    def test_password_hashing(self):
        """Password hashing should work"""
        from werkzeug.security import generate_password_hash, check_password_hash
        
        password = 'test123'
        hashed = generate_password_hash(password)
        
        assert check_password_hash(hashed, password)
        assert not check_password_hash(hashed, 'wrongpass')
