"""
Certificate Manager Application
Flask + SQLAlchemy + PostgreSQL
Compatible with SQLite and PostgreSQL for Railway deployment

This version uses SQLAlchemy ORM for database operations, making it compatible
with both SQLite (for development) and PostgreSQL (for production on Railway).

All database operations have been migrated from sqlite3 to SQLAlchemy.
"""

# ============================================================================
# Imports
# ============================================================================
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_from_directory,
    abort,
    jsonify,
    session,
    make_response,
)
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta, timezone
import os
import jwt
import base64
import json
import unicodedata
from functools import wraps

# ============================================================================
# SQLAlchemy Configuration
# ============================================================================
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import (
    text,
    and_,
    or_,
    func,
    Index,
    desc,
    asc,
    Date,
    DateTime,
    Boolean,
    Float,
    String,
    Text,
    Integer,
    ForeignKey,
)
from sqlalchemy.orm import relationship

# Initialize SQLAlchemy
db = SQLAlchemy()


# ============================================================================
# SQLAlchemy Models
# ============================================================================


class UserDB(db.Model):
    """SQLAlchemy model for users table"""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="user")
    created_at = db.Column(db.DateTime, server_default=func.now())

    # Relationships
    documents = db.relationship(
        "DocumentDB", backref="owner", lazy=True, cascade="all, delete-orphan"
    )
    dashboard_configs = db.relationship(
        "DashboardConfigDB", backref="user", lazy=True, cascade="all, delete-orphan"
    )


class DocumentDB(db.Model):
    """SQLAlchemy model for documents table"""

    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    upload_date = db.Column(db.DateTime, server_default=func.now())
    validity_date = db.Column(db.Date)
    file_path = db.Column(db.String(255))
    type = db.Column(db.String(50))
    attributes = db.Column(db.Text)


class DashboardConfigDB(db.Model):
    """SQLAlchemy model for user_dashboard_config table"""

    __tablename__ = "user_dashboard_config"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    config_name = db.Column(db.String(80), nullable=False, default="default")
    layout = db.Column(db.Text)
    widgets = db.Column(db.Text)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        db.UniqueConstraint("user_id", "config_name", name="uq_user_config"),
    )


# ============================================================================
# Product Models - User-specific products and their document relationships
# ============================================================================

class ProductDB(db.Model):
    """SQLAlchemy model for user products table"""

    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    user = db.relationship("UserDB", backref="products")
    documents = db.relationship(
        "DocumentDB", 
        secondary="product_document",
        backref=db.backref("products", lazy=True),
        lazy=True
    )

    __table_args__ = (
        db.UniqueConstraint("user_id", "name", name="uq_user_product_name"),
    )


class ProductDocumentDB(db.Model):
    """Association table between products and documents (many-to-many relationship)"""

    __tablename__ = "product_document"

    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), primary_key=True)
    created_at = db.Column(db.DateTime, server_default=func.now())

    __table_args__ = (
        db.UniqueConstraint("product_id", "document_id", name="uq_product_document"),
    )


class GeocodeCacheDB(db.Model):
    """SQLAlchemy model for geocode_cache table"""

    __tablename__ = "geocode_cache"

    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(255), unique=True, nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    accessed_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())
    created_at = db.Column(db.DateTime, server_default=func.now())

    __table_args__ = (db.Index("idx_geocode_address", "address"),)


# ============================================================================
# Flask App Initialization
# ============================================================================
app = Flask(__name__)

# Load secret key from environment or use default
app.secret_key = os.environ.get(
    "SECRET_KEY", "ta_cle_secrete_ic123456_changez_la_en_production"
)

# Configure SQLAlchemy
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///" + os.path.join(os.path.dirname(__file__), "documents.db"),
)

# Handle PostgreSQL URL format (Railway uses postgres://)
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize SQLAlchemy with Flask app
db.init_app(app)

