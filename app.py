from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, abort, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta, timezone
import sqlite3
import os
import jwt
import base64

# Initialisation Flask
app = Flask(__name__)
app.secret_key = 'ta_cle_secrete_ic123456_changez_la_en_production'

# Configuration
DATABASE = os.path.join(os.path.dirname(__file__), 'documents.db')
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'pdf'}

# Assurer que le dossier d'upload existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limite à 16 Mo

# Initialisation Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message_category = 'danger'
login_manager.init_app(app)

# Modèle User pour Flask-Login
class User(UserMixin):
    def __init__(self, id, username, password_hash, role):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    """Charge un utilisateur depuis la base de données"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, password, role FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        return User(id=user_data[0], username=user_data[1], 
                   password_hash=user_data[2], role=user_data[3])
    return None

def get_db():
    """Crée une connexion à la base de données SQLite"""
    from flask import current_app
    db_path = current_app.config.get('DATABASE', DATABASE)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def allowed_file(filename):
    """Vérifie si le fichier a une extension autorisée (PDF uniquement)"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def admin_required(f):
    """Décorateur pour vérifier que l'utilisateur est admin"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if current_user.role != 'admin':
            flash('Accès refusé. Réservé aux administrateurs.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function



# ============================================================================
# Systeme de types de documents extensible
# ============================================================================
import json

# Registre des types de documents avec leurs schemas de validation
DOCUMENT_TYPES = {
    'certificat': {
        'name': 'Certificat',
        'description': 'Certificat avec société certifiée et certificatrice',
        'attributes': {
            'nom_societe_certifiee': {
                'type': 'string',
                'label': 'Nom de la société certifiée',
                'required': True,
                'form_type': 'text'
            },
            'societe_certificatrice': {
                'type': 'string',
                'label': 'Société certificatrice',
                'required': True,
                'form_type': 'text'
            },
            'adresse': {
                'type': 'string',
                'label': 'Adresse de la société',
                'required': False,
                'form_type': 'textarea'
            },
            'date_peremption': {
                'type': 'date',
                'label': 'Date de péremption du certificat',
                'required': True,
                'form_type': 'date'
            },
            'url_telechargement': {
                'type': 'string',
                'label': 'URL de téléchargement',
                'required': False,
                'form_type': 'text'
            }
        }
    }
}


def register_document_type(type_name, config):
    DOCUMENT_TYPES[type_name] = config


def get_document_type(type_name):
    return DOCUMENT_TYPES.get(type_name)


def get_document_types():
    return DOCUMENT_TYPES


def validate_document_attributes(type_name, attributes):
    doc_type = get_document_type(type_name)
    if not doc_type:
        return False, [f"Type de document inconnu: {type_name}"]
    
    errors = []
    attr_schema = doc_type.get('attributes', {})
    
    for attr_name, schema in attr_schema.items():
        if schema.get('required', False):
            if attr_name not in attributes or not attributes[attr_name]:
                errors.append(f"{schema['label']} est obligatoire")
    
    for attr_name, value in attributes.items():
        if attr_name in attr_schema:
            expected_type = attr_schema[attr_name]['type']
            if expected_type == 'date' and value:
                try:
                    datetime.strptime(value, '%Y-%m-%d')
                except ValueError:
                    errors.append(f"{attr_schema[attr_name]['label']} doit etre une date valide (YYYY-MM-DD)")
            elif expected_type == 'number' and value:
                try:
                    float(value)
                except ValueError:
                    errors.append(f"{attr_schema[attr_name]['label']} doit etre un nombre")
    
    return len(errors) == 0, errors

def init_db():
    """Initialise la base de données avec les tables nécessaires"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Crée la table users avec mot de passe et rôle
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Crée la table documents
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
    
    # Migration : ajouter les colonnes manquantes
    cursor.execute("PRAGMA table_info(users)")
    user_columns = [column[1] for column in cursor.fetchall()]
    
    if 'password' not in user_columns:
        cursor.execute('ALTER TABLE users ADD COLUMN password TEXT NOT NULL DEFAULT ""')
    if 'role' not in user_columns:
        cursor.execute('ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT "user"')
    if 'created_at' not in user_columns:
        cursor.execute('ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
    
    cursor.execute("PRAGMA table_info(documents)")
    doc_columns = [column[1] for column in cursor.fetchall()]
    
    if 'file_path' not in doc_columns:
        cursor.execute('ALTER TABLE documents ADD COLUMN file_path TEXT')
    
    if 'type' not in doc_columns:
        cursor.execute('ALTER TABLE documents ADD COLUMN type TEXT')
    
    if 'attributes' not in doc_columns:
        cursor.execute('ALTER TABLE documents ADD COLUMN attributes TEXT')
    
    # Crée un utilisateur admin par défaut si la table est vide
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        # Mot de passe par défaut pour admin : "admin123"
        admin_password = generate_password_hash('admin123')
        cursor.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', 
                      ('admin', admin_password, 'admin'))
        
        # Ajouter quelques utilisateurs tests
        user_password = generate_password_hash('password')
        cursor.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', 
                      ('user1', user_password, 'user'))
        cursor.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', 
                      ('user2', user_password, 'user'))
    
    # Mettre à jour les utilisateurs existants sans password
    cursor.execute('SELECT id, username FROM users WHERE password IS NULL OR password = ""')
    users_to_update = cursor.fetchall()
    for user in users_to_update:
        # Générer un mot de passe par défaut (username + '123')
        default_password = generate_password_hash(user['username'] + '123')
        cursor.execute('UPDATE users SET password = ? WHERE id = ?', 
                      (default_password, user['id']))
    
    conn.commit()
    conn.close()

