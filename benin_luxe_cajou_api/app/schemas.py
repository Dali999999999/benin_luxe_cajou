from .extensions import ma
from .models import Utilisateur

class UtilisateurSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Utilisateur
        # Exclure les champs sensibles qui ne doivent jamais être retournés par l'API
        exclude = ('mot_de_passe', 'token_verification')
        load_instance = True # Permet de désérialiser en objet Utilisateur

# Initialiser les schémas pour une utilisation simple
utilisateur_schema = UtilisateurSchema()
utilisateurs_schema = UtilisateurSchema(many=True)