# Configuration
UPLOAD_FOLDER = os.environ.get(
    "UPLOAD_FOLDER", os.path.join(os.path.dirname(__file__), "static", "uploads")
)
ALLOWED_EXTENSIONS = {"pdf"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # Limite à 16 Mo


# ============================================================================
# Flask-Login Setup
# ============================================================================


class User(UserMixin):
    """User class for Flask-Login compatibility"""

    def __init__(self, id, username, password_hash, role):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.role = role


login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message_category = "danger"
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    """Load user from database using SQLAlchemy"""
    user_db = db.session.get(UserDB, int(user_id))
    if user_db:
        return User(
            id=user_db.id,
            username=user_db.username,
            password_hash=user_db.password,
            role=user_db.role,
        )
    return None


# ============================================================================
# Utility Functions
# ============================================================================


def ensure_upload_folder():
    """Ensure upload folder exists (lazy creation to avoid issues on read-only filesystems)"""
    try:
        # Create parent directory (static/) if it doesn't exist
        static_dir = os.path.dirname(UPLOAD_FOLDER)
        os.makedirs(static_dir, exist_ok=True)
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    except Exception as e:
        import sys

        print(f"Warning: Could not create upload folder: {e}", file=sys.stderr)
        pass


def allowed_file(filename):
    """Check if file has allowed extension (PDF only)"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def admin_required(f):
    """Decorator to check if user is admin"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("login"))
        if current_user.role != "admin":
            flash("Accès refusé. Réservé aux administrateurs.", "danger")
            return redirect(url_for("documents"))
        return f(*args, **kwargs)

    return decorated_function


# ============================================================================
# Document Types System
# ============================================================================

# Register of document types with their validation schemas
DOCUMENT_TYPES = {
    "certificat": {
        "name": "Certificat",
        "description": "Certificat avec société certifiée et certificatrice",
        "attributes": {
            "nom_societe_certifiee": {
                "type": "string",
                "label": "Nom de la société certifiée",
                "required": True,
                "form_type": "text",
            },
            "societe_certificatrice": {
                "type": "string",
                "label": "Société certificatrice",
                "required": True,
                "form_type": "text",
            },
            "adresse": {
                "type": "string",
                "label": "Adresse de la société",
                "required": False,
                "form_type": "textarea",
            },
            "date_peremption": {
                "type": "date",
                "label": "Date de péremption du certificat",
                "required": True,
                "form_type": "date",
            },
            "url_telechargement": {
                "type": "string",
                "label": "URL de téléchargement",
                "required": False,
                "form_type": "text",
            },
        },
    }
}


def register_document_type(type_name, config):
    DOCUMENT_TYPES[type_name] = config


def get_document_type(type_name):
    return DOCUMENT_TYPES.get(type_name)


def get_document_types():
    return DOCUMENT_TYPES


def validate_document_attributes(type_name, attributes):
    """Validate document attributes based on type schema"""
    doc_type = get_document_type(type_name)
    if not doc_type:
        return False, [f"Type de document inconnu: {type_name}"]

    errors = []
    attr_schema = doc_type.get("attributes", {})

    for attr_name, schema in attr_schema.items():
        if schema.get("required", False):
            if attr_name not in attributes or not attributes[attr_name]:
                errors.append(f"{schema['label']} est obligatoire")

    for attr_name, value in attributes.items():
        if attr_name in attr_schema:
            expected_type = attr_schema[attr_name]["type"]
            if expected_type == "date" and value:
                try:
                    datetime.strptime(value, "%Y-%m-%d")
                except ValueError:
                    errors.append(
                        f"{attr_schema[attr_name]['label']} doit etre une date valide (YYYY-MM-DD)"
                    )
            elif expected_type == "number" and value:
                try:
                    float(value)
                except ValueError:
                    errors.append(
                        f"{attr_schema[attr_name]['label']} doit etre un nombre"
                    )

    return len(errors) == 0, errors


# ============================================================================
# Database Functions (SQLAlchemy)
# ============================================================================


def init_db():
    """Initialise la base de données avec les tables nécessaires"""
    with app.app_context():
        # Create all tables defined in SQLAlchemy models
        db.create_all()

        # Check if we need to add default users
        if UserDB.query.count() == 0:
            # Mot de passe par défaut pour admin : "admin123"
            admin_password = generate_password_hash("admin123")
            admin = UserDB(username="admin", password=admin_password, role="admin")
            db.session.add(admin)

            # Ajouter quelques utilisateurs tests
            user_password = generate_password_hash("password")
            user1 = UserDB(username="user1", password=user_password, role="user")
            user2 = UserDB(username="user2", password=user_password, role="user")
            db.session.add(user1)
            db.session.add(user2)
            db.session.commit()

        # Mettre à jour les utilisateurs existants sans password
        users_without_pass = UserDB.query.filter(
            or_(UserDB.password.is_(None), UserDB.password == "")
        ).all()

        for user in users_without_pass:
            # Générer un mot de passe par défaut (username + '123')
            default_password = generate_password_hash(user.username + "123")
            user.password = default_password
        db.session.commit()


# ============================================================================
# Dashboard System - Default Coordinates
# ============================================================================

# Coordonnées géographiques par défaut pour les villes et sociétés connues
DEFAULT_COORDINATES = {
    # Villes françaises
    "besancon": (47.2380, 6.0241),
    "besançon": (47.2380, 6.0241),
    "paris": (48.8566, 2.3522),
    "lyon": (45.7640, 4.8357),
    "colmar": (48.0782, 7.3575),
    "avon": (48.4089, 2.7442),
    "molsheim": (48.5156, 7.4989),
    "illkirch": (48.5389, 7.6706),
    "strasbourg": (48.5734, 7.7521),
    "bornem": (51.1833, 4.2333),
    "vervier": (50.5939, 5.8842),
    "visp": (46.2922, 7.8858),
    # Pays
    "france": (46.2276, 2.2137),
    "suisse": (46.8182, 8.2275),
    "espagne": (40.4637, -3.7492),
    "belgique": (50.5039, 4.4699),
    "allemagne": (51.1657, 10.4515),
    "etats-unis": (37.0902, -95.7129),
    "usa": (37.0902, -95.7129),
    # Sociétés spécifiques
    "amcor": (47.2380, 6.0241),
    "ashland": (48.8566, 2.3522),
    "biomerieux": (45.7640, 4.8357),
    "corning": (48.4089, 2.7442),
    "lonza": (48.0782, 7.3575),
    "merck": (48.8566, 2.3522),
    "perlen": (47.0502, 8.3093),
    "thermofisher": (48.5734, 7.7521),
    "nalg": (48.5734, 7.7521),
    "nunc": (48.5734, 7.7521),
    "pamplona": (42.8125, -1.6458),
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
    normalized_addr = unicodedata.normalize("NFKD", address.lower())
    normalized_addr = "".join(
        c for c in normalized_addr if not unicodedata.combining(c)
    )

    # Vérifier le cache d'abord
    if use_cache:
        try:
            cached = GeocodeCacheDB.query.filter_by(address=normalized_addr).first()
            if cached:
                return float(cached.latitude), float(cached.longitude)
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
    significant_words = [
        w
        for w in words
        if len(w) > 3
        and w
        not in [
            "rue",
            "de",
            "la",
            "le",
            "les",
            "du",
            "des",
            "au",
            "en",
            "a",
            "d",
            "l",
            "an",
            "and",
            "the",
            "of",
            "at",
            "in",
            "for",
        ]
    ]

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
                "q": address,
                "format": "json",
                "limit": 1,
                "email": "contact@example.com",  # Recommandé par Nominatim
            }

            response = requests.get(url, params=params, timeout=5)

            if response.status_code == 200 and response.json():
                result = response.json()[0]
                lat = float(result.get("lat"))
                lon = float(result.get("lon"))

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
        # Upsert: update if exists, else create
        cache_entry = GeocodeCacheDB.query.filter_by(address=address).first()
        if cache_entry:
            cache_entry.latitude = latitude
            cache_entry.longitude = longitude
            cache_entry.accessed_at = func.now()
        else:
            cache_entry = GeocodeCacheDB(
                address=address, latitude=latitude, longitude=longitude
            )
            db.session.add(cache_entry)
        db.session.commit()
    except Exception as e:
        app.logger.error(f"Erreur lors de la sauvegarde du cache de géocodage: {e}")


# ============================================================================
# Dashboard Configuration Functions (SQLAlchemy)
# ============================================================================


def get_default_dashboard_config():
    """Retourne la configuration par défaut du dashboard"""
    return {
        "layout": [
            {"widget_id": "timeline", "x": 0, "y": 0, "w": 8, "h": 4},
            {"widget_id": "map", "x": 0, "y": 4, "w": 12, "h": 6},
            {"widget_id": "stats", "x": 8, "y": 0, "w": 4, "h": 4},
            {"widget_id": "alerts", "x": 8, "y": 4, "w": 4, "h": 5},
        ],
        "widgets": {
            widget_id: {"enabled": True, "params": widget_info["default_params"]}
            for widget_id, widget_info in DASHBOARD_WIDGETS.items()
        },
    }


# Widgets disponibles pour le dashboard
DASHBOARD_WIDGETS = {
    "timeline": {
        "id": "timeline",
        "name": "Timeline des péremptions",
        "name_en": "Expiry Timeline",
        "description": "Affiche les dates de péremption des certificats sur une timeline",
        "description_en": "Display certificate expiry dates on a timeline",
        "icon": "bi-calendar-range",
        "default_params": {
            "days_range": 60,  # Nombre de jours à afficher
            "show_expired": True,
            "show_valid": True,
        },
        "default_size": {"w": 8, "h": 4},
    },
    "map": {
        "id": "map",
        "name": "Carte des sites",
        "name_en": "Sites Map",
        "description": "Carte géographique des sites avec certificats (vert=valide, rouge=périmé)",
        "description_en": "Geographic map of sites with certificates (green=valid, red=expired)",
        "icon": "bi-geo-alt",
        "default_params": {
            "default_zoom": 6,
            "default_center": [47.0, 2.0],  # France par défaut
            "show_clusters": True,
        },
        "default_size": {"w": 12, "h": 6},
    },
    "stats": {
        "id": "stats",
        "name": "Statistiques",
        "name_en": "Statistics",
        "description": "Nombre de certificats valides, périmés et par type",
        "description_en": "Number of valid, expired certificates and by type",
        "icon": "bi-bar-chart",
        "default_params": {},
        "default_size": {"w": 6, "h": 4},
    },
    "alerts": {
        "id": "alerts",
        "name": "Alertes de péremption",
        "name_en": "Expiry Alerts",
        "description": "Liste des certificats expirant bientôt",
        "description_en": "List of certificates expiring soon",
        "icon": "bi-bell",
        "default_params": {
            "days_threshold": 30,  # Avertir si péremption dans X jours
            "show_expired": True,
        },
        "default_size": {"w": 6, "h": 5},
    },
}


def get_user_dashboard_config(user_id, config_name="default"):
    """
    Récupère la configuration du dashboard pour un utilisateur.
    Si elle n'existe pas, crée et retourne la configuration par défaut.
    """
    # Try to find existing config
    config_db = DashboardConfigDB.query.filter_by(
        user_id=user_id, config_name=config_name
    ).first()

    if config_db:
        config = {
            "layout": json.loads(config_db.layout) if config_db.layout else [],
            "widgets": json.loads(config_db.widgets) if config_db.widgets else {},
        }
    else:
        # Créer la configuration par défaut
        config = get_default_dashboard_config()

        # Save the default config
        new_config = DashboardConfigDB(
            user_id=user_id,
            config_name=config_name,
            layout=json.dumps(config["layout"]),
            widgets=json.dumps(config["widgets"]),
            is_default=True,
        )
        db.session.add(new_config)
        db.session.commit()

    return config


def save_user_dashboard_config(user_id, config_name, config):
    """Sauvegarde la configuration du dashboard pour un utilisateur"""
    # Check if config exists
    config_db = DashboardConfigDB.query.filter_by(
        user_id=user_id, config_name=config_name
    ).first()

    if config_db:
        # Update existing
        config_db.layout = json.dumps(config["layout"])
        config_db.widgets = json.dumps(config["widgets"])
        config_db.updated_at = func.now()
    else:
        # Create new
        config_db = DashboardConfigDB(
            user_id=user_id,
            config_name=config_name,
            layout=json.dumps(config["layout"]),
            widgets=json.dumps(config["widgets"]),
            is_default=True,
        )
        db.session.add(config_db)

    db.session.commit()
    return True


def delete_user_dashboard_config(user_id, config_name):
    """Supprime une configuration de dashboard"""
    if config_name == "default":
        return False  # On ne peut pas supprimer la config par défaut

    # Delete the configuration
    DashboardConfigDB.query.filter_by(user_id=user_id, config_name=config_name).delete()

    db.session.commit()
    return True


def get_user_dashboard_configs(user_id):
    """Récupère toutes les configurations de dashboard pour un utilisateur"""
    # Query all configs for this user
    configs = (
        DashboardConfigDB.query.filter_by(user_id=user_id)
        .order_by(
            desc(DashboardConfigDB.is_default), desc(DashboardConfigDB.updated_at)
        )
        .all()
    )

    return [
        {
            "name": config.config_name,
            "is_default": bool(config.is_default),
            "updated_at": config.updated_at,
        }
        for config in configs
    ]


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

    if widget_id == "timeline":
        return _prepare_timeline_data(documents)
    elif widget_id == "map":
        return _prepare_map_data(documents)
    elif widget_id == "stats":
        return _prepare_stats_data(documents)
    elif widget_id == "alerts":
        return _prepare_alerts_data(documents)
    else:
        return {"error": "Widget inconnu"}


def _prepare_timeline_data(documents):
    """Prépare les données pour la timeline"""
    from collections import defaultdict

    # Regrouper par date
    timeline_data = defaultdict(list)

    for doc in documents:
        if doc["validity_date"]:
            # Utiliser la date de validité
            date_key = doc["validity_date"]
            timeline_data[date_key].append(
                {
                    "id": doc["id"],
                    "title": doc["title"],
                    "societe": doc["attributes"].get(
                        "nom_societe_certifiee", "Inconnue"
                    ),
                    "is_expired": doc["validity_date"] < str(date.today()),
                    "validity_date": doc["validity_date"],
                }
            )

    return {
        "labels": sorted(timeline_data.keys()),
        "datasets": [
            {
                "label": "Valides",
                "data": [
                    {"date": k, "count": len([d for d in v if not d["is_expired"]])}
                    for k, v in sorted(timeline_data.items())
                ],
                "backgroundColor": "#10b981",
            },
            {
                "label": "Périmés",
                "data": [
                    {"date": k, "count": len([d for d in v if d["is_expired"]])}
                    for k, v in sorted(timeline_data.items())
                ],
                "backgroundColor": "#ef4444",
            },
        ],
        "documents_by_date": timeline_data,
    }


def _prepare_map_data(documents):
    """Prépare les données pour la carte"""
    features = []

    for doc in documents:
        attrs = doc["attributes"]

        if "_latitude" in attrs and "_longitude" in attrs:
            lat = attrs["_latitude"]
            lon = attrs["_longitude"]

            if lat is not None and lon is not None:
                is_expired = doc["validity_date"] and doc["validity_date"] < str(
                    date.today()
                )

                features.append(
                    {
                        "type": "Feature",
                        "properties": {
                            "id": doc["id"],
                            "title": doc["title"],
                            "societe": attrs.get("nom_societe_certifiee", "Inconnue"),
                            "adresse": attrs.get("adresse", ""),
                            "validity_date": doc["validity_date"] or "",
                            "is_expired": is_expired,
                            "certificatrice": attrs.get("societe_certificatrice", ""),
                        },
                        "geometry": {
                            "type": "Point",
                            "coordinates": [lon, lat],  # Leaflet utilise [long, lat]
                        },
                    }
                )

    return {"type": "FeatureCollection", "features": features}


def _prepare_stats_data(documents):
    """Prépare les données pour les statistiques"""
    from collections import Counter

    total = len(documents)
    expired = sum(
        1
        for d in documents
        if d["validity_date"] and d["validity_date"] < str(date.today())
    )
    valid = total - expired

    # Par type de certificat
    type_counter = Counter(d["type"] for d in documents if d["type"])

    # Par société certificatrice
    certificatrice_counter = Counter(
        d["attributes"].get("societe_certificatrice", "Inconnue")
        for d in documents
        if d["attributes"].get("societe_certificatrice")
    )

    return {
        "total": total,
        "valid": valid,
        "expired": expired,
        "by_type": dict(type_counter),
        "by_certificatrice": dict(certificatrice_counter),
    }


def _prepare_alerts_data(documents):
    from datetime import datetime, timedelta

    today = date.today()

    # Par défaut, seuil à 30 jours
    alerts = []

    for doc in documents:
        if doc["validity_date"]:
            validity = datetime.strptime(doc["validity_date"], "%Y-%m-%d").date()
            days_until_expiry = (validity - today).days

            if days_until_expiry < 30 or validity < today:
                alerts.append(
                    {
                        "id": doc["id"],
                        "title": doc["title"],
                        "societe": doc["attributes"].get(
                            "nom_societe_certifiee", "Inconnue"
                        ),
                        "validity_date": doc["validity_date"],
                        "days_remaining": days_until_expiry,
                        "is_expired": validity < today,
                        "type": doc["type"],
                        "username": doc["username"],
                    }
                )

    # Trier par date de péremption (les plus proches d'abord)
    alerts.sort(key=lambda x: x["days_remaining"])

    return {"alerts": alerts, "count": len(alerts)}


def get_all_documents_for_user(user_id=None, user_role=None):
    """
    Récupère tous les documents accessibles par un utilisateur.

    Args:
        user_id: ID de l'utilisateur (None si admin)
        user_role: Rôle de l'utilisateur

    Returns:
        Liste de dictionnaires avec les documents
    """
    # Build query based on user role
    if user_role == "admin":
        documents_query = DocumentDB.query.join(
            UserDB, DocumentDB.user_id == UserDB.id
        ).order_by(DocumentDB.upload_date.desc())
    else:
        documents_query = (
            DocumentDB.query.join(UserDB, DocumentDB.user_id == UserDB.id)
            .filter(DocumentDB.user_id == user_id)
            .order_by(DocumentDB.upload_date.desc())
        )

    documents = documents_query.all()

    result = []
    for doc in documents:
        # Parse attributes
        attrs = {}
        if doc.attributes:
            try:
                attrs = json.loads(doc.attributes)
            except:
                attrs = {}

        # Ajouter les coordonnées géographiques si adresse présente
        if "adresse" in attrs and attrs["adresse"]:
            lat, lon = geocode_address(attrs["adresse"])
            attrs["_latitude"] = lat
            attrs["_longitude"] = lon

        # Add to result with all data
        result.append(
            {
                "id": doc.id,
                "title": doc.title,
                "content": doc.content,
                "upload_date": doc.upload_date.isoformat() if doc.upload_date else None,
                "validity_date": str(doc.validity_date) if doc.validity_date else None,
                "file_path": doc.file_path,
                "type": doc.type,
                "attributes": attrs,
                "username": doc.owner.username,
                "user_id": doc.owner.id,
            }
        )

    return result


# ============================================================================
# Routes principales
# ============================================================================


# Contexte global pour les templates
@app.context_processor
def inject_global_vars():
    """Injecte des variables globales dans tous les templates"""
    try:
        from translations import (
            get_current_language,
            TRANSLATIONS,
            AVAILABLE_LANGUAGES,
            get_translation,
        )

        def get_current_lang():
            # Retourne la langue actuelle (utilisée dans les templates)
            return get_current_language()
        
        def translate_function(key):
            # Appeler get_current_language() à chaque fois pour avoir la langue la plus récente
            current_lang = get_current_lang()
            return get_translation(key, current_lang)
        
        return {
            "current_lang": get_current_lang(),
            "available_languages": AVAILABLE_LANGUAGES,
            "t": translate_function,
        }
    except ImportError:
        # translations module not available (e.g., during testing)
        return {
            "current_lang": "fr",
            "available_languages": {"fr": "Français", "en": "English"},
            "t": lambda key: key,
        }


@app.route("/health")
def health():
    """Health check endpoint for Railway"""
    # Initialize database on first healthcheck if not already done
    from app_sqlalchemy import db, init_db
    from flask import current_app

    try:
        # Check if DB is already initialized by trying a simple query
        with current_app.app_context():
            # Try to execute a simple query to test connection
            db.session.execute("SELECT 1")
    except:
        # DB not ready, initialize with retries
        max_retries = 5
        retry_count = 0

        while retry_count < max_retries:
            try:
                init_db()
                break
            except Exception as e:
                retry_count += 1
                import time

                wait_time = 2**retry_count
                if retry_count < max_retries:
                    time.sleep(wait_time)
                else:
                    raise

    return "OK", 200


@app.route("/")
@login_required
def home():
    """Page d'accueil avec présentation de l'outil"""
    return render_template(
        "home.html",
        current_user=current_user,
    )


@app.route("/documents")
@login_required
def documents():
    """Page avec la liste des documents et la recherche"""
    # Récupérer les critères de recherche et pagination
    search_author = request.args.get("author", "")
    search_upload_from = request.args.get("upload_from", "")
    search_upload_to = request.args.get("upload_to", "")
    search_validity_from = request.args.get("validity_from", "")
    search_validity_to = request.args.get("validity_to", "")
    search_type = request.args.get("doc_type", "")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    # Construire la requête SQLAlchemy
    if current_user.role == "admin":
        query = DocumentDB.query.join(UserDB, DocumentDB.user_id == UserDB.id)
    else:
        query = DocumentDB.query.join(UserDB, DocumentDB.user_id == UserDB.id).filter(
            DocumentDB.user_id == current_user.id
        )

    # Ajouter les filtres de recherche
    if search_author:
        query = query.filter(UserDB.username.ilike(f"%{search_author}%"))

    if search_upload_from:
        query = query.filter(func.date(DocumentDB.upload_date) >= search_upload_from)

    if search_upload_to:
        query = query.filter(func.date(DocumentDB.upload_date) <= search_upload_to)

    if search_validity_from:
        query = query.filter(DocumentDB.validity_date >= search_validity_from)

    if search_validity_to:
        query = query.filter(DocumentDB.validity_date <= search_validity_to)

    if search_type:
        query = query.filter(DocumentDB.type == search_type)

    # Tri
    query = query.order_by(DocumentDB.upload_date.desc())

    # Pagination
    paginated_documents = query.paginate(page=page, per_page=per_page, error_out=False)
    documents = paginated_documents.items

    # Parser les attributs JSON et ajouter les coordonnées
    docs_with_attrs = []
    for doc in documents:
        attrs = {}
        if doc.attributes:
            try:
                attrs = json.loads(doc.attributes)
            except:
                attrs = {}

        # Ajouter les coordonnées géographiques si adresse présente
        if "adresse" in attrs and attrs["adresse"]:
            lat, lon = geocode_address(attrs["adresse"])
            attrs["_latitude"] = lat
            attrs["_longitude"] = lon

        # Convert dates to strings for template compatibility
        upload_date_str = doc.upload_date.isoformat() if doc.upload_date else None
        validity_date_str = str(doc.validity_date) if doc.validity_date else None

        docs_with_attrs.append(
            {
                "id": doc.id,
                "title": doc.title,
                "content": doc.content,
                "upload_date": upload_date_str,
                "validity_date": validity_date_str,
                "file_path": doc.file_path,
                "type": doc.type,
                "username": doc.owner.username,
                "attributes": attrs,
            }
        )

    # Récupérer les produits de l'utilisateur pour le sélecteur
    user_products = ProductDB.query.filter_by(user_id=current_user.id).order_by(ProductDB.name).all()
    
    return render_template(
        "index.html",
        documents=docs_with_attrs,
        current_user=current_user,
        document_types=get_document_types(),
        current_date=date.today().isoformat(),
        user_products=user_products,
        pagination=paginated_documents,
        page=page,
        per_page=per_page,
    )


# Routes de login
@app.route("/login", methods=["GET", "POST"])
def login():
    """Page de connexion"""
    if current_user.is_authenticated:
        return redirect(url_for("documents"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        remember = True if request.form.get("remember") else False

        # Use SQLAlchemy instead of sqlite3
        user_db = UserDB.query.filter_by(username=username).first()

        if user_db and check_password_hash(user_db.password, password):
            user = User(
                id=user_db.id,
                username=user_db.username,
                password_hash=user_db.password,
                role=user_db.role,
            )
            login_user(user, remember=remember)
            flash("Connexion réussie !", "success")
            return redirect(url_for("documents"))
        else:
            flash("Nom d'utilisateur ou mot de passe incorrect", "danger")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    """Déconnexion"""
    logout_user()
    flash("Déconnexion réussie", "success")
    return redirect(url_for("login"))


@app.route("/set_language/<lang>")
def set_language_route(lang):
    """Change la langue de l'application"""
    try:
        from translations import TRANSLATIONS, set_language as set_lang

        if lang in TRANSLATIONS:
            # Store in session
            session["language"] = lang
            # Create response with cookie
            next_url = request.args.get('next', url_for('documents'))
            resp = make_response(redirect(next_url, code=303))  # 303 See Other pour forcer une requête GET fraîche
            resp.set_cookie("language", lang, max_age=60 * 60 * 24 * 365)  # 1 year
            # Also set in session via set_lang
            set_lang(lang)
            return resp
    except ImportError:
        pass
    next_url = request.args.get('next', url_for('documents'))
    return redirect(next_url)


# Routes documents
@app.route("/add", methods=["GET", "POST"])
@login_required
def add_document():
    """Ajouter un nouveau document"""
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        validity_date = request.form.get("validity_date")
        doc_type = request.form.get("doc_type", "")

        # L'auteur est automatiquement l'utilisateur connecté
        user_id = current_user.id

        # Gestion de l'upload du fichier PDF
        file_path = None
        if "file" in request.files:
            file = request.files["file"]
            if file and file.filename != "":
                # Vérifier que le fichier a une extension PDF
                if not allowed_file(file.filename):
                    flash("Seuls les fichiers PDF sont autorisés", "error")
                    return redirect(url_for("documents"))

                # Sécuriser le nom du fichier
                filename = secure_filename(file.filename)

                # Vérifier le MIME type (pour éviter les fichiers renommés)
                # Skip in testing mode
                if (
                    not app.config.get("TESTING", False)
                    and file.content_type != "application/pdf"
                ):
                    flash("Le fichier doit être un PDF valide", "error")
                    return redirect(url_for("documents"))

                # Assurer que le dossier d'upload existe
                ensure_upload_folder()

                # Sauvegarder le fichier
                try:
                    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                    file.save(file_path)
                except Exception as e:
                    flash(f"Erreur lors de l'upload : {str(e)}", "error")
                    return redirect(url_for("documents"))

        # Récupérer les attributs spécifiques au type
        attributes = {}
        if doc_type:
            doc_type_config = get_document_type(doc_type)
            if doc_type_config:
                for attr_name, attr_config in doc_type_config.get(
                    "attributes", {}
                ).items():
                    attr_value = request.form.get(f"doc_attr_{attr_name}", "").strip()
                    # Always include the attribute, even if empty (for optional fields)
                    attributes[attr_name] = attr_value

            # Valider les attributs
            is_valid, errors = validate_document_attributes(doc_type, attributes)
            if not is_valid:
                for error in errors:
                    flash(error, "error")
                return redirect(url_for("documents"))

        # Validation
        if not title:
            flash("Le titre est obligatoire", "error")
        elif not file_path:
            flash("Le fichier PDF est obligatoire", "error")
        else:
            try:
                # Stocker seulement le nom du fichier dans la base
                db_file_path = os.path.basename(file_path) if file_path else None

                # Create document using SQLAlchemy
                new_doc = DocumentDB(
                    title=title,
                    content=content,
                    user_id=user_id,
                    validity_date=validity_date,
                    file_path=db_file_path,
                    type=doc_type,
                    attributes=json.dumps(attributes),
                )
                db.session.add(new_doc)
                db.session.commit()
                
                # Associer le document aux produits sélectionnés
                product_ids = request.form.getlist("product_ids")
                if product_ids:
                    for prod_id in product_ids:
                        if prod_id.isdigit():
                            product = ProductDB.query.get(int(prod_id))
                            if product and product.user_id == current_user.id:
                                # Vérifier que la relation n'existe pas déjà
                                existing_rel = ProductDocumentDB.query.filter_by(
                                    product_id=int(prod_id), document_id=new_doc.id
                                ).first()
                                if not existing_rel:
                                    relation = ProductDocumentDB(
                                        product_id=int(prod_id),
                                        document_id=new_doc.id,
                                    )
                                    db.session.add(relation)
                    db.session.commit()

                flash("Document ajouté avec succès !", "success")
                return redirect(url_for("documents"))
            except Exception as e:
                flash(f"Erreur : {str(e)}", "error")

    return redirect(url_for("documents"))


@app.route("/delete/<int:doc_id>")
@login_required
def delete_document(doc_id):
    """Supprimer un document"""
    # Vérifier que l'utilisateur peut supprimer ce document
    doc = DocumentDB.query.filter_by(id=doc_id).first()

    if not doc:
        flash("Document non trouvé", "error")
        return redirect(url_for("documents"))

    # Vérifier les permissions

    # Vérifier les permissions
    if current_user.id != doc.user_id and current_user.role != "admin":
        flash("Vous ne pouvez pas supprimer ce document", "danger")
        return redirect(url_for("documents"))

    try:
        # Supprimer le fichier physique si il existe
        if doc.file_path:
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], doc.file_path)
            if os.path.exists(file_path):
                os.remove(file_path)

        # Supprimer l'entrée de la base
        db.session.delete(doc)
        db.session.commit()
        flash("Document supprimé avec succès !", "success")
    except Exception as e:
        flash(f"Erreur : {str(e)}", "error")

    return redirect(url_for("documents"))


# ============================================================================
# Routes Admin
# ============================================================================


@app.route("/admin/users")
@login_required
@admin_required
def admin_users():
    """Interface de gestion des utilisateurs"""
    users = UserDB.query.order_by(UserDB.created_at.desc()).all()

    users_list = [
        {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "created_at": user.created_at,
        }
        for user in users
    ]

    return render_template("admin/users.html", users=users_list)


@app.route("/admin/add_user", methods=["POST"])
@login_required
@admin_required
def admin_add_user():
    """Ajouter un nouvel utilisateur (admin seulement)"""
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "user")

    if not username:
        flash("Le nom d'utilisateur est obligatoire", "error")
        return redirect(url_for("admin_users"))

    if len(password) < 6:
        flash("Le mot de passe doit contenir au moins 6 caractères", "error")
        return redirect(url_for("admin_users"))

    try:
        # Check if user already exists
        existing_user = UserDB.query.filter_by(username=username).first()
        if existing_user:
            flash("Ce nom d'utilisateur existe déjà", "error")
            return redirect(url_for("admin_users"))

        password_hash = generate_password_hash(password)
        new_user = UserDB(username=username, password=password_hash, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash("Utilisateur ajouté avec succès !", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur : {str(e)}", "error")

    return redirect(url_for("admin_users"))


@app.route("/admin/edit_user/<int:user_id>", methods=["GET", "POST"])
@login_required
@admin_required
def admin_edit_user(user_id):
    """Modifier un utilisateur"""
    user = db.session.get(UserDB, user_id)

    if not user:
        flash("Utilisateur non trouvé", "error")
        return redirect(url_for("admin_users"))

    if request.method == "POST":
        new_username = request.form.get("username", "").strip()
        new_password = request.form.get("password", "")
        new_role = request.form.get("role", "user")

        if not new_username:
            flash("Le nom d'utilisateur est obligatoire", "error")
            return redirect(url_for("admin_edit_user", user_id=user_id))

        try:
            # Check if new username already exists (excluding current user)
            existing_user = UserDB.query.filter(
                UserDB.username == new_username, UserDB.id != user_id
            ).first()
            if existing_user:
                flash("Ce nom d'utilisateur existe déjà", "error")
                return redirect(url_for("admin_edit_user", user_id=user_id))

            # Update user
            user.username = new_username
            user.role = new_role

            if new_password:
                if len(new_password) < 6:
                    flash(
                        "Le mot de passe doit contenir au moins 6 caractères", "error"
                    )
                    return redirect(url_for("admin_edit_user", user_id=user_id))
                user.password = generate_password_hash(new_password)

            db.session.commit()
            flash("Utilisateur modifié avec succès !", "success")
            return redirect(url_for("admin_users"))
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur : {str(e)}", "error")

    return render_template("admin/edit_user.html", user=user)


@app.route("/admin/delete_user/<int:user_id>")
@login_required
@admin_required
def admin_delete_user(user_id):
    """Supprimer un utilisateur"""
    if current_user.id == user_id:
        flash("Vous ne pouvez pas supprimer votre propre compte", "danger")
        return redirect(url_for("admin_users"))

    user = db.session.get(UserDB, user_id)
    if not user:
        flash("Utilisateur non trouvé", "error")
        return redirect(url_for("admin_users"))

    try:
        # Supprimer les documents de l'utilisateur
        docs = DocumentDB.query.filter_by(user_id=user_id).all()

        for doc in docs:
            if doc.file_path:
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], doc.file_path)
                if os.path.exists(file_path):
                    os.remove(file_path)

        # Supprimer les documents de la base
        DocumentDB.query.filter_by(user_id=user_id).delete()

        # Supprimer l'utilisateur
        db.session.delete(user)
        db.session.commit()
        flash("Utilisateur et ses documents supprimés avec succès !", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur : {str(e)}", "error")

    return redirect(url_for("admin_users"))


@app.route("/admin/edit_user_page/<int:user_id>")
@login_required
@admin_required
def admin_edit_user_page(user_id):
    """Page de modification d'utilisateur"""
    user = db.session.get(UserDB, user_id)

    if not user:
        flash("Utilisateur non trouvé", "error")
        return redirect(url_for("admin_users"))

    return render_template("admin/edit_user.html", user=user)


# Route pour servir les fichiers
@app.route("/uploads/<filename>")
@login_required
def uploaded_file(filename):
    """Route pour servir les fichiers uploadés"""
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# ============================================================================
# Dashboard Operations - Routes principales
# ============================================================================


@app.route("/operations")
@login_required
def operations_dashboard():
    """Page du dashboard configurable"""
    # Récupérer la configuration de l'utilisateur
    config = get_user_dashboard_config(current_user.id)

    # Récupérer la liste des configurations de l'utilisateur
    user_configs = get_user_dashboard_configs(current_user.id)

    # Récupérer les infos des widgets disponibles
    widgets_info = DASHBOARD_WIDGETS

    # Récupérer les produits de l'utilisateur pour le filtre
    user_products = ProductDB.query.filter_by(user_id=current_user.id).order_by(ProductDB.name).all()
    
    # Récupérer le produit sélectionné depuis les query params ou la session
    selected_product_id = request.args.get('product_id', '')

    # Créer un token JWT pour les appels API depuis le frontend
    from app_sqlalchemy import create_jwt_token
    user_obj = User(
        id=current_user.id,
        username=current_user.username,
        password_hash=current_user.password_hash,
        role=current_user.role,
    )
    jwt_token = create_jwt_token(user_obj)

    return render_template(
        "operations.html",
        config=config,
        user_configs=user_configs,
        widgets=widgets_info,
        current_user=current_user,
        jwt_token=jwt_token,
        user_products=user_products,
        selected_product_id=selected_product_id,
    )


# ============================================================================
# Product Routes - User-specific products with document associations
# ============================================================================


@app.route("/products")
@login_required
def my_products():
    """Liste des produits de l'utilisateur"""
    # Récupérer tous les produits de l'utilisateur
    products = ProductDB.query.filter_by(user_id=current_user.id).order_by(ProductDB.name).all()
    
    return render_template("products.html", products=products)


@app.route("/products/add", methods=["GET", "POST"])
@login_required
def add_product():
    """Ajouter un nouveau produit"""
    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")
        document_ids = request.form.getlist("document_ids")
        
        # Validation
        if not name:
            flash("Le nom du produit est obligatoire", "error")
            return render_template(
                "products_add.html",
                old_name=name,
                old_description=description,
                user_documents=DocumentDB.query.filter_by(user_id=current_user.id).all(),
                selected_doc_ids=[int(x) for x in document_ids if x.isdigit()],
            )
        
        # Vérifier que le nom est unique pour cet utilisateur
        existing = ProductDB.query.filter_by(user_id=current_user.id, name=name).first()
        if existing:
            flash("Un produit avec ce nom existe déjà", "error")
            return render_template(
                "products_add.html",
                old_name=name,
                old_description=description,
                user_documents=DocumentDB.query.filter_by(user_id=current_user.id).all(),
                selected_doc_ids=[int(x) for x in document_ids if x.isdigit()],
            )
        
        # Créer le produit
        product = ProductDB(
            user_id=current_user.id,
            name=name,
            description=description,
        )
        db.session.add(product)
        db.session.commit()
        
        # Associer les documents sélectionnés
        if document_ids:
            for doc_id in document_ids:
                if doc_id.isdigit():
                    doc = DocumentDB.query.get(doc_id)
                    if doc and doc.user_id == current_user.id:
                        # Vérifier que la relation n'existe pas déjà
                        existing_rel = ProductDocumentDB.query.filter_by(
                            product_id=product.id, document_id=doc_id
                        ).first()
                        if not existing_rel:
                            relation = ProductDocumentDB(
                                product_id=product.id,
                                document_id=doc_id,
                            )
                            db.session.add(relation)
            db.session.commit()
        
        flash("Produit créé avec succès !", "success")
        return redirect(url_for("my_products"))
    
    # GET - Afficher le formulaire
    user_documents = DocumentDB.query.filter_by(user_id=current_user.id).all()
    return render_template("products_add.html", user_documents=user_documents)


@app.route("/products/<int:product_id>", methods=["GET"])
@login_required
def view_product(product_id):
    """Voir les détails d'un produit"""
    product = ProductDB.query.get_or_404(product_id)
    
    # Vérifier que le produit appartient à l'utilisateur
    if product.user_id != current_user.id:
        abort(403)
    
    return render_template("products_view.html", product=product)


@app.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    """Modifier un produit"""
    product = ProductDB.query.get_or_404(product_id)
    
    # Vérifier que le produit appartient à l'utilisateur
    if product.user_id != current_user.id:
        abort(403)
    
    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")
        document_ids = request.form.getlist("document_ids")
        
        # Validation
        if not name:
            flash("Le nom du produit est obligatoire", "error")
            user_documents = DocumentDB.query.filter_by(user_id=current_user.id).all()
            product_document_ids = [doc.id for doc in product.documents]
            return render_template(
                "products_edit.html",
                product=product,
                user_documents=user_documents,
                product_document_ids=product_document_ids,
            )
        
        # Vérifier que le nom est unique pour cet utilisateur (sauf pour le produit actuel)
        existing = ProductDB.query.filter(
            ProductDB.user_id == current_user.id,
            ProductDB.name == name,
            ProductDB.id != product_id
        ).first()
        if existing:
            flash("Un produit avec ce nom existe déjà", "error")
            user_documents = DocumentDB.query.filter_by(user_id=current_user.id).all()
            product_document_ids = [doc.id for doc in product.documents]
            return render_template(
                "products_edit.html",
                product=product,
                user_documents=user_documents,
                product_document_ids=product_document_ids,
            )
        
        # Mettre à jour le produit
        product.name = name
        product.description = description
        product.updated_at = func.now()
        
        # Mettre à jour les documents associés
        # D'abord, supprimer les anciennes relations qui ne sont plus sélectionnées
        selected_doc_ids = [int(x) for x in document_ids if x.isdigit()]
        
        # Récupérer les IDs des documents actuellement associés
        current_doc_ids = [doc.id for doc in product.documents]
        
        # Supprimer les relations pour les documents non sélectionnés
        for doc_id in current_doc_ids:
            if doc_id not in selected_doc_ids:
                relation = ProductDocumentDB.query.filter_by(
                    product_id=product.id, document_id=doc_id
                ).first()
                if relation:
                    db.session.delete(relation)
        
        # Ajouter les nouvelles relations
        for doc_id in selected_doc_ids:
            if doc_id not in current_doc_ids:
                doc = DocumentDB.query.get(doc_id)
                if doc and doc.user_id == current_user.id:
                    relation = ProductDocumentDB(
                        product_id=product.id,
                        document_id=doc_id,
                    )
                    db.session.add(relation)
        
        db.session.commit()
        
        flash("Produit mis à jour avec succès !", "success")
        return redirect(url_for("my_products"))
    
    # GET - Afficher le formulaire
    user_documents = DocumentDB.query.filter_by(user_id=current_user.id).all()
    product_document_ids = [doc.id for doc in product.documents]
    return render_template(
        "products_edit.html",
        product=product,
        user_documents=user_documents,
        product_document_ids=product_document_ids,
    )


@app.route("/products/<int:product_id>/delete", methods=["GET", "POST"])
@login_required
def delete_product(product_id):
    """Supprimer un produit"""
    product = ProductDB.query.get_or_404(product_id)
    
    # Vérifier que le produit appartient à l'utilisateur
    if product.user_id != current_user.id:
        abort(403)
    
    if request.method == "POST":
        # Supprimer les relations avec les documents
        ProductDocumentDB.query.filter_by(product_id=product.id).delete()
        
        # Supprimer le produit
        db.session.delete(product)
        db.session.commit()
        
        flash("Produit supprimé avec succès !", "success")
        return redirect(url_for("my_products"))
    
    return render_template("products_delete.html", product=product)


@app.route("/products/<int:product_id>/remove_document/<int:document_id>")
@login_required
def remove_document_from_product(product_id, document_id):
    """Retirer un document d'un produit"""
    product = ProductDB.query.get_or_404(product_id)
    
    # Vérifier que le produit appartient à l'utilisateur
    if product.user_id != current_user.id:
        abort(403)
    
    # Vérifier que le document appartient à l'utilisateur
    doc = DocumentDB.query.get_or_404(document_id)
    if doc.user_id != current_user.id:
        abort(403)
    
    # Supprimer la relation
    relation = ProductDocumentDB.query.filter_by(
        product_id=product_id, document_id=document_id
    ).first()
    
    if relation:
        db.session.delete(relation)
        db.session.commit()
        flash("Document retiré du produit avec succès", "success")
    
    return redirect(url_for("edit_product", product_id=product_id))


# ============================================================================
# Product API Routes
# ============================================================================


@app.route("/api/products", methods=["GET"])
@login_required
def api_get_user_products():
    """Récupère la liste des produits de l'utilisateur"""
    products = ProductDB.query.filter_by(user_id=current_user.id).order_by(ProductDB.name).all()
    
    products_list = []
    for product in products:
        products_list.append({
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "document_count": len(product.documents),
            "created_at": product.created_at.isoformat() if product.created_at else None,
        })
    
    return jsonify({"success": True, "products": products_list})


@app.route("/api/products/<int:product_id>/documents", methods=["GET"])
@login_required
def api_get_product_documents(product_id):
    """Récupère les documents associés à un produit"""
    product = ProductDB.query.get_or_404(product_id)
    
    if product.user_id != current_user.id:
        return jsonify({"success": False, "error": "Accès refusé"}), 403
    
    documents_list = []
    for doc in product.documents:
        documents_list.append({
            "id": doc.id,
            "title": doc.title,
            "type": doc.type,
            "validity_date": doc.validity_date.isoformat() if doc.validity_date else None,
            "upload_date": doc.upload_date.isoformat() if doc.upload_date else None,
        })
    
    return jsonify({"success": True, "documents": documents_list})


# ============================================================================
# Dashboard Operations - API Routes
# ============================================================================


@app.route("/api/dashboard/config", methods=["GET"])
@login_required
def api_get_dashboard_config():
    """Récupère la configuration du dashboard pour l'utilisateur"""
    config_name = request.args.get("config_name", "default")
    config = get_user_dashboard_config(current_user.id, config_name)
    return jsonify(config)


@app.route("/api/dashboard/config", methods=["POST"])
@login_required
def api_save_dashboard_config():
    """Sauvegarde la configuration du dashboard"""
    data = request.get_json()

    if (
        not data
        or "config_name" not in data
        or "layout" not in data
        or "widgets" not in data
    ):
        return jsonify({"error": "Missing required fields"}), 400

    config_name = data["config_name"]
    config = {"layout": data["layout"], "widgets": data["widgets"]}

    success = save_user_dashboard_config(current_user.id, config_name, config)

    if success:
        return jsonify({"message": "Configuration saved", "config_name": config_name})
    else:
        return jsonify({"error": "Failed to save configuration"}), 500


@app.route("/api/dashboard/configs", methods=["GET"])
@login_required
def api_get_dashboard_configs():
    """Récupère toutes les configurations de dashboard de l'utilisateur"""
    configs = get_user_dashboard_configs(current_user.id)
    return jsonify({"configs": configs})


@app.route("/api/dashboard/config/<config_name>", methods=["DELETE"])
@login_required
def api_delete_dashboard_config(config_name):
    """Supprime une configuration de dashboard"""
    if config_name == "default":
        return jsonify({"error": "Cannot delete default configuration"}), 400

    success = delete_user_dashboard_config(current_user.id, config_name)

    if success:
        return jsonify({"message": "Configuration deleted", "config_name": config_name})
    else:
        return jsonify({"error": "Failed to delete configuration"}), 500


@app.route("/api/dashboard/widgets/<widget_id>", methods=["GET"])
@login_required
def api_get_widget_data(widget_id):
    """Récupère les données pour un widget spécifique"""
    # Récupérer les paramètres du widget depuis la config utilisateur
    config = get_user_dashboard_config(current_user.id)
    widget_config = config.get("widgets", {}).get(widget_id, {})
    widget_params = widget_config.get("params", {})

    # Récupérer les données du widget
    data = get_dashboard_widget_data(widget_id, current_user.id, current_user.role)

    # Fusionner avec les paramètres
    return jsonify({"widget_id": widget_id, "params": widget_params, "data": data})


@app.route("/api/dashboard/widgets", methods=["GET"])
@login_required
def api_get_all_widgets_data():
    """Récupère les données pour tous les widgets actifs"""
    config = get_user_dashboard_config(current_user.id)
    active_widgets = {
        wid: info
        for wid, info in config.get("widgets", {}).items()
        if info.get("enabled", False)
    }

    results = {}
    for widget_id in active_widgets:
        results[widget_id] = get_dashboard_widget_data(
            widget_id, current_user.id, current_user.role
        )

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
        if "Authorization" in request.headers:
            auth_header = request.headers["Authorization"]
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        if not token:
            return jsonify({"error": "Token is missing!"}), 401

        try:
            # Décoder et vérifier le token
            data = jwt.decode(token, app.secret_key, algorithms=["HS256"])
            # Stocker les données utilisateur dans request pour les routes
            request.user_data = data
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired!"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token is invalid!"}), 401

        return f(*args, **kwargs)

    return decorated


