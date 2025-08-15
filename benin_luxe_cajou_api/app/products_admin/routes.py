# app/products_admin/routes.py

from flask import Blueprint, request, jsonify, g
from cloudinary.uploader import upload
from cloudinary.exceptions import Error as CloudinaryError
from datetime import datetime
import logging
import time

from app.extensions import db
from app.models import Categorie, TypeProduit, Produit, ImageProduit
from app.admin.admin_auth import admin_required
from app.schemas import (
    categorie_schema, categories_schema,
    type_produit_schema, types_produits_schema,
    produit_schema, produits_schema,
    image_produit_schema
)

# Configuration du logger avec niveau INFO pour avoir tous les détails
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

products_admin_bp = Blueprint('products_admin', __name__)

def log_request_start(route_name, **kwargs):
    """Démarre le logging d'une requête"""
    client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('HTTP_X_REAL_IP', request.remote_addr))
    user_agent = request.headers.get('User-Agent', 'Unknown')
    method = request.method
    
    # Stocker les infos dans g pour les utiliser plus tard
    g.start_time = time.time()
    g.client_ip = client_ip
    g.route_name = route_name
    
    extra_info = " - ".join([f"{k}: {v}" for k, v in kwargs.items() if v is not None])
    
    logger.info(f"🚀 [{route_name}] START - {method} - IP: {client_ip} - User-Agent: {user_agent}" + 
                (f" - {extra_info}" if extra_info else ""))
    
    return client_ip, user_agent

def log_request_end(status_code, message="", **kwargs):
    """Termine le logging d'une requête"""
    if not hasattr(g, 'start_time'):
        return
        
    duration = round((time.time() - g.start_time) * 1000, 2)
    route_name = getattr(g, 'route_name', 'UNKNOWN')
    client_ip = getattr(g, 'client_ip', 'Unknown')
    
    status_emoji = "✅" if 200 <= status_code < 300 else "⚠️" if 400 <= status_code < 500 else "❌"
    
    extra_info = " - ".join([f"{k}: {v}" for k, v in kwargs.items() if v is not None])
    
    logger.info(f"{status_emoji} [{route_name}] END - Status: {status_code} - Duration: {duration}ms - IP: {client_ip}" +
                (f" - {message}" if message else "") + 
                (f" - {extra_info}" if extra_info else ""))

def log_action(action, **kwargs):
    """Log une action spécifique pendant la requête"""
    route_name = getattr(g, 'route_name', 'UNKNOWN')
    client_ip = getattr(g, 'client_ip', 'Unknown')
    
    extra_info = " - ".join([f"{k}: {v}" for k, v in kwargs.items() if v is not None])
    
    logger.info(f"🔄 [{route_name}] {action} - IP: {client_ip}" + 
                (f" - {extra_info}" if extra_info else ""))

def log_error(error_msg, **kwargs):
    """Log une erreur pendant la requête"""
    route_name = getattr(g, 'route_name', 'UNKNOWN')
    client_ip = getattr(g, 'client_ip', 'Unknown')
    
    extra_info = " - ".join([f"{k}: {v}" for k, v in kwargs.items() if v is not None])
    
    logger.error(f"❌ [{route_name}] ERROR - {error_msg} - IP: {client_ip}" + 
                 (f" - {extra_info}" if extra_info else ""))

# --- GESTION DES CATEGORIES ---

@products_admin_bp.route('/categories', methods=['POST'])
@admin_required()
def create_categorie():
    client_ip, user_agent = log_request_start("CREATE_CATEGORIE")
    
    try:
        data = request.get_json()
        log_action("Data received", fields=list(data.keys()) if data else None)
        
        if not data:
            log_error("No JSON data provided")
            log_request_end(400, "Missing JSON data")
            return jsonify({"error": "Données JSON requises"}), 400
        
        nom_categorie = data.get('nom', 'Non spécifié')
        log_action("Creating category", name=nom_categorie)
        
        nouvelle_categorie = categorie_schema.load(data, session=db.session)
        db.session.add(nouvelle_categorie)
        db.session.commit()
        
        log_action("Category created successfully", id=nouvelle_categorie.id, name=nouvelle_categorie.nom)
        log_request_end(201, "Category created", category_id=nouvelle_categorie.id, name=nouvelle_categorie.nom)
        return jsonify(categorie_schema.dump(nouvelle_categorie)), 201
        
    except Exception as e:
        db.session.rollback()
        log_error(f"Exception during category creation: {str(e)}")
        log_request_end(400, "Creation failed")
        return jsonify({"error": str(e)}), 400