# Routes principales
@app.route('/')
@login_required
def index():
    """Page principale avec la liste des documents et la recherche"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Récupérer les critères de recherche
    search_author = request.args.get('author', '')
    search_upload_from = request.args.get('upload_from', '')
    search_upload_to = request.args.get('upload_to', '')
    search_validity_from = request.args.get('validity_from', '')
    search_validity_to = request.args.get('validity_to', '')
    search_type = request.args.get('doc_type', '')
    
    # Construire la requête SQL dynamique
    # Si l'utilisateur est admin, il voit tous les documents
    # Sinon, il ne voit que ses propres documents
    params = []
    if current_user.role == 'admin':
        query = 'SELECT d.id, d.title, d.content, d.upload_date, d.validity_date, d.file_path, d.type, d.attributes, u.username FROM documents d JOIN users u ON d.user_id = u.id WHERE 1=1'
    else:
        query = 'SELECT d.id, d.title, d.content, d.upload_date, d.validity_date, d.file_path, d.type, d.attributes, u.username FROM documents d JOIN users u ON d.user_id = u.id WHERE d.user_id = ?'
        params = [current_user.id]
    
    # Ajouter les filtres de recherche
    if search_author:
        query += ' AND u.username LIKE ?'
        params.append(f'%{search_author}%')
    
    if search_upload_from:
        query += ' AND date(d.upload_date) >= ?'
        params.append(search_upload_from)
    
    if search_upload_to:
        query += ' AND date(d.upload_date) <= ?'
        params.append(search_upload_to)
    
    if search_validity_from:
        query += ' AND d.validity_date >= ?'
        params.append(search_validity_from)
    
    if search_validity_to:
        query += ' AND d.validity_date <= ?'
        params.append(search_validity_to)
    
    if search_type:
        query += ' AND d.type = ?'
        params.append(search_type)
    
    # Tri
    query += ' ORDER BY d.upload_date DESC'
    
    # Exécuter la requête
    cursor.execute(query, params)
    documents = cursor.fetchall()
    
    # Parser les attributs JSON
    docs_with_attrs = []
    for doc in documents:
        attrs = {}
        if doc['attributes']:
            try:
                attrs = json.loads(doc['attributes'])
            except:
                attrs = {}
        docs_with_attrs.append({
            'id': doc['id'],
            'title': doc['title'],
            'content': doc['content'],
            'upload_date': doc['upload_date'],
            'validity_date': doc['validity_date'],
            'file_path': doc['file_path'],
            'type': doc['type'],
            'attributes': attrs,
            'username': doc['username']
        })
    
    conn.close()
    
    return render_template('index.html', 
                         documents=docs_with_attrs, 
                         document_types=get_document_types(),
                         current_date=str(date.today()),
                         search_author=search_author,
                         search_upload_from=search_upload_from,
                         search_upload_to=search_upload_to,
                         search_validity_from=search_validity_from,
                         search_validity_to=search_validity_to,
                         search_type=search_type)

# Routes de login
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Page de connexion"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, password, role FROM users WHERE username = ?', (username,))
        user_data = cursor.fetchone()
        conn.close()
        
        if user_data and check_password_hash(user_data[2], password):
            user = User(id=user_data[0], username=user_data[1], 
                       password_hash=user_data[2], role=user_data[3])
            login_user(user, remember=remember)
            flash('Connexion réussie !', 'success')
            return redirect(url_for('index'))
        else:
            flash('Nom d\'utilisateur ou mot de passe incorrect', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Déconnexion"""
    logout_user()
    flash('Déconnexion réussie', 'success')
    return redirect(url_for('login'))

