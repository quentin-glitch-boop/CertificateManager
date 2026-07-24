"""
Module de traduction pour l'application DocManager
Système simple de traduction sans dépendance externe
"""

# Dictionnaire des traductions
TRANSLATIONS = {
    'fr': {
        'app_title': 'Gestion des Documents',
        'documents': 'Documents',
        'doc_manager': 'DocManager',
        'welcome': 'Bienvenue',
        'my_documents': 'Mes Documents',
        'add': 'Ajouter',
        'add_document': 'Ajouter un document',
        'search': 'Rechercher',
        'reset': 'Réinitialiser',
        'save': 'Sauvegarder',
        'delete': 'Supprimer',
        'edit': 'Modifier',
        'open': 'Ouvrir',
        'open_pdf': 'Ouvrir PDF',
        'logout': 'Déconnexion',
        'login': 'Connexion',
        'title': 'Titre',
        'content': 'Contenu',
        'optional': '(optionnel)',
        'required': '*',
        'doc_type': 'Type de document',
        'select_type': '-- Sélectionnez un type --',
        'validity_date': 'Date de validité',
        'file_pdf': 'Fichier PDF',
        'pdf_only': 'Seuls les fichiers PDF sont acceptés (max 16 Mo)',
        'author': 'Auteur',
        'certificat': 'Certificat',
        'certificat_desc': 'Certificat avec société certifiée et certificatrice',
        'nom_societe_certifiee': 'Nom de la société certifiée',
        'societe_certificatrice': 'Société certificatrice',
        'adresse': 'Adresse de la société',
        'date_peremption': 'Date de péremption du certificat',
        'url_telechargement': 'URL de téléchargement',
        'no_documents': 'Aucun document trouvé',
        'try_search': 'Essayez de modifier vos critères de recherche ou',
        'add_first_document': 'ajoutez un document',
        'success': 'Succès',
        'error': 'Erreur',
        'login_success': 'Connexion réussie !',
        'login_failed': 'Nom d\'utilisateur ou mot de passe incorrect',
        'logout_success': 'Déconnexion réussie',
        'doc_added': 'Document ajouté avec succès !',
        'doc_deleted': 'Document supprimé avec succès !',
        'pdf_required': 'Le fichier PDF est obligatoire',
        'pdf_only_allowed': 'Seuls les fichiers PDF sont autorisés',
        'title_required': 'Le titre est obligatoire',
        'field_required': 'est obligatoire',
        'username': 'Nom d\'utilisateur',
        'password': 'Mot de passe',
        'remember_me': 'Se souvenir de moi',
        'role': 'Rôle',
        'user': 'Utilisateur',
        'admin': 'Administrateur',
        'users': 'Utilisateurs',
        'user_management': 'Gestion des utilisateurs',
        'search_author': 'Auteur',
        'search_upload_from': 'Upload à partir de',
        'search_upload_to': 'Upload jusqu\'à',
        'search_validity_from': 'Validité à partir de',
        'search_validity_to': 'Validité jusqu\'à',
        'search_type': 'Type de document',
        'all_types': 'Tous les types',
        'valid_until': 'Valide jusqu\'au:',
        'expired': 'Expiré',
        'details': 'Détails:',
        'are_you_sure': 'Êtes-vous sûr de vouloir supprimer ce document ?',
        'n_a': 'N/A',
        'admin_only': 'Réservé aux administrateurs',
        'access_denied': 'Accès refusé',
    },
    'en': {
        'app_title': 'Document Management',
        'documents': 'Documents',
        'doc_manager': 'DocManager',
        'welcome': 'Welcome',
        'my_documents': 'My Documents',
        'add': 'Add',
        'add_document': 'Add a document',
        'search': 'Search',
        'reset': 'Reset',
        'save': 'Save',
        'delete': 'Delete',
        'edit': 'Edit',
        'open': 'Open',
        'open_pdf': 'Open PDF',
        'logout': 'Logout',
        'login': 'Login',
        'title': 'Title',
        'content': 'Content',
        'optional': '(optional)',
        'required': '*',
        'doc_type': 'Document type',
        'select_type': '-- Select a type --',
        'validity_date': 'Validity date',
        'file_pdf': 'PDF File',
        'pdf_only': 'Only PDF files are accepted (max 16 MB)',
        'author': 'Author',
        'certificat': 'Certificate',
        'certificat_desc': 'Certificate with certified company and certifying body',
        'nom_societe_certifiee': 'Certified Company Name',
        'societe_certificatrice': 'Certifying Body',
        'adresse': 'Company Address',
        'date_peremption': 'Certificate Expiry Date',
        'url_telechargement': 'Download URL',
        'no_documents': 'No documents found',
        'try_search': 'Try modifying your search criteria or',
        'add_first_document': 'add a document',
        'success': 'Success',
        'error': 'Error',
        'login_success': 'Login successful!',
        'login_failed': 'Invalid username or password',
        'logout_success': 'Logout successful',
        'doc_added': 'Document added successfully!',
        'doc_deleted': 'Document deleted successfully!',
        'pdf_required': 'PDF file is required',
        'pdf_only_allowed': 'Only PDF files are allowed',
        'title_required': 'Title is required',
        'field_required': 'is required',
        'username': 'Username',
        'password': 'Password',
        'remember_me': 'Remember me',
        'role': 'Role',
        'user': 'User',
        'admin': 'Admin',
        'users': 'Users',
        'user_management': 'User Management',
        'search_author': 'Author',
        'search_upload_from': 'Upload from',
        'search_upload_to': 'Upload to',
        'search_validity_from': 'Valid from',
        'search_validity_to': 'Valid to',
        'search_type': 'Document type',
        'all_types': 'All types',
        'valid_until': 'Valid until:',
        'expired': 'Expired',
        'details': 'Details:',
        'are_you_sure': 'Are you sure you want to delete this document?',
        'n_a': 'N/A',
        'admin_only': 'Admin only',
        'access_denied': 'Access denied',
    }
}

DEFAULT_LANGUAGE = 'fr'

AVAILABLE_LANGUAGES = {
    'fr': 'Français',
    'en': 'English'
}


def get_translation(key, lang=None):
    if lang is None:
        lang = DEFAULT_LANGUAGE
    translations = TRANSLATIONS.get(lang, {})
    return translations.get(key, key)


def get_current_language():
    from flask import session, request
    if 'language' in session:
        return session['language']
    if request and hasattr(request, 'cookies') and 'language' in request.cookies:
        return request.cookies.get('language', DEFAULT_LANGUAGE)
    if request and hasattr(request, 'accept_languages'):
        for lang in request.accept_languages:
            if lang in TRANSLATIONS:
                return lang
    return DEFAULT_LANGUAGE


def set_language(lang):
    from flask import session
    if lang in TRANSLATIONS:
        session['language'] = lang
