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
    """Envoie une notification push pour une nouvelle commande avec un son spécifique."""
    try:
        if not firebase_initialized:
            current_app.logger.warning("Firebase non initialisé, impossible d'envoyer la notification push.")
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
                        token=admin.fcm_token,
                        data={
                            'order_id': str(order.id),
                            'type': 'new_order' # Étiquette pour que Flutter puisse identifier le type de notification
                        },
                        # --- Configuration du son personnalisé pour Android ---
                        android=messaging.AndroidConfig(
                            notification=messaging.AndroidNotification(
                                # Nom du fichier son dans android/app/src/main/res/raw (SANS extension)
                                sound='new_order_sound' 
                            )
                        ),
                        # --- Configuration du son personnalisé pour iOS ---
                        apns=messaging.APNSConfig(
                            payload=messaging.APNSPayload(
                                aps=messaging.APS(
                                    # Nom du fichier son ajouté au projet Xcode (AVEC extension)
                                    sound='new_order_sound.wav' 
                                )
                            )
                        )
                    )
                    
                    messaging.send(message)
                    notifications_sent += 1
                    current_app.logger.info(f"Notification push 'Nouvelle Commande' envoyée à l'admin {admin.id}")
                    
                except Exception as token_error:
                    current_app.logger.error(f"Erreur lors de l'envoi de la notification 'Nouvelle Commande' à l'admin {admin.id}: {token_error}")
        
        current_app.logger.info(f"{notifications_sent} notifications 'Nouvelle Commande' envoyées pour la commande {order.numero_commande}")
        
    except Exception as e:
        current_app.logger.error(f"Erreur générale lors de l'envoi des notifications push pour la commande {order.id}: {e}")

def send_low_stock_notification(product):
    """Envoie une notification push pour un produit en stock faible avec un son différent."""
    try:
        if not firebase_initialized:
            current_app.logger.warning("Firebase non initialisé, impossible d'envoyer la notification de stock faible.")
            return
            
        admins = Utilisateur.query.filter_by(role='admin').all()
        notifications_sent = 0
        
        for admin in admins:
            if admin.fcm_token:
                try:
                    message = messaging.Message(
                        notification=messaging.Notification(
                            title='⚠️ Alerte Stock Faible !',
                            body=f"Le stock pour '{product.nom}' est de {product.stock_disponible} (seuil: {product.stock_minimum})."
                        ),
                        token=admin.fcm_token,
                        data={
                            "product_id": str(product.id),
                            "type": "low_stock_alert" # Étiquette différente pour Flutter
                        },
                        # --- Configuration du son personnalisé pour Android ---
                        android=messaging.AndroidConfig(
                            notification=messaging.AndroidNotification(
                                # Nom du fichier son dans android/app/src/main/res/raw (SANS extension)
                                sound='low_stock_sound'
                            )
                        ),
                        # --- Configuration du son personnalisé pour iOS ---
                        apns=messaging.APNSConfig(
                            payload=messaging.APNSPayload(
                                aps=messaging.APS(
                                    # Nom du fichier son ajouté au projet Xcode (AVEC extension)
                                    sound='low_stock_sound.wav'
                                )
                            )
                        )
                    )
                    
                    messaging.send(message)
                    notifications_sent += 1
                    current_app.logger.info(f"Notification 'Stock Faible' envoyée à l'admin {admin.id} pour le produit {product.nom}")
                    
                except Exception as token_error:
                    current_app.logger.error(f"Erreur lors de l'envoi de la notification 'Stock Faible' à l'admin {admin.id}: {token_error}")
        
        current_app.logger.info(f"{notifications_sent} notifications 'Stock Faible' envoyées pour le produit {product.nom}")
        
    except Exception as e:
        current_app.logger.error(f"Erreur lors de l'envoi de la notification de stock faible pour le produit {product.id}: {e}")