@products_admin_bp.route('/categories', methods=['GET'])
@admin_required()
def get_categories():
    client_ip, user_agent = log_request_start("GET_CATEGORIES")
    
    try:
        categories = Categorie.query.all()
        log_action("Categories retrieved", count=len(categories))
        
        log_request_end(200, "Categories list retrieved", count=len(categories))
        return jsonify(categories_schema.dump(categories)), 200
        
    except Exception as e:
        log_error(f"Exception during categories retrieval: {str(e)}")
        log_request_end(500, "Retrieval failed")
        return jsonify({"error": "Erreur lors de la récupération des catégories"}), 500

@products_admin_bp.route('/categories/<int:id>', methods=['PUT'])
@admin_required()
def update_categorie(id):
    client_ip, user_agent = log_request_start("UPDATE_CATEGORIE", category_id=id)
    
    try:
        categorie = Categorie.query.get_or_404(id)
        log_action("Category found", current_name=categorie.nom)
        
        data = request.get_json()
        log_action("Update data received", fields=list(data.keys()) if data else None)
        
        ancien_nom = categorie.nom
        categorie.nom = data.get('nom', categorie.nom)
        categorie.description = data.get('description', categorie.description)
        categorie.statut = data.get('statut', categorie.statut)
        
        db.session.commit()
        
        log_action("Category updated successfully", old_name=ancien_nom, new_name=categorie.nom)
        log_request_end(200, "Category updated", category_id=id, old_name=ancien_nom, new_name=categorie.nom)
        return jsonify(categorie_schema.dump(categorie)), 200
        
    except Exception as e:
        db.session.rollback()
        log_error(f"Exception during category update: {str(e)}", category_id=id)
        log_request_end(400, "Update failed", category_id=id)
        return jsonify({"error": str(e)}), 400

# --- GESTION DES TYPES DE PRODUITS ---

@products_admin_bp.route('/product-types', methods=['POST'])
@admin_required()
def create_type_produit():
    client_ip, user_agent = log_request_start("CREATE_TYPE_PRODUIT")
    
    try:
        data = request.get_json()
        log_action("Data received", fields=list(data.keys()) if data else None)
        
        if not data:
            log_error("No JSON data provided")
            log_request_end(400, "Missing JSON data")
            return jsonify({"error": "Données JSON requises"}), 400
        
        nom_type = data.get('nom', 'Non spécifié')
        category_id = data.get('category_id')
        log_action("Creating product type", name=nom_type, category_id=category_id)
        
        nouveau_type = type_produit_schema.load(data, session=db.session)
        db.session.add(nouveau_type)
        db.session.commit()
        
        log_action("Product type created successfully", id=nouveau_type.id, name=nouveau_type.nom)
        log_request_end(201, "Product type created", type_id=nouveau_type.id, name=nouveau_type.nom)
        return jsonify(type_produit_schema.dump(nouveau_type)), 201
        
    except Exception as e:
        db.session.rollback()
        log_error(f"Exception during product type creation: {str(e)}")
        log_request_end(400, "Creation failed")
        return jsonify({"error": str(e)}), 400

@products_admin_bp.route('/product-types', methods=['GET'])
@admin_required()
def get_types_produits():
    client_ip, user_agent = log_request_start("GET_TYPES_PRODUITS")
    
    try:
        types = TypeProduit.query.all()
        log_action("Product types retrieved", count=len(types))
        
        log_request_end(200, "Product types list retrieved", count=len(types))
        return jsonify(types_produits_schema.dump(types)), 200
        
    except Exception as e:
        log_error(f"Exception during product types retrieval: {str(e)}")
        log_request_end(500, "Retrieval failed")
        return jsonify({"error": "Erreur lors de la récupération des types de produits"}), 500

