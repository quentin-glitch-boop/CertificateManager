#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script d'initialisation de la base de données avec les certificats du répertoire certificats_init_db/

Ce script:
1. Initialise la base de données SQLite avec les tables nécessaires
2. Copie les fichiers PDF du répertoire certificats_init_db/ vers static/uploads/
3. Ajoute des entrées dans la table documents avec des attributs réalistes

Utilisation:
    python init_db_with_certificates.py              # Ajoute les certificats sans effacer les existants
    python init_db_with_certificates.py --clean     # Efface d'abord les données existantes
"""

import os
import sys
import shutil
import json
from datetime import datetime, date, timedelta

# Chemin du répertoire courant (où se trouve ce script)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Configuration
CERTIFICATS_INIT_DIR = os.path.join(SCRIPT_DIR, 'certificats_init_db')
UPLOAD_FOLDER = os.path.join(SCRIPT_DIR, 'static', 'uploads')
DATABASE = os.path.join(SCRIPT_DIR, 'documents.db')


def get_db():
    """Crée une connexion à la base de données SQLite"""
    import sqlite3
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialise la base de données avec les tables nécessaires"""
    from werkzeug.security import generate_password_hash
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Crée la table users
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
    
    # Ajouter les colonnes manquantes (migrations)
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
    
    # Créer un utilisateur admin par défaut si la table est vide
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        admin_password = generate_password_hash('admin123')
        cursor.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', 
                      ('admin', admin_password, 'admin'))
    
    conn.commit()
    conn.close()
    print("[OK] Base de donnees initialisee")


def extract_info_from_filename(filename):
    """
    Extrait les informations du nom de fichier pour remplir les attributs.
    Retourne un dictionnaire avec les attributs du certificat.
    """
    # Supprimer l'extension
    name_without_ext = os.path.splitext(filename)[0]
    
    # Liste des sociétés certificatrices connues (par ordre de priorité)
    certificateurs = [
        'EXCiPACT', 'IVDR',
        'ISO 27001', 'ISO 22000', 'ISO 14001', 'ISO 45001',
        'ISO 13485', 'ISO 9001', 'ISO'
    ]
    
    # Date de péremption par défaut : 2 ans à partir d'aujourd'hui
    date_peremption = (date.today() + timedelta(days=365 * 2)).strftime('%Y-%m-%d')
    
    # Valeurs par défaut
    societe_certifiee = name_without_ext
    societe_certificatrice = "Organisme de Certification"
    
    # Détecter le type de certificat
    for cert in certificateurs:
        if cert in name_without_ext:
            societe_certificatrice = cert
            # Extraire la société (tout avant le certificat)
            idx = name_without_ext.find(cert)
            societe_certifiee = name_without_ext[:idx].strip()
            break
    
    # Nettoyer le nom de la société : remplacer tirets et underscores par des espaces
    societe_certifiee = societe_certifiee.replace('-', ' ').replace('_', ' ').strip()
    
    # Nettoyer la société certificatrice
    societe_certificatrice = societe_certificatrice.replace('-', ' ').replace('_', ' ').strip()
    
    # Adresse fictive basée sur le premier mot du nom de la société
    adresses = {
        'Amcor': '10 rue de l Industrie, Besancon, France',
        'Ashland': '25 avenue de la Chimie, Paris, France',
        'Biomerieux': '30 rue de la Science, Lyon, France',
        'Corning': '15 boulevard des Technologies, Avon, France',
        'Lonza': '5 rue de la Biotech, Colmar, France',
        'Merck': '10 allee des Laboratoires, Molsheim, France',
        'Perlen': '8 rue de l Innovation, Suisse',
        'Thermofisher': '12 rue des Sciences, Illkirch, France',
        'Nalg': '12 rue des Sciences, Illkirch, France',
    }
    
    # Extraire le premier mot significatif (ignorer les articles)
    first_word = societe_certifiee.split()[0] if societe_certifiee else ''
    adresse = adresses.get(first_word, 'Adresse non specifiee')
    
    return {
        'nom_societe_certifiee': societe_certifiee,
        'societe_certificatrice': societe_certificatrice,
        'adresse': adresse,
        'date_peremption': date_peremption,
        'url_telechargement': ''
    }


