#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script d'initialisation de la base de données avec des certificats de test.

Ce script:
1. Initialise la base de données PostgreSQL avec des tables nécessaires
2. Copie les fichiers PDF du répertoire certificats_init_db/ vers static/uploads/
3. Ajoute des entrées dans la table documents avec des attributs réalistes

Utilisation:
    python init_db_with_certificates.py              # Ajoute les certificats sans effacer les existants
    python init_db_with_certificates.py --clean     # Efface d'abord les données existantes
"""

import os
import sys
import shutil
from datetime import datetime, date, timedelta

# Chemin du répertoire courant (où se trouve ce script)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Configuration
CERTIFICATS_INIT_DIR = os.path.join(SCRIPT_DIR, "certificats_init_db")
UPLOAD_FOLDER = os.path.join(SCRIPT_DIR, "static", "uploads")


def init_db():
    """Initialise la base de données avec des certificats de test"""
    import sys
    sys.path.insert(0, SCRIPT_DIR)
    
    from app_sqlalchemy import app, db, UserDB, DocumentDB
    from werkzeug.security import generate_password_hash
    
    with app.app_context():
        # Créer les tables
        db.create_all()
        
        # Créer un utilisateur admin s'il n'existe pas
        admin = UserDB.query.filter_by(username='admin').first()
        if not admin:
            admin = UserDB(
                username='admin',
                password=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
        
        # Créer un utilisateur normal s'il n'existe pas
        user = UserDB.query.filter_by(username='user').first()
        if not user:
            user = UserDB(
                username='user',
                password=generate_password_hash('user123'),
                role='user'
            )
            db.session.add(user)
            db.session.commit()
        
        # Créer le dossier uploads s'il n'existe pas
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        # Copier les fichiers PDF vers uploads
        pdf_files = []
        for filename in os.listdir(CERTIFICATS_INIT_DIR):
            if filename.lower().endswith('.pdf'):
                src_path = os.path.join(CERTIFICATS_INIT_DIR, filename)
                dst_path = os.path.join(UPLOAD_FOLDER, filename)
                if not os.path.exists(dst_path):
                    shutil.copy2(src_path, dst_path)
                pdf_files.append(filename)
        
        # Ajouter des documents avec des dates réalistes
        # Certificats valides
        documents_data = [
            {
                'title': 'Amcor Besancon - ISO 9001',
                'content': 'Certificat de qualité ISO 9001 pour le site de Besancon',
                'file_path': 'Amcor Besancon - ISO 9001.pdf',
                'upload_date': datetime(2026, 1, 15),
                'validity_date': datetime(2027, 1, 14).date(),
                'type': 'Certificat',
                'user_id': admin.id,
                'attributes': {
                    'organisme': 'ISO',
                    'norme': '9001',
                    'site': 'Besancon',
                    'domaine': 'Qualité'
                }
            },
            {
                'title': 'Ashland - ISO 22000',
                'content': 'Certificat de sécurité alimentaire ISO 22000',
                'file_path': 'Ashland - ISO 22000.pdf',
                'upload_date': datetime(2026, 2, 20),
                'validity_date': datetime(2027, 2, 19).date(),
                'type': 'Certificat',
                'user_id': admin.id,
                'attributes': {
                    'organisme': 'ISO',
                    'norme': '22000',
                    'site': 'Ashland',
                    'domaine': 'Sécurité alimentaire'
                }
            },
            {
                'title': 'Biomerieux - ISO 13485',
                'content': 'Certificat pour dispositifs médicaux ISO 13485',
                'file_path': 'Biomerieux - ISO 13485.pdf',
                'upload_date': datetime(2026, 3, 10),
                'validity_date': datetime(2027, 3, 9).date(),
                'type': 'Certificat',
                'user_id': admin.id,
                'attributes': {
                    'organisme': 'ISO',
                    'norme': '13485',
                    'site': 'Lyon',
                    'domaine': 'Dispositifs médicaux'
                }
            },
            {
                'title': 'Lonza Bornem - EXCiPACT',
                'content': 'Certification EXCiPACT pour les excipients pharmaceutiques',
                'file_path': 'Lonza Bornem - EXCiPACT.pdf',
                'upload_date': datetime(2026, 4, 1),
                'validity_date': datetime(2027, 3, 31).date(),
                'type': 'Certificat',
                'user_id': admin.id,
                'attributes': {
                    'organisme': 'EXCiPACT',
                    'norme': 'EXCiPACT',
                    'site': 'Bornem',
                    'domaine': 'Excipients'
                }
            },
            {
                'title': 'Merck - ISO 27001',
                'content': 'Certificat de sécurité de l\'information ISO 27001',
                'file_path': 'Merck - Certificate-ISO-9001-EN.pdf',
                'upload_date': datetime(2026, 5, 12),
                'validity_date': datetime(2027, 5, 11).date(),
                'type': 'Certificat',
                'user_id': user.id,
                'attributes': {
                    'organisme': 'ISO',
                    'norme': '27001',
                    'site': 'Merck',
                    'domaine': 'Sécurité de l\'information'
                }
            },
            # Certificats expirés
            {
                'title': 'Lionza Vervier - ISO 9001',
                'content': 'Certificat ISO 9001 expiré',
                'file_path': 'Lionza Vervier  - ISO 9001.pdf',
                'upload_date': datetime(2025, 6, 1),
                'validity_date': datetime(2026, 5, 31).date(),
                'type': 'Certificat',
                'user_id': user.id,
                'attributes': {
                    'organisme': 'ISO',
                    'norme': '9001',
                    'site': 'Vervier',
                    'domaine': 'Qualité'
                }
            },
            {
                'title': 'Lonza Visp - ISO 9001',
                'content': 'Certificat ISO 9001 expiré',
                'file_path': 'Lonza Visp - ISO 9001.pdf',
                'upload_date': datetime(2025, 7, 15),
                'validity_date': datetime(2026, 7, 14).date(),
                'type': 'Certificat',
                'user_id': user.id,
                'attributes': {
                    'organisme': 'ISO',
                    'norme': '9001',
                    'site': 'Visp',
                    'domaine': 'Qualité'
                }
            },
            # Certificat expirant bientôt (dans 15 jours)
            {
                'title': 'Thermofisher - ISO 9001',
                'content': 'Certificat ISO 9001 expirant bientôt',
                'file_path': 'Thermofisher (Nalg Nunc) - ISO 9001.pdf',
                'upload_date': datetime(2026, 6, 1),
                'validity_date': datetime(2026, 8, 10).date(),
                'type': 'Certificat',
                'user_id': admin.id,
                'attributes': {
                    'organisme': 'ISO',
                    'norme': '9001',
                    'site': 'Thermofisher',
                    'domaine': 'Qualité'
                }
            },
        ]
        
        # Ajouter les documents s'ils n'existent pas
        for doc_data in documents_data:
            existing = DocumentDB.query.filter_by(title=doc_data['title']).first()
            if not existing:
                doc = DocumentDB(**doc_data)
                db.session.add(doc)
        
        db.session.commit()
        print(f"Base de données initialisée avec {len(documents_data)} certificats de test")


def clean_db():
    """Efface les données existantes"""
    import sys
    sys.path.insert(0, SCRIPT_DIR)
    
    from app_sqlalchemy import app, db, DocumentDB, UserDB
    
    with app.app_context():
        # Effacer tous les documents
        db.session.query(DocumentDB).delete()
        
        # Effacer tous les utilisateurs (sauf admin et user créés par init_db)
        db.session.query(UserDB).filter(UserDB.username.notin_(['admin', 'user'])).delete()
        
        db.session.commit()
        print("Données existantes effacées")


if __name__ == '__main__':
    clean = '--clean' in sys.argv
    
    if clean:
        clean_db()
    
    init_db()
    
    print("\nInitialisation terminée !")
    print("Utilisateurs créés:")
    print("  - admin / admin123 (rôle: admin)")
    print("  - user / user123 (rôle: user)")
    print(f"\nCertificats ajoutés depuis: {CERTIFICATS_INIT_DIR}")
