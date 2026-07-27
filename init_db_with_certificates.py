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
import json
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

    from app_sqlalchemy import app, db, UserDB, DocumentDB, ProductDB, ProductDocumentDB
    from werkzeug.security import generate_password_hash

    with app.app_context():
        # Créer les tables
        db.create_all()

        # Créer un utilisateur admin s'il n'existe pas
        admin = UserDB.query.filter_by(username="admin").first()
        if not admin:
            admin = UserDB(username="admin", password=generate_password_hash("admin123"), role="admin")
            db.session.add(admin)
            db.session.commit()

        # Créer un utilisateur normal s'il n'existe pas
        user = UserDB.query.filter_by(username="user").first()
        if not user:
            user = UserDB(username="user", password=generate_password_hash("user123"), role="user")
            db.session.add(user)
            db.session.commit()

        # Créer le dossier uploads s'il n'existe pas
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        # Créer des produits pour l'admin s'ils n'existent pas
        products_data = [
            {"name": "Doliprane", "description": "Médicament contre la douleur et la fièvre"},
            {"name": "Aspirine", "description": "Anti-douleur et anti-inflammatoire"},
            {"name": "Mercurochrome", "description": "Antiseptique pour désinfecter les plaies"},
        ]

        for product_data in products_data:
            existing = ProductDB.query.filter_by(name=product_data["name"]).first()
            if not existing:
                product = ProductDB(
                    user_id=admin.id, name=product_data["name"], description=product_data["description"]
                )
                db.session.add(product)
        db.session.commit()

        # Associer certains documents aux produits (après avoir créé les documents)
        product_doliprane = ProductDB.query.filter_by(name="Doliprane").first()
        product_aspirine = ProductDB.query.filter_by(name="Aspirine").first()
        product_mercurochrome = ProductDB.query.filter_by(name="Mercurochrome").first()

        # Copier les fichiers PDF vers uploads
        pdf_files = []
        for filename in os.listdir(CERTIFICATS_INIT_DIR):
            if filename.lower().endswith(".pdf"):
                src_path = os.path.join(CERTIFICATS_INIT_DIR, filename)
                dst_path = os.path.join(UPLOAD_FOLDER, filename)
                if not os.path.exists(dst_path):
                    shutil.copy2(src_path, dst_path)
                pdf_files.append(filename)

        # Ajouter des documents avec des attributs standardisés
        # Certificats valides
        documents_data = [
            {
                "title": "Amcor Besancon - ISO 9001",
                "content": "Certificat de qualité ISO 9001 pour le site de Besancon",
                "file_path": "Amcor Besancon - ISO 9001.pdf",
                "upload_date": datetime(2026, 1, 15),
                "type": "Certificat",
                "user_id": admin.id,
                "attributes": {
                    "organisme_certificateur": "DNV",
                    "norme": "ISO 9001:2015",
                    "entreprise_certifiee": "Amcor Besancon",
                    "pays": "France",
                    "adresse": "123 Rue de Besancon, 25000 Besancon, France",
                    "date_peremption": "2027-01-14",
                    "url_telechargement": "https://example.com/certs/amcor-iso9001.pdf",
                },
            },
            {
                "title": "Ashland - ISO 22000",
                "content": "Certificat de sécurité alimentaire ISO 22000",
                "file_path": "Ashland - ISO 22000.pdf",
                "upload_date": datetime(2026, 2, 20),
                "type": "Certificat",
                "user_id": admin.id,
                "attributes": {
                    "organisme_certificateur": "LLoyds Register",
                    "norme": "ISO 22000:2018",
                    "entreprise_certifiee": "Ashland",
                    "pays": "France",
                    "adresse": "456 Avenue de Paris, 75001 Paris, France",
                    "date_peremption": "2027-02-19",
                    "url_telechargement": "https://www.ashland.com/file_source/Ashland/Documents/FSSC%2022%200000%20Certificate%20_%20Ashland%20Specialties%20France%20SARL%20_190116.pdf",
                },
            },
            {
                "title": "Ashland - ISO 22000",
                "content": "Certificat de sécurité alimentaire ISO 22000",
                "file_path": "Ashland - ISO 22000 - V2.pdf",
                "upload_date": datetime(2026, 2, 20),
                "type": "Certificat",
                "user_id": admin.id,
                "attributes": {
                    "organisme_certificateur": "LLoyds Register",
                    "norme": "ISO 22000:2018",
                    "entreprise_certifiee": "Ashland",
                    "pays": "France",
                    "adresse": "456 Avenue de Paris, 75001 Paris, France",
                    "date_peremption": "2028-02-19",
                    "url_telechargement": "https://www.ashland.com/file_source/Ashland/Documents/FSSC%2022%200000%20Certificate%20_%20Ashland%20Specialties%20France%20SARL%20_190116.pdf",
                },
            },
            {
                "title": "Biomerieux - ISO 13485",
                "content": "Certificat pour dispositifs médicaux ISO 13485",
                "file_path": "Biomerieux - ISO 13485.pdf",
                "upload_date": datetime(2026, 3, 10),
                "type": "Certificat",
                "user_id": admin.id,
                "attributes": {
                    "organisme_certificateur": "GMED",
                    "norme": "ISO 13485:2016",
                    "entreprise_certifiee": "Biomerieux",
                    "pays": "France",
                    "adresse": "789 Boulevard de Lyon, 69000 Lyon, France",
                    "date_peremption": "2027-03-09",
                    "url_telechargement": "https://example.com/certs/biomerieux-iso13485.pdf",
                },
            },
            {
                "title": "Lonza Bornem - EXCiPACT",
                "content": "Certification EXCiPACT pour les excipients pharmaceutiques",
                "file_path": "Lonza Bornem - EXCiPACT.pdf",
                "upload_date": datetime(2026, 4, 1),
                "type": "Certificat",
                "user_id": admin.id,
                "attributes": {
                    "organisme_certificateur": "EXCiPACT",
                    "norme": "EXCiPACT GMP",
                    "entreprise_certifiee": "Lonza Bornem",
                    "pays": "Belgique",
                    "adresse": "12 Rue de Bornem, 4000 Liege, Belgique",
                    "date_peremption": "2027-03-31",
                    "url_telechargement": "https://example.com/certs/lonza-excipact.pdf",
                },
            },
            {
                "title": "Merck - ISO 27001",
                "content": "Certificat de sécurité de l'information ISO 27001",
                "file_path": "Merck - Certificate-ISO-9001-EN.pdf",
                "upload_date": datetime(2026, 5, 12),
                "type": "Certificat",
                "user_id": user.id,
                "attributes": {
                    "organisme_certificateur": "ISO",
                    "norme": "ISO 27001:2022",
                    "entreprise_certifiee": "Merck",
                    "pays": "Allemagne",
                    "adresse": "123 Merck Strasse, 64293 Darmstadt, Allemagne",
                    "date_peremption": "2027-05-11",
                },
            },
            # Certificats expirés
            {
                "title": "Lonza Vervier - ISO 9001",
                "content": "Certificat ISO 9001 expiré",
                "file_path": "Lonza Vervier  - ISO 9001.pdf",
                "upload_date": datetime(2025, 6, 1),
                "type": "Certificat",
                "user_id": user.id,
                "attributes": {
                    "organisme_certificateur": "ISO",
                    "norme": "ISO 9001:2015",
                    "entreprise_certifiee": "Lonza Vervier",
                    "pays": "Belgique",
                    "adresse": "234 Rue de Vervier, 4800 Vervier, Belgique",
                    "date_peremption": "2026-05-31",
                },
            },
            {
                "title": "Lonza Visp - ISO 9001",
                "content": "Certificat ISO 9001 expiré",
                "file_path": "Lonza Visp - ISO 9001.pdf",
                "upload_date": datetime(2025, 7, 15),
                "type": "Certificat",
                "user_id": user.id,
                "attributes": {
                    "organisme_certificateur": "ISO",
                    "norme": "ISO 9001:2015",
                    "entreprise_certifiee": "Lonza Visp",
                    "pays": "Suisse",
                    "adresse": "456 Avenue de Visp, 3930 Visp, Suisse",
                    "date_peremption": "2026-07-14",
                },
            },
            # Certificat expirant bientôt (dans 15 jours)
            {
                "title": "Thermofisher - ISO 9001",
                "content": "Certificat ISO 9001 expirant bientôt",
                "file_path": "Thermofisher (Nalg Nunc) - ISO 9001.pdf",
                "upload_date": datetime(2026, 6, 1),
                "type": "Certificat",
                "user_id": admin.id,
                "attributes": {
                    "organisme_certificateur": "ISO",
                    "norme": "ISO 9001:2015",
                    "entreprise_certifiee": "Thermofisher (Nalg Nunc)",
                    "pays": "France",
                    "adresse": "567 Rue de Thermofisher, 75002 Paris, France",
                    "date_peremption": "2026-08-10",
                },
            },
        ]

        # Ajouter les documents s'ils n'existent pas
        for doc_data in documents_data:
            existing = DocumentDB.query.filter_by(title=doc_data["title"]).first()
            if not existing:
                # Convertir attributes dict en JSON string
                if "attributes" in doc_data and isinstance(doc_data["attributes"], dict):
                    doc_data_copy = doc_data.copy()
                    doc_data_copy["attributes"] = json.dumps(doc_data["attributes"], ensure_ascii=False)
                else:
                    doc_data_copy = doc_data
                doc = DocumentDB(**doc_data_copy)
                db.session.add(doc)

        db.session.commit()

        # Associer les documents aux produits pour admin
        # Récupérer les documents créés
        amcor_doc = DocumentDB.query.filter_by(title="Amcor Besancon - ISO 9001").first()
        ashland_doc = DocumentDB.query.filter_by(title="Ashland - ISO 22000").first()
        biomerieux_doc = DocumentDB.query.filter_by(title="Biomerieux - ISO 13485").first()
        lonza_bornem_doc = DocumentDB.query.filter_by(title="Lonza Bornem - EXCiPACT").first()

        if product_doliprane and product_aspirine and product_mercurochrome:
            # Associer des documents à Doliprane
            if amcor_doc:
                relation = ProductDocumentDB.query.filter_by(
                    product_id=product_doliprane.id, document_id=amcor_doc.id
                ).first()
                if not relation:
                    db.session.add(ProductDocumentDB(product_id=product_doliprane.id, document_id=amcor_doc.id))

            # Associer des documents à Aspirine
            if ashland_doc:
                relation = ProductDocumentDB.query.filter_by(
                    product_id=product_aspirine.id, document_id=ashland_doc.id
                ).first()
                if not relation:
                    db.session.add(ProductDocumentDB(product_id=product_aspirine.id, document_id=ashland_doc.id))

            # Associer des documents à Mercurochrome
            if biomerieux_doc:
                relation = ProductDocumentDB.query.filter_by(
                    product_id=product_mercurochrome.id, document_id=biomerieux_doc.id
                ).first()
                if not relation:
                    db.session.add(
                        ProductDocumentDB(product_id=product_mercurochrome.id, document_id=biomerieux_doc.id)
                    )

            if lonza_bornem_doc:
                relation = ProductDocumentDB.query.filter_by(
                    product_id=product_mercurochrome.id, document_id=lonza_bornem_doc.id
                ).first()
                if not relation:
                    db.session.add(
                        ProductDocumentDB(product_id=product_mercurochrome.id, document_id=lonza_bornem_doc.id)
                    )

            db.session.commit()

        print(f"Base de données initialisée avec {len(documents_data)} certificats de test")