def copy_and_insert_certificates():
    """
    Copie les fichiers PDF du répertoire certificats_init_db/ vers static/uploads/
    et les ajoute à la base de données.
    """
    # Vérifier que le répertoire source existe
    if not os.path.exists(CERTIFICATS_INIT_DIR):
        print(f"⚠ Répertoire {CERTIFICATS_INIT_DIR} non trouvé")
        return
    
    # S'assurer que le dossier de destination existe
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # Lister les fichiers PDF dans le répertoire source
    pdf_files = [f for f in os.listdir(CERTIFICATS_INIT_DIR) 
                 if f.lower().endswith('.pdf') or f.lower().endswith('.png')]
    
    if not pdf_files:
        print("⚠ Aucun fichier PDF trouvé dans certificats_init_db/")
        return
    
    # Récupérer l'ID de l'utilisateur admin (ou créer un utilisateur si nécessaire)
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id FROM users WHERE username = ?', ('admin',))
    user = cursor.fetchone()
    
    if not user:
        # Créer l'utilisateur admin s'il n'existe pas
        from werkzeug.security import generate_password_hash
        admin_password = generate_password_hash('admin123')
        cursor.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', 
                      ('admin', admin_password, 'admin'))
        user_id = cursor.lastrowid
        conn.commit()
    else:
        user_id = user['id']
    
    print(f"\n-> Importation de {len(pdf_files)} certificats...")
    
    # Insérer chaque certificat
    for filename in pdf_files:
        # Copier le fichier vers le dossier uploads
        src_path = os.path.join(CERTIFICATS_INIT_DIR, filename)
        dst_filename = filename  # Garder le nom original
        dst_path = os.path.join(UPLOAD_FOLDER, dst_filename)
        
        # Copier le fichier (écraser s'il existe déjà)
        shutil.copy2(src_path, dst_path)
        
        # Extraire les attributs du certificat
        attributes = extract_info_from_filename(filename)
        
        # Déterminer le titre (sans extension)
        title = os.path.splitext(filename)[0]
        
        # Déterminer le type de document
        doc_type = 'certificat'
        
        # Date de validité : extraire de l'année dans le nom si présente
        # Sinon utiliser la date de péremption des attributs
        validity_date = attributes.get('date_peremption')
        
        # Insérer dans la base de données
        cursor.execute('''
            INSERT INTO documents (title, content, user_id, validity_date, file_path, type, attributes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            title,
            f"Certificat pour {attributes.get('nom_societe_certifiee', '')}",
            user_id,
            validity_date,
            dst_filename,
            doc_type,
            json.dumps(attributes)
        ))
        
        print(f"  [OK] {filename}")
    
    conn.commit()
    conn.close()
    print(f"\n[OK] {len(pdf_files)} certificats importes avec succes")


def clear_existing_data():
    """
    Efface les données existantes de la base et les fichiers uploadés.
    À utiliser avec précaution !
    """
    # Supprimer tous les fichiers du dossier uploads
    if os.path.exists(UPLOAD_FOLDER):
        for filename in os.listdir(UPLOAD_FOLDER):
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(f"[WARNING] Erreur lors de la suppression de {file_path}: {e}")
    
    # Supprimer les données de la base (mais garder les tables)
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM documents')
    cursor.execute("DELETE FROM users WHERE username != 'admin'")  # Garder admin
    
    conn.commit()
    conn.close()
    print("[OK] Donnees existantes effacees")


def main():
    """Fonction principale"""
    # Vérifier l'argument --clean
    clean_first = '--clean' in sys.argv
    
    print("=" * 60)
    print("Initialisation de la base de donnees avec les certificats")
    print("=" * 60)
    
    # Initialiser la base de données
    init_db()
    
    # Option : effacer les données existantes si --clean est passé
    if clean_first:
        print("\n-> Nettoyage des donnees existantes...")
        clear_existing_data()
    
    # Importer les certificats
    copy_and_insert_certificates()
    
    print("\n" + "=" * 60)
    print("Initialisation terminee avec succes !")
    print("=" * 60)
    print("\nPour vous connecter:")
    print("  Utilisateur: admin")
    print("  Mot de passe: admin123")
    print("\nLes certificats sont maintenant disponibles dans l'application.")


if __name__ == '__main__':
    main()