@products_admin_bp.route('/product-types/<int:id>', methods=['PUT'])
@admin_required()
def update_type_produit(id):
    client_ip, user_agent = log_request_start("UPDATE_TYPE_PRODUIT", type_id=id)
    
    try:
        type_produit = TypeProduit.query.get_or_404(id)
        log_action("Product type found", current_name=type_produit.nom)
        
        data = request.get_json()
        log_action("Update data received", fields=list(data.keys()) if data else None)
        
        ancien_nom = type_produit.nom
        type_produit.nom = data.get('nom', type_produit.nom)
        type_produit.description = data.get('description', type_produit.description)
        type_produit.statut = data.get('statut', type_produit.statut)
        type_produit.category_id = data.get('category_id', type_produit.category_id)
        
        db.session.commit()
        
        log_action("Product type updated successfully", old_name=ancien_nom, new_name=type_produit.nom)
        log_request_end(200, "Product type updated", type_id=id, old_name=ancien_nom, new_name=type_produit.nom)
        return jsonify(type_produit_schema.dump(type_produit)), 200
        
    except Exception as e:
        db.session.rollback()
        log_error(f"Exception during product type update: {str(e)}", type_id=id)
        log_request_end(400, "Update failed", type_id=id)
        return jsonify({"error": str(e)}), 400

# --- GESTION DES PRODUITS ---

@products_admin_bp.route('/products', methods=['POST'])
@admin_required()
def create_produit():
    client_ip, user_agent = log_request_start("CREATE_PRODUIT")
    
    try:
        data = request.get_json()
        log_action("Data received", fields=list(data.keys()) if data else None)
        
        if not data:
            log_error("No JSON data provided")
            log_request_end(400, "Missing JSON data")
            return jsonify({"error": "Données JSON requises"}), 400
        
        nom_produit = data.get('nom', 'Non spécifié')
        prix = data.get('prix', 0)
        log_action("Creating product", name=nom_produit, price=prix)
        
        nouveau_produit = produit_schema.load(data, session=db.session)
        db.session.add(nouveau_produit)
        db.session.commit()
        
        log_action("Product created successfully", id=nouveau_produit.id, name=nouveau_produit.nom)
        log_request_end(201, "Product created", product_id=nouveau_produit.id, name=nouveau_produit.nom)
        return jsonify(produit_schema.dump(nouveau_produit)), 201
        
    except Exception as e:
        db.session.rollback()
        log_error(f"Exception during product creation: {str(e)}")
        log_request_end(400, "Creation failed")
        return jsonify({"error": str(e)}), 400

@products_admin_bp.route('/products', methods=['GET'])
@admin_required()
def get_produits():
    client_ip, user_agent = log_request_start("GET_PRODUITS")
    
    try:
        produits = Produit.query.order_by(Produit.id.desc()).all()
        log_action("Products retrieved", count=len(produits))
        
        log_request_end(200, "Products list retrieved", count=len(produits))
        return jsonify(produits_schema.dump(produits)), 200
        
    except Exception as e:
        log_error(f"Exception during products retrieval: {str(e)}")
        log_request_end(500, "Retrieval failed")
        return jsonify({"error": "Erreur lors de la récupération des produits"}), 500

@products_admin_bp.route('/products/<int:id>', methods=['GET'])
@admin_required()
def get_produit_detail(id):
    client_ip, user_agent = log_request_start("GET_PRODUIT_DETAIL", product_id=id)
    
    try:
        produit = Produit.query.get_or_404(id)
        log_action("Product found", name=produit.nom)
        
        log_request_end(200, "Product details retrieved", product_id=id, name=produit.nom)
        return jsonify(produit_schema.dump(produit)), 200
        
    except Exception as e:
        log_error(f"Exception during product detail retrieval: {str(e)}", product_id=id)
        log_request_end(404, "Product not found", product_id=id)
        return jsonify({"error": "Produit non trouvé"}), 404

@products_admin_bp.route('/products/<int:id>', methods=['PUT'])
@admin_required()
def update_produit(id):
    client_ip, user_agent = log_request_start("UPDATE_PRODUIT", product_id=id)
    
    try:
        produit = Produit.query.get_or_404(id)
        log_action("Product found", current_name=produit.nom)
        
        data = request.get_json()
        log_action("Update data received", fields=list(data.keys()) if data else None)
        
        ancien_nom = produit.nom
        champs_modifies = []
        
        # Simple mise à jour champ par champ avec tracking
        for key, value in data.items():
            if hasattr(produit, key):
                ancienne_valeur = getattr(produit, key)
                setattr(produit, key, value)
                if ancienne_valeur != value:
                    champs_modifies.append(f"{key}: {ancienne_valeur} → {value}")
        
        log_action("Fields modified", changes=", ".join(champs_modifies) if champs_modifies else "None")
        
        db.session.commit()
        
        log_action("Product updated successfully", old_name=ancien_nom, new_name=produit.nom)
        log_request_end(200, "Product updated", product_id=id, changes_count=len(champs_modifies))
        return jsonify(produit_schema.dump(produit)), 200
        
    except Exception as e:
        db.session.rollback()
        log_error(f"Exception during product update: {str(e)}", product_id=id)
        log_request_end(400, "Update failed", product_id=id)
        return jsonify({"error": str(e)}), 400

