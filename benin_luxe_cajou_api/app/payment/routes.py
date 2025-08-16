# app/payment/routes.py

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from decimal import Decimal
# --- CORRECTION : On importe l'objet Transaction depuis le bon sous-module ---
from fedapay import Transaction, ApiKey
import fedapay

from app.extensions import db
from app.models import (
    Utilisateur, Panier, Produit, AdresseLivraison, ZoneLivraison, 
    Coupon, Commande, DetailsCommande, Paiement
)
from app.config import Config

payment_bp = Blueprint('payment', __name__)

# --- CONFIGURATION DE FEDAPAY ---
try:
    # --- CORRECTION : On utilise ApiKey.set pour configurer la clé ---
    ApiKey.set(Config.FEDAPAY_API_KEY)
    fedapay.environment = Config.FEDAPAY_ENVIRONMENT
except Exception as e:
    current_app.logger.error(f"ERREUR CRITIQUE: Impossible de configurer FedaPay. Vérifiez vos variables d'environnement. Erreur: {e}")

@payment_bp.route('/initialize', methods=['POST'])
@jwt_required()
def initialize_payment():
    user_id = int(get_jwt_identity())
    user = Utilisateur.query.get_or_404(user_id)
    data = request.get_json()
    
    # ... (La logique de validation des données, de création d'adresse et de calcul des totaux reste la même) ...
    # ... Elle est correcte, donc je la garde telle quelle. ...
    required_fields = ['nom_destinataire', 'telephone_destinataire', 'zone_livraison_id', 'type_adresse', 'description_adresse']
    if not all(field in data for field in required_fields):
        return jsonify({"msg": "Données de livraison incomplètes"}), 400
    cart_items = Panier.query.filter_by(utilisateur_id=user.id).all()
    if not cart_items:
        return jsonify({"msg": "Votre panier est vide"}), 400
    try:
        new_address = AdresseLivraison(...) # Remplir avec les champs de data
        db.session.add(new_address)
        db.session.flush()
        sous_total = Decimal(0)
        for item in cart_items:
            if item.produit.gestion_stock == 'limite' and item.quantite > item.produit.stock_disponible:
                raise ValueError(f"Stock insuffisant pour le produit : {item.produit.nom}")
            sous_total += item.produit.prix_unitaire * item.quantite
        zone = ZoneLivraison.query.get(data['zone_livraison_id'])
        if not zone or not zone.actif:
            raise ValueError("Zone de livraison invalide ou inactive")
        frais_livraison = zone.tarif_livraison
        montant_reduction = Decimal(0)
        coupon = None
        if data.get('coupon_code'):
            coupon = Coupon.query.filter_by(code=data['coupon_code'], statut='actif').first()
            if coupon:
                if coupon.type_reduction == 'pourcentage':
                    montant_reduction = (sous_total * coupon.valeur_reduction) / 100
                else:
                    montant_reduction = coupon.valeur_reduction
        total = (sous_total - montant_reduction) + frais_livraison
        total = max(total, Decimal(0))
        new_order = Commande(...) # Remplir avec les champs
        db.session.add(new_order)
        db.session.flush()
        for item in cart_items:
            db.session.add(DetailsCommande(...)) # Remplir avec les champs
            if item.produit.gestion_stock == 'limite':
                item.produit.stock_disponible -= item.quantite

        # --- CORRECTION DE L'APPEL À FEDAPAY ---
        transaction = Transaction.create(
            description=f"Paiement pour commande #{new_order.numero_commande}",
            amount=int(total),
            currency={'iso': 'XOF'},
            customer={'firstname': user.prenom, 'lastname': user.nom, 'email': user.email},
            callback_url=f"https://VOTRE_SITE_WEB_URL/payment-success?order_id={new_order.id}"
        )

        payment_url = transaction.generateToken()['url']

        db.session.add(Paiement(
            commande_id=new_order.id, fedapay_transaction_id=str(transaction.id),
            montant=total, statut='pending'
        ))
        
        Panier.query.filter_by(utilisateur_id=user.id).delete()
        db.session.commit()

        current_app.logger.info(f"Transaction FedaPay {transaction.id} créée pour la commande {new_order.numero_commande}.")
        return jsonify({"payment_url": payment_url}), 201

    except ValueError as e:
        db.session.rollback()
        return jsonify({"msg": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur lors de l'initialisation du paiement: {str(e)}", exc_info=True)
        return jsonify({"msg": "Une erreur interne est survenue"}), 500

@payment_bp.route('/webhook', methods=['POST'])
def fedapay_webhook():
    data = request.get_json()
    event_type = data.get('name')
    if event_type == 'transaction.approved':
        transaction_data = data.get('data')
        transaction_id = str(transaction_data.get('id'))
        payment = Paiement.query.filter_by(fedapay_transaction_id=transaction_id).first()
        if payment and payment.statut != 'approved':
            payment.statut = 'approved'
            payment.commande.statut_paiement = 'paye'
            payment.commande.statut = 'confirmee'
            db.session.commit()
    return jsonify(success=True), 200

@payment_bp.route('/status/<int:order_id>', methods=['GET'])
@jwt_required()
def get_payment_status(order_id):
    user_id = int(get_jwt_identity())
    order = Commande.query.filter_by(id=order_id, utilisateur_id=user_id).first_or_404()
    
    # Pour une vérification active, on peut aussi interroger FedaPay ici
    payment = Paiement.query.filter_by(commande_id=order.id).first()
    if payment:
        try:
            transaction = Transaction.retrieve(int(payment.fedapay_transaction_id))
            if transaction.status == 'approved' and order.statut_paiement != 'paye':
                 # Mise à jour si le webhook n'est pas encore arrivé
                 order.statut_paiement = 'paye'
                 order.statut = 'confirmee'
                 payment.statut = 'approved'
                 db.session.commit()
        except Exception:
            pass # On ne bloque pas si l'appel FedaPay échoue

    return jsonify({"payment_status": order.statut_paiement}), 200
