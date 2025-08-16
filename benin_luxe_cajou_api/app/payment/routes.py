# app/payment/routes.py

import requests
import json
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from decimal import Decimal

from app.extensions import db
from app.models import (
    Utilisateur, Panier, Produit, AdresseLivraison, ZoneLivraison, 
    Coupon, Commande, DetailsCommande, Paiement
)
from config import Config

payment_bp = Blueprint('payment', __name__)

class FedaPayClient:
    """Client pour l'API FedaPay"""
    
    def __init__(self, api_key, environment='sandbox'):
        self.api_key = api_key
        self.environment = environment
        # URLs correctes pour FedaPay
        if environment == 'sandbox':
            self.base_url = 'https://sandbox-api.fedapay.com'
        else:
            self.base_url = 'https://api.fedapay.com'
            
        # Format d'authentification correct
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'FedaPay-Python-Client/1.0'
        }
    
    def _log_info(self, message):
        """Log sécurisé qui fonctionne avec ou sans contexte Flask"""
        try:
            current_app.logger.info(message)
        except RuntimeError:
            # Si pas de contexte Flask, utiliser print pour débugger
            print(f"[INFO] {message}")
    
    def _log_error(self, message):
        """Log sécurisé qui fonctionne avec ou sans contexte Flask"""
        try:
            current_app.logger.error(message)
        except RuntimeError:
            # Si pas de contexte Flask, utiliser print pour débugger
            print(f"[ERROR] {message}")
    
    def create_transaction(self, data):
        """Créer une transaction"""
        url = f"{self.base_url}/v1/transactions"
        
        self._log_info(f"Tentative de création de transaction sur: {url}")
        
        try:
            response = requests.post(url, headers=self.headers, json=data, timeout=30)
            self._log_info(f"Réponse FedaPay: Status {response.status_code}")
            
            # Log du contenu de l'erreur pour diagnostic
            if response.status_code != 200:
                self._log_error(f"Erreur FedaPay - Status: {response.status_code}, Response: {response.text}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            self._log_error(f"Erreur lors de l'appel FedaPay API: {str(e)}")
            raise
    
    def get_transaction(self, transaction_id):
        """Récupérer une transaction"""
        url = f"{self.base_url}/v1/transactions/{transaction_id}"
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self._log_error(f"Erreur lors de la récupération de transaction {transaction_id}: {str(e)}")
            raise
    
    def generate_token(self, transaction_id):
        """Générer le token de paiement"""
        url = f"{self.base_url}/v1/transactions/{transaction_id}/token"
        try:
            response = requests.post(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self._log_error(f"Erreur lors de la génération du token pour {transaction_id}: {str(e)}")
            raise

# Variable globale pour le client (sera initialisée dans la route)
fedapay_client = None

def get_fedapay_client():
    """Récupère ou crée le client FedaPay de manière sécurisée"""
    global fedapay_client
    if fedapay_client is None:
        try:
            fedapay_client = FedaPayClient(
                api_key=Config.FEDAPAY_API_KEY,
                environment=Config.FEDAPAY_ENVIRONMENT
            )
        except Exception as e:
            current_app.logger.error(f"Impossible de configurer FedaPay: {e}")
            return None
    return fedapay_client

@payment_bp.route('/initialize', methods=['POST'])
@jwt_required()
def initialize_payment():
    """
    Orchestre le début du processus de paiement.
    """
    # Initialiser le client FedaPay dans le contexte de la requête
    client = get_fedapay_client()
    if not client:
        return jsonify({"msg": "Service de paiement indisponible"}), 503
        
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
        # Log de debug pour vérifier la configuration
        current_app.logger.info(f"FEDAPAY_ENVIRONMENT: {Config.FEDAPAY_ENVIRONMENT}")
        current_app.logger.info(f"FEDAPAY_API_KEY commence par: {Config.FEDAPAY_API_KEY[:15] if Config.FEDAPAY_API_KEY else 'NONE'}...")

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
                if coupon.montant_minimum_commande and sous_total < coupon.montant_minimum_commande:
                    raise ValueError("Le montant minimum n'est pas atteint pour ce coupon.")
                if coupon.type_reduction == 'pourcentage':
                    montant_reduction = (sous_total * coupon.valeur_reduction) / 100
                else:
                    montant_reduction = coupon.valeur_reduction
        
        total = (sous_total - montant_reduction) + frais_livraison
        total = max(total, Decimal(0))

        # --- Étape 3 : Création de la commande "en attente" ---
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
            db.session.add(DetailsCommande(
                commande_id=new_order.id,
                produit_id=item.produit_id,
                quantite=item.quantite,
                prix_unitaire=item.produit.prix_unitaire,
                sous_total=item.produit.prix_unitaire * item.quantite
            ))
            if item.produit.gestion_stock == 'limite':
                item.produit.stock_disponible -= item.quantite

        # --- Étape 4 : Création de la transaction FedaPay ---
        transaction_data = {
            "description": f"Paiement pour commande #{new_order.numero_commande}",
            "amount": int(total),  # Montant en centimes (XOF)
            "currency": {
                "iso": "XOF"
            },
            "callback_url": f"http://localhost:3000/payment-success?order_id={new_order.id}",
            "customer": {
                "firstname": user.prenom,
                "lastname": user.nom,
                "email": user.email,
                "phone_number": {
                    "number": data['telephone_destinataire'],
                    "country": "bj"  # Code pays pour le Bénin
                }
            }
        }

        # Créer la transaction
        transaction_response = client.create_transaction(transaction_data)
        transaction_id = transaction_response['v1/transaction']['id']
        
        # Générer le token de paiement
        token_response = client.generate_token(transaction_id)
        payment_url = token_response['url']

        # --- Étape 5 : Liaison de la commande et de la transaction ---
        db.session.add(Paiement(
            commande_id=new_order.id,
            fedapay_transaction_id=str(transaction_id),
            montant=total,
            statut='pending'
        ))
        
        Panier.query.filter_by(utilisateur_id=user.id).delete()
        db.session.commit()

        current_app.logger.info(f"Transaction FedaPay {transaction_id} créée pour la commande {new_order.numero_commande}.")
        return jsonify({"payment_url": payment_url}), 201

    except ValueError as e:
        db.session.rollback()
        return jsonify({"msg": str(e)}), 400
    except requests.exceptions.RequestException as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur FedaPay API: {str(e)}")
        return jsonify({"msg": "Erreur de communication avec le service de paiement"}), 500
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur lors de l'initialisation du paiement: {str(e)}", exc_info=True)
        return jsonify({"msg": "Une erreur interne est survenue"}), 500

@payment_bp.route('/webhook', methods=['POST'])
def fedapay_webhook():
    """Webhook pour recevoir les notifications de FedaPay"""
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
            current_app.logger.info(f"Webhook: Paiement pour commande {payment.commande.id} confirmé.")
    
    return jsonify(success=True), 200

@payment_bp.route('/status/<int:order_id>', methods=['GET'])
@jwt_required()
def get_payment_status(order_id):
    """Vérifier le statut d'un paiement"""
    client = get_fedapay_client()
    if not client:
        return jsonify({"msg": "Service de paiement indisponible"}), 503
        
    user_id = int(get_jwt_identity())
    order = Commande.query.filter_by(id=order_id, utilisateur_id=user_id).first_or_404()
    
    payment = Paiement.query.filter_by(commande_id=order.id).first()
    if payment:
        try:
            transaction_response = client.get_transaction(payment.fedapay_transaction_id)
            transaction_status = transaction_response['v1/transaction']['status']
            
            if transaction_status == 'approved' and order.statut_paiement != 'paye':
                order.statut_paiement = 'paye'
                order.statut = 'confirmee'
                payment.statut = 'approved'
                db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Erreur lors de la vérification du statut: {str(e)}")
    
    return jsonify({"payment_status": order.statut_paiement}), 200