def get_jwt_user():
    """Récupère les données de l'utilisateur depuis le token JWT"""
    if hasattr(request, "user_data"):
        return request.user_data
    return None


def create_jwt_token(user):
    """Crée un token JWT pour un utilisateur"""
    token = jwt.encode(
        {
            "user_id": user.id,
            "username": user.username,
            "role": user.role,
            "exp": datetime.now(timezone.utc) + timedelta(hours=24),  # Valide pour 24h
        },
        app.secret_key,
        algorithm="HS256",
    )
    return token


# ============================================================================
# Routes API REST
# ============================================================================


@app.route("/api/login", methods=["POST"])
def api_login():
    """Authentification via API - retourne un token JWT"""
    data = request.get_json()

    if not data or "username" not in data or "password" not in data:
        return jsonify({"error": "Username and password are required"}), 400

    username = data["username"]
    password = data["password"]

    user_db = UserDB.query.filter_by(username=username).first()

    if not user_db or not check_password_hash(user_db.password, password):
        return jsonify({"error": "Invalid username or password"}), 401

    # Créer l'objet User pour Flask-Login (optionnel, pour compatibilité)
    user_obj = User(
        id=user_db.id,
        username=user_db.username,
        password_hash=user_db.password,
        role=user_db.role,
    )

    # Créer le token JWT
    token = create_jwt_token(user_obj)

    return jsonify(
        {
            "token": token,
            "user": {
                "id": user_obj.id,
                "username": user_obj.username,
                "role": user_obj.role,
            },
        }
    )


