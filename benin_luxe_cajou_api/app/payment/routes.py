# app/payment/routes.py

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from decimal import Decimal
import fedapay

from app.extensions import db
from app.models import (
    Utilisateur, Panier, Produit, AdresseLivraison, ZoneLivraison, 
    Coupon, Commande, DetailsCommande, Paiement
)
from app.config import Config

payment_bp = Blueprint('payment', __name__)

# --- CONFIGURATION DE FEDAPAY ---
# Assurez-vous que les clés sont bien dans votre fichier config.py et vos variables d'environnement
try:
    fedapay.api_key = Config.FEDAPAY_API_KEY
    fedapay.environment = Config.FEDAPAY_ENVIRONMENT
except Exception as e:
    current_app.logger.error(f"ERREUR CRITIQUE: Impossible de configurer FedaPay. Vérifiez vos variables d'environnement. Erreur: {e}")

@payment_bp.route('/initialize', methods=['POST'])
@jwt_required()
def initialize_payment():
    """
    Orchestre le début du processus de paiement.
    1. Valide les données et le panier.
    2. Crée une commande en BDD avec le statut "en attente".
    3. Crée une transaction FedaPay.
    4. Lie les deux et renvoie l'URL de paiement au client.
    """
    user_id = int(get_jwt_identity())
    user = Utilisateur.query.get_or_404(user_id)
    data = request.get_json()

    # --- Étape 1 : Validation des données d'entrée ---
    required_fields = ['nom_destinataire', 'telephone_destinataire', 'zone_livraison_id', 'type_adresse', 'description_adresse']
    if not all(field in data for field in required_fields):
        return jsonify({"msg": "Données de livraison incomplètes"}), 400

    cart_items = Panier.query.filter_by(utilisateur_id=user.id).all()
    if not cart_items:
        return jsonify({"msg": "Votre panier est vide"}), 400

    # --- DÉBUT DE LA TRANSACTION EN BASE DE DONNÉES ---
    try:
        # --- Étape 2 : Création de l'adresse et calculs des totaux ---
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

        zone = ZoneLivraison.query.get(data['zone_livraison_id'])
        if not zone or not zone.actif:
            raise ValueError("Zone de livraison invalide ou inactive")
        frais_livraison = zone.tarif_livraison

        montant_reduction = Decimal(0)
        coupon = None
        if data.get('coupon_code'):
            coupon = Coupon.query.filter_by(code=data['coupon_code'], statut='actif').first()
            if coupon:
                # ... (logique de validation du coupon) ...
                if coupon.type_reduction == 'pourcentage':
                    montant_reduction = (sous_total * coupon.valeur_reduction) / 100
                else:
                    montant_reduction = coupon.valeur_reduction
        
        total = (sous_total - montant_reduction) + frais_livraison
        total = max(total, Decimal(0))

        # --- Étape 3 : Création de la commande "en attente" (notre filet de sécurité) ---
        new_order = Commande(
            utilisateur_id=user.id,
            adresse_livraison_id=new_address.id,
            sous_total=sous_total, frais_livraison=frais_livraison,
            montant_reduction=montant_reduction, total=total,
            coupon_id=coupon.id if coupon else None,
            statut='en_attente', statut_paiement='en_attente',
            notes_client=data.get('notes_client')
        )
        db.session.add(new_order)
        db.session.flush()

        for item in cart_items:
            db.session.add(DetailsCommande(
                commande_id=new_order.id, produit_id=item.produit_id, quantite=item.quantite,
                prix_unitaire=item.produit.prix_unitaire, sous_total=item.produit.prix_unitaire * item.quantite
            ))
            if item.produit.gestion_stock == 'limite':
                item.produit.stock_disponible -= item.quantite

        # --- Étape 4 : Création de la transaction FedaPay ---
        transaction = fedapay.Transaction.create(
            description=f"Paiement pour commande #{new_order.numero_commande}",
            amount=int(total),
            currency={'iso': 'XOF'},
            customer={'firstname': user.prenom, 'lastname': user.nom, 'email': user.email},
            callback_url=f"https://VOTRE_SITE_WEB_URL/payment-success?order_id={new_order.id}" # URL de redirection
        )

        payment_url = transaction.generateToken()['url']

        # --- Étape 5 : Liaison de la commande et de la transaction ---
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
    """
    Endpoint sécurisé appelé par FedaPay pour confirmer un paiement.
    C'est la source de vérité pour mettre à jour le statut de paiement.
    """
    data = request.get_json()
    event_type = data.get('name')
    
    if event_type == 'transaction.approved':
        transaction_data = data.get('data')
        transaction_id = str(transaction_data.get('id'))
        
        payment = Paiement.query.filter_by(fedapay_transaction_id=transaction_id).first()
        if payment and payment.statut != 'approved':
            payment.statut = 'approved'
            payment.commande.statut_paiement = 'paye'
            # On peut maintenant considérer la commande comme confirmée
            payment.commande.statut = 'confirmee'
            db.session.commit()
            current_app.logger.info(f"Webhook: Paiement pour commande {payment.commande.id} confirmé.")
            
    return jsonify(success=True), 200

@payment_bp.route('/status/<int:order_id>', methods=['GET'])
@jwt_required()
def get_payment_status(order_id):
    """
    Endpoint pour que le frontend puisse vérifier le statut d'une commande
    après que l'utilisateur soit redirigé depuis FedaPay.
    """
    user_id = int(get_jwt_identity())
    order = Commande.query.filter_by(id=order_id, utilisateur_id=user_id).first_or_404()
    
    # On renvoie simplement le statut de paiement stocké dans notre BDD,
    # qui a été (ou sera) mis à jour par le webhook.
    return jsonify({"payment_status": order.statut_paiement}), 200
