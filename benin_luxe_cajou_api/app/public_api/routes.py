# app/public_api/routes.py

from flask import Blueprint, jsonify, request
from app.extensions import db
from app.models import Categorie, Produit, TypeProduit, ZoneLivraison, NewsletterSubscription
from app.schemas import (
    categories_schema, 
    produits_schema, 
    produit_schema,
    zones_livraison_schema,
    newsletter_subscription_schema
)

public_api_bp = Blueprint('public_api', __name__)


@public_api_bp.route('/catalogue-structure', methods=['GET'])
def get_catalogue_structure():
    """
    Retourne en UN SEUL APPEL toute la hiérarchie des catégories
    et de leurs types de produits respectifs (actifs uniquement).
    C'est l'endpoint principal pour construire la navigation du site.
    """
    # La requête est optimisée par la relation 'lazy="joined"' dans le modèle Categorie
    categories = Categorie.query.filter_by(statut='actif').all()
    return jsonify(categories_schema.dump(categories)), 200


@public_api_bp.route('/products', methods=['GET'])
def get_public_products():
    """
    Retourne une liste de produits actifs.
    Peut être filtrée par `type_id` ou `category_id` via les paramètres de l'URL.
    Exemples:
    - /api/products -> Tous les produits populaires
    - /api/products?type_id=2 -> Produits du type 2
    - /api/products?category_id=1 -> Tous les produits de la catégorie 1
    """
    query = Produit.query.filter_by(statut='actif')
    
    # Récupérer les paramètres de l'URL
    type_id = request.args.get('type_id', type=int)
    category_id = request.args.get('category_id', type=int)

    if type_id:
        # Filtrer par le type de produit exact
        query = query.filter(Produit.type_produit_id == type_id)
    elif category_id:
        # Filtrer par la catégorie parente (nécessite une jointure)
        query = query.join(TypeProduit).filter(TypeProduit.category_id == category_id)
    
    # Si aucun filtre, on peut retourner les plus récents ou les plus populaires
    produits = query.order_by(Produit.id.desc()).all()
    return jsonify(produits_schema.dump(produits)), 200


@public_api_bp.route('/products/<int:id>', methods=['GET'])
def get_public_product_detail(id):
    """
    Retourne les détails d'un seul produit ACTIF.
    """
    produit = Produit.query.filter_by(id=id, statut='actif').first_or_404()
    return jsonify(produit_schema.dump(produit)), 200


@public_api_bp.route('/delivery-zones', methods=['GET'])
def get_public_delivery_zones():
    """
    Retourne la liste des zones de livraison ACTIVES pour la page de checkout.
    """
    zones = ZoneLivraison.query.filter_by(actif=True).all()
    return jsonify(zones_livraison_schema.dump(zones)), 200


# NOTE: L'ancienne route '/categories' n'est plus nécessaire pour la page d'accueil,
# mais on la garde car elle peut être utile ailleurs et ne coûte rien.
@public_api_bp.route('/categories', methods=['GET'])
def get_public_categories():
    """
    Retourne la liste simple de toutes les catégories ACTIVES.
    """
    categories = Categorie.query.filter_by(statut='actif').all()
    return jsonify(categories_schema.dump(categories)), 200

@public_api_bp.route('/newsletter/subscribe', methods=['POST'])
def subscribe_newsletter():
    """
    Inscrit un nouvel email à la newsletter.
    """
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({"msg": "Email requis"}), 400

    # Vérifier si l'email n'est pas déjà inscrit
    if NewsletterSubscription.query.filter_by(email=email).first():
        return jsonify({"msg": "Cet email est déjà inscrit."}), 409 # Conflict

    new_subscription = NewsletterSubscription(email=email)
    db.session.add(new_subscription)
    db.session.commit()
    
    return jsonify({"msg": "Merci ! Vous êtes maintenant inscrit(e) à notre newsletter."}), 201
