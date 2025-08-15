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

# --- GESTION DES CATEGORIES ---

@products_admin_bp.route('/categories', methods=['POST'])
@admin_required()
def create_categorie():
    """
    Crée une catégorie en recevant des données de formulaire et un fichier image.
    Utilise multipart/form-data.
    """
    current_app.logger.info("POST /api/admin/categories - Début de la création de catégorie.")
    
    # Les données de formulaire sont dans request.form, pas request.json
    data = request.form.to_dict()
    current_app.logger.info(f"Données de formulaire reçues: {list(data.keys())}")

    if 'nom' not in data:
        current_app.logger.error("Champ 'nom' manquant dans les données du formulaire.")
        return jsonify({"error": "Le nom de la catégorie est requis"}), 400

    image_url = None
    # Vérifier si un fichier image est envoyé
    if 'image' in request.files:
        image_file = request.files['image']
        if image_file.filename != '':
            current_app.logger.info(f"Fichier image reçu: {image_file.filename}. Upload vers Cloudinary...")
            try:
                upload_result = upload(image_file, folder="benin_luxe_cajou/categories")
                image_url = upload_result['secure_url']
                current_app.logger.info(f"Upload Cloudinary réussi. URL: {image_url}")
            except CloudinaryError as e:
                current_app.logger.error(f"Erreur Cloudinary: {str(e)}")
                return jsonify({"error": f"Erreur lors de l'upload de l'image: {e.message}"}), 500
    
    # Ajouter l'URL de l'image (si elle existe) aux données à enregistrer
    if image_url:
        data['image_url'] = image_url

    try:
        # Création de la catégorie avec les données du formulaire et l'URL de l'image
        nouvelle_categorie = categorie_schema.load(data, session=db.session)
        db.session.add(nouvelle_categorie)
        db.session.commit()
        
        current_app.logger.info(f"Catégorie '{nouvelle_categorie.nom}' créée avec succès (ID: {nouvelle_categorie.id}).")
        return jsonify(categorie_schema.dump(nouvelle_categorie)), 201
        
    except ValidationError as err:
        current_app.logger.error(f"Erreur de validation lors de la création de la catégorie: {err.messages}")
        return jsonify(err.messages), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur inattendue lors de la création de la catégorie: {str(e)}")
        return jsonify({"error": "Erreur interne du serveur"}), 500


@products_admin_bp.route('/product-types', methods=['POST'])
@admin_required()
def create_type_produit():
    """
    Crée un type de produit en recevant des données de formulaire et un fichier image.
    Utilise multipart/form-data.
    """
    current_app.logger.info("POST /api/admin/product-types - Début de la création du type de produit.")
    
    data = request.form.to_dict()
    current_app.logger.info(f"Données de formulaire reçues: {list(data.keys())}")

    if 'nom' not in data or 'category_id' not in data:
        current_app.logger.error("Champs 'nom' ou 'category_id' manquants.")
        return jsonify({"error": "Le nom et l'ID de la catégorie sont requis"}), 400

    image_url = None
    if 'image' in request.files:
        image_file = request.files['image']
        if image_file.filename != '':
            current_app.logger.info(f"Fichier image reçu: {image_file.filename}. Upload vers Cloudinary...")
            try:
                upload_result = upload(image_file, folder="benin_luxe_cajou/types_produits")
                image_url = upload_result['secure_url']
                current_app.logger.info(f"Upload Cloudinary réussi. URL: {image_url}")
            except CloudinaryError as e:
                current_app.logger.error(f"Erreur Cloudinary: {str(e)}")
                return jsonify({"error": f"Erreur lors de l'upload de l'image: {e.message}"}), 500

    if image_url:
        data['image_url'] = image_url

    try:
        nouveau_type = type_produit_schema.load(data, session=db.session)
        db.session.add(nouveau_type)
        db.session.commit()
        
        current_app.logger.info(f"Type de produit '{nouveau_type.nom}' créé avec succès (ID: {nouveau_type.id}).")
        return jsonify(type_produit_schema.dump(nouveau_type)), 201
        
    except ValidationError as err:
        current_app.logger.error(f"Erreur de validation: {err.messages}")
        return jsonify(err.messages), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur inattendue: {str(e)}")
        return jsonify({"error": "Erreur interne du serveur"}), 500


# --- LES AUTRES ROUTES RESTENT INCHANGÉES ---
# (Je les inclus pour que le fichier soit complet)

@products_admin_bp.route('/categories', methods=['GET'])
@admin_required()
def get_categories():
    categories = Categorie.query.all()
    return jsonify(categories_schema.dump(categories)), 200

@products_admin_bp.route('/categories/<int:id>', methods=['PUT'])
@admin_required()
def update_categorie(id):
    # La mise à jour reste en JSON pour le moment.
    # Si vous voulez aussi l'upload d'image à la mise à jour, la logique sera similaire au POST.
    categorie = Categorie.query.get_or_404(id)
    data = request.get_json()
    try:
        updated_categorie = categorie_schema.load(data, instance=categorie, partial=True, session=db.session)
        db.session.commit()
        return jsonify(categorie_schema.dump(updated_categorie)), 200
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

@products_admin_bp.route('/products', methods=['GET'])
@admin_required()
def get_produits():
    produits = Produit.query.order_by(Produit.id.desc()).all()
    return jsonify(produits_schema.dump(produits)), 200

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
