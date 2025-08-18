# app/user_profile/routes.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import Utilisateur, AdresseLivraison, Commande
from app.extensions import db
from app.schemas import (
    utilisateur_schema, 
    adresses_livraison_schema,
    commandes_summary_schema,
    commande_detail_schema
)

user_profile_bp = Blueprint('user_profile', __name__)

# --- GESTION DU PROFIL PRINCIPAL ---

@user_profile_bp.route('/', methods=['GET'])
@jwt_required()
def get_profile():
    """
    Récupère les informations de base de l'utilisateur connecté.
    """
    # On s'attend à recevoir l'ID sous forme de string, on le convertit en entier
    user_id = int(get_jwt_identity())
    user = Utilisateur.query.get_or_404(user_id)
    return jsonify(utilisateur_schema.dump(user)), 200

@user_profile_bp.route('/', methods=['PUT'])
@jwt_required()
def update_profile():
    """
    Met à jour les informations de base de l'utilisateur (nom, prénom, téléphone).
    """
    # On s'attend à recevoir l'ID sous forme de string, on le convertit en entier
    user_id = int(get_jwt_identity())
    user = Utilisateur.query.get_or_404(user_id)
    data = request.get_json()

    # On ne met à jour que les champs fournis
    user.nom = data.get('nom', user.nom)
    user.prenom = data.get('prenom', user.prenom)
    user.telephone = data.get('telephone', user.telephone)
    
    db.session.commit()
    return jsonify(utilisateur_schema.dump(user)), 200

@user_profile_bp.route('/password', methods=['PUT'])
@jwt_required()
def update_password():
    """
    Met à jour le mot de passe de l'utilisateur.
    Nécessite l'ancien mot de passe pour des raisons de sécurité.
    """
    # On s'attend à recevoir l'ID sous forme de string, on le convertit en entier
    user_id = int(get_jwt_identity())
    user = Utilisateur.query.get_or_404(user_id)
    data = request.get_json()
    old_password = data.get('old_password')
    new_password = data.get('new_password')

    if not old_password or not new_password:
        return jsonify({"msg": "Ancien et nouveau mots de passe requis"}), 400

    if not user.check_password(old_password):
        return jsonify({"msg": "L'ancien mot de passe est incorrect"}), 401

    user.set_password(new_password)
    db.session.commit()
    
    return jsonify({"msg": "Mot de passe mis à jour avec succès"}), 200

# --- GESTION DES DONNÉES LIÉES ---

@user_profile_bp.route('/addresses', methods=['GET'])
@jwt_required()
def get_user_addresses():
    """
    Récupère la liste des adresses de livraison de l'utilisateur connecté.
    """
    # On s'attend à recevoir l'ID sous forme de string, on le convertit en entier
    user_id = int(get_jwt_identity())
    addresses = AdresseLivraison.query.filter_by(utilisateur_id=user_id).all()
    return jsonify(adresses_livraison_schema.dump(addresses)), 200

@user_profile_bp.route('/orders', methods=['GET'])
@jwt_required()
def get_user_orders():
    """
    Récupère l'historique des commandes de l'utilisateur connecté.
    """
    # On s'attend à recevoir l'ID sous forme de string, on le convertit en entier
    user_id = int(get_jwt_identity())
    orders = Commande.query.filter_by(utilisateur_id=user_id).order_by(Commande.date_commande.desc()).all()
    return jsonify(commandes_summary_schema.dump(orders)), 200

@user_profile_bp.route('/orders/<int:order_id>', methods=['GET'])
@jwt_required()
def get_order_details(order_id):
    """
    Récupère les détails complets d'une seule commande, incluant
    les produits, l'adresse de livraison et le suivi.
    """
    user_id = int(get_jwt_identity())
    
    # Requête sécurisée : on vérifie que la commande existe ET qu'elle appartient bien à l'utilisateur connecté.
    order = Commande.query.filter_by(id=order_id, utilisateur_id=user_id).first_or_404()
    
    return jsonify(commande_detail_schema.dump(order)), 200