# Routes documents
@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_document():
    """Ajouter un nouveau document"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        validity_date = request.form.get('validity_date')
        doc_type = request.form.get('doc_type', '')
        
        # L'auteur est automatiquement l'utilisateur connecté
        user_id = current_user.id
        
        # Gestion de l'upload du fichier PDF
        file_path = None
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename != '':
                # Vérifier que le fichier a une extension PDF
                if not allowed_file(file.filename):
                    flash('Seuls les fichiers PDF sont autorisés', 'error')
                    return redirect(url_for('index'))
                
                # Sécuriser le nom du fichier
                filename = secure_filename(file.filename)
                
                # Vérifier le MIME type (pour éviter les fichiers renommés)
                if file.content_type != 'application/pdf':
                    flash('Le fichier doit être un PDF valide', 'error')
                    return redirect(url_for('index'))
                
                # Sauvegarder le fichier
                try:
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                except Exception as e:
                    flash(f'Erreur lors de l\'upload : {str(e)}', 'error')
                    return redirect(url_for('index'))
        
        # Récupérer les attributs spécifiques au type
        attributes = {}
        if doc_type:
            doc_type_config = get_document_type(doc_type)
            if doc_type_config:
                for attr_name, attr_config in doc_type_config.get('attributes', {}).items():
                    attr_value = request.form.get(f'doc_attr_{attr_name}', '').strip()
                    if attr_value:
                        attributes[attr_name] = attr_value
            
            # Valider les attributs
            is_valid, errors = validate_document_attributes(doc_type, attributes)
            if not is_valid:
                for error in errors:
                    flash(error, 'error')
                return redirect(url_for('index'))
        
        # Validation
        if not title:
            flash('Le titre est obligatoire', 'error')
        elif not file_path:
            flash('Le fichier PDF est obligatoire', 'error')
        else:
            try:
                # Stocker seulement le nom du fichier dans la base
                db_file_path = os.path.basename(file_path) if file_path else None
                
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO documents (title, content, user_id, validity_date, file_path, type, attributes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (title, content, user_id, validity_date, db_file_path, doc_type, json.dumps(attributes)))
                conn.commit()
                conn.close()
                flash('Document ajouté avec succès !', 'success')
                return redirect(url_for('index'))
            except Exception as e:
                flash(f'Erreur : {str(e)}', 'error')
    
    return redirect(url_for('index'))

@app.route('/delete/<int:doc_id>')
@login_required
def delete_document(doc_id):
    """Supprimer un document"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Vérifier que l'utilisateur peut supprimer ce document
    cursor.execute('SELECT user_id, file_path FROM documents WHERE id = ?', (doc_id,))
    doc = cursor.fetchone()
    
    if not doc:
        flash('Document non trouvé', 'error')
        conn.close()
        return redirect(url_for('index'))
    
    # Vérifier les permissions
    if current_user.id != doc['user_id'] and current_user.role != 'admin':
        flash('Vous ne pouvez pas supprimer ce document', 'danger')
        conn.close()
        return redirect(url_for('index'))
    
    try:
        # Supprimer le fichier physique si il existe
        if doc['file_path']:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], doc['file_path'])
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # Supprimer l'entrée de la base
        cursor.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
        conn.commit()
        flash('Document supprimé avec succès !', 'success')
    except Exception as e:
        flash(f'Erreur : {str(e)}', 'error')
    
    conn.close()
    return redirect(url_for('index'))

