# app/schemas.py

from .extensions import ma
from .models import Categorie, TypeProduit, Produit, ImageProduit

class ImageProduitSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = ImageProduit
        load_instance = True
        include_fk = True

class CategorieSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Categorie
        load_instance = True

class TypeProduitSchema(ma.SQLAlchemyAutoSchema):
    categorie = ma.Nested(CategorieSchema, only=("id", "nom"))
    class Meta:
        model = TypeProduit
        load_instance = True
        include_fk = True

class ProduitSchema(ma.SQLAlchemyAutoSchema):
    type_produit = ma.Nested(TypeProduitSchema, only=("id", "nom", "categorie"))
    images = ma.Nested(ImageProduitSchema, many=True, only=("id", "url_image", "est_principale"))
    prix_unitaire = ma.auto_field(as_string=True)
    
    class Meta:
        model = Produit
        load_instance = True
        include_fk = True

# Initialisation des schémas pour usage global
categorie_schema = CategorieSchema()
categories_schema = CategorieSchema(many=True)

type_produit_schema = TypeProduitSchema()
types_produits_schema = TypeProduitSchema(many=True)

produit_schema = ProduitSchema()
produits_schema = ProduitSchema(many=True)

image_produit_schema = ImageProduitSchema()

