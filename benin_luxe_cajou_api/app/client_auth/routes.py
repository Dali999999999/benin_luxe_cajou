# app/client_auth/routes.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from app.models import Utilisateur, Panier
from app.extensions import db

client_auth_bp = Blueprint('client_auth', __name__)

def merge_guest_cart_to_user(user_id, session_id):
    """
    Fonction utilitaire pour fusionner le panier invité avec le panier de l'utilisateur.
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
        else:
            # Sinon, on transfère l'item en changeant le propriétaire
            guest_item.session_id = None
            guest_item.utilisateur_id = user_id
    
    # On supprime les items invités qui ont été fusionnés (ceux qui n'ont pas été transférés)
    for item in guest_cart_items:
        if item.session_id is not None:
             db.session.delete(item)

    db.session.commit()

@client_auth_bp.route('/register', methods=['POST'])
def client_register():
    data = request.get_json()
    # ... (les vérifications de champs restent les mêmes) ...
    nom = data.get('nom')
    prenom = data.get('prenom')
    email = data.get('email')
    password = data.get('password')
    session_id = data.get('session_id') # <<< NOUVEAU

    if not all([nom, prenom, email, password]):
        return jsonify({"msg": "Nom, prénom, email et mot de passe sont requis"}), 400
    if Utilisateur.query.filter_by(email=email).first():
        return jsonify({"msg": "Un compte existe déjà avec cet email"}), 409

    new_client = Utilisateur(nom=nom, prenom=prenom, email=email, role='client', email_verifie=True)
    new_client.set_password(password)
    
    db.session.add(new_client)
    db.session.commit() # On commit pour obtenir l'ID du nouvel utilisateur
    
    # --- LOGIQUE DE FUSION ---
    merge_guest_cart_to_user(new_client.id, session_id)
    
    access_token = create_access_token(identity=new_client.id)
    return jsonify(access_token=access_token), 201

@client_auth_bp.route('/login', methods=['POST'])
def client_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    session_id = data.get('session_id') # <<< NOUVEAU

    if not email or not password:
        return jsonify({"msg": "Email et mot de passe requis"}), 400

    user = Utilisateur.query.filter_by(email=email).first()

    if user and user.check_password(password):
        if user.statut != 'actif':
            return jsonify({"msg": "Votre compte est inactif ou suspendu."}), 403
        
        # --- LOGIQUE DE FUSION ---
        merge_guest_cart_to_user(user.id, session_id)
        
        access_token = create_access_token(identity=user.id)
        return jsonify(access_token=access_token)
    
    return jsonify({"msg": "Email ou mot de passe incorrect"}), 401
