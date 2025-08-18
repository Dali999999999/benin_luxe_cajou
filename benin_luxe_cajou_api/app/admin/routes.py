# app/admin/routes.py

from flask import Blueprint, jsonify, request, current_app
from .admin_auth import admin_required
from flask_jwt_extended import get_jwt_identity
from datetime import datetime, timedelta
from sqlalchemy import func # <<<--- CORRECTION : Ajout de l'import manquant

from app.models import Utilisateur, Commande, Produit
from app.extensions import db

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard/stats', methods=['GET'])
@admin_required()
def get_dashboard_stats():
    """
    Retourne les statistiques clés pour le tableau de bord de l'administrateur.
    """
    try:
        # --- Calculs pour les dates ---
        today = datetime.utcnow().date()
        start_of_week = today - timedelta(days=today.weekday())
        start_of_month = today.replace(day=1)

        # --- 1. Chiffre d'Affaires (CA) ---
        ca_today = db.session.query(func.sum(Commande.total)).filter(
            Commande.statut_paiement == 'paye',
            func.date(Commande.date_commande) == today
        ).scalar() or 0

        ca_week = db.session.query(func.sum(Commande.total)).filter(
            Commande.statut_paiement == 'paye',
            func.date(Commande.date_commande) >= start_of_week
        ).scalar() or 0

        ca_month = db.session.query(func.sum(Commande.total)).filter(
            Commande.statut_paiement == 'paye',
            func.date(Commande.date_commande) >= start_of_month
        ).scalar() or 0

        # --- 2. Commandes en Attente ---
        # Commandes payées ('confirmee') mais pas encore en préparation ou expédiées.
        pending_orders_count = db.session.query(func.count(Commande.id)).filter(
            Commande.statut == 'confirmee'
        ).scalar() or 0

        # --- 3. Nouveaux Clients ---
        seven_days_ago = today - timedelta(days=7)
        new_clients_count = db.session.query(func.count(Utilisateur.id)).filter(
            Utilisateur.role == 'client',
            func.date(Utilisateur.date_creation) >= seven_days_ago
        ).scalar() or 0

        # --- 4. Alertes de Stock Faible ---
        low_stock_products = Produit.query.filter(
            Produit.gestion_stock == 'limite',
            Produit.stock_disponible <= Produit.stock_minimum
        ).all()
        
        # Formater la réponse pour le stock faible
        low_stock_list = [
            {"id": p.id, "nom": p.nom, "stock_disponible": p.stock_disponible, "stock_minimum": p.stock_minimum}
            for p in low_stock_products
        ]
        
        # --- Assemblage de la réponse finale ---
        stats = {
            "ca_today": str(ca_today),
            "ca_week": str(ca_week),
            "ca_month": str(ca_month),
            "pending_orders_count": pending_orders_count,
            "new_clients_last_7_days": new_clients_count,
            "low_stock_products": low_stock_list
        }

        return jsonify(stats), 200

    except Exception as e:
        current_app.logger.error(f"Erreur lors de la récupération des statistiques du dashboard: {str(e)}", exc_info=True)
        return jsonify({"msg": "Erreur interne lors du calcul des statistiques"}), 500

@admin_bp.route('/register-device', methods=['POST'])
@admin_required()
def register_device():
    """
    Enregistre le token FCM de l'appareil de l'administrateur.
    """
    user_id = int(get_jwt_identity())
    admin = Utilisateur.query.get_or_404(user_id)
    data = request.get_json()
    fcm_token = data.get('fcm_token')

    if not fcm_token:
        return jsonify({"msg": "Token FCM manquant"}), 400

    admin.fcm_token = fcm_token
    db.session.commit()
    return jsonify({"msg": "Appareil enregistré avec succès pour les notifications."}), 200