# Routes admin
@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    """Interface de gestion des utilisateurs"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, role, created_at FROM users ORDER BY created_at DESC')
    users = cursor.fetchall()
    conn.close()
    
    return render_template('admin/users.html', users=users)

@app.route('/admin/add_user', methods=['POST'])
@login_required
@admin_required
def admin_add_user():
    """Ajouter un nouvel utilisateur (admin seulement)"""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role', 'user')
    
    if not username:
        flash('Le nom d\'utilisateur est obligatoire', 'error')
        return redirect(url_for('admin_users'))
    
    if len(password) < 6:
        flash('Le mot de passe doit contenir au moins 6 caractères', 'error')
        return redirect(url_for('admin_users'))
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        password_hash = generate_password_hash(password)
        cursor.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', 
                      (username, password_hash, role))
        conn.commit()
        flash('Utilisateur ajouté avec succès !', 'success')
    except sqlite3.IntegrityError:
        flash('Ce nom d\'utilisateur existe déjà', 'error')
    except Exception as e:
        flash(f'Erreur : {str(e)}', 'error')
    
    conn.close()
    return redirect(url_for('admin_users'))

@app.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_user(user_id):
    """Modifier un utilisateur"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, username, role FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        flash('Utilisateur non trouvé', 'error')
        conn.close()
        return redirect(url_for('admin_users'))
    
    if request.method == 'POST':
        new_username = request.form.get('username', '').strip()
        new_password = request.form.get('password', '')
        new_role = request.form.get('role', 'user')
        
        if not new_username:
            flash('Le nom d\'utilisateur est obligatoire', 'error')
            conn.close()
            return redirect(url_for('admin_edit_user', user_id=user_id))
        
        try:
            # Mettre à jour l'utilisateur
            if new_password:
                if len(new_password) < 6:
                    flash('Le mot de passe doit contenir au moins 6 caractères', 'error')
                    conn.close()
                    return redirect(url_for('admin_edit_user', user_id=user_id))
                password_hash = generate_password_hash(new_password)
                cursor.execute('UPDATE users SET username = ?, password = ?, role = ? WHERE id = ?',
                              (new_username, password_hash, new_role, user_id))
            else:
                cursor.execute('UPDATE users SET username = ?, role = ? WHERE id = ?',
                              (new_username, new_role, user_id))
            conn.commit()
            flash('Utilisateur modifié avec succès !', 'success')
            conn.close()
            return redirect(url_for('admin_users'))
        except sqlite3.IntegrityError:
            flash('Ce nom d\'utilisateur existe déjà', 'error')
        except Exception as e:
            flash(f'Erreur : {str(e)}', 'error')
    
    conn.close()
    return render_template('admin/edit_user.html', user=user)

@app.route('/admin/delete_user/<int:user_id>')
@login_required
@admin_required
def admin_delete_user(user_id):
    """Supprimer un utilisateur"""
    if current_user.id == user_id:
        flash('Vous ne pouvez pas supprimer votre propre compte', 'danger')
        return redirect(url_for('admin_users'))
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Supprimer les documents de l'utilisateur (optionnel)
        # On pourrait aussi les conserver avec user_id = NULL
        # Ici on supprime tout
        cursor.execute('SELECT file_path FROM documents WHERE user_id = ?', (user_id,))
        docs = cursor.fetchall()
        
        for doc in docs:
            if doc['file_path']:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], doc['file_path'])
                if os.path.exists(file_path):
                    os.remove(file_path)
        
        cursor.execute('DELETE FROM documents WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        flash('Utilisateur et ses documents supprimés avec succès !', 'success')
    except Exception as e:
        flash(f'Erreur : {str(e)}', 'error')
    
    conn.close()
    return redirect(url_for('admin_users'))

@app.route('/admin/edit_user_page/<int:user_id>')
@login_required
@admin_required
def admin_edit_user_page(user_id):
    """Page de modification d'utilisateur"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, role FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        flash('Utilisateur non trouvé', 'error')
        return redirect(url_for('admin_users'))
    
    return render_template('admin/edit_user.html', user=user)

# Route pour servir les fichiers
@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    """Route pour servir les fichiers uploadés"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ============================================================================
# API REST avec authentification JWT
# ============================================================================

# Décorateur pour vérifier le token JWT
def jwt_required(f):
    """Décorateur pour vérifier que la requête a un token JWT valide"""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Vérifier le header Authorization
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'error': 'Token is missing!'}), 401
        
        try:
            # Décoder et vérifier le token
            data = jwt.decode(token, app.secret_key, algorithms=['HS256'])
            # Stocker les données utilisateur dans request pour les routes
            request.user_data = data
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token is invalid!'}), 401
        
        return f(*args, **kwargs)
    return decorated


def get_jwt_user():
    """Récupère les données de l'utilisateur depuis le token JWT"""
    if hasattr(request, 'user_data'):
        return request.user_data
    return None


