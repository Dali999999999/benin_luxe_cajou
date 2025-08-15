# app/auth/routes.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from flask_mail import Message
import secrets
import logging
from datetime import datetime

from app.models import Utilisateur
from app.extensions import db, mail

# Configuration du logger spécifique pour l'authentification
auth_logger = logging.getLogger('auth')
auth_logger.setLevel(logging.DEBUG)

# Handler pour fichier avec rotation
from logging.handlers import RotatingFileHandler
file_handler = RotatingFileHandler('logs/auth.log', maxBytes=10000000, backupCount=3)
file_handler.setLevel(logging.DEBUG)

# Handler pour la console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Format des logs avec plus de détails
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s() - %(message)s'
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Ajout des handlers au logger
if not auth_logger.handlers:
    auth_logger.addHandler(file_handler)
    auth_logger.addHandler(console_handler)

auth_bp = Blueprint('auth', __name__)

# --- FONCTION UTILITAIRE POUR L'ENVOI D'EMAIL ---

def send_verification_email(user_email, code, subject):
    """
    Fonction centralisée pour envoyer un code de vérification par email.
    """
    auth_logger.info(f"Tentative d'envoi d'email de vérification - Destinataire: {user_email}, Sujet: {subject}")
    
    try:
        msg = Message(subject=subject,
                      recipients=[user_email],
                      html=f"""
                      <p>Bonjour,</p>
                      <p>Voici votre code de vérification pour l'application Benin Luxe Cajou :</p>
                      <h2 style='text-align: center; color: #333;'>{code}</h2>
                      <p>Ce code est valable pour une durée limitée. Ne le partagez avec personne.</p>
                      <p>Cordialement,<br>L'équipe Benin Luxe Cajou</p>
                      """)
        mail.send(msg)
        auth_logger.info(f"Email de vérification envoyé avec succès à {user_email}")
        return True
    except Exception as e:
        auth_logger.error(f"Échec de l'envoi d'email à {user_email} - Erreur: {str(e)}")
        return False

# --- ROUTES POUR L'ADMINISTRATEUR ---

@auth_bp.route('/admin/register', methods=['POST'])
def admin_register():
    """
    Étape 1: Création du compte admin (non vérifié).
    """
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    auth_logger.info(f"Tentative d'inscription admin depuis IP: {client_ip}")
    
    try:
        data = request.get_json()
        auth_logger.debug(f"Données reçues pour inscription admin: {list(data.keys()) if data else 'None'}")
        
        if not data:
            auth_logger.warning(f"Inscription admin échouée - Aucune donnée JSON reçue - IP: {client_ip}")
            return jsonify({"msg": "Données JSON requises"}), 400
            
        email = data.get('email')
        password = data.get('password')
        nom = data.get('nom')
        prenom = data.get('prenom')

        auth_logger.debug(f"Email fourni: {email}, Nom: {nom}, Prénom: {prenom}")

        if not all([email, password, nom, prenom]):
            auth_logger.warning(f"Inscription admin échouée - Champs manquants pour email: {email} - IP: {client_ip}")
            return jsonify({"msg": "Tous les champs sont requis"}), 400

        # Vérification de l'existence de l'utilisateur
        existing_user = Utilisateur.query.filter_by(email=email).first()
        if existing_user:
            auth_logger.warning(f"Tentative d'inscription admin avec email existant: {email} - IP: {client_ip}")
            return jsonify({"msg": "Un compte existe déjà avec cet email"}), 409

        # Création de l'utilisateur avec le rôle 'admin'
        auth_logger.info(f"Création d'un nouveau compte admin pour: {email}")
        new_admin = Utilisateur(
            email=email,
            nom=nom,
            prenom=prenom,
            role='admin',
            email_verifie=False
        )
        new_admin.set_password(password)
        
        # Génération et stockage du code de vérification
        verification_code = str(secrets.randbelow(900000) + 100000)
        new_admin.token_verification = verification_code
        auth_logger.debug(f"Code de vérification généré pour {email}: {verification_code}")
        
        db.session.add(new_admin)
        db.session.commit()
        auth_logger.info(f"Compte admin créé avec succès en base de données pour: {email} - ID: {new_admin.id}")
        
        # Envoi de l'email de vérification
        email_sent = send_verification_email(new_admin.email, verification_code, "Activez votre compte Admin")
        
        if email_sent:
            auth_logger.info(f"Processus d'inscription admin terminé avec succès pour: {email} - IP: {client_ip}")
            return jsonify({"msg": "Compte Admin créé. Un code de vérification a été envoyé à votre adresse email."}), 201
        else:
            auth_logger.error(f"Compte admin créé mais email non envoyé pour: {email}")
            return jsonify({"msg": "Compte créé mais erreur lors de l'envoi de l'email de vérification."}), 201
            
    except Exception as e:
        auth_logger.error(f"Erreur inattendue lors de l'inscription admin - IP: {client_ip} - Erreur: {str(e)}")
        db.session.rollback()
        return jsonify({"msg": "Erreur serveur lors de la création du compte"}), 500

