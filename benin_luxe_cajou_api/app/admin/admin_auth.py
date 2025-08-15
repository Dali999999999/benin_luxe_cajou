from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from app.models import Utilisateur

def admin_required():
    """
    Décorateur qui vérifie que l'utilisateur est bien un admin.
    """
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            # Vérifie d'abord la validité du token JWT
            verify_jwt_in_request()
            # Récupère l'ID de l'utilisateur depuis le token
            user_id = get_jwt_identity()
            user = Utilisateur.query.get(user_id)
            
            # Vérifie que l'utilisateur existe et a le rôle 'admin'
            if user and user.role == 'admin':
                return fn(*args, **kwargs)
            else:
                return jsonify(msg="Accès réservé aux administrateurs"), 403
        return decorator
    return wrapper