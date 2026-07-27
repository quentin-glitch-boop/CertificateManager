"""
Module de vérification automatique des certificats via URL.

Ce module permet de :
- Vérifier régulièrement si les certificats ont été mis à jour sur leur URL
- Calculer et comparer les checksums (SHA-256)
- Conserver un historique des vérifications (configurable, max 1 an par défaut)
- Vérifier que les fichiers téléchargés sont des PDF valides
"""

import hashlib
import requests
from datetime import datetime, timedelta
import json
import os
from typing import Tuple, Dict, Any, Optional
from flask import current_app


def is_valid_pdf(content: bytes) -> bool:
    """
    Vérifie que le contenu est un PDF valide.

    Args:
        content: Contenu binaire du fichier

    Returns:
        bool: True si c'est un PDF valide, False sinon
    """
    if not content or len(content) < 8:
        return False

    # Vérifier le magic number PDF (%PDF)
    if not content.startswith(b"%PDF"):
        return False

    # Vérifier la fin du fichier (%%EOF)
    # Note: Certains PDF peuvent ne pas avoir %%EOF, mais c'est un bon indicateur
    if len(content) > 10 and not content[-10:].endswith(b"%%EOF"):
        # Pas critique, mais on vérifie quand même
        pass

    return True


def calculate_checksum(content: bytes) -> str:
    """
    Calcule le checksum SHA-256 d'un contenu.

    Args:
        content: Contenu binaire

    Returns:
        str: Checksum hexadécimal
    """
    return hashlib.sha256(content).hexdigest()


