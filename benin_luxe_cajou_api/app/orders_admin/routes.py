# app/orders_admin/routes.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import Commande, Utilisateur, SuiviCommande
from app.extensions import db
from app.schemas import commandes_schema, commande_schema, utilisateur_schema, utilisateurs_schema
from app.admin.admin_auth import admin_required

orders_admin_bp = Blueprint('orders_admin', __name__)

# --- GESTION DES COMMANDES ---

@orders_admin_bp.route('/', methods=['GET'])
@admin_required()
def get_orders():
    """
    Récupère la liste de toutes les commandes.
    Peut être filtrée par statut (ex: /api/admin/orders?statut=confirmee).
    """
    statut_filter = request.args.get('statut')
    
    query = Commande.query.order_by(Commande.date_commande.desc())
    
    if statut_filter:
        query = query.filter(Commande.statut == statut_filter)
        
    commandes = query.all()
    return jsonify(commandes_schema.dump(commandes)), 200

@orders_admin_bp.route('/<int:order_id>', methods=['GET'])
@admin_required()
def get_order_details(order_id):
    """
    Récupère les détails complets d'une seule commande.
    """
    commande = Commande.query.get_or_404(order_id)
    return jsonify(commande_schema.dump(commande)), 200


@orders_admin_bp.route('/<int:order_id>/status', methods=['PUT'])
@admin_required()
def update_order_status(order_id):
    """
    Met à jour le statut d'une commande et notifie le client par email.
    """
    admin_id = int(get_jwt_identity())
    commande = Commande.query.get_or_404(order_id)
    data = request.get_json()
    new_status = data.get('statut')

    # On peut élargir les statuts valides si besoin
    valid_statuses = ['en_preparation', 'expedie', 'livree', 'annulee']
    if not new_status or new_status not in valid_statuses:
        return jsonify({"msg": "Statut invalide"}), 400

    # On met à jour le statut
    commande.statut = new_status
    
    # On enregistre cette action dans le suivi
    suivi = SuiviCommande(
        commande_id=order_id,
        statut=new_status,
        modifie_par=admin_id,
        message=f"Statut mis à jour par l'administrateur."
    )
    db.session.add(suivi)
    db.session.commit()
    
    # <<< 2. APPELER LA FONCTION D'ENVOI D'EMAIL ---
    # On le fait après le commit pour s'assurer que le statut est bien sauvegardé
    send_status_update_email(commande)
    
    return jsonify(commande_schema.dump(commande)), 200
# --- GESTION DES CLIENTS ---

@orders_admin_bp.route('/clients', methods=['GET'])
@admin_required()
def get_clients():
    """
    Récupère la liste de tous les utilisateurs avec le rôle 'client'.
    """
    clients = Utilisateur.query.filter_by(role='client').order_by(Utilisateur.date_creation.desc()).all()
    # On réutilise le schéma utilisateur, mais au pluriel
    return jsonify(utilisateurs_schema.dump(clients)), 200

@orders_admin_bp.route('/clients/<int:client_id>', methods=['GET'])
@admin_required()
def get_client_details(client_id):
    """
    Récupère les détails d'un client, y compris son historique de commandes.
    """
    client = Utilisateur.query.filter_by(id=client_id, role='client').first_or_404()
    # On réutilise le schéma utilisateur standard qui a déjà les champs nécessaires
    return jsonify(utilisateur_schema.dump(client)), 200

@orders_admin_bp.route('/clients/<int:client_id>/status', methods=['PUT'])
@admin_required()
def update_client_status(client_id):
    """
    Met à jour le statut d'un client (actif, inactif, suspendu).
    """
    client = Utilisateur.query.filter_by(id=client_id, role='client').first_or_404()
    data = request.get_json()
    new_status = data.get('statut')

    valid_statuses = ['actif', 'inactif', 'suspendu']
    if not new_status or new_status not in valid_statuses:
        return jsonify({"msg": "Statut de client invalide"}), 400

    client.statut = new_status
    db.session.commit()
    
    return jsonify(utilisateur_schema.dump(client)), 200
