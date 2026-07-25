from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, abort, jsonify, session, make_response
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

# Assurer que le dossier d'upload existe (lazy creation to avoid issues on read-only filesystems)
def ensure_upload_folder():
    """Crée le dossier d'upload s'il n'existe pas"""
    try:
        # Créer le répertoire parent (static/) s'il n'existe pas
        static_dir = os.path.dirname(UPLOAD_FOLDER)
        os.makedirs(static_dir, exist_ok=True)
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    except Exception:
        pass  # Ignorer les erreurs sur les systèmes de fichiers en lecture seule

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limite à 16 Mo

# Contexte global pour les templates
@app.context_processor
def inject_global_vars():
    """Injecte des variables globales dans tous les templates"""
    try:
        from translations import get_current_language, TRANSLATIONS, AVAILABLE_LANGUAGES, get_translation
        lang = get_current_language()
        return {
            'current_lang': lang,
            'available_languages': AVAILABLE_LANGUAGES,
            't': lambda key: get_translation(key, lang)
        }
    except ImportError:
        # translations module not available (e.g., during testing)
        return {
            'current_lang': 'fr',
            'available_languages': {'fr': 'Français', 'en': 'English'},
            't': lambda key: key
        }

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
    
    # Crée la table user_dashboard_config pour les configurations de dashboard
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_dashboard_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            config_name TEXT NOT NULL DEFAULT 'default',
            layout TEXT,
            widgets TEXT,
            is_default BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, config_name)
        )
    ''')
    
    # Crée la table de cache pour les coordonnées géographiques
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS geocode_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            address TEXT NOT NULL UNIQUE,
            latitude REAL,
            longitude REAL,
            accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Index pour les recherches fréquentes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_geocode_address ON geocode_cache(address)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_dashboard_user ON user_dashboard_config(user_id)')
    
    conn.commit()
    conn.close()


# ============================================================================
# Système de Dashboard Configurable
# ============================================================================

# Coordonnées géographiques par défaut pour les villes et sociétés connues
DEFAULT_COORDINATES = {
    # Villes françaises
    'besancon': (47.2380, 6.0241),
    'besançon': (47.2380, 6.0241),
    'paris': (48.8566, 2.3522),
    'lyon': (45.7640, 4.8357),
    'colmar': (48.0782, 7.3575),
    'avon': (48.4089, 2.7442),
    'molsheim': (48.5156, 7.4989),
    'illkirch': (48.5389, 7.6706),
    'strasbourg': (48.5734, 7.7521),
    'bornem': (51.1833, 4.2333),
    'vervier': (50.5939, 5.8842),
    'visp': (46.2922, 7.8858),
    
    # Pays
    'france': (46.2276, 2.2137),
    'suisse': (46.8182, 8.2275),
    'espagne': (40.4637, -3.7492),
    'belgique': (50.5039, 4.4699),
    'allemagne': (51.1657, 10.4515),
    'etats-unis': (37.0902, -95.7129),
    'usa': (37.0902, -95.7129),
    
    # Sociétés spécifiques
    'amcor': (47.2380, 6.0241),
    'ashland': (48.8566, 2.3522),
    'biomerieux': (45.7640, 4.8357),
    'corning': (48.4089, 2.7442),
    'lonza': (48.0782, 7.3575),
    'merck': (48.8566, 2.3522),
    'perlen': (47.0502, 8.3093),
    'thermofisher': (48.5734, 7.7521),
    'nalg': (48.5734, 7.7521),
    'nunc': (48.5734, 7.7521),
    'pamplona': (42.8125, -1.6458),
}


def geocode_address(address, use_cache=True):
    """
    Convertit une adresse en coordonnées géographiques (latitude, longitude)
    Utilise Nominatim (OpenStreetMap) ou le cache local.
    
    Args:
        address (str): Adresse à géocoder
        use_cache (bool): Utiliser le cache local
    
    Returns:
        tuple: (latitude, longitude) ou (None, None) si échoue
    """
    if not address:
        return None, None
    
    # Normaliser l'adresse (minuscules, sans accents)
    import unicodedata
    normalized_addr = unicodedata.normalize('NFKD', address.lower())
    normalized_addr = ''.join(c for c in normalized_addr if not unicodedata.combining(c))
    
    # Vérifier le cache d'abord
    if use_cache:
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT latitude, longitude FROM geocode_cache WHERE address = ?', 
                          (normalized_addr,))
            cached = cursor.fetchone()
            if cached:
                conn.close()
                return float(cached['latitude']), float(cached['longitude'])
            conn.close()
        except Exception:
            pass
    
    # Vérifier les coordonnées par défaut
    for key, coords in DEFAULT_COORDINATES.items():
        if key in normalized_addr:
            # Sauvegarder dans le cache
            if use_cache:
                _save_to_geocode_cache(normalized_addr, coords[0], coords[1])
            return coords
    
    # Essayer de trouver dans l'adresse des mots clés
    # Extraire les mots significatifs (sans articles, prépositions)
    words = normalized_addr.split()
    significant_words = [w for w in words if len(w) > 3 and w not in ['rue', 'de', 'la', 'le', 'les', 'du', 'des', 'au', 'en', 'a', 'd', 'l', 'an', 'and', 'the', 'of', 'at', 'in', 'for']]
    
    for word in significant_words:
        for key, coords in DEFAULT_COORDINATES.items():
            if word.startswith(key) or key.startswith(word):
                if use_cache:
                    _save_to_geocode_cache(normalized_addr, coords[0], coords[1])
                return coords
    
    # Essayer Nominatim (OpenStreetMap) seulement si requests est disponible
    try:
        import requests
        has_requests = True
    except ImportError:
        has_requests = False
    
    if has_requests:
        try:
            # URL de Nominatim avec délai pour éviter d'être bloqué
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': address,
                'format': 'json',
                'limit': 1,
                'email': 'contact@example.com'  # Recommandé par Nominatim
            }
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200 and response.json():
                result = response.json()[0]
                lat = float(result.get('lat'))
                lon = float(result.get('lon'))
                
                # Sauvegarder dans le cache
                if use_cache:
                    _save_to_geocode_cache(normalized_addr, lat, lon)
                
                return lat, lon
                
        except Exception as e:
            # Si le géocodage échoue, essayer avec les mots clés de l'adresse originale
            app.logger.warning(f"Géocodage échoué pour '{address}': {e}")
    
    # Retourner None si rien n'a fonctionné
    return None, None


def _save_to_geocode_cache(address, latitude, longitude):
    """Sauvegarde une entrée dans le cache de géocodage"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO geocode_cache (address, latitude, longitude)
            VALUES (?, ?, ?)
        ''', (address, latitude, longitude))
        conn.commit()
        conn.close()
    except Exception as e:
        app.logger.error(f"Erreur lors de la sauvegarde du cache de géocodage: {e}")


