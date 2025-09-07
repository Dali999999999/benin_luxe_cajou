# app/auth/routes.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt_identity, jwt_required
from flask_mail import Message
import secrets
import logging
from datetime import datetime

from app.models import Utilisateur
from app.extensions import db, mail

# Configuration du logger pour sortie console uniquement
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

auth_bp = Blueprint('auth', __name__)

# --- FONCTION UTILITAIRE POUR L'ENVOI D'EMAIL ---

def send_verification_email(user_email, code, subject):
    """
    Fonction centralisée pour envoyer un code de vérification par email.
    """
    print(f"[EMAIL] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Tentative d'envoi à {user_email} - Sujet: {subject}")
    
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
        print(f"[EMAIL] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ Email envoyé avec succès à {user_email}")
        return True
    except Exception as e:
        print(f"[EMAIL] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ Échec envoi à {user_email} - Erreur: {str(e)}")
        return False

# --- ROUTES POUR L'ADMINISTRATEUR ---

@auth_bp.route('/admin/register', methods=['POST'])
def admin_register():
    """
    Étape 1: Création du compte admin (non vérifié).
    """
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    route_name = "ADMIN_REGISTER"
    
    print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🚀 DÉBUT - IP: {client_ip}")
    
    try:
        data = request.get_json()
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📥 Données reçues: {list(data.keys()) if data else 'None'}")
        
        if not data:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⚠️ ÉCHEC - Aucune donnée JSON - IP: {client_ip}")
            return jsonify({"msg": "Données JSON requises"}), 400
            
        email = data.get('email')
        password = data.get('password')
        nom = data.get('nom')
        prenom = data.get('prenom')

        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📧 Email: {email}, Nom: {nom}, Prénom: {prenom}")

        if not all([email, password, nom, prenom]):
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⚠️ ÉCHEC - Champs manquants pour {email} - IP: {client_ip}")
            return jsonify({"msg": "Tous les champs sont requis"}), 400

        # Vérification de l'existence de l'utilisateur
        existing_user = Utilisateur.query.filter_by(email=email).first()
        if existing_user:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⚠️ CONFLIT - Email existant: {email} - IP: {client_ip}")
            return jsonify({"msg": "Un compte existe déjà avec cet email"}), 409

        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔄 Création compte admin pour: {email}")
        
        # Création de l'utilisateur avec le rôle 'admin'
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
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔐 Code généré pour {email}: {verification_code}")
        
        db.session.add(new_admin)
        db.session.commit()
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 💾 Compte sauvegardé en DB - ID: {new_admin.id}")
        
        # Envoi de l'email de vérification
        email_sent = send_verification_email(new_admin.email, verification_code, "Activez votre compte Admin")
        
        if email_sent:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ SUCCÈS COMPLET pour {email} - ID: {new_admin.id} - IP: {client_ip}")
            return jsonify({"msg": "Compte Admin créé. Un code de vérification a été envoyé à votre adresse email."}), 201
        else:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⚠️ SUCCÈS PARTIEL - Compte créé mais email non envoyé pour: {email}")
            return jsonify({"msg": "Compte créé mais erreur lors de l'envoi de l'email de vérification."}), 201
            
    except Exception as e:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ ERREUR CRITIQUE - IP: {client_ip} - {str(e)}")
        db.session.rollback()
        return jsonify({"msg": "Erreur serveur lors de la création du compte"}), 500
    
    finally:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🏁 FIN - IP: {client_ip}")