def create_jwt_token(user):
    """Crée un token JWT pour un utilisateur"""
    token = jwt.encode({
        'user_id': user.id,
        'username': user.username,
        'role': user.role,
        'exp': datetime.now(timezone.utc) + timedelta(hours=24)  # Valide pour 24h
    }, app.secret_key, algorithm='HS256')
    return token


# ============================================================================
# Routes API REST
# ============================================================================

@app.route('/api/login', methods=['POST'])
def api_login():
    """Authentification via API - retourne un token JWT"""
    data = request.get_json()
    
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Username and password are required'}), 400
    
    username = data['username']
    password = data['password']
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, password, role FROM users WHERE username = ?', (username,))
    user_data = cursor.fetchone()
    conn.close()
    
    if not user_data or not check_password_hash(user_data[2], password):
        return jsonify({'error': 'Invalid username or password'}), 401
    
    # Créer l'objet User pour Flask-Login (optionnel, pour compatibilité)
    user_obj = User(id=user_data[0], username=user_data[1], 
                   password_hash=user_data[2], role=user_data[3])
    
    # Créer le token JWT
    token = create_jwt_token(user_obj)
    
    return jsonify({
        'token': token,
        'user': {
            'id': user_obj.id,
            'username': user_obj.username,
            'role': user_obj.role
        }
    })


@app.route('/api/logout', methods=['POST'])
@jwt_required
def api_logout():
    """Déconnexion via API (invalide le token côté client)"""
    # Avec JWT, la déconnexion est gérée côté client
    # On pourrait ajouter le token à une blacklist, mais ce n'est pas implémenté ici
    return jsonify({'message': 'Successfully logged out. Please clear your token client-side.'})


@app.route('/api/documents', methods=['GET'])
@jwt_required
def api_get_documents():
    """Récupère la liste des documents (API)"""
    user_data = get_jwt_user()
    user_id = user_data['user_id']
    user_role = user_data['role']
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Filtres depuis les query params
    author = request.args.get('author')
    upload_from = request.args.get('upload_from')
    upload_to = request.args.get('upload_to')
    validity_from = request.args.get('validity_from')
    validity_to = request.args.get('validity_to')
    
    # Construire la requête
    if user_role == 'admin':
        query = 'SELECT d.id, d.title, d.content, d.upload_date, d.validity_date, d.file_path, u.username FROM documents d JOIN users u ON d.user_id = u.id WHERE 1=1'
        params = []
    else:
        query = 'SELECT d.id, d.title, d.content, d.upload_date, d.validity_date, d.file_path, u.username FROM documents d JOIN users u ON d.user_id = u.id WHERE d.user_id = ?'
        params = [user_id]
    
    if author:
        query += ' AND u.username LIKE ?'
        params.append(f'%{author}%')
    
    if upload_from:
        query += ' AND date(d.upload_date) >= ?'
        params.append(upload_from)
    
    if upload_to:
        query += ' AND date(d.upload_date) <= ?'
        params.append(upload_to)
    
    if validity_from:
        query += ' AND d.validity_date >= ?'
        params.append(validity_from)
    
    if validity_to:
        query += ' AND d.validity_date <= ?'
        params.append(validity_to)
    
    query += ' ORDER BY d.upload_date DESC'
    
    cursor.execute(query, params)
    documents = cursor.fetchall()
    conn.close()
    
    # Convertir en JSON
    docs_list = []
    for doc in documents:
        docs_list.append({
            'id': doc['id'],
            'title': doc['title'],
            'content': doc['content'],
            'upload_date': doc['upload_date'],
            'validity_date': doc['validity_date'],
            'file_path': doc['file_path'],
            'file_url': url_for('uploaded_file', filename=doc['file_path'], _external=True) if doc['file_path'] else None,
            'author': doc['username']
        })
    
    return jsonify({'documents': docs_list, 'count': len(docs_list)})


