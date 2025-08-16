# app/checkout/routes.py

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from decimal import Decimal

from app.extensions import db
from app.models import Utilisateur, Panier, Produit, AdresseLivraison, ZoneLivraison, Coupon, Commande, DetailsCommande
from app.schemas import commande_schema

checkout_bp = Blueprint('checkout', __name__)

@checkout_bp.route('/place-order', methods=['POST'])
@jwt_required()
def place_order():
    user_id = int(get_jwt_identity())
    user = Utilisateur.query.get_or_404(user_id)
    data = request.get_json()

    required_fields = ['nom_destinataire', 'telephone_destinataire', 'zone_livraison_id', 'type_adresse', 'description_adresse']
    if not all(field in data for field in required_fields):
        return jsonify({"msg": "Données de livraison incomplètes"}), 400

    cart_items = Panier.query.filter_by(utilisateur_id=user.id).all()
    if not cart_items:
        return jsonify({"msg": "Votre panier est vide"}), 400

    try:
        # --- CORRECTION : 'zone_livraison_id' est retiré de la création de l'adresse ---
        new_address = AdresseLivraison(
            utilisateur_id=user.id,
            nom_destinataire=data['nom_destinataire'],
            telephone_destinataire=data['telephone_destinataire'],
            type_adresse=data['type_adresse'],
            ville=data.get('ville'),
            quartier=data.get('quartier'),
            description_adresse=data['description_adresse'],
            point_repere=data.get('point_repere'),
            latitude=data.get('latitude'),
            longitude=data.get('longitude')
        )
        db.session.add(new_address)
        db.session.flush()

        sous_total = Decimal(0)
        for item in cart_items:
            if item.produit.gestion_stock == 'limite' and item.quantite > item.produit.stock_disponible:
                raise ValueError(f"Stock insuffisant pour le produit : {item.produit.nom}")
            sous_total += item.produit.prix_unitaire * item.quantite

        # Frais de livraison (utilisé ici, mais pas stocké dans l'adresse)
        zone = ZoneLivraison.query.get(data['zone_livraison_id'])
        if not zone or not zone.actif:
            raise ValueError("Zone de livraison invalide ou inactive")
        frais_livraison = zone.tarif_livraison

        montant_reduction = Decimal(0)
        coupon = None
        if data.get('coupon_code'):
            coupon = Coupon.query.filter_by(code=data['coupon_code'], statut='actif').first()
            if coupon:
                if coupon.montant_minimum_commande and sous_total < coupon.montant_minimum_commande:
                    raise ValueError("Le montant minimum n'est pas atteint pour ce coupon.")
                
                if coupon.type_reduction == 'pourcentage':
                    montant_reduction = (sous_total * coupon.valeur_reduction) / 100
                else:
                    montant_reduction = coupon.valeur_reduction
        
        total = (sous_total - montant_reduction) + frais_livraison
        total = max(total, Decimal(0))

        new_order = Commande(
            utilisateur_id=user.id,
            adresse_livraison_id=new_address.id,
            sous_total=sous_total,
            frais_livraison=frais_livraison,
            montant_reduction=montant_reduction,
            total=total,
            coupon_id=coupon.id if coupon else None,
            statut='en_attente',
            statut_paiement='en_attente',
            notes_client=data.get('notes_client')
        )
        db.session.add(new_order)
        db.session.flush()

        for item in cart_items:
            detail = DetailsCommande(
                commande_id=new_order.id,
                produit_id=item.produit_id,
                quantite=item.quantite,
                prix_unitaire=item.produit.prix_unitaire,
                sous_total=item.produit.prix_unitaire * item.quantite
            )
            db.session.add(detail)
            
            if item.produit.gestion_stock == 'limite':
                item.produit.stock_disponible -= item.quantite

        Panier.query.filter_by(utilisateur_id=user.id).delete()
        db.session.commit()
        
        current_app.logger.info(f"Commande {new_order.numero_commande} créée avec succès pour l'utilisateur ID {user_id}.")
        
        return jsonify({
            "message": "Commande créée avec succès. En attente de paiement.",
            "commande": {
                "numero_commande": new_order.numero_commande,
                "total": str(new_order.total)
            }
        }), 201

    except ValueError as e:
        db.session.rollback()
        return jsonify({"msg": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur lors de la création de la commande: {str(e)}", exc_info=True)
        return jsonify({"msg": "Une erreur interne est survenue"}), 500
