import pytest
import sqlite3
import os
import sys
from datetime import datetime, timedelta

# Add parent directory to path to import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app as _app, init_db, get_db
from werkzeug.security import generate_password_hash


@pytest.fixture
def app(tmp_path):
    """Flask application in test mode"""
    import os
    
    # Create a temporary database file in pytest's tmp_path
    db_path = tmp_path / 'test_documents.db'
    
    _app.config['TESTING'] = True
    _app.config['DATABASE'] = str(db_path)
    _app.config['WTF_CSRF_ENABLED'] = False
    _app.config['SECRET_KEY'] = 'test_secret_key_for_testing_only'
    
    return _app


@pytest.fixture
def client(app):
    """Test client with application context"""
    with app.app_context():
        # Initialize database - this will create tables in the in-memory database
        conn = get_db()
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT,
                user_id INTEGER NOT NULL,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                validity_date DATE,
                file_path TEXT,
                type TEXT,
                attributes TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        conn.commit()
        
        # Clear existing data
        cursor.execute('DELETE FROM documents')
        cursor.execute('DELETE FROM users')
        
        # Add test users
        user_password = generate_password_hash('testpass123')
        cursor.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', 
                      ('testuser', user_password, 'user'))
        user1_id = cursor.lastrowid
        
        admin_password = generate_password_hash('adminpass123')
        cursor.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', 
                      ('testadmin', admin_password, 'admin'))
        user2_id = cursor.lastrowid
        
        cursor.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', 
                      ('user2', generate_password_hash('password123'), 'user'))
        
        # Add test document
        cursor.execute('''
            INSERT INTO documents (title, content, user_id, validity_date, file_path, type, attributes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('Test Document', 'Contenu de test', user1_id, '2026-12-31', None, 'certificat', None))
        
        conn.commit()
        conn.close()
    
    with app.test_client() as client:
        yield client
    # pytest's tmp_path fixture handles cleanup automatically


@pytest.fixture
def logged_in_client(client):
    """Client logged in as testuser via actual login"""
    # Perform actual login
    client.post('/login', data={
        'username': 'testuser',
        'password': 'testpass123'
    }, follow_redirects=True)
    
    yield client
    
    # Logout
    client.get('/logout', follow_redirects=True)


@pytest.fixture
def admin_client(client):
    """Client logged in as admin via actual login"""
    # Perform actual login as admin
    client.post('/login', data={
        'username': 'testadmin',
        'password': 'adminpass123'
    }, follow_redirects=True)
    
    yield client
    
    # Logout
    client.get('/logout', follow_redirects=True)


@pytest.fixture
def test_db():
    """Temporary database for unit tests"""
    import tempfile
    db_fd, db_path = tempfile.mkstemp()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            user_id INTEGER NOT NULL,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            validity_date DATE,
            file_path TEXT,
            type TEXT,
            attributes TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    
    yield conn
    
    conn.close()
    os.unlink(db_path)
