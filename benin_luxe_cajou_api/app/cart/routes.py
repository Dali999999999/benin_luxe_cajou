# app/cart/routes.py

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import get_jwt_identity
from app.models import Panier, Produit
from app.extensions import db
from app.schemas import paniers_schema

cart_bp = Blueprint('cart', __name__)

@cart_bp.route('/', methods=['POST'])
def handle_cart():
    """
    Route unifiée et robuste pour gérer toutes les opérations du panier.
    Elle distingue l'action à effectuer en fonction des données reçues.
    """
    try:
        # On utilise get_jwt_identity avec optional=True pour gérer les deux cas
        user_id = get_jwt_identity(optional=True)
        data = request.get_json()

        session_id = data.get('session_id') if not user_id else None

        if not user_id and not session_id:
            return jsonify({"msg": "Identification requise (Token JWT ou session_id)"}), 401

        # Détermine sur quel panier on travaille (celui de l'utilisateur ou de l'invité)
        filter_criteria = {'utilisateur_id': user_id} if user_id else {'session_id': session_id}
        
        # --- NOUVELLE LOGIQUE DE ROUTAGE ---
        # Si un product_id est fourni, c'est une opération de modification.
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
            else: # Si la quantité est 0 ou moins, on supprime
                if cart_item:
                    db.session.delete(cart_item)
                    db.session.commit()
                return jsonify({"msg": f"'{produit.nom}' a été retiré du panier."}), 200

        # Si aucun product_id n'est fourni, c'est une demande pour récupérer le panier.
        else:
            cart_items = Panier.query.filter_by(**filter_criteria).all()
            return jsonify(paniers_schema.dump(cart_items)), 200

    except Exception as e:
        # Ce bloc attrapera les erreurs inattendues et les loguera au lieu de crasher
        current_app.logger.error(f"Erreur inattendue dans la gestion du panier: {str(e)}", exc_info=True)
        return jsonify({"error": "Une erreur interne est survenue"}), 500