def get_all_documents_for_user(user_id=None, user_role=None):
    """
    Récupère tous les documents accessibles par un utilisateur.
    
    Args:
        user_id: ID de l'utilisateur (None si admin)
        user_role: Rôle de l'utilisateur
    
    Returns:
        Liste de dictionnaires avec les documents
    """
    conn = get_db()
    cursor = conn.cursor()
    
    if user_role == 'admin':
        cursor.execute('''
            SELECT d.id, d.title, d.content, d.upload_date, d.validity_date, 
                   d.file_path, d.type, d.attributes, u.username, u.id as user_id
            FROM documents d 
            JOIN users u ON d.user_id = u.id
            ORDER BY d.upload_date DESC
        ''')
    else:
        cursor.execute('''
            SELECT d.id, d.title, d.content, d.upload_date, d.validity_date, 
                   d.file_path, d.type, d.attributes, u.username, u.id as user_id
            FROM documents d 
            JOIN users u ON d.user_id = u.id
            WHERE d.user_id = ?
            ORDER BY d.upload_date DESC
        ''', (user_id,))
    
    documents = cursor.fetchall()
    conn.close()
    
    result = []
    for doc in documents:
        attrs = {}
        if doc['attributes']:
            try:
                attrs = json.loads(doc['attributes'])
            except:
                attrs = {}
        
        # Ajouter les coordonnées géographiques si adresse présente
        if 'adresse' in attrs and attrs['adresse']:
            lat, lon = geocode_address(attrs['adresse'])
            attrs['_latitude'] = lat
            attrs['_longitude'] = lon
        
        result.append({
            'id': doc['id'],
            'title': doc['title'],
            'content': doc['content'],
            'upload_date': doc['upload_date'],
            'validity_date': doc['validity_date'],
            'file_path': doc['file_path'],
            'type': doc['type'],
            'attributes': attrs,
            'username': doc['username'],
            'user_id': doc['user_id']
        })
    
    return result


