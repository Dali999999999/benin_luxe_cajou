# app/auth/routes.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from flask_mail import Message
import secrets

from app.models import Utilisateur
from app.extensions import db, mail

auth_bp = Blueprint('auth', __name__)

# --- FONCTION UTILITAIRE POUR L'ENVOI D'EMAIL ---

def send_verification_email(user_email, code, subject):
    """
    Fonction centralisée pour envoyer un code de vérification par email.
    """
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
        return True
    except Exception as e:
        # En production, il faudrait logguer cette erreur
        print(f"Erreur lors de l'envoi de l'email : {e}")
        return False

# --- ROUTES POUR L'ADMINISTRATEUR ---

@auth_bp.route('/admin/register', methods=['POST'])
def admin_register():
    """
    Étape 1: Création du compte admin (non vérifié).
    """
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    nom = data.get('nom')
    prenom = data.get('prenom')

    if not all([email, password, nom, prenom]):
        return jsonify({"msg": "Tous les champs sont requis"}), 400

    if Utilisateur.query.filter_by(email=email).first():
        return jsonify({"msg": "Un compte existe déjà avec cet email"}), 409 # 409 Conflict

    # Création de l'utilisateur avec le rôle 'admin'
    new_admin = Utilisateur(
        email=email,
        nom=nom,
        prenom=prenom,
        role='admin',
        email_verifie=False # Le compte n'est pas actif avant vérification
    )
    new_admin.set_password(password)
    
    # Génération et stockage du code de vérification
    verification_code = str(secrets.randbelow(900000) + 100000) # Code à 6 chiffres
    new_admin.token_verification = verification_code
    
    db.session.add(new_admin)
    db.session.commit()
    
    # Envoi de l'email de vérification
    send_verification_email(new_admin.email, verification_code, "Activez votre compte Admin")

    return jsonify({"msg": "Compte Admin créé. Un code de vérification a été envoyé à votre adresse email."}), 201

@auth_bp.route('/admin/verify-account', methods=['POST'])
def admin_verify_account():
    """
    Étape 2: Vérification du compte admin avec le code reçu par email.
    """
    data = request.get_json()
    email = data.get('email')
    code = data.get('code')

    if not email or not code:
        return jsonify({"msg": "Email et code de vérification requis"}), 400

    admin = Utilisateur.query.filter_by(email=email, role='admin').first()

    if not admin:
        return jsonify({"msg": "Aucun compte admin trouvé pour cet email"}), 404
    
    if admin.email_verifie:
        return jsonify({"msg": "Ce compte est déjà vérifié"}), 400

    if admin.token_verification == code:
        admin.email_verifie = True
        admin.token_verification = None # On nettoie le token après usage
        db.session.commit()
        return jsonify({"msg": "Votre compte a été activé avec succès. Vous pouvez maintenant vous connecter."}), 200
    else:
        return jsonify({"msg": "Code de vérification incorrect"}), 400


@auth_bp.route('/admin/login', methods=['POST'])
def admin_login():
    """
    Connexion de l'administrateur.
    """
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"msg": "Email et mot de passe requis"}), 400

    admin = Utilisateur.query.filter_by(email=email, role='admin').first()

    if not admin:
        return jsonify({"msg": "Email ou mot de passe incorrect"}), 401
    
    if not admin.email_verifie:
        return jsonify({"msg": "Votre compte n'est pas encore activé. Veuillez vérifier vos emails."}), 403

    if admin.check_password(password):
        # Création du token JWT qui contient l'ID de l'admin
        access_token = create_access_token(identity=admin.id)
        return jsonify(access_token=access_token)
    
    return jsonify({"msg": "Email ou mot de passe incorrect"}), 401


@auth_bp.route('/admin/forgot-password', methods=['POST'])
def admin_forgot_password():
    """
    Étape 1 du renouvellement: L'admin renseigne son email pour recevoir un code.
    """
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({"msg": "Email requis"}), 400
        
    admin = Utilisateur.query.filter_by(email=email, role='admin').first()

    # On renvoie une réponse positive même si l'email n'existe pas
    # pour ne pas permettre de deviner les emails des admins (sécurité).
    if admin:
        verification_code = str(secrets.randbelow(900000) + 100000)
        admin.token_verification = verification_code
        db.session.commit()
        send_verification_email(admin.email, verification_code, "Réinitialisation de votre mot de passe")

    return jsonify({"msg": "Si un compte admin est associé à cet email, un code de réinitialisation a été envoyé."}), 200


@auth_bp.route('/admin/reset-password', methods=['POST'])
def admin_reset_password():
    """
    Étape 2 du renouvellement: L'admin fournit le code et son nouveau mot de passe.
    """
    data = request.get_json()
    email = data.get('email')
    code = data.get('code')
    new_password = data.get('new_password')

    if not all([email, code, new_password]):
        return jsonify({"msg": "Email, code et nouveau mot de passe requis"}), 400

    admin = Utilisateur.query.filter_by(email=email, role='admin').first()

    if not admin:
        return jsonify({"msg": "Action non autorisée"}), 404
        
    if admin.token_verification == code:
        admin.set_password(new_password)
        admin.token_verification = None # Nettoyage du token
        db.session.commit()
        return jsonify({"msg": "Votre mot de passe a été mis à jour avec succès."}), 200
    else:
        return jsonify({"msg": "Le code de vérification est invalide ou a expiré."}), 400

# --- ROUTES POUR LES CLIENTS (À DÉVELOPPER PLUS TARD) ---
# ...
# Les routes pour l'inscription et la connexion des clients seront ici
# et suivront une logique similaire mais avec `role='client'`.
# ...
