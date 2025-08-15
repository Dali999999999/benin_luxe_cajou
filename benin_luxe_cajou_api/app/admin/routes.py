from flask import Blueprint, jsonify
from .admin_auth import admin_required

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