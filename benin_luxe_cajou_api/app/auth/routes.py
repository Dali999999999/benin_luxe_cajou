from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from app.models import Utilisateur

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"msg": "Email et mot de passe requis"}), 400

    user = Utilisateur.query.filter_by(email=email).first()

    if user and user.check_password(password):
        # Vérification supplémentaire pour le panel admin
        if user.role != 'admin':
            return jsonify({"msg": "Accès non autorisé pour ce rôle"}), 403
        
        # L'identité du token sera l'ID de l'utilisateur
        access_token = create_access_token(identity=user.id)
        return jsonify(access_token=access_token)
    
    return jsonify({"msg": "Email ou mot de passe incorrect"}), 401