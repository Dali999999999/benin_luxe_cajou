# app/client_auth/routes.py

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token
from flask_mail import Message
import secrets

from app.models import Utilisateur, Panier
from app.extensions import db, mail

client_auth_bp = Blueprint('client_auth', __name__)


# --- FONCTIONS UTILITAIRES LOCALES À CE FICHIER ---

def send_verification_email(user_email, code, subject):
    """
    Fonction locale pour envoyer un code de vérification par email.
    """
    try:
        msg = Message(subject=subject,
                      recipients=[user_email],
                      html=f"""
                      <p>Bonjour,</p>
                      <p>Voici votre code de vérification pour Benin Luxe Cajou :</p>
                      <h2 style='text-align: center; color: #333;'>{code}</h2>
                      <p>Ce code est valable pour une durée limitée. Ne le partagez avec personne.</p>
                      """)
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Erreur lors de l'envoi de l'email à {user_email}: {e}")
        return False

def merge_guest_cart_to_user(user_id, session_id):
    """
    Fonction locale pour fusionner le panier invité avec le panier de l'utilisateur.
    """
    if not session_id:
        return

    guest_cart_items = Panier.query.filter_by(session_id=session_id).all()
    if not guest_cart_items:
        return

    for guest_item in guest_cart_items:
        user_item = Panier.query.filter_by(utilisateur_id=user_id, produit_id=guest_item.produit_id).first()
        
        if user_item:
            # Si l'utilisateur avait déjà ce produit, on additionne les quantités
            user_item.quantite += guest_item.quantite
            # On supprime l'ancien item invité car il a été fusionné
            db.session.delete(guest_item)
        else:
            # Sinon, on transfère l'item en changeant le propriétaire
            guest_item.session_id = None
            guest_item.utilisateur_id = user_id
    
    db.session.commit()


# --- ROUTES D'AUTHENTIFICATION CLIENT ---

@client_auth_bp.route('/register', methods=['POST'])
def client_register():
    """
    Étape 1: Inscription du client. Crée un compte inactif et envoie un code.
    """
    data = request.get_json()
    nom, prenom, email, password = data.get('nom'), data.get('prenom'), data.get('email'), data.get('password')

    if not all([nom, prenom, email, password]):
        return jsonify({"msg": "Tous les champs sont requis"}), 400
    if Utilisateur.query.filter_by(email=email).first():
        return jsonify({"msg": "Un compte existe déjà avec cet email"}), 409

    new_client = Utilisateur(
        nom=nom,
        prenom=prenom,
        email=email,
        role='client',
        email_verifie=False
    )
    new_client.set_password(password)
    
    verification_code = str(secrets.randbelow(900000) + 100000)
    new_client.token_verification = verification_code
    
    db.session.add(new_client)
    db.session.commit()
    
    send_verification_email(new_client.email, verification_code, "Activez votre compte Benin Luxe Cajou")

    return jsonify({"msg": "Compte créé. Un code de vérification a été envoyé à votre adresse email."}), 201

@client_auth_bp.route('/verify-account', methods=['POST'])
def client_verify_account():
    """
    Étape 2: Vérification du compte. Active le compte, fusionne le panier et renvoie le token.
    """
    data = request.get_json()
    email = data.get('email')
    code = data.get('code')
    session_id = data.get('session_id')

    if not email or not code:
        return jsonify({"msg": "Email et code requis"}), 400

    user = Utilisateur.query.filter_by(email=email, role='client').first()

    if not user:
        return jsonify({"msg": "Utilisateur non trouvé"}), 404
    if user.email_verifie:
        return jsonify({"msg": "Compte déjà vérifié"}), 400

    if user.token_verification == code:
        user.email_verifie = True
        user.token_verification = None
        db.session.commit()

        merge_guest_cart_to_user(user.id, session_id)
        
        access_token = create_access_token(identity=str(user.id))
        return jsonify(access_token=access_token), 200
    else:
        return jsonify({"msg": "Code de vérification incorrect"}), 400

@client_auth_bp.route('/login', methods=['POST'])
def client_login():
    """
    Connexion du client. Fusionne le panier et renvoie le token.
    """
    data = request.get_json()
    email, password, session_id = data.get('email'), data.get('password'), data.get('session_id')

    if not email or not password:
        return jsonify({"msg": "Email et mot de passe requis"}), 400

    user = Utilisateur.query.filter_by(email=email).first()

    if user and user.check_password(password):
        if not user.email_verifie:
            # On pourrait ici proposer de renvoyer un code si besoin
            return jsonify({"msg": "Votre compte n'est pas encore vérifié. Veuillez vérifier vos emails."}), 403
        if user.statut != 'actif':
            return jsonify({"msg": "Votre compte est inactif ou suspendu."}), 403
        
        merge_guest_cart_to_user(user.id, session_id)
        
        access_token = create_access_token(identity=str(user.id))
        return jsonify(access_token=access_token)
    
    return jsonify({"msg": "Email ou mot de passe incorrect"}), 401

@client_auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification_code():
    """
    Renvoie un nouveau code de vérification à un utilisateur non encore vérifié.
    """
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({"msg": "Email requis"}), 400
        
    user = Utilisateur.query.filter_by(email=email, role='client').first()

    # On ne renvoie pas d'erreur si l'utilisateur n'existe pas ou est déjà vérifié
    # pour des raisons de sécurité (éviter l'énumération d'emails).
    if user and not user.email_verifie:
        verification_code = str(secrets.randbelow(900000) + 100000)
        user.token_verification = verification_code
        db.session.commit()
        send_verification_email(user.email, verification_code, "Votre nouveau code de vérification")

    return jsonify({"msg": "Si un compte non vérifié est associé à cet email, un nouveau code a été envoyé."}), 200

@client_auth_bp.route('/forgot-password', methods=['POST'])
def client_forgot_password():
    """
    Étape 1: Le client entre son email pour recevoir un code de réinitialisation.
    """
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({"msg": "Email requis"}), 400
        
    user = Utilisateur.query.filter_by(email=email, role='client').first()

    # Pour des raisons de sécurité, on renvoie toujours un message de succès
    # pour ne pas révéler si un email existe dans la base de données.
    if user:
        verification_code = str(secrets.randbelow(900000) + 100000)
        user.token_verification = verification_code
        db.session.commit()
        send_verification_email(user.email, verification_code, "Réinitialisation de votre mot de passe")

    return jsonify({"msg": "Si un compte est associé à cet email, un code de réinitialisation a été envoyé."}), 200


@client_auth_bp.route('/reset-password', methods=['POST'])
def client_reset_password():
    """
    Étape 2: Le client fournit le code et son nouveau mot de passe pour finaliser la réinitialisation.
    """
    data = request.get_json()
    email = data.get('email')
    code = data.get('code')
    new_password = data.get('new_password')

    if not all([email, code, new_password]):
        return jsonify({"msg": "Email, code et nouveau mot de passe requis"}), 400

    user = Utilisateur.query.filter_by(email=email, role='client').first()

    # On vérifie que l'utilisateur existe et que le code est correct
    if user and user.token_verification == code:
        user.set_password(new_password)
        user.token_verification = None # On nettoie le token après usage
        db.session.commit()
        return jsonify({"msg": "Votre mot de passe a été mis à jour avec succès. Vous pouvez maintenant vous connecter."}), 200
    else:
        # Message d'erreur générique pour la sécurité
        return jsonify({"msg": "Le code de vérification est invalide ou a expiré."}), 400
