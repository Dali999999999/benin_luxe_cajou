# app/payment/routes.py

import requests
import json
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from decimal import Decimal
import firebase_admin
from firebase_admin import credentials, messaging
from flask_mail import Message

from app.extensions import db, mail
from app.models import (
    Utilisateur, Panier, Produit, AdresseLivraison, ZoneLivraison, 
    Coupon, Commande, DetailsCommande, Paiement
)
from config import Config

payment_bp = Blueprint('payment', __name__)

# --- CLASSES ET UTILITAIRES ---

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
            print(f"[INFO] {message}")
    
    def _log_error(self, message):
        """Log sécurisé qui fonctionne avec ou sans contexte Flask"""
        try:
            current_app.logger.error(message)
        except RuntimeError:
            print(f"[ERROR] {message}")
    
    def create_transaction(self, data):
        """Créer une transaction"""
        url = f"{self.base_url}/v1/transactions"
        
        self._log_info(f"Tentative de création de transaction sur: {url}")
        
        try:
            response = requests.post(url, headers=self.headers, json=data, timeout=30)
            self._log_info(f"Réponse FedaPay: Status {response.status_code}")
            
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

# Variables globales
fedapay_client = None
firebase_initialized = False

def initialize_services():
    """Initialise Firebase et FedaPay de manière sécurisée"""
    global fedapay_client, firebase_initialized
    
    # Initialisation Firebase
    if not firebase_initialized:
        try:
            if not firebase_admin._apps:
                cred_json = json.loads(Config.FIREBASE_SERVICE_ACCOUNT_JSON)
                cred = credentials.Certificate(cred_json)
                firebase_admin.initialize_app(cred)
                firebase_initialized = True
                current_app.logger.info("Firebase initialisé avec succès")
        except Exception as e:
            current_app.logger.error(f"Erreur lors de l'initialisation de Firebase: {e}")
    
    # Initialisation FedaPay
    if fedapay_client is None:
        try:
            fedapay_client = FedaPayClient(
                api_key=Config.FEDAPAY_API_KEY,
                environment=Config.FEDAPAY_ENVIRONMENT
            )
            current_app.logger.info("FedaPay client initialisé avec succès")
        except Exception as e:
            current_app.logger.error(f"Erreur lors de l'initialisation de FedaPay: {e}")

def get_fedapay_client():
    """Récupère le client FedaPay, l'initialise si nécessaire"""
    if fedapay_client is None:
        initialize_services()
    return fedapay_client

# --- FONCTIONS UTILITAIRES DE NOTIFICATION ---