@auth_bp.route('/admin/verify-account', methods=['POST'])
def admin_verify_account():
    """
    Étape 2: Vérification du compte admin avec le code reçu par email.
    """
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    auth_logger.info(f"Tentative de vérification de compte admin depuis IP: {client_ip}")
    
    try:
        data = request.get_json()
        
        if not data:
            auth_logger.warning(f"Vérification admin échouée - Aucune donnée JSON - IP: {client_ip}")
            return jsonify({"msg": "Données JSON requises"}), 400
            
        email = data.get('email')
        code = data.get('code')

        auth_logger.debug(f"Tentative de vérification pour email: {email}")

        if not email or not code:
            auth_logger.warning(f"Vérification admin échouée - Données manquantes - Email: {email} - IP: {client_ip}")
            return jsonify({"msg": "Email et code de vérification requis"}), 400

        admin = Utilisateur.query.filter_by(email=email, role='admin').first()

        if not admin:
            auth_logger.warning(f"Tentative de vérification pour email admin inexistant: {email} - IP: {client_ip}")
            return jsonify({"msg": "Aucun compte admin trouvé pour cet email"}), 404
        
        auth_logger.debug(f"Compte admin trouvé - ID: {admin.id}, Email vérifié: {admin.email_verifie}")
        
        if admin.email_verifie:
            auth_logger.info(f"Tentative de vérification d'un compte déjà vérifié: {email} - IP: {client_ip}")
            return jsonify({"msg": "Ce compte est déjà vérifié"}), 400

        if admin.token_verification == code:
            admin.email_verifie = True
            admin.token_verification = None
            db.session.commit()
            
            auth_logger.info(f"Compte admin vérifié avec succès: {email} - ID: {admin.id} - IP: {client_ip}")
            return jsonify({"msg": "Votre compte a été activé avec succès. Vous pouvez maintenant vous connecter."}), 200
        else:
            auth_logger.warning(f"Code de vérification incorrect pour admin: {email} - Code fourni: {code} - IP: {client_ip}")
            return jsonify({"msg": "Code de vérification incorrect"}), 400
            
    except Exception as e:
        auth_logger.error(f"Erreur inattendue lors de la vérification admin - IP: {client_ip} - Erreur: {str(e)}")
        return jsonify({"msg": "Erreur serveur lors de la vérification"}), 500

@auth_bp.route('/admin/login', methods=['POST'])
def admin_login():
    """
    Connexion de l'administrateur.
    """
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    auth_logger.info(f"Tentative de connexion admin depuis IP: {client_ip}")
    
    try:
        data = request.get_json()
        
        if not data:
            auth_logger.warning(f"Connexion admin échouée - Aucune donnée JSON - IP: {client_ip}")
            return jsonify({"msg": "Données JSON requises"}), 400
            
        email = data.get('email')
        password = data.get('password')

        auth_logger.debug(f"Tentative de connexion pour email: {email}")

        if not email or not password:
            auth_logger.warning(f"Connexion admin échouée - Données manquantes - Email: {email} - IP: {client_ip}")
            return jsonify({"msg": "Email et mot de passe requis"}), 400

        admin = Utilisateur.query.filter_by(email=email, role='admin').first()

        if not admin:
            auth_logger.warning(f"Tentative de connexion avec email admin inexistant: {email} - IP: {client_ip}")
            return jsonify({"msg": "Email ou mot de passe incorrect"}), 401
        
        auth_logger.debug(f"Compte admin trouvé - ID: {admin.id}, Email vérifié: {admin.email_verifie}")
        
        if not admin.email_verifie:
            auth_logger.warning(f"Tentative de connexion avec compte non vérifié: {email} - ID: {admin.id} - IP: {client_ip}")
            return jsonify({"msg": "Votre compte n'est pas encore activé. Veuillez vérifier vos emails."}), 403

        if admin.check_password(password):
            # Création du token JWT qui contient l'ID de l'admin
            access_token = create_access_token(identity=admin.id)
            
            auth_logger.info(f"Connexion admin réussie: {email} - ID: {admin.id} - IP: {client_ip}")
            return jsonify(access_token=access_token)
        else:
            auth_logger.warning(f"Connexion admin échouée - Mot de passe incorrect: {email} - IP: {client_ip}")
            return jsonify({"msg": "Email ou mot de passe incorrect"}), 401
            
    except Exception as e:
        auth_logger.error(f"Erreur inattendue lors de la connexion admin - IP: {client_ip} - Erreur: {str(e)}")
        return jsonify({"msg": "Erreur serveur lors de la connexion"}), 500

