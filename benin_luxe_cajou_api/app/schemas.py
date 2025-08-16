# app/schemas.py

from .extensions import ma
from .models import Categorie, TypeProduit, Produit, ImageProduit, Panier

# -----------------------------------------------------------------------------
# DÉFINITIONS DES SCHÉMAS AVEC GESTION EXPLICITE DES TYPES COMPLEXES
# -----------------------------------------------------------------------------

class ImageProduitSchema(ma.SQLAlchemyAutoSchema):
    # Gère la conversion de l'objet datetime en une chaîne de caractères (format ISO 8601)
    date_creation = ma.auto_field()

    class Meta:
        model = ImageProduit
        load_instance = True
        include_fk = True

class CategorieSchema(ma.SQLAlchemyAutoSchema):
    # Gère la conversion des objets datetime en chaînes de caractères
    date_creation = ma.auto_field()
    date_modification = ma.auto_field()

    class Meta:
        model = Categorie
        load_instance = True

class TypeProduitSchema(ma.SQLAlchemyAutoSchema):
    categorie = ma.Nested(CategorieSchema, only=("id", "nom"))
    # Gère la conversion des objets datetime en chaînes de caractères
    date_creation = ma.auto_field()
    date_modification = ma.auto_field()

    class Meta:
        model = TypeProduit
        load_instance = True
        include_fk = True

class ProduitSchema(ma.SQLAlchemyAutoSchema):
    # Définition des relations imbriquées pour un JSON plus riche
    type_produit = ma.Nested(TypeProduitSchema, only=("id", "nom", "categorie"))
    images = ma.Nested(ImageProduitSchema, many=True, only=("id", "url_image", "est_principale", "date_creation"))
    
    # Gère la conversion du type Decimal en une chaîne pour éviter les erreurs de précision
    prix_unitaire = ma.auto_field(as_string=True) 
    
    # Gère la conversion des objets datetime en chaînes de caractères
    date_creation = ma.auto_field()
    date_modification = ma.auto_field()
    
    class Meta:
        model = Produit
        load_instance = True
        include_fk = True

class PanierSchema(ma.SQLAlchemyAutoSchema):
    # On inclut les détails du produit directement dans la réponse du panier
    # pour simplifier le travail du frontend.
    produit = ma.Nested(ProduitSchema)

    class Meta:
        model = Panier
        load_instance = True
        include_fk = True

# -----------------------------------------------------------------------------
# INITIALISATION DES SCHÉMAS POUR UN USAGE GLOBAL DANS L'APPLICATION
# -----------------------------------------------------------------------------

categorie_schema = CategorieSchema()
categories_schema = CategorieSchema(many=True)

type_produit_schema = TypeProduitSchema()
types_produits_schema = TypeProduitSchema(many=True)

produit_schema = ProduitSchema()
produits_schema = ProduitSchema(many=True)

image_produit_schema = ImageProduitSchema()

panier_schema = PanierSchema()
paniers_schema = PanierSchema(many=True)