def send_order_confirmation_email(order):
    """Envoie un email de confirmation de commande au client"""
    try:
        client = order.client if hasattr(order, 'client') else Utilisateur.query.get(order.utilisateur_id)
        
        msg = Message(
            subject=f"Confirmation de votre commande #{order.numero_commande}",
            recipients=[client.email],
            html=f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #2E7D32;">🌰 Benin Luxe Cajou</h2>
                <h3 style="color: #4CAF50;">Merci pour votre achat !</h3>
                <p>Bonjour <strong>{client.prenom}</strong>,</p>
                <p>Nous avons bien reçu votre commande <strong>#{order.numero_commande}</strong> 
                   d'un montant de <strong>{order.total} FCFA</strong>.</p>
                <div style="background-color: #f5f5f5; padding: 15px; margin: 20px 0; border-radius: 5px;">
                    <h4>Détails de la commande:</h4>
                    <p>• Sous-total: {order.sous_total} FCFA</p>
                    <p>• Frais de livraison: {order.frais_livraison} FCFA</p>
                    {f'<p>• Réduction: -{order.montant_reduction} FCFA</p>' if order.montant_reduction > 0 else ''}
                    <p><strong>Total: {order.total} FCFA</strong></p>
                </div>
                <p>Elle est maintenant en cours de préparation et vous serez notifié(e) lors de son expédition.</p>
                <p style="margin-top: 30px;">Cordialement,<br>
                   <strong>L'équipe Benin Luxe Cajou</strong></p>
            </div>
            """
        )
        mail.send(msg)
        current_app.logger.info(f"Email de confirmation envoyé pour la commande {order.numero_commande}")
        
    except Exception as e:
        current_app.logger.error(f"Erreur lors de l'envoi de l'email de confirmation pour la commande {order.id}: {e}")

def send_new_order_push_notification(order):
    """Envoie une notification push aux admins pour une nouvelle commande"""
    try:
        if not firebase_initialized:
            current_app.logger.warning("Firebase non initialisé, impossible d'envoyer la notification push")
            return
            
        admins = Utilisateur.query.filter_by(role='admin').all()
        notifications_sent = 0
        
        for admin in admins:
            if admin.fcm_token:
                try:
                    message = messaging.Message(
                        notification=messaging.Notification(
                            title='🎉 Nouvelle Commande !',
                            body=f'Commande #{order.numero_commande} ({order.total} FCFA) a été payée.'
                        ),
                        data={
                            'order_id': str(order.id),
                            'order_number': order.numero_commande,
                            'amount': str(order.total),
                            'type': 'new_order'
                        },
                        token=admin.fcm_token,
                    )
                    
                    response = messaging.send(message)
                    notifications_sent += 1
                    current_app.logger.info(f"Notification push envoyée à l'admin {admin.id} (token: {admin.fcm_token[:10]}...)")
                    
                except Exception as token_error:
                    current_app.logger.error(f"Erreur lors de l'envoi de la notification à l'admin {admin.id}: {token_error}")
        
        current_app.logger.info(f"{notifications_sent} notifications push envoyées pour la commande {order.numero_commande}")
        
    except Exception as e:
        current_app.logger.error(f"Erreur générale lors de l'envoi des notifications push pour la commande {order.id}: {e}")

def send_low_stock_notification(product):
    """Envoie une notification push pour un produit en stock faible."""
    try:
        if not firebase_initialized:
            current_app.logger.warning("Firebase non initialisé, impossible d'envoyer la notification de stock faible")
            return
            
        admins = Utilisateur.query.filter_by(role='admin').all()
        notifications_sent = 0
        
        for admin in admins:
            if admin.fcm_token:
                try:
                    message = messaging.Message(
                        notification=messaging.Notification(
                            title='⚠️ Alerte Stock Faible !',
                            body=f"Le stock pour '{product.nom}' est de {product.stock_disponible}. Le seuil est de {product.stock_minimum}."
                        ),
                        data={
                            "product_id": str(product.id),
                            "product_name": product.nom,
                            "current_stock": str(product.stock_disponible),
                            "minimum_stock": str(product.stock_minimum),
                            "type": "low_stock_alert"
                        },
                        token=admin.fcm_token,
                    )
                    
                    messaging.send(message)
                    notifications_sent += 1
                    current_app.logger.info(f"Notification de stock faible envoyée à l'admin {admin.id} pour le produit {product.nom}")
                    
                except Exception as token_error:
                    current_app.logger.error(f"Erreur lors de l'envoi de la notification de stock faible à l'admin {admin.id}: {token_error}")
        
        current_app.logger.info(f"{notifications_sent} notifications de stock faible envoyées pour le produit {product.nom}")
        
    except Exception as e:
        current_app.logger.error(f"Erreur lors de l'envoi de la notification de stock faible pour le produit {product.id}: {e}")

def process_payment_confirmation(order):
    """Traite la confirmation d'un paiement (mise à jour + notifications)"""
    try:
        # 1. Mettre à jour la base de données
        order.statut_paiement = 'paye'
        order.statut = 'confirmee'
        
        # Mettre à jour le statut du paiement
        payment = Paiement.query.filter_by(commande_id=order.id).first()
        if payment:
            payment.statut = 'approved'
        
        db.session.commit()
        current_app.logger.info(f"Statut de la commande {order.numero_commande} mis à jour: paiement confirmé")
        
        # 2. Envoyer l'email de confirmation au client
        send_order_confirmation_email(order)
        
        # 3. Envoyer la notification push à l'admin
        send_new_order_push_notification(order)
        
        return True
        
    except Exception as e:
        current_app.logger.error(f"Erreur lors du traitement de la confirmation de paiement pour la commande {order.id}: {e}")
        db.session.rollback()
        return False

# --- ROUTES DE PAIEMENT ---

@payment_bp.route('/initialize', methods=['POST'])
@jwt_required()
def initialize_payment():
    """
    Orchestre le début du processus de paiement et envoie des alertes de stock faible.
    """
    # Initialiser les services
    initialize_services()
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
        
        # <<<--- CORRECTION APPLIQUÉE ICI ---
        # On récupère les coordonnées et on les nettoie
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        
        # Si le frontend envoie des chaînes vides pour une adresse manuelle,
        # on les convertit en None pour que la base de données les accepte comme NULL.
        if latitude == '':
            latitude = None
        if longitude == '':
            longitude = None
        # --- FIN DE LA CORRECTION ---

        new_address = AdresseLivraison(
            utilisateur_id=user.id,
            nom_destinataire=data['nom_destinataire'],
            telephone_destinataire=data['telephone_destinataire'],
            type_adresse=data['type_adresse'],
            ville=data.get('ville'),
            quartier=data.get('quartier'),
            description_adresse=data['description_adresse'],
            point_repere=data.get('point_repere'),
            latitude=latitude,   # Utilisation de la variable nettoyée
            longitude=longitude  # Utilisation de la variable nettoyée
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

        products_to_check_stock = []

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
                products_to_check_stock.append(item.produit)

        # --- Étape 4 : Création de la transaction FedaPay ---
        transaction_data = {
            "description": f"Paiement pour commande #{new_order.numero_commande}",
            "amount": int(total),
            "currency": { "iso": "XOF" },
            "callback_url": f"https://benin-luxe-cajou-frontend-842xbmltr-dalis-projects-fdecfaab.vercel.app/payment-success?order_id={new_order.id}",
            "customer": {
                "firstname": user.prenom,
                "lastname": user.nom,
                "email": user.email,
                "phone_number": {
                    "number": data['telephone_destinataire'],
                    "country": "bj"
                }
            }
        }

        transaction_response = client.create_transaction(transaction_data)
        transaction_id = transaction_response['v1/transaction']['id']
        
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

        # --- Étape 6 : Vérification du stock après le commit ---
        for product in products_to_check_stock:
            if product.stock_disponible <= product.stock_minimum:
                send_low_stock_notification(product)

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

@payment_bp.route('/status/<int:order_id>', methods=['GET'])
@jwt_required()
def get_payment_status(order_id):
    """
    LE DÉCLENCHEUR : Vérifie le statut et envoie les notifications si le paiement est confirmé.
    """
    initialize_services()  # S'assurer que les services sont initialisés
    
    user_id = int(get_jwt_identity())
    order = Commande.query.filter_by(id=order_id, utilisateur_id=user_id).first_or_404()
    
    # On vérifie d'abord notre BDD. Si le webhook est déjà passé, on ne fait rien de plus.
    if order.statut_paiement == 'paye':
        return jsonify({"payment_status": "paye"}), 200

    payment = Paiement.query.filter_by(commande_id=order.id).first()
    if payment:
        try:
            client = get_fedapay_client()
            if not client:
                return jsonify({"payment_status": order.statut_paiement}), 200
            
            # La source de vérité : on interroge FedaPay avec l'API REST
            transaction_response = client.get_transaction(payment.fedapay_transaction_id)
            transaction_status = transaction_response['v1/transaction']['status']
            
            # Si le paiement est approuvé ET que nous ne l'avions pas encore enregistré...
            if transaction_status == 'approved' and order.statut_paiement != 'paye':
                # Traiter la confirmation de paiement
                if process_payment_confirmation(order):
                    current_app.logger.info(f"Paiement confirmé et notifications envoyées pour la commande {order.numero_commande}")
                
        except Exception as e:
            current_app.logger.error(f"Erreur lors de la vérification du statut FedaPay pour la commande {order.id}: {str(e)}")
    
    return jsonify({"payment_status": order.statut_paiement}), 200

@payment_bp.route('/webhook', methods=['POST'])
def fedapay_webhook():
    """Webhook pour recevoir les notifications de FedaPay - Filet de sécurité"""
    initialize_services()  # S'assurer que les services sont initialisés
    
    data = request.get_json()
    event_type = data.get('name')
    
    if event_type == 'transaction.approved':
        transaction_data = data.get('data')
        transaction_id = str(transaction_data.get('id'))
        
        payment = Paiement.query.filter_by(fedapay_transaction_id=transaction_id).first()
        if payment and payment.commande.statut_paiement != 'paye':  # On vérifie pour ne pas traiter 2 fois
            # Traiter la confirmation de paiement
            if process_payment_confirmation(payment.commande):
                current_app.logger.info(f"Webhook: Paiement confirmé et notifications envoyées pour la commande {payment.commande.numero_commande}")
    
    return jsonify(success=True), 200