# Widgets disponibles pour le dashboard
DASHBOARD_WIDGETS = {
    'timeline': {
        'id': 'timeline',
        'name': 'Timeline des péremptions',
        'name_en': 'Expiry Timeline',
        'description': 'Affiche les dates de péremption des certificats sur une timeline',
        'description_en': 'Display certificate expiry dates on a timeline',
        'icon': 'bi-calendar-range',
        'default_params': {
            'days_range': 60,  # Nombre de jours à afficher
            'show_expired': True,
            'show_valid': True
        },
        'default_size': {'w': 8, 'h': 4}
    },
    'map': {
        'id': 'map',
        'name': 'Carte des sites',
        'name_en': 'Sites Map',
        'description': 'Carte géographique des sites avec certificats (vert=valide, rouge=périmé)',
        'description_en': 'Geographic map of sites with certificates (green=valid, red=expired)',
        'icon': 'bi-geo-alt',
        'default_params': {
            'default_zoom': 6,
            'default_center': [47.0, 2.0],  # France par défaut
            'show_clusters': True
        },
        'default_size': {'w': 12, 'h': 6}
    },
    'stats': {
        'id': 'stats',
        'name': 'Statistiques',
        'name_en': 'Statistics',
        'description': 'Nombre de certificats valides, périmés et par type',
        'description_en': 'Number of valid, expired certificates and by type',
        'icon': 'bi-bar-chart',
        'default_params': {},
        'default_size': {'w': 6, 'h': 4}
    },
    'alerts': {
        'id': 'alerts',
        'name': 'Alertes de péremption',
        'name_en': 'Expiry Alerts',
        'description': 'Liste des certificats expirant bientôt',
        'description_en': 'List of certificates expiring soon',
        'icon': 'bi-bell',
        'default_params': {
            'days_threshold': 30,  # Avertir si péremption dans X jours
            'show_expired': True
        },
        'default_size': {'w': 6, 'h': 5}
    }
}


def get_default_dashboard_config():
    """Retourne la configuration par défaut du dashboard"""
    return {
        'layout': [
            {'widget_id': 'timeline', 'x': 0, 'y': 0, 'w': 8, 'h': 4},
            {'widget_id': 'map', 'x': 0, 'y': 4, 'w': 12, 'h': 6},
            {'widget_id': 'stats', 'x': 8, 'y': 0, 'w': 4, 'h': 4},
            {'widget_id': 'alerts', 'x': 8, 'y': 4, 'w': 4, 'h': 5}
        ],
        'widgets': {
            widget_id: {
                'enabled': True,
                'params': widget_info['default_params']
            }
            for widget_id, widget_info in DASHBOARD_WIDGETS.items()
        }
    }


