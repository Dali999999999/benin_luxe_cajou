# app/cart/routes.py

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity # On importe jwt_required
from app.models import Panier, Produit
from app.extensions import db
from app.schemas import paniers_schema

cart_bp = Blueprint('cart', __name__)

# --- CORRECTION : On utilise le décorateur jwt_required(optional=True) ---
@cart_bp.route('/', methods=['POST'])
@jwt_required(optional=True) 
def handle_cart():
    """
    Route unifiée et robuste pour gérer toutes les opérations du panier.
    Grâce à @jwt_required(optional=True), elle accepte les requêtes avec ou sans token.
    """
    try:
        # --- CORRECTION : get_jwt_identity() est maintenant appelé sans argument ---
        # Il retournera l'ID si le token est valide, sinon None.
        user_id = get_jwt_identity()
        data = request.get_json()

        session_id = data.get('session_id') if not user_id else None

        if not user_id and not session_id:
            return jsonify({"msg": "Identification requise (Token JWT ou session_id)"}), 401

        filter_criteria = {'utilisateur_id': user_id} if user_id else {'session_id': session_id}
        
        if 'product_id' in data:
            product_id = data.get('product_id')
            quantity = data.get('quantity', 1)

            if not isinstance(quantity, int):
                return jsonify({"msg": "La quantité doit être un nombre entier"}), 400

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
            else:
                if cart_item:
                    db.session.delete(cart_item)
                    db.session.commit()
                return jsonify({"msg": f"'{produit.nom}' a été retiré du panier."}), 200
        else:
            cart_items = Panier.query.filter_by(**filter_criteria).all()
            return jsonify(paniers_schema.dump(cart_items)), 200

    except Exception as e:
        current_app.logger.error(f"Erreur inattendue dans la gestion du panier: {str(e)}", exc_info=True)
        return jsonify({"error": "Une erreur interne est survenue"}), 500
