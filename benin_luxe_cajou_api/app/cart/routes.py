# app/cart/routes.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import Panier, Produit
from app.extensions import db
from app.schemas import paniers_schema

cart_bp = Blueprint('cart', __name__)

@cart_bp.route('/', methods=['GET'])
@jwt_required()
def get_cart():
    """
    Récupère le contenu complet du panier de l'utilisateur connecté.
    """
    user_id = get_jwt_identity()
    cart_items = Panier.query.filter_by(utilisateur_id=user_id).all()
    return jsonify(paniers_schema.dump(cart_items)), 200

@cart_bp.route('/add', methods=['POST'])
@jwt_required()
def add_to_cart():
    """
    Ajoute un produit au panier ou incrémente sa quantité.
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)

    if not product_id:
        return jsonify({"msg": "ID du produit manquant"}), 400

    # Vérifier que le produit existe et est actif
    produit = Produit.query.filter_by(id=product_id, statut='actif').first()
    if not produit:
        return jsonify({"msg": "Produit non trouvé ou inactif"}), 404
        
    # Vérifier si le produit est déjà dans le panier
    cart_item = Panier.query.filter_by(utilisateur_id=user_id, produit_id=product_id).first()
    
    if cart_item:
        # Si oui, on augmente la quantité
        cart_item.quantite += quantity
    else:
        # Sinon, on crée une nouvelle entrée
        cart_item = Panier(utilisateur_id=user_id, produit_id=product_id, quantite=quantity)
        db.session.add(cart_item)
        
    db.session.commit()
    
    return jsonify({"msg": f"'{produit.nom}' a été ajouté au panier."}), 200
