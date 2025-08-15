# app/products_admin/routes.py

from flask import Blueprint, request, jsonify, current_app
from cloudinary.uploader import upload
from cloudinary.exceptions import Error as CloudinaryError
from marshmallow import ValidationError

from app.extensions import db
from app.models import Categorie, TypeProduit, Produit, ImageProduit
from app.admin.admin_auth import admin_required
from app.schemas import (
    categorie_schema, categories_schema,
    type_produit_schema, types_produits_schema,
    produit_schema, produits_schema,
    image_produit_schema
)

products_admin_bp = Blueprint('products_admin', __name__)

# --- FONCTION DE DIAGNOSTIC ---
@products_admin_bp.before_request
def log_request_headers():
    """
    Cette fonction s'exécute AVANT chaque requête de ce blueprint,
    y compris avant les décorateurs d'authentification.
    """
    auth_header = request.headers.get('Authorization')
    current_app.logger.info(f"--- NOUVELLE REQUÊTE SUR LE BLUEPRINT ADMIN ---")
    current_app.logger.info(f"URL: {request.url}")
    current_app.logger.info(f"Authorization Header Reçu: {auth_header}")
    current_app.logger.info(f"---------------------------------------------")

# --- GESTION DES PRODUITS (AVEC LE DIAGNOSTIC AMÉLIORÉ) ---

@products_admin_bp.route('/products', methods=['GET'])
@admin_required()
def get_produits():
    current_app.logger.info('GET /api/admin/products - Requête reçue')
    try:
        produits = Produit.query.order_by(Produit.id.desc()).all()
        current_app.logger.info(f'{len(produits)} produits récupérés de la base de données.')

        # C'est ici que l'erreur 422 se produit.
        # Le nouveau bloc `except ValidationError` va nous dire pourquoi.
        result = produits_schema.dump(produits)
        
        current_app.logger.info('Sérialisation des produits réussie.')
        return jsonify(result), 200

    except ValidationError as err:
        # --- C'EST LE BLOC LE PLUS IMPORTANT ---
        # Il attrape l'erreur de Marshmallow et nous donne les détails.
        current_app.logger.error(f'ERREUR DE VALIDATION (Serialization) : {err.messages}')
        return jsonify({"error": "Erreur de sérialisation des données", "details": err.messages}), 422
        
    except Exception as e:
        current_app.logger.error(f'Exception inattendue dans get_produits : {str(e)}', exc_info=True)
        return jsonify({"error": "Erreur interne du serveur"}), 500

# --- TOUTES LES AUTRES ROUTES ---
# (Le reste de vos routes pour POST, PUT, etc. peut rester le même pour l'instant)
# (Je les inclus pour que le fichier soit complet et fonctionnel)

@products_admin_bp.route('/categories', methods=['POST'])
@admin_required()
def create_categorie():
    data = request.get_json()
    try:
        nouvelle_categorie = categorie_schema.load(data, session=db.session)
        db.session.add(nouvelle_categorie)
        db.session.commit()
        return jsonify(categorie_schema.dump(nouvelle_categorie)), 201
    except ValidationError as err:
        return jsonify(err.messages), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@products_admin_bp.route('/categories', methods=['GET'])
@admin_required()
def get_categories():
    categories = Categorie.query.all()
    return jsonify(categories_schema.dump(categories)), 200

@products_admin_bp.route('/categories/<int:id>', methods=['PUT'])
@admin_required()
def update_categorie(id):
    categorie = Categorie.query.get_or_404(id)
    data = request.get_json()
    try:
        updated_categorie = categorie_schema.load(data, instance=categorie, partial=True, session=db.session)
        db.session.commit()
        return jsonify(categorie_schema.dump(updated_categorie)), 200
    except ValidationError as err:
        return jsonify(err.messages), 400

@products_admin_bp.route('/product-types', methods=['POST'])
@admin_required()
def create_type_produit():
    data = request.get_json()
    try:
        nouveau_type = type_produit_schema.load(data, session=db.session)
        db.session.add(nouveau_type)
        db.session.commit()
        return jsonify(type_produit_schema.dump(nouveau_type)), 201
    except ValidationError as err:
        return jsonify(err.messages), 400

@products_admin_bp.route('/product-types', methods=['GET'])
@admin_required()
def get_types_produits():
    types = TypeProduit.query.all()
    return jsonify(types_produits_schema.dump(types)), 200

@products_admin_bp.route('/product-types/<int:id>', methods=['PUT'])
@admin_required()
def update_type_produit(id):
    type_produit = TypeProduit.query.get_or_404(id)
    data = request.get_json()
    try:
        updated_type = type_produit_schema.load(data, instance=type_produit, partial=True, session=db.session)
        db.session.commit()
        return jsonify(type_produit_schema.dump(updated_type)), 200
    except ValidationError as err:
        return jsonify(err.messages), 400

@products_admin_bp.route('/products', methods=['POST'])
@admin_required()
def create_produit():
    data = request.get_json()
    try:
        nouveau_produit = produit_schema.load(data, session=db.session)
        db.session.add(nouveau_produit)
        db.session.commit()
        return jsonify(produit_schema.dump(nouveau_produit)), 201
    except ValidationError as err:
        return jsonify(err.messages), 400

@products_admin_bp.route('/products/<int:id>', methods=['GET'])
@admin_required()
def get_produit_detail(id):
    produit = Produit.query.get_or_404(id)
    return jsonify(produit_schema.dump(produit)), 200

@products_admin_bp.route('/products/<int:id>', methods=['PUT'])
@admin_required()
def update_produit(id):
    produit = Produit.query.get_or_404(id)
    data = request.get_json()
    try:
        updated_produit = produit_schema.load(data, instance=produit, partial=True, session=db.session)
        db.session.commit()
        return jsonify(produit_schema.dump(updated_produit)), 200
    except ValidationError as err:
        return jsonify(err.messages), 400

@products_admin_bp.route('/products/<int:id>/images', methods=['POST'])
@admin_required()
def upload_product_image(id):
    produit = Produit.query.get_or_404(id)
    if 'image' not in request.files:
        return jsonify({"error": "Aucun fichier image n'a été envoyé"}), 400
    file_to_upload = request.files['image']
    try:
        upload_result = upload(file_to_upload, folder="benin_luxe_cajou/produits")
        nouvelle_image = ImageProduit(produit_id=id, url_image=upload_result['secure_url'], alt_text=produit.nom)
        if not produit.images:
            nouvelle_image.est_principale = True
        db.session.add(nouvelle_image)
        db.session.commit()
        return jsonify(image_produit_schema.dump(nouvelle_image)), 201
    except CloudinaryError as e:
        return jsonify({"error": f"Erreur Cloudinary : {e.message}"}), 500

@products_admin_bp.route('/images/<int:image_id>/set-primary', methods=['POST'])
@admin_required()
def set_primary_image(image_id):
    image_a_definir = ImageProduit.query.get_or_404(image_id)
    produit_id = image_a_definir.produit_id
    ImageProduit.query.filter_by(produit_id=produit_id).update({'est_principale': False})
    image_a_definir.est_principale = True
    db.session.commit()
    return jsonify({"message": "Image principale définie avec succès"}), 200
