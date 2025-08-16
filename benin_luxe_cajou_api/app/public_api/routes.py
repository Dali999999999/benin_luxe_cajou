# app/public_api/routes.py

from flask import Blueprint, jsonify
from app.models import Categorie, Produit
from app.schemas import categories_schema, produits_schema, produit_schema, zones_livraison_schema

public_api_bp = Blueprint('public_api', __name__)

@public_api_bp.route('/categories', methods=['GET'])
def get_public_categories():
    """
    Retourne la liste de toutes les catégories ACTIVES pour le site client.
    """
    categories = Categorie.query.filter_by(statut='actif').all()
    return jsonify(categories_schema.dump(categories)), 200

@public_api_bp.route('/products', methods=['GET'])
def get_public_products():
    """
    Retourne la liste de tous les produits ACTIFS pour le site client.
    (Pourrait être amélioré plus tard avec de la pagination)
    """
    produits = Produit.query.filter_by(statut='actif').order_by(Produit.id.desc()).all()
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