@app.route("/api/logout", methods=["POST"])
@jwt_required
def api_logout():
    """Déconnexion via API (invalide le token côté client)"""
    # Avec JWT, la déconnexion est gérée côté client
    # On pourrait ajouter le token à une blacklist, mais ce n'est pas implémenté ici
    return jsonify(
        {"message": "Successfully logged out. Please clear your token client-side."}
    )


@app.route("/api/documents", methods=["GET"])
@jwt_required
def api_get_documents():
    """Récupère la liste des documents (API)"""
    user_data = get_jwt_user()
    user_id = user_data["user_id"]
    user_role = user_data["role"]

    # Filtres depuis les query params
    author = request.args.get("author")
    upload_from = request.args.get("upload_from")
    upload_to = request.args.get("upload_to")
    validity_from = request.args.get("validity_from")
    validity_to = request.args.get("validity_to")
    product_id = request.args.get("product_id")

    # Construire la requête SQLAlchemy
    if user_role == "admin":
        query = DocumentDB.query.join(UserDB, DocumentDB.user_id == UserDB.id)
    else:
        query = DocumentDB.query.join(UserDB, DocumentDB.user_id == UserDB.id).filter(
            DocumentDB.user_id == user_id
        )
    
    # Filtrer par produit si un product_id est spécifié
    if product_id and product_id.isdigit():
        # Filtrer par produit si un product_id est spécifié
        if product_id and product_id.isdigit():
            # Vérifier que le produit appartient à l'utilisateur (ou que l'utilisateur est admin)
            product = ProductDB.query.get(int(product_id))
            if product:
                if user_role == "admin" or product.user_id == user_id:
                    # Joindre avec la table product_document et filtrer
                    query = query.join(ProductDocumentDB, DocumentDB.id == ProductDocumentDB.document_id)
                    query = query.filter(ProductDocumentDB.product_id == int(product_id))
                    # Distinct pour éviter les doublons si un document est dans plusieurs produits
                    query = query.distinct()
                else:
                    # Le produit n'appartient pas à cet utilisateur, retourner une liste vide
                    query = query.filter(False)
            else:
                query = query.filter(False)

    if author:
        query = query.filter(UserDB.username.ilike(f"%{author}%"))

    if upload_from:
        query = query.filter(func.date(DocumentDB.upload_date) >= upload_from)

    if upload_to:
        query = query.filter(func.date(DocumentDB.upload_date) <= upload_to)

    if validity_from:
        query = query.filter(DocumentDB.validity_date >= validity_from)

    if validity_to:
        query = query.filter(DocumentDB.validity_date <= validity_to)

    query = query.order_by(DocumentDB.upload_date.desc())

    documents = query.all()

    # Convertir en JSON
    docs_list = []
    for doc in documents:
        # Parse attributes
        attrs = {}
        if doc.attributes:
            try:
                attrs = json.loads(doc.attributes)
            except:
                attrs = {}

        docs_list.append(
            {
                "id": doc.id,
                "title": doc.title,
                "content": doc.content,
                "upload_date": doc.upload_date.isoformat() if doc.upload_date else None,
                "validity_date": str(doc.validity_date) if doc.validity_date else None,
                "file_path": doc.file_path,
                "file_url": (
                    url_for("uploaded_file", filename=doc.file_path, _external=True)
                    if doc.file_path
                    else None
                ),
                "author": doc.owner.username,
                "type": doc.type,
                "attributes": attrs,
            }
        )

    return jsonify({"documents": docs_list, "count": len(docs_list)})


