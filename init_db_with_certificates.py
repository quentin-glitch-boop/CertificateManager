#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script d'initialisation de la base de données avec des certificats de test.

Ce script:
1. Initialise la base de données PostgreSQL avec des tables nécessaires
2. Copie les fichiers PDF du répertoire certificats_init_db/ vers static/uploads/
3. Ajoute des entrées dans la table documents avec des attributs réalistes

Utilisation:
    python init_db_with_certificates.py              # Ajoute les certificats de base sans effacer les existants
    python init_db_with_certificates.py --clean     # Efface d'abord les données existantes
    python init_db_with_certificates.py --massive   # Génère ~1000 certificats avec historique
    python init_db_with_certificates.py --clean --massive  # Nettoie puis génère ~1000 certificats

Mode massif (--massive):
    - ~1000 certificats générés
    - Dates s'étalant sur 10 ans
    - 80% de certificats périmés
    - 100 sites industriels fictifs dans toute l'Europe
    - 4 types de normes (ISO 9001:2015, ISO 13485:2016, ISO 22000:2018, EXCiPACT GMP)
    - 10 produits pharmaceutiques
    - Chaque site/norme a 2-4 versions de certificats (historique)
    - Environ 30% des certificats sont associés à des produits
"""

import os
import sys
import shutil
import json
import random
from datetime import datetime, date, timedelta

# Chemin du répertoire courant (où se trouve ce script)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Configuration
CERTIFICATS_INIT_DIR = os.path.join(SCRIPT_DIR, "certificats_init_db")
UPLOAD_FOLDER = os.path.join(SCRIPT_DIR, "static", "uploads")

# Données pour la génération massive
INDUSTRIAL_SITES = [
    # France
    {
        "name": "Sanofi Paris",
        "address": "174 Avenue de France, 75013 Paris, France",
        "country": "France",
    },
    {
        "name": "Sanofi Lyon",
        "address": "24 Avenue des Terroirs de l'Esterel, 69800 Saint-Priest, France",
        "country": "France",
    },
    {
        "name": "Servier Suresnes",
        "address": "50 Rue Carnot, 92284 Suresnes, France",
        "country": "France",
    },
    {
        "name": "Servier Gidy",
        "address": "1 Rue des Moissons, 28530 Gidy, France",
        "country": "France",
    },
    {
        "name": "Pierre Fabre Castres",
        "address": "Avenue du Granat, 81100 Castres, France",
        "country": "France",
    },
    {
        "name": "Pierre Fabre Paris",
        "address": "45 Place Abel Gance, 92100 Boulogne-Billancourt, France",
        "country": "France",
    },
    {
        "name": "Boehringer Ingelheim Lyon",
        "address": "26 Avenue Tony Garnier, 69007 Lyon, France",
        "country": "France",
    },
    {
        "name": "Boehringer Ingelheim Reims",
        "address": "100-104 Rue de Jargeau, 51350 Cormontreuil, France",
        "country": "France",
    },
    {
        "name": "Merck Molsheim",
        "address": "2 Rue du President Roosevelt, 67120 Molsheim, France",
        "country": "France",
    },
    {
        "name": "Merck Saint-Louis",
        "address": "1 Rue de Mulhouse, 68300 Saint-Louis, France",
        "country": "France",
    },
    # Allemagne
    {
        "name": "Bayer Leverkusen",
        "address": "Kaiser-Wilhelm-Allee, 51373 Leverkusen, Germany",
        "country": "Germany",
    },
    {
        "name": "Bayer Berlin",
        "address": "Muellenhoffstrasse 1, 13405 Berlin, Germany",
        "country": "Germany",
    },
    {
        "name": "BASF Ludwigshafen",
        "address": "Carl-Bosch-Strasse 38, 67056 Ludwigshafen, Germany",
        "country": "Germany",
    },
    {
        "name": "BASF Schwarzheide",
        "address": "BASF Strasse 1, 01989 Schwarzheide, Germany",
        "country": "Germany",
    },
    {
        "name": "Merck Darmstadt",
        "address": "Frankfurter Strasse 250, 64293 Darmstadt, Germany",
        "country": "Germany",
    },
    {
        "name": "Merck Gernsheim",
        "address": "Industriestrasse 25, 55411 Bingen am Rhein, Germany",
        "country": "Germany",
    },
    {
        "name": "Boehringer Ingelheim Ingelheim",
        "address": "Binger Strasse 173, 55216 Ingelheim am Rhein, Germany",
        "country": "Germany",
    },
    {
        "name": "Boehringer Ingelheim Biberach",
        "address": "Birkendorf 30, 88400 Biberach an der Riss, Germany",
        "country": "Germany",
    },
    {
        "name": "Fresenius Kabi Bad Homburg",
        "address": "Else-Kroener-Strasse 1, 61352 Bad Homburg, Germany",
        "country": "Germany",
    },
    {
        "name": "Fresenius Kabi Graz",
        "address": "Hafnerstrasse 36, 8042 Graz, Austria",
        "country": "Austria",
    },
    # Belgique
    {
        "name": "UCB Brussels",
        "address": "Allée de la Recherche 60, 1070 Anderlecht, Belgium",
        "country": "Belgium",
    },
    {
        "name": "UCB Bulle",
        "address": "Chemin du Foriest, 1700 Fribourg, Switzerland",
        "country": "Switzerland",
    },
    {
        "name": "Janssen Beerse",
        "address": "Turnhoutseweg 30, 2340 Beerse, Belgium",
        "country": "Belgium",
    },
    {
        "name": "Janssen Geel",
        "address": "Janssen Pharmaceutica NV, 2440 Geel, Belgium",
        "country": "Belgium",
    },
    {
        "name": "GlaxoSmithKline Wavre",
        "address": "Rue de l'Institut 89, 1300 Wavre, Belgium",
        "country": "Belgium",
    },
    {
        "name": "GlaxoSmithKline Genval",
        "address": "Avenue Fleming 20, 1300 Wavre, Belgium",
        "country": "Belgium",
    },
    {
        "name": "Pfizer Puurs",
        "address": "Bourgoyen 33, 2870 Puurs, Belgium",
        "country": "Belgium",
    },
    {
        "name": "Pfizer Zaventem",
        "address": "Hoge Wei 34, 1930 Zaventem, Belgium",
        "country": "Belgium",
    },
    {
        "name": "Novartis Basel",
        "address": "Lichtstrasse 35, 4056 Basel, Switzerland",
        "country": "Switzerland",
    },
    {
        "name": "Novartis Huningue",
        "address": "2 Rue de la Haye, 68330 Huningue, France",
        "country": "France",
    },
    # Suisse
    {
        "name": "Roche Basel",
        "address": "Grenchenstrasse 41, 4070 Basel, Switzerland",
        "country": "Switzerland",
    },
    {
        "name": "Roche Kaiseraugst",
        "address": "Industrieareal F.Hoffmann-La Roche, 6343 Kaiseraugst, Switzerland",
        "country": "Switzerland",
    },
    {
        "name": "Lonza Visp",
        "address": "Muhlematte 1, 3930 Visp, Switzerland",
        "country": "Switzerland",
    },
    {
        "name": "Lonza Porriño",
        "address": "Rua da Pateira 44, 36400 Porriño, Spain",
        "country": "Spain",
    },
    {
        "name": "Lonza Basel",
        "address": "Lonza AG, Muenchwilen, 3401 Burgdorf, Switzerland",
        "country": "Switzerland",
    },
    {
        "name": "Novartis Stein",
        "address": "Klybeckstrasse 141, 4057 Basel, Switzerland",
        "country": "Switzerland",
    },
    {
        "name": "Actelion Allschwil",
        "address": "Gewerbestrasse 16, 4123 Allschwil, Switzerland",
        "country": "Switzerland",
    },
    {
        "name": "Idorsia Allschwil",
        "address": "Hegenheimermattweg 91, 4123 Allschwil, Switzerland",
        "country": "Switzerland",
    },
    {
        "name": "Debiopharm Lausanne",
        "address": "Route de la Corniche 4, 1066 Epalinges, Switzerland",
        "country": "Switzerland",
    },
    {
        "name": "Debiopharm Martigny",
        "address": "Avenue de la Gare 4, 1920 Martigny, Switzerland",
        "country": "Switzerland",
    },
    # Espagne
    {
        "name": "Almirall Barcelona",
        "address": "Ronda General Mitre 151, 08022 Barcelona, Spain",
        "country": "Spain",
    },
    {
        "name": "Almirall Sant Andreu",
        "address": "Carrer de la Selva de Mar 211, 08041 Barcelona, Spain",
        "country": "Spain",
    },
    {
        "name": "Grifols Barcelona",
        "address": "Can Guasch 2-4, 08174 Sant Cugat del Vallès, Spain",
        "country": "Spain",
    },
    {
        "name": "Grifols Parets",
        "address": "Carretera de la Riera de Caldes 12, 08150 Parets del Vallès, Spain",
        "country": "Spain",
    },
    {
        "name": "Esteve Barcelona",
        "address": "Avinguda Diagonal 607, 08014 Barcelona, Spain",
        "country": "Spain",
    },
    {
        "name": "PharmaMar Colmenar Viejo",
        "address": "Poligono Industrial, 28770 Colmenar Viejo, Spain",
        "country": "Spain",
    },
    {
        "name": "PharmaMar Tres Cantos",
        "address": "Calle Jose Echegaray 8, 28760 Tres Cantos, Spain",
        "country": "Spain",
    },
    {
        "name": "Rovi Madrid",
        "address": "Calle Julian Camarillo 35, 28037 Madrid, Spain",
        "country": "Spain",
    },
    # Italie
    {
        "name": "Chiesi Parma",
        "address": "Via Palermitana 1/A, 43122 Parma, Italy",
        "country": "Italy",
    },
    {
        "name": "Chiesi Lainate",
        "address": "Via San Francesco 5, 20020 Lainate, Italy",
        "country": "Italy",
    },
    {
        "name": "Menarini Firenze",
        "address": "Via Sette Santi 3, 50131 Firenze, Italy",
        "country": "Italy",
    },
    {
        "name": "Menarini Pomezia",
        "address": "Via Vito Volterra 60, 00071 Pomezia, Italy",
        "country": "Italy",
    },
    {
        "name": "Bracco Milano",
        "address": "Via Egidio Folli 50, 20134 Milano, Italy",
        "country": "Italy",
    },
    {
        "name": "Bracco Torviscosa",
        "address": "Via E. Fermi 5, 33050 Torviscosa, Italy",
        "country": "Italy",
    },
    {
        "name": "Angelini Roma",
        "address": "Via Pomezia 65, 00148 Roma, Italy",
        "country": "Italy",
    },
    {
        "name": "Angelini Anagni",
        "address": "Via Vecchia Appia 2, 03012 Anagni, Italy",
        "country": "Italy",
    },
    {
        "name": "Dompé L'Aquila",
        "address": "Via Campo di Pile, 67100 L'Aquila, Italy",
        "country": "Italy",
    },
    {
        "name": "Dompé Milan",
        "address": "Via San Martino 12, 20122 Milano, Italy",
        "country": "Italy",
    },
    # Pays-Bas
    {
        "name": "MSD Oss",
        "address": "Waardenburg 59, 5347 KH Oss, Netherlands",
        "country": "Netherlands",
    },
    {
        "name": "MSD Haarlem",
        "address": "De Vliet 15, 2013 AE Haarlem, Netherlands",
        "country": "Netherlands",
    },
    {
        "name": "Janssen Leiden",
        "address": "Archimedesweg 4, 2333 AA Leiden, Netherlands",
        "country": "Netherlands",
    },
    {
        "name": "Janssen Tilburg",
        "address": "Culliganlaan 5, 5042 SB Tilburg, Netherlands",
        "country": "Netherlands",
    },
    {
        "name": "Astellas Leiden",
        "address": "Silviusweg 62, 2333 AA Leiden, Netherlands",
        "country": "Netherlands",
    },
    {
        "name": "Astellas Meppel",
        "address": "Burgemeester van Grunsvenplein 1, 7941 GA Meppel, Netherlands",
        "country": "Netherlands",
    },
    {
        "name": "Teva Utrecht",
        "address": "Sweder van Woerdenweg 100, 3528 BG Utrecht, Netherlands",
        "country": "Netherlands",
    },
    {
        "name": "Teva Duiven",
        "address": "Hoofdstraat 30, 6921 EA Duiven, Netherlands",
        "country": "Netherlands",
    },
    # Irlande
    {
        "name": "Pfizer Ringaskiddy",
        "address": "Ballymacus Point, Ringaskiddy, Cork, Ireland",
        "country": "Ireland",
    },
    {
        "name": "Pfizer Dublin",
        "address": "Lakeside Drive, Westpark, Shannon, Ireland",
        "country": "Ireland",
    },
    {
        "name": "MSD Dublin",
        "address": "South County Business Park, Leopardstown, Dublin 18, Ireland",
        "country": "Ireland",
    },
    {
        "name": "MSD Carlow",
        "address": "Tempe Hill, Carlton Road, Carlow, Ireland",
        "country": "Ireland",
    },
    {
        "name": "Janssen Cork",
        "address": "Little Island, Cork, Ireland",
        "country": "Ireland",
    },
    {
        "name": "Regeneron Limerick",
        "address": "Westpark, Shannon, Co. Clare, Ireland",
        "country": "Ireland",
    },
    # Royaume-Uni
    {
        "name": "AstraZeneca Cambridge",
        "address": "1 Francis Crick Avenue, Cambridge Biomedical Campus, CB2 0AA Cambridge, UK",
        "country": "United Kingdom",
    },
    {
        "name": "AstraZeneca Macclesfield",
        "address": "Hurdsfield Road, Macclesfield, SK10 2NA, UK",
        "country": "United Kingdom",
    },
    {
        "name": "GSK Ware",
        "address": "Priestley Road, Ware, SG12 0DJ, UK",
        "country": "United Kingdom",
    },
    {
        "name": "GSK London",
        "address": "980 Great West Road, Brentford, TW8 9GS, UK",
        "country": "United Kingdom",
    },
    {
        "name": "Pfizer Sandwich",
        "address": "Ramsgate Road, Sandwich, CT13 9NJ, UK",
        "country": "United Kingdom",
    },
    {
        "name": "Merck Hoddesdon",
        "address": "Stanstead Road, Hoddesdon, EN11 9BU, UK",
        "country": "United Kingdom",
    },
    # Portugal
    {
        "name": "Bial Porto",
        "address": "Av. da Siderurgia Nacional, 4745-457 Coronado, Portugal",
        "country": "Portugal",
    },
    {
        "name": "Bial Trofa",
        "address": "Avenida das Forças Armadas 46, 4745-457 Trofa, Portugal",
        "country": "Portugal",
    },
    {
        "name": "Hovione Loures",
        "address": "Rua da Tapada Grande 2, 2674-517 Loures, Portugal",
        "country": "Portugal",
    },
    {
        "name": "Hovione Lisboa",
        "address": "Rua do Alvito 110, 1100-054 Lisboa, Portugal",
        "country": "Portugal",
    },
    # Pologne
    {
        "name": "Adamed Piotrkow",
        "address": "ul. Przemysłowa 15, 97-300 Piotrków Trybunalski, Poland",
        "country": "Poland",
    },
    {
        "name": "Adamed Pabianice",
        "address": "ul. Kostromska 9, 95-200 Pabianice, Poland",
        "country": "Poland",
    },
    {
        "name": "Polfa Tarchomin",
        "address": "ul. Przemysłowa 2, 03-284 Warszawa, Poland",
        "country": "Poland",
    },
    {
        "name": "Polfa Starogard",
        "address": "ul. 11 Listopada 10, 83-200 Starogard Gdanski, Poland",
        "country": "Poland",
    },
    # République Tchèque
    {
        "name": "Zentiva Prague",
        "address": "U Kabelovny 130, 102 00 Praha 10, Czech Republic",
        "country": "Czech Republic",
    },
    {
        "name": "Zentiva Hlohovec",
        "address": "Nitrianska 100, 920 21 Hlohovec, Slovakia",
        "country": "Slovakia",
    },
    # Hongrie
    {
        "name": "Gedeon Richter Budapest",
        "address": "Gyömrői út 19-21, 1103 Budapest, Hungary",
        "country": "Hungary",
    },
    {
        "name": "EGIS Budapest",
        "address": "Keresztúri út 30-38, 1106 Budapest, Hungary",
        "country": "Hungary",
    },
    # Autriche
    {
        "name": "Octapharma Vienna",
        "address": "Oberlaaer Straße 235, 1100 Wien, Austria",
        "country": "Austria",
    },
    {
        "name": "Sandoz Kundl",
        "address": "Biochemiestrasse 10, 6250 Kundl, Austria",
        "country": "Austria",
    },
    {
        "name": "Sandoz Schaftenau",
        "address": "Biochemiestrasse 10, 6301 Schaftenau, Austria",
        "country": "Austria",
    },
    # Danemark
    {
        "name": "Novo Nordisk Bagsvaerd",
        "address": "Novo Allé, 2880 Bagsvaerd, Denmark",
        "country": "Denmark",
    },
    {
        "name": "Novo Nordisk Kalundborg",
        "address": "Hallas Allé 1, 4400 Kalundborg, Denmark",
        "country": "Denmark",
    },
    {
        "name": "Lundbeck Copenhagen",
        "address": "Ottiliavej 9, 2500 Valby, Denmark",
        "country": "Denmark",
    },
    {
        "name": "LEO Pharma Ballerup",
        "address": "Industriparken 55, 2750 Ballerup, Denmark",
        "country": "Denmark",
    },
    # Suède
    {
        "name": "AstraZeneca Sodertalje",
        "address": "151 85 Södertälje, Sweden",
        "country": "Sweden",
    },
    {
        "name": "AstraZeneca Gothenburg",
        "address": "Pepparedsleden 1, 431 83 Mölndal, Sweden",
        "country": "Sweden",
    },
    {
        "name": "Recipharm Stockholm",
        "address": "Lagervägen 7, 136 40 Handen, Sweden",
        "country": "Sweden",
    },
    # Norvège
    {
        "name": "Nycomed Asker",
        "address": "P.O. Box 263, 1379 Asker, Norway",
        "country": "Norway",
    },
    # Finlande
    {
        "name": "Fimea Helsinki",
        "address": "Mannerheimintie 103B, 00280 Helsinki, Finland",
        "country": "Finland",
    },
    {
        "name": "Orion Pharma Espoo",
        "address": "Orionintie 1, 02200 Espoo, Finland",
        "country": "Finland",
    },
]

# 4 types de normes
NORMES = ["ISO 9001:2015", "ISO 13485:2016", "ISO 22000:2018", "EXCiPACT GMP"]

# 10 produits pharmaceutiques
PRODUCTS_PHARMA = [
    {"name": "Paracétamol 500mg", "description": "Analgésique et antipyrétique"},
    {"name": "Ibuprofène 200mg", "description": "Anti-inflammatoire non stéroïdien"},
    {"name": "Amoxicilline 1g", "description": "Antibiotique à large spectre"},
    {"name": "Oméprazole 20mg", "description": "Inhibiteur de la pompe à protons"},
    {"name": "Atorvastatine 20mg", "description": "Hypolipidémiant (statine)"},
    {"name": "Métformine 500mg", "description": "Antidiabétique oral"},
    {
        "name": "Losartan 50mg",
        "description": "Antagoniste des récepteurs de l'angiotensine II",
    },
    {
        "name": "Lévothyroxine 50μg",
        "description": "Hormone thyroïdienne de substitution",
    },
    {"name": "Sérotraline 50mg", "description": "Antidépresseur (ISRS)"},
    {"name": "Montélukast 10mg", "description": "Antileucotriène pour l'asthme"},
]


def generate_massive_data():
    """Génère des données massives : ~1000 certificats, 100 sites, 4 normes, 10 produits"""
    import sys

    sys.path.insert(0, SCRIPT_DIR)

    from app_sqlalchemy import app, db, UserDB, DocumentDB, ProductDB, ProductDocumentDB
    from werkzeug.security import generate_password_hash

    with app.app_context():
        # Créer un utilisateur admin s'il n'existe pas
        admin = UserDB.query.filter_by(username="admin").first()
        if not admin:
            admin = UserDB(
                username="admin",
                password=generate_password_hash("admin123"),
                role="admin",
            )
            db.session.add(admin)
            db.session.commit()

        # Créer un utilisateur normal s'il n'existe pas
        user = UserDB.query.filter_by(username="user").first()
        if not user:
            user = UserDB(
                username="user", password=generate_password_hash("user123"), role="user"
            )
            db.session.add(user)
            db.session.commit()

        # Créer le dossier uploads s'il n'existe pas
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        # Créer les 10 produits pharmaceutiques pour l'admin
        for product_data in PRODUCTS_PHARMA:
            existing = ProductDB.query.filter_by(name=product_data["name"]).first()
            if not existing:
                product = ProductDB(
                    user_id=admin.id,
                    name=product_data["name"],
                    description=product_data["description"],
                )
                db.session.add(product)
        db.session.commit()

        # Récupérer les produits créés
        products = ProductDB.query.filter_by(user_id=admin.id).all()

        # Générer ~1000 certificats
        # 80% périmés, 20% valides
        # Dates s'étalant sur 10 ans (2020-2030)
        # Environ 100 sites industriels

        today = date.today()

        # Compter les certificats existants pour ne pas dépasser
        existing_docs = DocumentDB.query.count()
        target_count = 1000

        certificats_crees = 0

        # Pour chaque site industriel
        for site in INDUSTRIAL_SITES:
            # Pour chaque norme
            for norme in NORMES:
                # Générer 2-4 certificats par site/norme pour créer de l'historique
                num_certs = random.randint(2, 4)

                # Trier les certificats par date (le plus récent en dernier)
                cert_dates = []
                for i in range(num_certs):
                    # Générer une date aléatoire dans les 10 dernières années
                    days_offset = random.randint(0, 365 * 10)
                    cert_date = today - timedelta(days=days_offset)
                    cert_dates.append(cert_date)

                # Trier par date ascendante (ancien au récent)
                cert_dates.sort()

                # Créer les certificats pour ce site/norme
                for i, cert_date in enumerate(cert_dates):
                    if certificats_crees >= target_count:
                        break

                    # 80% de chance d'être périmé
                    is_expired = random.random() < 0.8

                    # Date de péremption : entre la date de création et aujourd'hui (périmé) ou dans le futur (valide)
                    if is_expired:
                        # Date de péremption dans le passé (déjà expiré)
                        days_to_expiry = random.randint(30, 365 * 10)
                        date_peremption = cert_date + timedelta(days=days_to_expiry)
                        # S'assurer que c'est bien dans le passé
                        if date_peremption > today:
                            date_peremption = today - timedelta(
                                days=random.randint(1, 365 * 5)
                            )
                    else:
                        # Date de péremption dans le futur (encore valide)
                        days_to_expiry = random.randint(30, 365 * 3)  # 3 ans max
                        date_peremption = today + timedelta(days=days_to_expiry)

                    # Formater la date de péremption
                    date_peremption_str = date_peremption.isoformat()

                    # Sélectionner un organisme certificateur aléatoire
                    organismes = [
                        "DNV",
                        "Bureau Veritas",
                        "AFNOR",
                        "Lloyds Register",
                        "TUV",
                        "SGS",
                        "DEKRA",
                        "GMED",
                    ]
                    organisme = random.choice(organismes)

                    # Créer le certificat
                    title = f"{site['name']} - {norme}"
                    if num_certs > 1:
                        title += f" (v{i+1})"

                    content = (
                        f"Certificat {norme} pour {site['name']} - {site['address']}"
                    )

                    attributes = {
                        "organisme_certificateur": organisme,
                        "norme": norme,
                        "entreprise_certifiee": site["name"],
                        "pays": site["country"],
                        "adresse": site["address"],
                        "date_peremption": date_peremption_str,
                    }

                    # Vérifier si ce certificat existe déjà (même site, norme, version)
                    existing = DocumentDB.query.filter_by(
                        title=title, user_id=admin.id
                    ).first()

                    if not existing:
                        doc = DocumentDB(
                            title=title,
                            content=content,
                            user_id=admin.id,
                            file_path=None,  # Pas de fichier pour ces certificats de test
                            type="Certificat",
                            attributes=json.dumps(attributes),
                            upload_date=datetime.combine(
                                cert_date, datetime.min.time()
                            ),
                        )
                        db.session.add(doc)
                        certificats_crees += 1

                        # Associer ce certificat à un produit aléatoire (10-60% de chance)
                        if (
                            random.random() < 0.3
                        ):  # 30% de chance d'être associé à un produit
                            selected_product = random.choice(products)
                            relation = ProductDocumentDB(
                                product_id=selected_product.id,
                                document_id=doc.id,
                            )
                            db.session.add(relation)

            if certificats_crees >= target_count:
                break

        db.session.commit()

        print(f"Génération massive terminée : {certificats_crees} certificats créés")
        print(f"  - {len(INDUSTRIAL_SITES)} sites industriels couverts")
        print(f"  - {len(NORMES)} types de normes")
        print(f"  - {len(PRODUCTS_PHARMA)} produits pharmaceutiques")

        # Statistiques
        all_docs = DocumentDB.query.count()
        # Compter les périmés
        expired_count = 0
        all_docs_list = DocumentDB.query.all()
        for doc in all_docs_list:
            try:
                attrs = json.loads(doc.attributes) if doc.attributes else {}
                if "date_peremption" in attrs:
                    exp_date = datetime.strptime(
                        attrs["date_peremption"], "%Y-%m-%d"
                    ).date()
                    if exp_date < today:
                        expired_count += 1
            except:
                pass

        valid_count = all_docs - expired_count
        print(
            f"  - {expired_count} certificats périmés ({expired_count/all_docs*100:.1f}%)"
        )
        print(
            f"  - {valid_count} certificats valides ({valid_count/all_docs*100:.1f}%)"
        )


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
            admin = UserDB(
                username="admin",
                password=generate_password_hash("admin123"),
                role="admin",
            )
            db.session.add(admin)
            db.session.commit()

        # Créer un utilisateur normal s'il n'existe pas
        user = UserDB.query.filter_by(username="user").first()
        if not user:
            user = UserDB(
                username="user", password=generate_password_hash("user123"), role="user"
            )
            db.session.add(user)
            db.session.commit()

        # Créer le dossier uploads s'il n'existe pas
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        # Créer des produits pour l'admin s'ils n'existent pas
        products_data = [
            {
                "name": "Doliprane",
                "description": "Médicament contre la douleur et la fièvre",
            },
            {"name": "Aspirine", "description": "Anti-douleur et anti-inflammatoire"},
            {
                "name": "Mercurochrome",
                "description": "Antiseptique pour désinfecter les plaies",
            },
        ]

        for product_data in products_data:
            existing = ProductDB.query.filter_by(name=product_data["name"]).first()
            if not existing:
                product = ProductDB(
                    user_id=admin.id,
                    name=product_data["name"],
                    description=product_data["description"],
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
                "title": "Ashland - ISO 22000 - V2",
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
                if "attributes" in doc_data and isinstance(
                    doc_data["attributes"], dict
                ):
                    doc_data_copy = doc_data.copy()
                    doc_data_copy["attributes"] = json.dumps(
                        doc_data["attributes"], ensure_ascii=False
                    )
                else:
                    doc_data_copy = doc_data
                doc = DocumentDB(**doc_data_copy)
                db.session.add(doc)

        db.session.commit()

        # Associer les documents aux produits pour admin
        # Récupérer les documents créés
        amcor_doc = DocumentDB.query.filter_by(
            title="Amcor Besancon - ISO 9001"
        ).first()
        ashland_doc = DocumentDB.query.filter_by(title="Ashland - ISO 22000").first()
        biomerieux_doc = DocumentDB.query.filter_by(
            title="Biomerieux - ISO 13485"
        ).first()
        lonza_bornem_doc = DocumentDB.query.filter_by(
            title="Lonza Bornem - EXCiPACT"
        ).first()

        if product_doliprane and product_aspirine and product_mercurochrome:
            # Associer des documents à Doliprane
            if amcor_doc:
                relation = ProductDocumentDB.query.filter_by(
                    product_id=product_doliprane.id, document_id=amcor_doc.id
                ).first()
                if not relation:
                    db.session.add(
                        ProductDocumentDB(
                            product_id=product_doliprane.id, document_id=amcor_doc.id
                        )
                    )

            # Associer des documents à Aspirine
            if ashland_doc:
                relation = ProductDocumentDB.query.filter_by(
                    product_id=product_aspirine.id, document_id=ashland_doc.id
                ).first()
                if not relation:
                    db.session.add(
                        ProductDocumentDB(
                            product_id=product_aspirine.id, document_id=ashland_doc.id
                        )
                    )

            # Associer des documents à Mercurochrome
            if biomerieux_doc:
                relation = ProductDocumentDB.query.filter_by(
                    product_id=product_mercurochrome.id, document_id=biomerieux_doc.id
                ).first()
                if not relation:
                    db.session.add(
                        ProductDocumentDB(
                            product_id=product_mercurochrome.id,
                            document_id=biomerieux_doc.id,
                        )
                    )

            if lonza_bornem_doc:
                relation = ProductDocumentDB.query.filter_by(
                    product_id=product_mercurochrome.id, document_id=lonza_bornem_doc.id
                ).first()
                if not relation:
                    db.session.add(
                        ProductDocumentDB(
                            product_id=product_mercurochrome.id,
                            document_id=lonza_bornem_doc.id,
                        )
                    )

            db.session.commit()

        print(
            f"Base de données initialisée avec {len(documents_data)} certificats de test"
        )


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
        db.session.query(UserDB).filter(
            UserDB.username.notin_(["admin", "user"])
        ).delete()

        db.session.commit()
        print("Données existantes effacées")


if __name__ == "__main__":
    clean = "--clean" in sys.argv
    massive = "--massive" in sys.argv

    if clean:
        clean_db()

    if massive:
        print("Génération de données massives en cours...")
        generate_massive_data()
    else:
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
        print(
            "\n  - Le champ validity_date a été supprimé (utilisez date_peremption dans attributes)"
        )

    if massive:
        print("\nUtilisation:")
        print("  python init_db_with_certificates.py              # Mode normal")
        print(
            "  python init_db_with_certificates.py --clean     # Nettoyer puis mode normal"
        )
        print(
            "  python init_db_with_certificates.py --massive   # Générer ~1000 certificats"
        )
        print(
            "  python init_db_with_certificates.py --clean --massive  # Nettoyer puis générer ~1000 certificats"
        )