@auth_bp.route('/admin/verify-account', methods=['POST'])
def admin_verify_account():
    """
    Étape 2: Vérification du compte admin avec le code reçu par email.
    """
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    route_name = "ADMIN_VERIFY"
    
    print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🚀 DÉBUT - IP: {client_ip}")
    
    try:
        data = request.get_json()
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📥 Données reçues: {list(data.keys()) if data else 'None'}")
        
        if not data:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⚠️ ÉCHEC - Aucune donnée JSON - IP: {client_ip}")
            return jsonify({"msg": "Données JSON requises"}), 400
            
        email = data.get('email')
        code = data.get('code')

        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📧 Vérification pour: {email}")

        if not email or not code:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⚠️ ÉCHEC - Données manquantes - Email: {email} - IP: {client_ip}")
            return jsonify({"msg": "Email et code de vérification requis"}), 400

        admin = Utilisateur.query.filter_by(email=email, role='admin').first()

        if not admin:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⚠️ ÉCHEC - Email admin inexistant: {email} - IP: {client_ip}")
            return jsonify({"msg": "Aucun compte admin trouvé pour cet email"}), 404
        
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 👤 Compte trouvé - ID: {admin.id}, Vérifié: {admin.email_verifie}")
        
        if admin.email_verifie:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⚠️ ÉCHEC - Compte déjà vérifié: {email} - IP: {client_ip}")
            return jsonify({"msg": "Ce compte est déjà vérifié"}), 400

        if admin.token_verification == code:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔐 Code correct - Activation du compte")
            admin.email_verifie = True
            admin.token_verification = None
            db.session.commit()
            
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ SUCCÈS - Compte vérifié: {email} - ID: {admin.id} - IP: {client_ip}")
            return jsonify({"msg": "Votre compte a été activé avec succès. Vous pouvez maintenant vous connecter."}), 200
        else:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ ÉCHEC - Code incorrect pour {email} - Code fourni: {code} - IP: {client_ip}")
            return jsonify({"msg": "Code de vérification incorrect"}), 400
            
    except Exception as e:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ ERREUR CRITIQUE - IP: {client_ip} - {str(e)}")
        return jsonify({"msg": "Erreur serveur lors de la vérification"}), 500
    
    finally:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🏁 FIN - IP: {client_ip}")

@auth_bp.route('/admin/login', methods=['POST'])
def admin_login():
    """
    Connexion de l'administrateur.
    """
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    route_name = "ADMIN_LOGIN"
    
    print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🚀 DÉBUT - IP: {client_ip}")
    
    try:
        data = request.get_json()
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📥 Données reçues: {list(data.keys()) if data else 'None'}")
        
        if not data:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⚠️ ÉCHEC - Aucune donnée JSON - IP: {client_ip}")
            return jsonify({"msg": "Données JSON requises"}), 400
            
        email = data.get('email')
        password = data.get('password')

        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔐 Tentative connexion: {email}")

        if not email or not password:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⚠️ ÉCHEC - Données manquantes - Email: {email} - IP: {client_ip}")
            return jsonify({"msg": "Email et mot de passe requis"}), 400

        admin = Utilisateur.query.filter_by(email=email, role='admin').first()

        if not admin:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ ÉCHEC - Email admin inexistant: {email} - IP: {client_ip}")
            return jsonify({"msg": "Email ou mot de passe incorrect"}), 401
        
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 👤 Compte trouvé - ID: {admin.id}, Vérifié: {admin.email_verifie}")
        
        if not admin.email_verifie:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⚠️ ÉCHEC - Compte non vérifié: {email} - ID: {admin.id} - IP: {client_ip}")
            return jsonify({"msg": "Votre compte n'est pas encore activé. Veuillez vérifier vos emails."}), 403

        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔍 Vérification mot de passe pour: {email}")
        
        if admin.check_password(password):
            # Création des tokens JWT (access + refresh)
            access_token = create_access_token(identity=str(admin.id))
            refresh_token = create_refresh_token(identity=str(admin.id))
            
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ SUCCÈS - Connexion réussie: {email} - ID: {admin.id} - IP: {client_ip}")
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🎫 Token JWT généré pour ID: {admin.id}")
            return jsonify(access_token=access_token, refresh_token=refresh_token)
        else:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ ÉCHEC - Mot de passe incorrect: {email} - IP: {client_ip}")
            return jsonify({"msg": "Email ou mot de passe incorrect"}), 401
            
    except Exception as e:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ ERREUR CRITIQUE - IP: {client_ip} - {str(e)}")
        return jsonify({"msg": "Erreur serveur lors de la connexion"}), 500
    
    finally:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🏁 FIN - IP: {client_ip}")

