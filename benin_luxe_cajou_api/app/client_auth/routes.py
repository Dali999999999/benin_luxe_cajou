# app/client_auth/routes.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from app.models import Utilisateur
from app.extensions import db

client_auth_bp = Blueprint('client_auth', __name__)

@client_auth_bp.route('/register', methods=['POST'])
def client_register():
    """
    Inscription d'un nouveau client.
    """
    data = request.get_json()
    nom = data.get('nom')
    prenom = data.get('prenom') # L'UI l'appelle "Username", ici on le mappe à "prénom"
    email = data.get('email')
    password = data.get('password')

    if not all([nom, prenom, email, password]):
        return jsonify({"msg": "Nom, prénom, email et mot de passe sont requis"}), 400

    if Utilisateur.query.filter_by(email=email).first():
        return jsonify({"msg": "Un compte existe déjà avec cet email"}), 409

    new_client = Utilisateur(
        nom=nom,
        prenom=prenom,
        email=email,
        role='client',
        email_verifie=True # On considère les clients vérifiés par défaut pour plus de simplicité
    )
    new_client.set_password(password)
    
    db.session.add(new_client)
    db.session.commit()
    
    access_token = create_access_token(identity=new_client.id)
    return jsonify(access_token=access_token), 201

@client_auth_bp.route('/login', methods=['POST'])
def client_login():
    """
    Connexion d'un client.
    """
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"msg": "Email et mot de passe requis"}), 400

    user = Utilisateur.query.filter_by(email=email).first()

    if user and user.check_password(password):
        if user.statut != 'actif':
            return jsonify({"msg": "Votre compte est inactif ou suspendu."}), 403
        
        access_token = create_access_token(identity=user.id)
        return jsonify(access_token=access_token)
    
    return jsonify({"msg": "Email ou mot de passe incorrect"}), 401