@app.route('/api/documents', methods=['POST'])
@jwt_required
def api_create_document():
    """Crée un nouveau document via API"""
    user_data = get_jwt_user()
    user_id = user_data['user_id']
    
    data = request.get_json()
    
    if not data or 'title' not in data:
        return jsonify({'error': 'Title is required'}), 400
    
    title = data.get('title', '').strip()
    content = data.get('content', '')
    validity_date = data.get('validity_date')
    file_base64 = data.get('file')
    
    # Gestion du fichier PDF (base64)
    file_path = None
    if file_base64:
        try:
            # Décoder le base64
            file_data = base64.b64decode(file_base64)
            
            # Vérifier que c'est un PDF (magic number)
            if not file_data.startswith(b'%PDF'):
                return jsonify({'error': 'File must be a valid PDF'}), 400
            
            # Générer un nom de fichier
            filename = f"doc_{datetime.now().strftime('%Y%m%d%H%M%S')}_{user_id}.pdf"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Sauvegarder le fichier
            with open(file_path, 'wb') as f:
                f.write(file_data)
        except Exception as e:
            return jsonify({'error': f'Error saving file: {str(e)}'}), 500
    
    # Validation
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    
    try:
        db_file_path = os.path.basename(file_path) if file_path else None
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO documents (title, content, user_id, validity_date, file_path)
            VALUES (?, ?, ?, ?, ?)
        ''', (title, content, user_id, validity_date, db_file_path))
        conn.commit()
        doc_id = cursor.lastrowid
        conn.close()
        
        return jsonify({
            'message': 'Document created successfully',
            'document_id': doc_id,
            'file_path': db_file_path
        }), 201
    except Exception as e:
        # Nettoyer le fichier si la DB échoue
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({'error': str(e)}), 500


@app.route('/api/documents/<int:doc_id>', methods=['DELETE'])
@jwt_required
def api_delete_document(doc_id):
    """Supprime un document via API"""
    user_data = get_jwt_user()
    user_id = user_data['user_id']
    user_role = user_data['role']
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Récupérer le document
    cursor.execute('SELECT user_id, file_path FROM documents WHERE id = ?', (doc_id,))
    doc = cursor.fetchone()
    
    if not doc:
        conn.close()
        return jsonify({'error': 'Document not found'}), 404
    
    # Vérifier les permissions
    if doc['user_id'] != user_id and user_role != 'admin':
        conn.close()
        return jsonify({'error': 'You do not have permission to delete this document'}), 403
    
    try:
        # Supprimer le fichier physique
        if doc['file_path']:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], doc['file_path'])
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # Supprimer de la base
        cursor.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Document deleted successfully'})
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/users', methods=['GET'])
@jwt_required
def api_get_users():
    """Récupère la liste des utilisateurs (admin uniquement)"""
    user_data = get_jwt_user()
    
    # Seuls les admins peuvent accéder à cette route
    if user_data['role'] != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, role, created_at FROM users ORDER BY created_at DESC')
    users = cursor.fetchall()
    conn.close()
    
    users_list = []
    for user in users:
        users_list.append({
            'id': user['id'],
            'username': user['username'],
            'role': user['role'],
            'created_at': user['created_at']
        })
    
    return jsonify({'users': users_list, 'count': len(users_list)})


@app.route('/api/users', methods=['POST'])
@jwt_required
def api_create_user():
    """Crée un nouvel utilisateur via API (admin uniquement)"""
    user_data = get_jwt_user()
    
    # Seuls les admins peuvent créer des utilisateurs
    if user_data['role'] != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    
    data = request.get_json()
    
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Username and password are required'}), 400
    
    username = data['username'].strip()
    password = data['password']
    role = data.get('role', 'user')
    
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        password_hash = generate_password_hash(password)
        cursor.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                      (username, password_hash, role))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        
        return jsonify({
            'message': 'User created successfully',
            'user_id': user_id,
            'username': username,
            'role': role
        }), 201
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Username already exists'}), 400
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@jwt_required
def api_delete_user(user_id):
    """Supprime un utilisateur via API (admin uniquement)"""
    user_data = get_jwt_user()
    
    # Seuls les admins peuvent supprimer des utilisateurs
    if user_data['role'] != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    
    # On ne peut pas se supprimer soi-même
    if user_data['user_id'] == user_id:
        return jsonify({'error': 'Cannot delete your own account'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Supprimer les documents de l'utilisateur
        cursor.execute('SELECT file_path FROM documents WHERE user_id = ?', (user_id,))
        docs = cursor.fetchall()
        
        for doc in docs:
            if doc['file_path']:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], doc['file_path'])
                if os.path.exists(file_path):
                    os.remove(file_path)
        
        cursor.execute('DELETE FROM documents WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'User and their documents deleted successfully'})
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Routes pour servir les fichiers via API
# ============================================================================

@app.route('/api/uploads/<filename>')
@jwt_required
def api_uploaded_file(filename):
    """Route pour télécharger un fichier via API"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ============================================================================
# Initialisation
# ============================================================================
if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