@app.route("/api/documents", methods=["POST"])
@jwt_required
def api_create_document():
    """Crée un nouveau document via API"""
    user_data = get_jwt_user()
    user_id = user_data["user_id"]

    data = request.get_json()

    if not data or "title" not in data:
        return jsonify({"error": "Title is required"}), 400

    title = data.get("title", "").strip()
    content = data.get("content", "")
    validity_date = data.get("validity_date")
    file_base64 = data.get("file")
    doc_type = data.get("doc_type", "")

    # Assurer que le dossier d'upload existe
    ensure_upload_folder()

    # Gestion du fichier PDF (base64)
    file_path = None
    if file_base64:
        try:
            # Décoder le base64
            file_data = base64.b64decode(file_base64)

            # Vérifier que c'est un PDF (magic number)
            if not file_data.startswith(b"%PDF"):
                return jsonify({"error": "File must be a valid PDF"}), 400

            # Générer un nom de fichier
            filename = f"doc_{datetime.now().strftime('%Y%m%d%H%M%S')}_{user_id}.pdf"
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

            # Sauvegarder le fichier
            with open(file_path, "wb") as f:
                f.write(file_data)
        except Exception as e:
            return jsonify({"error": f"Error saving file: {str(e)}"}), 500

    # Validation
    if not title:
        return jsonify({"error": "Title is required"}), 400

    try:
        db_file_path = os.path.basename(file_path) if file_path else None

        # Récupérer les attributs spécifiques au type
        attributes = {}
        if doc_type:
            doc_type_config = get_document_type(doc_type)
            if doc_type_config:
                for attr_name, attr_config in doc_type_config.get(
                    "attributes", {}
                ).items():
                    attr_value = data.get(attr_name, "").strip()
                    attributes[attr_name] = attr_value

        # Convert validity_date string to date object if needed
        if validity_date and isinstance(validity_date, str):
            try:
                validity_date = datetime.strptime(validity_date, "%Y-%m-%d").date()
            except:
                validity_date = None

        # Create document using SQLAlchemy
        new_doc = DocumentDB(
            title=title,
            content=content,
            user_id=user_id,
            validity_date=validity_date,
            file_path=db_file_path,
            type=doc_type,
            attributes=json.dumps(attributes),
        )
        db.session.add(new_doc)
        db.session.commit()
        doc_id = new_doc.id

        return (
            jsonify(
                {
                    "message": "Document created successfully",
                    "document_id": doc_id,
                    "file_path": db_file_path,
                }
            ),
            201,
        )
    except Exception as e:
        # Nettoyer le fichier si la DB échoue
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({"error": str(e)}), 500


