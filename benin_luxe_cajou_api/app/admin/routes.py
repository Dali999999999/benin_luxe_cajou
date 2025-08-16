from flask import Blueprint, jsonify
from .admin_auth import admin_required
from flask_jwt_extended import get_jwt_identity

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard/stats', methods=['GET'])
@admin_required() # <-- Notre décorateur de protection est ici !
def get_dashboard_stats():
    """
    Un premier endpoint protégé pour tester l'authentification admin.
    """
    # Ici, vous mettrez la logique pour récupérer les stats réelles.
    # Pour l'instant, on renvoie un message de succès.
    return jsonify({
        "message": "Bienvenue sur le tableau de bord admin !",
        "chiffre_affaires_jour": 0,
        "nouvelles_commandes": 0

    })

@admin_bp.route('/register-device', methods=['POST'])
@admin_required()
def register_device():
    user_id = int(get_jwt_identity())
    admin = Utilisateur.query.get_or_404(user_id)
    data = request.get_json()
    fcm_token = data.get('fcm_token')

    if not fcm_token:
        return jsonify({"msg": "Token FCM manquant"}), 400

    admin.fcm_token = fcm_token
    db.session.commit()
    return jsonify({"msg": "Appareil enregistré avec succès pour les notifications."}), 200