@auth_bp.route('/admin/forgot-password', methods=['POST'])
def admin_forgot_password():
    """
    Étape 1 du renouvellement: L'admin renseigne son email pour recevoir un code.
    """
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    route_name = "ADMIN_FORGOT_PASSWORD"
    
    print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🚀 DÉBUT - IP: {client_ip}")
    
    try:
        data = request.get_json()
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📥 Données reçues: {list(data.keys()) if data else 'None'}")
        
        if not data:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⚠️ ÉCHEC - Aucune donnée JSON - IP: {client_ip}")
            return jsonify({"msg": "Données JSON requises"}), 400
            
        email = data.get('email')

        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📧 Demande réinitialisation pour: {email}")

        if not email:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⚠️ ÉCHEC - Email manquant - IP: {client_ip}")
            return jsonify({"msg": "Email requis"}), 400
            
        admin = Utilisateur.query.filter_by(email=email, role='admin').first()

        if admin:
            verification_code = str(secrets.randbelow(900000) + 100000)
            admin.token_verification = verification_code
            db.session.commit()
            
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔐 Code réinitialisation généré pour {email} - ID: {admin.id} - Code: {verification_code}")
            email_sent = send_verification_email(admin.email, verification_code, "Réinitialisation de votre mot de passe")
            
            if email_sent:
                print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ Email réinitialisation envoyé à: {email}")
            else:
                print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ Échec envoi email réinitialisation pour: {email}")
        else:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⚠️ Email admin inexistant: {email} - IP: {client_ip}")

        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📤 Réponse standard envoyée pour: {email} - IP: {client_ip}")
        return jsonify({"msg": "Si un compte admin est associé à cet email, un code de réinitialisation a été envoyé."}), 200
        
    except Exception as e:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ ERREUR CRITIQUE - IP: {client_ip} - {str(e)}")
        return jsonify({"msg": "Erreur serveur lors de la demande"}), 500
    
    finally:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🏁 FIN - IP: {client_ip}")

@auth_bp.route('/admin/reset-password', methods=['POST'])
def admin_reset_password():
    """
    Étape 2 du renouvellement: L'admin fournit le code et son nouveau mot de passe.
    """
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    route_name = "ADMIN_RESET_PASSWORD"
    
    print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🚀 DÉBUT - IP: {client_ip}")
    
    try:
        data = request.get_json()
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📥 Données reçues: {list(data.keys()) if data else 'None'}")
        
        if not data:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⚠️ ÉCHEC - Aucune donnée JSON - IP: {client_ip}")
            return jsonify({"msg": "Données JSON requises"}), 400
            
        email = data.get('email')
        code = data.get('code')
        new_password = data.get('new_password')

        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔐 Réinitialisation pour: {email}")

        if not all([email, code, new_password]):
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⚠️ ÉCHEC - Données manquantes - Email: {email} - IP: {client_ip}")
            return jsonify({"msg": "Email, code et nouveau mot de passe requis"}), 400

        admin = Utilisateur.query.filter_by(email=email, role='admin').first()

        if not admin:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ ÉCHEC - Email admin inexistant: {email} - IP: {client_ip}")
            return jsonify({"msg": "Action non autorisée"}), 404
        
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 👤 Compte trouvé - ID: {admin.id}")
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔍 Vérification code pour: {email}")
            
        if admin.token_verification == code:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ Code correct - Mise à jour mot de passe")
            admin.set_password(new_password)
            admin.token_verification = None
            db.session.commit()
            
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ SUCCÈS - Mot de passe mis à jour pour {email} - ID: {admin.id} - IP: {client_ip}")
            return jsonify({"msg": "Votre mot de passe a été mis à jour avec succès."}), 200
        else:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ ÉCHEC - Code incorrect pour {email} - Code fourni: {code} - IP: {client_ip}")
            return jsonify({"msg": "Le code de vérification est invalide ou a expiré."}), 400
            
    except Exception as e:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ ERREUR CRITIQUE - IP: {client_ip} - {str(e)}")
        return jsonify({"msg": "Erreur serveur lors de la réinitialisation"}), 500
    
    finally:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🏁 FIN - IP: {client_ip}")

@auth_bp.route('/admin/refresh', methods=['POST'])
@jwt_required(refresh=True)
def admin_refresh():
    """
    Route pour rafraîchir le token d'accès admin.
    """
    current_user_id = get_jwt_identity()
    new_access_token = create_access_token(identity=current_user_id)
    return jsonify(access_token=new_access_token)

# --- ROUTES POUR LES CLIENTS (À DÉVELOPPER PLUS TARD) ---
# ...
# Les routes pour l'inscription et la connexion des clients seront ici
# et suivront une logique similaire mais avec `role='client'`.
# ...

