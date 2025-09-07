# Route de déconnexion temporaire - à ajouter à routes.py

@client_auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout_client():
    """
    Route de déconnexion qui nettoie les cookies d'authentification.
    """
    response = make_response(jsonify({"msg": "Déconnexion réussie"}))
    
    # Supprimer les cookies en les expirant
    response.set_cookie('access_token', '', expires=0, httponly=True, samesite='Lax')
    response.set_cookie('refresh_token', '', expires=0, httponly=True, samesite='Lax')
    
    return response