@auth_bp.route('/admin/forgot-password', methods=['POST'])
def admin_forgot_password():
    """
    Étape 1 du renouvellement: L'admin renseigne son email pour recevoir un code.
    """
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    auth_logger.info(f"Demande de réinitialisation mot de passe admin depuis IP: {client_ip}")
    
    try:
        data = request.get_json()
        
        if not data:
            auth_logger.warning(f"Demande réinitialisation échouée - Aucune donnée JSON - IP: {client_ip}")
            return jsonify({"msg": "Données JSON requises"}), 400
            
        email = data.get('email')

        auth_logger.debug(f"Demande de réinitialisation pour email: {email}")

        if not email:
            auth_logger.warning(f"Demande réinitialisation échouée - Email manquant - IP: {client_ip}")
            return jsonify({"msg": "Email requis"}), 400
            
        admin = Utilisateur.query.filter_by(email=email, role='admin').first()

        # On renvoie une réponse positive même si l'email n'existe pas
        # pour ne pas permettre de deviner les emails des admins (sécurité).
        if admin:
            verification_code = str(secrets.randbelow(900000) + 100000)
            admin.token_verification = verification_code
            db.session.commit()
            
            auth_logger.info(f"Code de réinitialisation généré pour admin: {email} - ID: {admin.id}")
            email_sent = send_verification_email(admin.email, verification_code, "Réinitialisation de votre mot de passe")
            
            if not email_sent:
                auth_logger.error(f"Échec de l'envoi du code de réinitialisation pour: {email}")
        else:
            auth_logger.info(f"Demande de réinitialisation pour email admin inexistant: {email} - IP: {client_ip}")

        auth_logger.info(f"Réponse standard envoyée pour demande de réinitialisation - Email: {email} - IP: {client_ip}")
        return jsonify({"msg": "Si un compte admin est associé à cet email, un code de réinitialisation a été envoyé."}), 200
        
    except Exception as e:
        auth_logger.error(f"Erreur inattendue lors de la demande de réinitialisation - IP: {client_ip} - Erreur: {str(e)}")
        return jsonify({"msg": "Erreur serveur lors de la demande"}), 500

@auth_bp.route('/admin/reset-password', methods=['POST'])
def admin_reset_password():
    """
    Étape 2 du renouvellement: L'admin fournit le code et son nouveau mot de passe.
    """
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    auth_logger.info(f"Tentative de réinitialisation mot de passe admin depuis IP: {client_ip}")
    
    try:
        data = request.get_json()
        
        if not data:
            auth_logger.warning(f"Réinitialisation échouée - Aucune donnée JSON - IP: {client_ip}")
            return jsonify({"msg": "Données JSON requises"}), 400
            
        email = data.get('email')
        code = data.get('code')
        new_password = data.get('new_password')

        auth_logger.debug(f"Tentative de réinitialisation pour email: {email}")

        if not all([email, code, new_password]):
            auth_logger.warning(f"Réinitialisation échouée - Données manquantes - Email: {email} - IP: {client_ip}")
            return jsonify({"msg": "Email, code et nouveau mot de passe requis"}), 400

        admin = Utilisateur.query.filter_by(email=email, role='admin').first()

        if not admin:
            auth_logger.warning(f"Tentative de réinitialisation pour email admin inexistant: {email} - IP: {client_ip}")
            return jsonify({"msg": "Action non autorisée"}), 404
        
        auth_logger.debug(f"Compte admin trouvé pour réinitialisation - ID: {admin.id}")
            
        if admin.token_verification == code:
            admin.set_password(new_password)
            admin.token_verification = None
            db.session.commit()
            
            auth_logger.info(f"Mot de passe réinitialisé avec succès pour admin: {email} - ID: {admin.id} - IP: {client_ip}")
            return jsonify({"msg": "Votre mot de passe a été mis à jour avec succès."}), 200
        else:
            auth_logger.warning(f"Code de réinitialisation incorrect pour admin: {email} - Code fourni: {code} - IP: {client_ip}")
            return jsonify({"msg": "Le code de vérification est invalide ou a expiré."}), 400
            
    except Exception as e:
        auth_logger.error(f"Erreur inattendue lors de la réinitialisation mot de passe - IP: {client_ip} - Erreur: {str(e)}")
        return jsonify({"msg": "Erreur serveur lors de la réinitialisation"}), 500

# --- ROUTES POUR LES CLIENTS (À DÉVELOPPER PLUS TARD) ---
# ...
# Les routes pour l'inscription et la connexion des clients seront ici
# et suivront une logique similaire mais avec `role='client'`.
# ...