def clean_db():
    """Efface les données existantes"""
    import sys

    sys.path.insert(0, SCRIPT_DIR)

    from app_sqlalchemy import app, db, DocumentDB, UserDB, ProductDB, ProductDocumentDB

    with app.app_context():
        # Créer les tables si elles n'existent pas
        db.create_all()

        # Effacer toutes les relations produit-document
        db.session.query(ProductDocumentDB).delete()

        # Effacer tous les produits
        db.session.query(ProductDB).delete()

        # Effacer tous les documents
        db.session.query(DocumentDB).delete()

        # Effacer tous les utilisateurs (sauf admin et user créés par init_db)
        db.session.query(UserDB).filter(UserDB.username.notin_(["admin", "user"])).delete()

        db.session.commit()
        print("Données existantes effacées")


if __name__ == "__main__":
    clean = "--clean" in sys.argv

    if clean:
        clean_db()

    init_db()

    print("\nInitialisation terminée !")
    print("Utilisateurs créés:")
    print("  - admin / admin123 (rôle: admin)")
    print("  - user / user123 (rôle: user)")
    print(f"\nCertificats ajoutés depuis: {CERTIFICATS_INIT_DIR}")
    print("\nProduits créés pour l'utilisateur admin:")
    print("  - Doliprane")
    print("  - Aspirine")
    print("  - Mercurochrome")
    print("\nCertains certificats ont été associés à ces produits.")
    print("\nNouveautés:")
    print("  - Les certificats utilisent les attributs standardisés:")
    print("    * organisme_certificateur")
    print("    * norme")
    print("    * entreprise_certifiee")
    print("    * pays")
    print("    * adresse")
    print("    * date_peremption")
    print("    * url_telechargement (pour 4 certificats)")
    print("\n  - Le champ validity_date a été supprimé (utilisez date_peremption dans attributes)")
