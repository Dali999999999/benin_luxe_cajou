# app/cart/routes.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import Panier, Produit
from app.extensions import db
from app.schemas import paniers_schema

cart_bp = Blueprint('cart', __name__)

@cart_bp.route('/', methods=['POST'])
def get_or_update_cart():
    """
    Route unifiée pour gérer le panier.
    - Si GET : Récupère le contenu du panier.
    - Si POST : Ajoute/met à jour un produit dans le panier.
    - Si DELETE : Supprime un produit du panier.
    Gère à la fois les utilisateurs connectés (JWT) et les invités (session_id).
    """
    user_id = get_jwt_identity(optional=True)
    data = request.get_json()
    session_id = data.get('session_id') if not user_id else None

    if not user_id and not session_id:
        return jsonify({"msg": "Identification requise (Token JWT ou session_id)"}), 401

    # Détermine le filtre à utiliser pour la base de données
    filter_criteria = {'utilisateur_id': user_id} if user_id else {'session_id': session_id}

    # --- LOGIQUE POUR AJOUTER/METTRE À JOUR UN PRODUIT ---
    if request.method == 'POST':
        product_id = data.get('product_id')
        quantity = data.get('quantity', 1)

        if not product_id or not isinstance(quantity, int):
            return jsonify({"msg": "product_id et quantity (entier) requis"}), 400

        produit = Produit.query.filter_by(id=product_id, statut='actif').first()
        if not produit:
            return jsonify({"msg": "Produit non trouvé ou inactif"}), 404
        
        cart_item = Panier.query.filter_by(**filter_criteria, produit_id=product_id).first()

        if quantity > 0:
            if cart_item:
                cart_item.quantite = quantity
            else:
                cart_item = Panier(**filter_criteria, produit_id=product_id, quantite=quantity)
                db.session.add(cart_item)
            db.session.commit()
            return jsonify({"msg": f"Panier mis à jour pour '{produit.nom}'."}), 200
        else: # Si la quantité est 0, on supprime l'article
            if cart_item:
                db.session.delete(cart_item)
                db.session.commit()
            return jsonify({"msg": f"'{produit.nom}' a été retiré du panier."}), 200

    # --- LOGIQUE POUR RÉCUPÉRER LE PANIER (implicitement GET, mais on utilise POST pour envoyer session_id) ---
    cart_items = Panier.query.filter_by(**filter_criteria).all()
    return jsonify(paniers_schema.dump(cart_items)), 200
