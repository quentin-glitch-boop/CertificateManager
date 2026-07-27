"""
Module d'extraction de texte et de données à partir de fichiers PDF et images.

Ce module utilise OCR (pytesseract) pour les images et pdfplumber pour les PDF.
L'extraction des informations est basée sur des motifs simples (regex et string matching).
"""

import re
import io
import tempfile
import os
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    import PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False


# Configuration de pytesseract (si nécessaire)
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extrait le texte d'un fichier PDF.
    
    Args:
        pdf_path: Chemin vers le fichier PDF
        
    Returns:
        str: Texte extrait
    """
    if not PDF_AVAILABLE:
        return ""
    
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"Erreur lors de l'extraction PDF avec pdfplumber: {e}")
        # Essayer avec PyMuPDF
        if FITZ_AVAILABLE:
            try:
                doc = PyMuPDF.open(pdf_path)
                for page in doc:
                    text += page.get_text() + "\n"
                doc.close()
            except Exception as e2:
                print(f"Erreur avec PyMuPDF: {e2}")
    
    return text


def extract_text_from_image(image_path: str) -> str:
    """
    Extrait le texte d'une image (PNG, JPG) en utilisant OCR.
    
    Args:
        image_path: Chemin vers le fichier image
        
    Returns:
        str: Texte extrait
    """
    if not OCR_AVAILABLE:
        return ""
    
    try:
        # Ouvrir l'image et utiliser pytesseract
        text = pytesseract.image_to_string(image_path, lang='fra+eng')
        return text
    except Exception as e:
        print(f"Erreur lors de l'OCR: {e}")
        return ""


def extract_text_from_file(file_path: str) -> str:
    """
    Extrait le texte d'un fichier (PDF ou image).
    
    Args:
        file_path: Chemin vers le fichier
        
    Returns:
        str: Texte extrait
    """
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext in ['.pdf']:
        return extract_text_from_pdf(file_path)
    elif ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff']:
        return extract_text_from_image(file_path)
    else:
        return ""


def extract_document_info(text: str) -> Dict[str, Any]:
    """
    Extrait les informations du document à partir du texte.
    
    Cette fonction utilise des motifs simples pour identifier les informations.
    Elle sera améliorée par la suite.
    
    Args:
        text: Texte extrait du document
        
    Returns:
        Dict: Dictionnaire contenant les informations extraites
    """
    if not text or not text.strip():
        return {}
    
    # Nettoyer le texte
    text = text.strip()
    
    # Créer une copie en minuscules pour la recherche (mais garder l'original pour les valeurs)
    text_lower = text.lower()
    
    info = {
        'title': '',
        'organisme_certificateur': '',
        'type_norme': '',
        'date_peremption': '',
        'entreprise_certifiee': '',
        'pays': '',
        'adresse': '',
        'content': text  # Garde tout le texte comme content
    }
    
    # ========================================================================
    # Extraction par motifs simples
    # ========================================================================
    
    # 1. Titre - Essayer de trouver un titre ou une référence
    # Motifs : "Certificat", "Attestation", "Document", ou les premières lignes
    lines = text.split('\n')
    for line in lines[:5]:  # Vérifier les 5 premières lignes
        line_stripped = line.strip()
        if line_stripped and len(line_stripped) > 10 and len(line_stripped) < 200:
            # Vérifier si c'est un titre (contient des mots clés)
            title_keywords = ['certificat', 'attestation', 'certificate', 'statement', 'docUMENT']
            if any(kw in line_stripped.lower() for kw in title_keywords):
                info['title'] = line_stripped
                break
    
    if not info['title']:
        # Prendre la première ligne non vide
        for line in lines:
            if line.strip():
                info['title'] = line.strip()[:100]
                break
    
    # 2. Organisme Certificateur
    # Motifs : "organisme certificateur", "certifié par", "certifying body", "issued by"
    org_patterns = [
        (r'organisme[\s\-]?certificateur[\s\-]?:?\s*([^\n]+)', 'organisme_certificateur'),
        (r'certifié[\s\-]?par[\s\-]?:?\s*([^\n]+)', 'organisme_certificateur'),
        (r'issued[\s\-]?by[\s\-]?:?\s*([^\n]+)', 'organisme_certificateur'),
        (r'certifying[\s\-]?body[\s\-]?:?\s*([^\n]+)', 'organisme_certificateur'),
        (r'certification[\s\-]?body[\s\-]?:?\s*([^\n]+)', 'organisme_certificateur'),
        (r'by[\s\-]?:?\s*([A-Z][^\n]{10,})', 'organisme_certificateur'),
    ]
    
    for pattern, field in org_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            # Nettoyer la valeur (enlever les caractères spéciaux au début/fin)
            value = re.sub(r'[^a-zA-Z0-9\s\-\.\,]+$', '', value)
            value = re.sub(r'^[^a-zA-Z0-9\s\-\.\,]+', '', value)
            if value and len(value) > 2:
                info[field] = value
                break
    
    # 3. Type de Norme
    # Motifs : "norme", "standard", "ISO", "EN", "NF", etc.
    norme_patterns = [
        (r'norme[\s\-]?:?\s*([A-Z0-9\s\-\.]+)', 'type_norme'),
        (r'standard[\s\-]?:?\s*([A-Z0-9\s\-\.]+)', 'type_norme'),
        (r'ISO[\s\-]?([0-9\s\-]+)', 'type_norme'),
        (r'EN[\s\-]?([0-9\s\-]+)', 'type_norme'),
        (r'NF[\s\-]?([A-Z0-9\s\-\.]+)', 'type_norme'),
        (r'DIN[\s\-]?([0-9\s\-]+)', 'type_norme'),
    ]
    
    for pattern, field in norme_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            value = re.sub(r'[^A-Z0-9\s\-\.]+', '', value)
            if value and len(value) >= 2:
                info[field] = value
                break
    
    # 4. Date de péremption / Date de validité
    # Motifs : "validité", "expiration", "expire", "valid until", dates au format YYYY-MM-DD ou DD/MM/YYYY
    date_patterns = [
        (r'validité[\s\-]?:?\s*([0-9]{2}[\/\-][0-9]{2}[\/\-][0-9]{4})', 'date_peremption'),
        (r'expiration[\s\-]?:?\s*([0-9]{2}[\/\-][0-9]{2}[\/\-][0-9]{4})', 'date_peremption'),
        (r'expire[\s\-]?:?\s*([0-9]{2}[\/\-][0-9]{2}[\/\-][0-9]{4})', 'date_peremption'),
        (r'valid[\s\-]?until[\s\-]?:?\s*([0-9]{2}[\/\-][0-9]{2}[\/\-][0-9]{4})', 'date_peremption'),
        (r'date[\s\-]?de[\s\-]?fin[\s\-]?:?\s*([0-9]{2}[\/\-][0-9]{2}[\/\-][0-9]{4})', 'date_peremption'),
        (r'valable[\s\-]?jusqu[\'\`]au[\s\-]?:?\s*([0-9]{2}[\/\-][0-9]{2}[\/\-][0-9]{4})', 'date_peremption'),
        # Format YYYY-MM-DD
        (r'([0-9]{4}[\-][0-9]{2}[\-][0-9]{2})', 'date_peremption'),
        # Format DD/MM/YYYY
        (r'([0-9]{2}[\/][0-9]{2}[\/][0-9]{4})', 'date_peremption'),
    ]
    
    for pattern, field in date_patterns:
        match = re.search(pattern, text)
        if match:
            value = match.group(1).strip()
            # Valider le format de la date
            if re.match(r'^[0-9]{4}[\-][0-9]{2}[\-][0-9]{2}$', value):
                info[field] = value
                break
            elif re.match(r'^[0-9]{2}[\/][0-9]{2}[\/][0-9]{4}$', value):
                # Convertir DD/MM/YYYY en YYYY-MM-DD
                try:
                    day, month, year = value.split('/')
                    info[field] = f"{year}-{month}-{day}"
                except:
                    info[field] = value
                break
    
    # 5. Entreprise Certifiée
    # Motifs : "entreprise", "société", "company", "client"
    entreprise_patterns = [
        (r'entreprise[\s\-]?certifiée[\s\-]?:?\s*([^\n]+)', 'entreprise_certifiee'),
        (r'société[\s\-]?certifiée[\s\-]?:?\s*([^\n]+)', 'entreprise_certifiee'),
        (r'certified[\s\-]?company[\s\-]?:?\s*([^\n]+)', 'entreprise_certifiee'),
        (r'company[\s\-]?name[\s\-]?:?\s*([^\n]+)', 'entreprise_certifiee'),
        (r'client[\s\-]?:?\s*([A-Z][^\n]{5,})', 'entreprise_certifiee'),
    ]
    
    for pattern, field in entreprise_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            value = re.sub(r'[^a-zA-Z0-9\s\-\.\,]+$', '', value)
            value = re.sub(r'^[^a-zA-Z0-9\s\-\.\,]+', '', value)
            if value and len(value) > 2:
                info[field] = value
                break
    
    # 6. Pays
    # Motifs : mots clés de pays
    country_keywords = [
        'france', 'germany', 'allemagne', 'belgique', 'belgium', 'pays-bas', 'netherlands',
        'spain', 'espagne', 'italy', 'italie', 'switzerland', 'suisse', 'luxembourg',
        'austria', 'autriche', 'portugal', 'united kingdom', 'royaume-uni',
        'usa', 'united states', 'etats-unis', 'canada', 'sweden', 'suède'
    ]
    
    for keyword in country_keywords:
        if keyword in text_lower:
            # Trouver le mot ou l'expression
            match = re.search(r'\b(' + re.escape(keyword) + r')\b', text, re.IGNORECASE)
            if match:
                value = match.group(1)
                # Normaliser (première lettre en majuscule)
                info['pays'] = value.capitalize()
                break
    
    # 7. Adresse
    # Motifs : mots clés d'adresse
    address_patterns = [
        (r'adresse[\s\-]?:?\s*([^\n]+)', 'adresse'),
        (r'address[\s\-]?:?\s*([^\n]+)', 'adresse'),
        (r'[0-9]+[\s,][a-zA-Z\s]+', 'adresse'),  # Numéro + rue
    ]
    
    for pattern, field in address_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            value = re.sub(r'[^a-zA-Z0-9\s\-\.\,]+$', '', value)
            if value and len(value) > 5:
                info[field] = value
                break
    
    # Nettoyage final - limiter la longueur des champs
    for key in info:
        if isinstance(info[key], str) and len(info[key]) > 500:
            info[key] = info[key][:500]
    
    return info


def process_uploaded_file(file_storage) -> Dict[str, Any]:
    """
    Traite un fichier uploadé (PDF ou image) et extrait les informations.
    
    Args:
        file_storage: Objet FileStorage de Flask (request.files)
        
    Returns:
        Dict: Dictionnaire contenant :
            - success: bool
            - text: str (texte extrait)
            - info: dict (informations extraites)
            - error: str (message d'erreur si échec)
    """
    result = {
        'success': False,
        'text': '',
        'info': {},
        'error': ''
    }
    
    if not file_storage:
        result['error'] = 'Aucun fichier fourni'
        return result
    
    # Vérifier l'extension
    filename = file_storage.filename
    if not filename:
        result['error'] = 'Nom de fichier invalide'
        return result
    
    ext = os.path.splitext(filename)[1].lower()
    allowed_extensions = ['.pdf', '.png', '.jpg', '.jpeg']
    
    if ext not in allowed_extensions:
        result['error'] = f'Type de fichier non autorisé: {ext}. Seuls PDF, PNG et JPG sont acceptés.'
        return result
    
    # Sauvegarder temporairement le fichier
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_file:
            file_storage.save(temp_file.name)
            temp_path = temp_file.name
        
        # Extraire le texte
        text = extract_text_from_file(temp_path)
        
        if not text or not text.strip():
            result['error'] = 'Aucun texte extrait du fichier. Le fichier peut être vide ou illisible.'
            os.unlink(temp_path)
            return result
        
        result['text'] = text
        result['info'] = extract_document_info(text)
        result['success'] = True
        
        # Nettoyer
        os.unlink(temp_path)
        
    except Exception as e:
        result['error'] = f'Erreur lors du traitement du fichier: {str(e)}'
        try:
            if 'temp_path' in locals():
                os.unlink(temp_path)
        except:
            pass
    
    return result


if __name__ == '__main__':
    # Test
    print("Testing text extractor...")
    print(f"PDF available: {PDF_AVAILABLE}")
    print(f"OCR available: {OCR_AVAILABLE}")
    
    # Tester l'extraction de texte
    test_text = """
    Certificat N° CERT-2024-001
    
    Organisme Certificateur: Bureau Veritas
    Norme: ISO 9001:2015
    
    Entreprise Certifiée: Societe XYZ SAS
    Adresse: 123 Rue de Paris, 75001 Paris, France
    
    Date de validité: 31/12/2025
    """
    
    info = extract_document_info(test_text)
    print("\nExtracted info from test text:")
    for key, value in info.items():
        print(f"  {key}: {value}")
