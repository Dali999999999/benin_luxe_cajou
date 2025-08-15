from functools import wraps
from flask import jsonify, current_app
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from jwt.exceptions import ExpiredSignatureError, DecodeError, InvalidTokenError
from app.models import Utilisateur

def admin_required():
    """
    Décorateur qui vérifie que l'utilisateur est bien un admin.
    """
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            try:
                # DIAGNOSTIC : Logs détaillés
                current_app.logger.info("🔐 DÉBUT - Vérification admin_required")
                
                # Vérifie d'abord la validité du token JWT
                current_app.logger.info("🔍 Vérification JWT...")
                verify_jwt_in_request()
                current_app.logger.info("✅ Token JWT valide")
                
                # Récupère l'ID de l'utilisateur depuis le token
                user_id = get_jwt_identity()
                current_app.logger.info(f"👤 User ID récupéré: {user_id}")
                
                # Recherche l'utilisateur en base
                current_app.logger.info(f"🔍 Recherche utilisateur ID: {user_id}")
                user = Utilisateur.query.get(user_id)
                
                if not user:
                    current_app.logger.error(f"❌ Utilisateur ID {user_id} non trouvé en base")
                    return jsonify({"msg": "Utilisateur non trouvé"}), 404
                
                current_app.logger.info(f"👤 Utilisateur trouvé: {user.email}, rôle: {user.role}")
                
                # Vérifie que l'utilisateur a le rôle 'admin'
                if user.role == 'admin':
                    current_app.logger.info("✅ Accès admin autorisé")
                    return fn(*args, **kwargs)
                else:
                    current_app.logger.warning(f"🚫 Accès refusé - Rôle: {user.role} (attendu: admin)")
                    return jsonify({"msg": "Accès réservé aux administrateurs"}), 403
                    
            except ExpiredSignatureError:
                current_app.logger.error("❌ Token JWT expiré")
                return jsonify({"msg": "Token expiré"}), 401
                
            except (DecodeError, InvalidTokenError) as e:
                current_app.logger.error(f"❌ Token JWT invalide: {str(e)}")
                return jsonify({"msg": "Token invalide"}), 401
                
            except Exception as e:
                current_app.logger.error(f"❌ Erreur inattendue dans admin_required: {str(e)}", exc_info=True)
                return jsonify({"msg": "Erreur d'authentification"}), 500
                
        return decorator
    return wrapper