# --- GESTION DES IMAGES DE PRODUITS ---

@products_admin_bp.route('/products/<int:id>/images', methods=['POST'])
@admin_required()
def upload_product_image(id):
    client_ip, user_agent = log_request_start("UPLOAD_PRODUCT_IMAGE", product_id=id)
    
    try:
        produit = Produit.query.get_or_404(id)
        log_action("Product found", name=produit.nom)
        
        if 'image' not in request.files:
            log_error("No image file provided")
            log_request_end(400, "Missing image file", product_id=id)
            return jsonify({"error": "Aucun fichier image n'a été envoyé"}), 400
            
        file_to_upload = request.files['image']
        filename = file_to_upload.filename
        log_action("Image file received", filename=filename)
        
        try:
            log_action("Starting Cloudinary upload", filename=filename)
            # Envoi de l'image à Cloudinary
            upload_result = upload(
                file_to_upload,
                folder=f"benin_luxe_cajou/produits",
                public_id=f"prod_{id}_{filename}"
            )
            
            cloudinary_url = upload_result['secure_url']
            log_action("Cloudinary upload successful", url=cloudinary_url)
            
            # Créer l'entrée dans la base de données
            nouvelle_image = ImageProduit(
                produit_id=id,
                url_image=cloudinary_url,
                alt_text=produit.nom
            )

            # Si c'est la première image, la définir comme principale
            images_existantes = len(produit.images)
            if images_existantes == 0:
                nouvelle_image.est_principale = True
                log_action("First image - set as primary", existing_images=images_existantes)
            else:
                log_action("Additional image", existing_images=images_existantes)

            db.session.add(nouvelle_image)
            db.session.commit()
            
            log_action("Image saved to database", image_id=nouvelle_image.id)
            log_request_end(201, "Image uploaded successfully", 
                          product_id=id, image_id=nouvelle_image.id, filename=filename)
            return jsonify(image_produit_schema.dump(nouvelle_image)), 201

        except CloudinaryError as e:
            log_error(f"Cloudinary upload error: {str(e)}", filename=filename)
            log_request_end(500, "Cloudinary upload failed", product_id=id)
            return jsonify({"error": f"Erreur Cloudinary : {e.message}"}), 500
            
    except Exception as e:
        db.session.rollback()
        log_error(f"Exception during image upload: {str(e)}", product_id=id)
        log_request_end(500, "Upload failed", product_id=id)
        return jsonify({"error": f"Erreur interne : {str(e)}"}), 500

@products_admin_bp.route('/images/<int:image_id>/set-primary', methods=['POST'])
@admin_required()
def set_primary_image(image_id):
    client_ip, user_agent = log_request_start("SET_PRIMARY_IMAGE", image_id=image_id)
    
    try:
        image_a_definir = ImageProduit.query.get_or_404(image_id)
        produit_id = image_a_definir.produit_id
        
        log_action("Image found", product_id=produit_id)
        
        # Compter les images actuelles du produit
        images_produit = ImageProduit.query.filter_by(produit_id=produit_id).all()
        ancienne_principale = next((img for img in images_produit if img.est_principale), None)
        
        log_action("Changing primary image", 
                  old_primary=ancienne_principale.id if ancienne_principale else None,
                  new_primary=image_id,
                  total_images=len(images_produit))

        # Retirer le statut "principal" de toutes les autres images de ce produit
        ImageProduit.query.filter_by(produit_id=produit_id).update({'est_principale': False})
        
        # Définir la nouvelle image comme principale
        image_a_definir.est_principale = True
        
        db.session.commit()
        
        log_action("Primary image set successfully")
        log_request_end(200, "Primary image updated", image_id=image_id, product_id=produit_id)
        return jsonify({"message": "Image principale définie avec succès"}), 200
        
    except Exception as e:
        db.session.rollback()
        log_error(f"Exception during primary image setting: {str(e)}", image_id=image_id)
        log_request_end(400, "Primary image update failed", image_id=image_id)
        return jsonify({"error": str(e)}), 400