@app.route("/api/documents/<int:doc_id>", methods=["DELETE"])
@jwt_required
def api_delete_document(doc_id):
    """Supprime un document via API"""
    user_data = get_jwt_user()
    user_id = user_data["user_id"]
    user_role = user_data["role"]

    doc = db.session.get(DocumentDB, doc_id)

    if not doc:
        return jsonify({"error": "Document not found"}), 404

    # Vérifier les permissions
    if doc.user_id != user_id and user_role != "admin":
        return (
            jsonify({"error": "You do not have permission to delete this document"}),
            403,
        )

    try:
        # Supprimer le fichier physique
        if doc.file_path:
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], doc.file_path)
            if os.path.exists(file_path):
                os.remove(file_path)

        # Supprimer de la base
        db.session.delete(doc)
        db.session.commit()

        return jsonify({"message": "Document deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route("/api/users", methods=["GET"])
@jwt_required
def api_get_users():
    """Récupère la liste des utilisateurs (admin uniquement)"""
    user_data = get_jwt_user()

    # Seuls les admins peuvent accéder à cette route
    if user_data["role"] != "admin":
        return jsonify({"error": "Admin access required"}), 403

    users = UserDB.query.order_by(UserDB.created_at.desc()).all()

    users_list = []
    for user in users:
        users_list.append(
            {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
        )

    return jsonify({"users": users_list, "count": len(users_list)})


@app.route("/api/users", methods=["POST"])
@jwt_required
def api_create_user():
    """Crée un nouvel utilisateur via API (admin uniquement)"""
    user_data = get_jwt_user()

    # Seuls les admins peuvent créer des utilisateurs
    if user_data["role"] != "admin":
        return jsonify({"error": "Admin access required"}), 403

    data = request.get_json()

    if not data or "username" not in data or "password" not in data:
        return jsonify({"error": "Username and password are required"}), 400

    username = data["username"].strip()
    password = data["password"]
    role = data.get("role", "user")

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    try:
        # Check if user already exists
        existing_user = UserDB.query.filter_by(username=username).first()
        if existing_user:
            return jsonify({"error": "Username already exists"}), 400

        password_hash = generate_password_hash(password)
        new_user = UserDB(username=username, password=password_hash, role=role)
        db.session.add(new_user)
        db.session.commit()
        user_id = new_user.id

        return (
            jsonify(
                {
                    "message": "User created successfully",
                    "user_id": user_id,
                    "username": username,
                    "role": role,
                }
            ),
            201,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
@jwt_required
def api_delete_user(user_id):
    """Supprime un utilisateur via API (admin uniquement)"""
    user_data = get_jwt_user()

    # Seuls les admins peuvent supprimer des utilisateurs
    if user_data["role"] != "admin":
        return jsonify({"error": "Admin access required"}), 403

    # On ne peut pas se supprimer soi-même
    if user_data["user_id"] == user_id:
        return jsonify({"error": "Cannot delete your own account"}), 400

    user = db.session.get(UserDB, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        # Supprimer les documents de l'utilisateur
        docs = DocumentDB.query.filter_by(user_id=user_id).all()

        for doc in docs:
            if doc.file_path:
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], doc.file_path)
                if os.path.exists(file_path):
                    os.remove(file_path)

        DocumentDB.query.filter_by(user_id=user_id).delete()
        db.session.delete(user)
        db.session.commit()

        return jsonify({"message": "User and their documents deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route("/api/uploads/<filename>")
@jwt_required
def api_uploaded_file(filename):
    """Route pour télécharger un fichier via API"""
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# ============================================================================
# Initialisation
# ============================================================================
if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