def process_payment_confirmation(order):
    """
    Traite la confirmation d'un paiement : met à jour la BDD, le stock,
    vide le panier et envoie les notifications.
    """
    try:
        # 1. Mettre à jour les statuts de la commande et du paiement
        order.statut_paiement = 'paye'
        order.statut = 'confirmee'
        
        payment = Paiement.query.filter_by(commande_id=order.id).first()
        if payment:
            payment.statut = 'approved'
        
        # --- NOUVELLE LOGIQUE CRITIQUE AJOUTÉE ICI ---
        # 2. Décrémenter le stock des produits commandés
        details = DetailsCommande.query.filter_by(commande_id=order.id).all()
        for detail in details:
            product = detail.produit # Utiliser la relation pré-chargée
            if product and product.gestion_stock == 'limite':
                product.stock_disponible -= detail.quantite
                # Envoyer une notification si le stock devient faible après cet achat
                if product.stock_disponible <= product.stock_minimum:
                    send_low_stock_notification(product)

        # 3. Vider le panier de l'utilisateur
        Panier.query.filter_by(utilisateur_id=order.utilisateur_id).delete()
        # --- FIN DE LA NOUVELLE LOGIQUE ---
        
        db.session.commit()
        current_app.logger.info(f"Statut et stock mis à jour pour la commande {order.numero_commande}.")
        
        # 4. Envoyer les notifications (email et push)
        send_order_confirmation_email(order)
        send_new_order_push_notification(order)
        
        return True
        
    except Exception as e:
        current_app.logger.error(f"Erreur lors du traitement de la confirmation de paiement pour la commande {order.id}: {e}", exc_info=True)
        db.session.rollback()
        return False

# --- ROUTES DE PAIEMENT ---

@payment_bp.route('/initialize', methods=['POST'])
@jwt_required()
def initialize_payment():
    """
    Orchestre le début du processus de paiement.
    Crée une commande "en attente" SANS modifier le stock ni vider le panier.
    """
    initialize_services()
    client = get_fedapay_client()
    if not client:
        return jsonify({"msg": "Service de paiement indisponible"}), 503
        
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
        current_app.logger.info(f"FEDAPAY_ENVIRONMENT: {Config.FEDAPAY_ENVIRONMENT}")
        current_app.logger.info(f"FEDAPAY_API_KEY commence par: {Config.FEDAPAY_API_KEY[:15] if Config.FEDAPAY_API_KEY else 'NONE'}...")

        latitude = data.get('latitude')
        longitude = data.get('longitude')
        if latitude == '': latitude = None
        if longitude == '': longitude = None

        new_address = AdresseLivraison(
            utilisateur_id=user.id, nom_destinataire=data['nom_destinataire'],
            telephone_destinataire=data['telephone_destinataire'], type_adresse=data['type_adresse'],
            ville=data.get('ville'), quartier=data.get('quartier'),
            description_adresse=data['description_adresse'], point_repere=data.get('point_repere'),
            latitude=latitude, longitude=longitude
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

        new_order = Commande(
            utilisateur_id=user.id, adresse_livraison_id=new_address.id, sous_total=sous_total,
            frais_livraison=frais_livraison, montant_reduction=montant_reduction, total=total,
            coupon_id=coupon.id if coupon else None, statut='en_attente',
            statut_paiement='en_attente', notes_client=data.get('notes_client')
        )
        db.session.add(new_order)
        db.session.flush()

        for item in cart_items:
            db.session.add(DetailsCommande(
                commande_id=new_order.id, produit_id=item.produit_id, quantite=item.quantite,
                prix_unitaire=item.produit.prix_unitaire,
                sous_total=item.produit.prix_unitaire * item.quantite
            ))
            # <<<--- SUPPRESSION DE LA MODIFICATION DU STOCK ICI ---

        transaction_data = {
            "description": f"Paiement pour commande #{new_order.numero_commande}", "amount": int(total),
            "currency": { "iso": "XOF" },
            "callback_url": f"https://benin-luxe-cajou-frontend.vercel.app/payment-success?order_id={new_order.id}",
            "customer": {
                "firstname": user.prenom, "lastname": user.nom, "email": user.email,
                "phone_number": { "number": data['telephone_destinataire'], "country": "bj" }
            }
        }

        transaction_response = client.create_transaction(transaction_data)
        transaction_id = transaction_response['v1/transaction']['id']
        token_response = client.generate_token(transaction_id)
        payment_url = token_response['url']

        db.session.add(Paiement(
            commande_id=new_order.id, fedapay_transaction_id=str(transaction_id),
            montant=total, statut='pending'
        ))
        
        # <<<--- SUPPRESSION DU VIDAGE DU PANIER ICI ---
        
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
