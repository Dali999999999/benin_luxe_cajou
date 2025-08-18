# app/schemas.py

from .extensions import ma
from .models import (
    Categorie, TypeProduit, Produit, ImageProduit, Panier, 
    Utilisateur, AdresseLivraison, Commande, DetailsCommande, SuiviCommande,
    ZoneLivraison, Coupon
)

# --- SCHÉMA UTILITAIRE (Défini en premier pour être utilisé par CategorieSchema) ---

class SimpleTypeProduitSchema(ma.SQLAlchemyAutoSchema):
    """Schéma simplifié pour la structure du catalogue, évite les dépendances circulaires."""
    class Meta:
        model = TypeProduit
        fields = ("id", "nom", "image_url") 
        load_instance = True

# -----------------------------------------------------------------------------
# DÉFINITIONS DES SCHÉMAS PRINCIPAUX
# -----------------------------------------------------------------------------

class ImageProduitSchema(ma.SQLAlchemyAutoSchema):
    date_creation = ma.auto_field()
    class Meta:
        model = ImageProduit
        load_instance = True
        include_fk = True

class CategorieSchema(ma.SQLAlchemyAutoSchema):
    date_creation = ma.auto_field()
    date_modification = ma.auto_field()
    types_produits = ma.Nested(SimpleTypeProduitSchema, many=True, dump_only=True)
    class Meta:
        model = Categorie
        load_instance = True

class TypeProduitSchema(ma.SQLAlchemyAutoSchema):
    categorie = ma.Nested(CategorieSchema, only=("id", "nom"), dump_only=True)
    date_creation = ma.auto_field()
    date_modification = ma.auto_field()
    class Meta:
        model = TypeProduit
        load_instance = True
        include_fk = True

class ProduitSchema(ma.SQLAlchemyAutoSchema):
    type_produit = ma.Nested(TypeProduitSchema, dump_only=True)
    images = ma.Nested(ImageProduitSchema, many=True)
    prix_unitaire = ma.auto_field(as_string=True) 
    date_creation = ma.auto_field()
    date_modification = ma.auto_field()
    class Meta:
        model = Produit
        load_instance = True
        include_fk = True

class PanierSchema(ma.SQLAlchemyAutoSchema):
    produit = ma.Nested(ProduitSchema)
    date_ajout = ma.auto_field()
    date_modification = ma.auto_field()
    class Meta:
        model = Panier
        load_instance = True
        include_fk = True

class UtilisateurSchema(ma.SQLAlchemyAutoSchema):
    derniere_connexion = ma.auto_field()
    date_creation = ma.auto_field()
    commandes = ma.Nested('CommandeSummarySchema', many=True, dump_only=True)
    class Meta:
        model = Utilisateur
        exclude = ("mot_de_passe", "token_verification", "role")
        load_instance = True

class AdresseLivraisonSchema(ma.SQLAlchemyAutoSchema):
    date_creation = ma.auto_field()
    latitude = ma.auto_field(as_string=True)
    longitude = ma.auto_field(as_string=True)
    class Meta:
        model = AdresseLivraison
        load_instance = True
        include_fk = True

class CommandeSummarySchema(ma.SQLAlchemyAutoSchema):
    date_commande = ma.auto_field()
    total = ma.auto_field(as_string=True)
    class Meta:
        model = Commande
        fields = ("id", "numero_commande", "statut", "total", "date_commande")
        load_instance = True

class ZoneLivraisonSchema(ma.SQLAlchemyAutoSchema):
    tarif_livraison = ma.auto_field(as_string=True)
    date_creation = ma.auto_field()
    class Meta:
        model = ZoneLivraison
        load_instance = True

class CouponSchema(ma.SQLAlchemyAutoSchema):
    valeur_reduction = ma.auto_field(as_string=True)
    montant_minimum_commande = ma.auto_field(as_string=True)
    date_debut = ma.auto_field()
    date_fin = ma.auto_field()
    class Meta:
        model = Coupon
        load_instance = True

# --- SCHÉMAS DÉDIÉS AU DÉTAIL DE LA COMMANDE ---

class DetailsCommandeSchema(ma.SQLAlchemyAutoSchema):
    """Schéma pour un article dans le détail d'une commande."""
    produit = ma.Nested(ProduitSchema(only=("nom", "images"))) # On inclut l'image pour l'UI
    prix_unitaire = ma.auto_field(as_string=True)
    sous_total = ma.auto_field(as_string=True)
    class Meta:
        model = DetailsCommande
        load_instance = True

class SuiviCommandeSchema(ma.SQLAlchemyAutoSchema):
    """Schéma pour une étape du suivi de livraison."""
    date_changement = ma.auto_field()
    class Meta:
        model = SuiviCommande
        load_instance = True
        exclude = ("modifie_par",) # L'ID de l'admin n'est pas utile pour le client

class CommandeDetailSchema(ma.SQLAlchemyAutoSchema):
    """Schéma complet pour la page de détail d'une commande (côté client et admin)."""
    # Informations sur le client (backref depuis le modèle Commande)
    client = ma.Nested(UtilisateurSchema(only=("prenom", "nom", "email", "telephone")))
    # Données imbriquées
    adresse_livraison = ma.Nested(AdresseLivraisonSchema)
    details = ma.Nested(DetailsCommandeSchema, many=True)
    suivi = ma.Nested(SuiviCommandeSchema, many=True)
    # Champs financiers formatés
    total = ma.auto_field(as_string=True)
    sous_total = ma.auto_field(as_string=True)
    frais_livraison = ma.auto_field(as_string=True)
    montant_reduction = ma.auto_field(as_string=True)
    date_commande = ma.auto_field()
    class Meta:
        model = Commande
        load_instance = True
        include_fk = True

# -----------------------------------------------------------------------------
# INITIALISATION GLOBALE DE TOUS LES SCHÉMAS
# -----------------------------------------------------------------------------
categorie_schema, categories_schema = CategorieSchema(), CategorieSchema(many=True)
type_produit_schema, types_produits_schema = TypeProduitSchema(), TypeProduitSchema(many=True)
produit_schema, produits_schema = ProduitSchema(), ProduitSchema(many=True)
image_produit_schema = ImageProduitSchema()
panier_schema, paniers_schema = PanierSchema(), PanierSchema(many=True)
utilisateur_schema, utilisateurs_schema = UtilisateurSchema(), UtilisateurSchema(many=True)
adresse_livraison_schema, adresses_livraison_schema = AdresseLivraisonSchema(), AdresseLivraisonSchema(many=True)
commande_summary_schema, commandes_summary_schema = CommandeSummarySchema(), CommandeSummarySchema(many=True)
zone_livraison_schema, zones_livraison_schema = ZoneLivraisonSchema(), ZoneLivraisonSchema(many=True)
coupon_schema, coupons_schema = CouponSchema(), CouponSchema(many=True)
# Schéma pour la liste des commandes admin (optimisé)
commandes_schema = CommandeDetailSchema(many=True, only=("id", "numero_commande", "client.prenom", "client.nom", "total", "statut", "date_commande"))
# Schéma pour le détail d'une commande (côté client et admin)
commande_detail_schema = CommandeDetailSchema()