def get_user_dashboard_config(user_id, config_name='default'):
    """
    Récupère la configuration du dashboard pour un utilisateur.
    Si elle n'existe pas, crée et retourne la configuration par défaut.
    """
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT layout, widgets FROM user_dashboard_config 
        WHERE user_id = ? AND config_name = ?
    ''', (user_id, config_name))
    
    result = cursor.fetchone()
    
    if result:
        config = {
            'layout': json.loads(result['layout']) if result['layout'] else [],
            'widgets': json.loads(result['widgets']) if result['widgets'] else {}
        }
    else:
        # Créer la configuration par défaut
        config = get_default_dashboard_config()
        
        cursor.execute('''
            INSERT INTO user_dashboard_config (user_id, config_name, layout, widgets, is_default)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            user_id,
            config_name,
            json.dumps(config['layout']),
            json.dumps(config['widgets']),
            True
        ))
        conn.commit()
    
    conn.close()
    return config


def save_user_dashboard_config(user_id, config_name, config):
    """Sauvegarde la configuration du dashboard pour un utilisateur"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Vérifier si la config existe déjà
    cursor.execute('''
        SELECT id FROM user_dashboard_config 
        WHERE user_id = ? AND config_name = ?
    ''', (user_id, config_name))
    
    exists = cursor.fetchone()
    
    if exists:
        cursor.execute('''
            UPDATE user_dashboard_config 
            SET layout = ?, widgets = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND config_name = ?
        ''', (
            json.dumps(config['layout']),
            json.dumps(config['widgets']),
            user_id,
            config_name
        ))
    else:
        cursor.execute('''
            INSERT INTO user_dashboard_config (user_id, config_name, layout, widgets, is_default)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            user_id,
            config_name,
            json.dumps(config['layout']),
            json.dumps(config['widgets']),
            True
        ))
    
    conn.commit()
    conn.close()
    return True


def delete_user_dashboard_config(user_id, config_name):
    """Supprime une configuration de dashboard"""
    if config_name == 'default':
        return False  # On ne peut pas supprimer la config par défaut
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        DELETE FROM user_dashboard_config 
        WHERE user_id = ? AND config_name = ?
    ''', (user_id, config_name))
    
    conn.commit()
    conn.close()
    return True


def get_user_dashboard_configs(user_id):
    """Récupère toutes les configurations de dashboard pour un utilisateur"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT config_name, is_default, updated_at 
        FROM user_dashboard_config 
        WHERE user_id = ?
        ORDER BY is_default DESC, updated_at DESC
    ''', (user_id,))
    
    configs = cursor.fetchall()
    conn.close()
    
    return [{'name': row['config_name'], 'is_default': bool(row['is_default']), 
             'updated_at': row['updated_at']} for row in configs]


def get_dashboard_widget_data(widget_id, user_id=None, user_role=None):
    """
    Récupère les données pour un widget spécifique.
    
    Args:
        widget_id: ID du widget
        user_id: ID de l'utilisateur
        user_role: Rôle de l'utilisateur
    
    Returns:
        Dictionnaire avec les données du widget
    """
    documents = get_all_documents_for_user(user_id, user_role)
    
    if widget_id == 'timeline':
        return _prepare_timeline_data(documents)
    elif widget_id == 'map':
        return _prepare_map_data(documents)
    elif widget_id == 'stats':
        return _prepare_stats_data(documents)
    elif widget_id == 'alerts':
        return _prepare_alerts_data(documents)
    else:
        return {'error': 'Widget inconnu'}


def _prepare_timeline_data(documents):
    """Prépare les données pour la timeline"""
    from collections import defaultdict
    
    # Regrouper par date
    timeline_data = defaultdict(list)
    
    for doc in documents:
        if doc['validity_date']:
            # Utiliser la date de validité
            date_key = doc['validity_date']
            timeline_data[date_key].append({
                'id': doc['id'],
                'title': doc['title'],
                'societe': doc['attributes'].get('nom_societe_certifiee', 'Inconnue'),
                'is_expired': doc['validity_date'] < str(date.today()),
                'validity_date': doc['validity_date']
            })
    
    return {
        'labels': sorted(timeline_data.keys()),
        'datasets': [
            {
                'label': 'Valides',
                'data': [{'date': k, 'count': len([d for d in v if not d['is_expired']])} 
                         for k, v in sorted(timeline_data.items())],
                'backgroundColor': '#10b981'
            },
            {
                'label': 'Périmés',
                'data': [{'date': k, 'count': len([d for d in v if d['is_expired']])} 
                         for k, v in sorted(timeline_data.items())],
                'backgroundColor': '#ef4444'
            }
        ],
        'documents_by_date': timeline_data
    }


def _prepare_map_data(documents):
    """Prépare les données pour la carte"""
    features = []
    
    for doc in documents:
        attrs = doc['attributes']
        
        if '_latitude' in attrs and '_longitude' in attrs:
            lat = attrs['_latitude']
            lon = attrs['_longitude']
            
            if lat is not None and lon is not None:
                is_expired = doc['validity_date'] and doc['validity_date'] < str(date.today())
                
                features.append({
                    'type': 'Feature',
                    'properties': {
                        'id': doc['id'],
                        'title': doc['title'],
                        'societe': attrs.get('nom_societe_certifiee', 'Inconnue'),
                        'adresse': attrs.get('adresse', ''),
                        'validity_date': doc['validity_date'] or '',
                        'is_expired': is_expired,
                        'certificatrice': attrs.get('societe_certificatrice', '')
                    },
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [lon, lat]  # Leaflet utilise [long, lat]
                    }
                })
    
    return {
        'type': 'FeatureCollection',
        'features': features
    }


def _prepare_stats_data(documents):
    """Prépare les données pour les statistiques"""
    from collections import Counter
    
    total = len(documents)
    expired = sum(1 for d in documents if d['validity_date'] and d['validity_date'] < str(date.today()))
    valid = total - expired
    
    # Par type de certificat
    type_counter = Counter(d['type'] for d in documents if d['type'])
    
    # Par société certificatrice
    certificatrice_counter = Counter(
        d['attributes'].get('societe_certificatrice', 'Inconnue') 
        for d in documents 
        if d['attributes'].get('societe_certificatrice')
    )
    
    return {
        'total': total,
        'valid': valid,
        'expired': expired,
        'by_type': dict(type_counter),
        'by_certificatrice': dict(certificatrice_counter)
    }


def _prepare_alerts_data(documents):
    """Prépare les données pour les alertes"""
    from datetime import datetime, timedelta
    
    today = date.today()
    
    # Par défaut, seuil à 30 jours
    alerts = []
    
    for doc in documents:
        if doc['validity_date']:
            validity = datetime.strptime(doc['validity_date'], '%Y-%m-%d').date()
            days_until_expiry = (validity - today).days
            
            if days_until_expiry < 30 or validity < today:
                alerts.append({
                    'id': doc['id'],
                    'title': doc['title'],
                    'societe': doc['attributes'].get('nom_societe_certifiee', 'Inconnue'),
                    'validity_date': doc['validity_date'],
                    'days_remaining': days_until_expiry,
                    'is_expired': validity < today,
                    'type': doc['type'],
                    'username': doc['username']
                })
    
    # Trier par date de péremption (les plus proches d'abord)
    alerts.sort(key=lambda x: x['days_remaining'])
    
    return {
        'alerts': alerts,
        'count': len(alerts)
    }


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

@app.route('/set_language/<lang>')
def set_language_route(lang):
    """Change la langue de l'application"""
    try:
        from translations import TRANSLATIONS, set_language as set_lang
        if lang in TRANSLATIONS:
            set_lang(lang)
            # Store in session
            session['language'] = lang
            # Create response with cookie
            resp = make_response(redirect(request.referrer or url_for('index')))
            resp.set_cookie('language', lang, max_age=60*60*24*365)  # 1 year
            return resp
    except ImportError:
        pass
    return redirect(request.referrer or url_for('index'))

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
                # Skip in testing mode
                if not app.config.get('TESTING', False) and file.content_type != 'application/pdf':
                    flash('Le fichier doit être un PDF valide', 'error')
                    return redirect(url_for('index'))
                
                # Assurer que le dossier d'upload existe
                ensure_upload_folder()
                
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
                    # Always include the attribute, even if empty (for optional fields)
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
# Dashboard Operations - Routes principales
# ============================================================================

@app.route('/operations')
@login_required
def operations_dashboard():
    """Page du dashboard configurable"""
    # Récupérer la configuration de l'utilisateur
    config = get_user_dashboard_config(current_user.id)
    
    # Récupérer la liste des configurations de l'utilisateur
    user_configs = get_user_dashboard_configs(current_user.id)
    
    # Récupérer les infos des widgets disponibles
    widgets_info = DASHBOARD_WIDGETS
    
    return render_template('operations.html',
                         config=config,
                         user_configs=user_configs,
                         widgets=widgets_info,
                         current_user=current_user)


# ============================================================================
# Dashboard Operations - API Routes
# ============================================================================

@app.route('/api/dashboard/config', methods=['GET'])
@login_required
def api_get_dashboard_config():
    """Récupère la configuration du dashboard pour l'utilisateur"""
    config_name = request.args.get('config_name', 'default')
    config = get_user_dashboard_config(current_user.id, config_name)
    return jsonify(config)


@app.route('/api/dashboard/config', methods=['POST'])
@login_required
def api_save_dashboard_config():
    """Sauvegarde la configuration du dashboard"""
    data = request.get_json()
    
    if not data or 'config_name' not in data or 'layout' not in data or 'widgets' not in data:
        return jsonify({'error': 'Missing required fields'}), 400
    
    config_name = data['config_name']
    config = {
        'layout': data['layout'],
        'widgets': data['widgets']
    }
    
    success = save_user_dashboard_config(current_user.id, config_name, config)
    
    if success:
        return jsonify({'message': 'Configuration saved', 'config_name': config_name})
    else:
        return jsonify({'error': 'Failed to save configuration'}), 500


@app.route('/api/dashboard/configs', methods=['GET'])
@login_required
def api_get_dashboard_configs():
    """Récupère toutes les configurations de dashboard de l'utilisateur"""
    configs = get_user_dashboard_configs(current_user.id)
    return jsonify({'configs': configs})


@app.route('/api/dashboard/config/<config_name>', methods=['DELETE'])
@login_required
def api_delete_dashboard_config(config_name):
    """Supprime une configuration de dashboard"""
    if config_name == 'default':
        return jsonify({'error': 'Cannot delete default configuration'}), 400
    
    success = delete_user_dashboard_config(current_user.id, config_name)
    
    if success:
        return jsonify({'message': 'Configuration deleted', 'config_name': config_name})
    else:
        return jsonify({'error': 'Failed to delete configuration'}), 500


@app.route('/api/dashboard/widgets/<widget_id>', methods=['GET'])
@login_required
def api_get_widget_data(widget_id):
    """Récupère les données pour un widget spécifique"""
    # Récupérer les paramètres du widget depuis la config utilisateur
    config = get_user_dashboard_config(current_user.id)
    widget_config = config.get('widgets', {}).get(widget_id, {})
    widget_params = widget_config.get('params', {})
    
    # Récupérer les données du widget
    data = get_dashboard_widget_data(widget_id, current_user.id, current_user.role)
    
    # Fusionner avec les paramètres
    return jsonify({
        'widget_id': widget_id,
        'params': widget_params,
        'data': data
    })


@app.route('/api/dashboard/widgets', methods=['GET'])
@login_required
def api_get_all_widgets_data():
    """Récupère les données pour tous les widgets actifs"""
    config = get_user_dashboard_config(current_user.id)
    active_widgets = {wid: info for wid, info in config.get('widgets', {}).items() if info.get('enabled', False)}
    
    results = {}
    for widget_id in active_widgets:
        results[widget_id] = get_dashboard_widget_data(widget_id, current_user.id, current_user.role)
    
    return jsonify(results)


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