def download_file(url: str, timeout: int = 30) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Télécharge un fichier depuis une URL.

    Args:
        url: URL du fichier à télécharger
        timeout: Timeout en secondes (défaut: 30)

    Returns:
        Tuple: (contenu binaire, erreur) - si erreur, contenu est None
    """
    try:
        response = requests.get(url, timeout=timeout, headers={"User-Agent": "CertiFlow/1.0"}, allow_redirects=True)
        response.raise_for_status()
        return response.content, None
    except requests.exceptions.Timeout:
        return None, "Timeout: Le téléchargement a pris trop de temps"
    except requests.exceptions.TooManyRedirects:
        return None, "Trop de redirections"
    except requests.exceptions.RequestException as e:
        return None, f"Erreur de téléchargement: {str(e)}"
    except Exception as e:
        return None, f"Erreur inattendue: {str(e)}"


def purge_old_history(attrs: Dict[str, Any], max_age_days: int = 365) -> Dict[str, Any]:
    """
    Supprime les entrées d'historique de vérification de plus de max_age_days.

    Args:
        attrs: Dictionnaire des attributs du document
        max_age_days: Âge maximum en jours (défaut: 365)

    Returns:
        Dict: Attributs mis à jour
    """
    if "check_history" not in attrs:
        return attrs

    try:
        cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
        filtered_history = []

        for entry in attrs["check_history"]:
            try:
                entry_date_str = entry.get("date", "")
                # Gérer différents formats de date
                if entry_date_str.endswith("Z"):
                    entry_date_str = entry_date_str.replace("Z", "+00:00")
                entry_date = datetime.fromisoformat(entry_date_str)

                if entry_date >= cutoff_date:
                    filtered_history.append(entry)
            except (ValueError, TypeError):
                # Si la date est invalide, on garde l'entrée
                filtered_history.append(entry)

        attrs["check_history"] = filtered_history
    except Exception:
        # En cas d'erreur, on ne purge pas
        pass

    return attrs


def get_max_history_age_days() -> int:
    """
    Récupère la durée maximale de conservation de l'historique (en jours).

    Returns:
        int: Nombre de jours (défaut: 365)
    """
    try:
        # Essayer de récupérer depuis les variables d'environnement
        return int(os.environ.get("CERTIFICATE_CHECK_HISTORY_DAYS", 365))
    except (ValueError, TypeError):
        return 365


def check_document_for_updates(doc, max_age_days: Optional[int] = None) -> Dict[str, Any]:
    """
    Vérifie si un document a été mis à jour sur son URL.

    Args:
        doc: Objet DocumentDB
        max_age_days: Âge maximum de l'historique en jours (optionnel)

    Returns:
        Dict: Résultat de la vérification
    """
    if max_age_days is None:
        max_age_days = get_max_history_age_days()

    # Récupérer les attributs
    attrs = {}
    if doc.attributes:
        try:
            attrs = json.loads(doc.attributes)
        except (json.JSONDecodeError, TypeError):
            attrs = {}

    url = attrs.get("url_telechargement", "")
    if not url:
        return {"status": "skipped", "reason": "No URL", "document_id": doc.id, "title": doc.title}

    # Télécharger le fichier
    content, error = download_file(url)
    if error:
        return {"status": "error", "error": error, "document_id": doc.id, "title": doc.title, "url": url}

    # Vérifier que c'est un PDF valide
    if not is_valid_pdf(content):
        return {
            "status": "error",
            "error": "Fichier non valide ou n'est pas un PDF",
            "document_id": doc.id,
            "title": doc.title,
            "url": url,
        }

    # Calculer le checksum
    current_checksum = calculate_checksum(content)
    file_size = len(content)
    now = datetime.utcnow().isoformat()

    # Récupérer le dernier checksum
    last_checksum = attrs.get("last_checksum", "")
    last_checked = attrs.get("last_checked", "")

    # Initialiser l'historique si nécessaire
    if "check_history" not in attrs:
        attrs["check_history"] = []

    # Déterminer le statut
    if last_checksum == current_checksum:
        status = "unchanged"
    elif not last_checksum:
        status = "new"
    else:
        status = "changed"

    # Ajouter à l'historique
    attrs["check_history"].append({"date": now, "checksum": current_checksum, "status": status, "file_size": file_size})

    # Mettre à jour les champs principaux
    attrs["last_checksum"] = current_checksum
    attrs["last_checked"] = now

    # Purger l'historique ancien
    attrs = purge_old_history(attrs, max_age_days)

    # Retourner le résultat (sans sauvegarder, c'est fait par l'appelant)
    return {
        "status": status,
        "document_id": doc.id,
        "title": doc.title,
        "url": url,
        "checksum": current_checksum,
        "file_size": file_size,
        "updated_attrs": attrs,
    }


def check_all_documents():
    """
    Vérifie tous les documents avec une URL valide.

    Returns:
        Dict: Statistiques et détails des vérifications
    """
    from app_sqlalchemy import DocumentDB

    max_age_days = get_max_history_age_days()

    # Obtenir db et travailler dans le contexte
    with current_app.app_context():
        db = current_app.extensions["sqlalchemy"]

        # Récupérer uniquement les documents avec une URL
        docs_with_url = DocumentDB.query.filter(DocumentDB.attributes.ilike('%"url_telechargement"%')).all()

        results = {"total_checked": 0, "unchanged": 0, "changed": 0, "errors": 0, "new": 0, "skipped": 0, "details": []}

        for doc in docs_with_url:
            result = check_document_for_updates(doc, max_age_days)

            # Sauvegarder les attributs mis à jour
            if "updated_attrs" in result:
                doc.attributes = json.dumps(result["updated_attrs"])
                db.session.add(doc)

            # Compter le résultat
            results[result["status"]] += 1
            results["total_checked"] += 1
            results["details"].append(result)

        db.session.commit()
    return results


def run_manual_check():
    """
    Exécute une vérification manuelle de tous les documents.

    Returns:
        Dict: Résultat de la vérification
    """
    return check_all_documents()


def get_document_check_status(doc) -> Dict[str, Any]:
    """
    Récupère le statut de vérification d'un document.

    Args:
        doc: Objet DocumentDB

    Returns:
        Dict: Statut de vérification
    """
    attrs = {}
    if doc.attributes:
        try:
            attrs = json.loads(doc.attributes)
        except (json.JSONDecodeError, TypeError):
            attrs = {}

    url = attrs.get("url_telechargement", "")
    last_checksum = attrs.get("last_checksum", "")
    last_checked = attrs.get("last_checked", "")
    check_history = attrs.get("check_history", [])

    return {
        "has_url": bool(url),
        "url": url,
        "last_checksum": last_checksum,
        "last_checked": last_checked,
        "check_history": check_history,
        "check_count": len(check_history),
    }
