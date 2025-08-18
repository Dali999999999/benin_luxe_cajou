# app/products_admin/routes.py

from flask import Blueprint, request, jsonify, current_app, g
from cloudinary.uploader import upload
from cloudinary.exceptions import Error as CloudinaryError
from marshmallow import ValidationError
import json
import time
from functools import wraps

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

# ===== SYSTÈME DE LOGGING DÉTAILLÉ =====

def log_request_response(f):
    """Décorateur pour logger les requêtes et réponses en détail"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Timestamp de début
        start_time = time.time()
        request_id = f"{int(start_time * 1000000) % 1000000:06d}"
        
        # === LOGGING REQUÊTE ===
        current_app.logger.info(f"🚀 [{request_id}] === DÉBUT REQUÊTE ===")
        current_app.logger.info(f"📍 [{request_id}] {request.method} {request.url}")
        current_app.logger.info(f"🌐 [{request_id}] IP Client: {request.remote_addr}")
        current_app.logger.info(f"🔧 [{request_id}] User-Agent: {request.headers.get('User-Agent', 'N/A')}")
        
        # Headers (filtrage des sensibles)
        headers = dict(request.headers)
        if 'Authorization' in headers:
            headers['Authorization'] = f"{headers['Authorization'][:20]}..." if len(headers['Authorization']) > 20 else headers['Authorization']
        current_app.logger.info(f"📋 [{request_id}] Headers: {json.dumps(headers, indent=2, ensure_ascii=False)}")
        
        # Paramètres URL
        if request.args:
            current_app.logger.info(f"❓ [{request_id}] Query Params: {dict(request.args)}")
        
        # Corps de la requête
        try:
            if request.method in ['POST', 'PUT', 'PATCH']:
                # Données du formulaire
                if request.form:
                    form_data = dict(request.form)
                    current_app.logger.info(f"📝 [{request_id}] Form Data: {json.dumps(form_data, indent=2, ensure_ascii=False)}")
                
                # Fichiers uploadés
                if request.files:
                    files_info = {}
                    for key, file in request.files.items():
                        if file and file.filename:
                            files_info[key] = {
                                'filename': file.filename,
                                'content_type': file.content_type,
                                'size_bytes': len(file.read()) if hasattr(file, 'read') else 'unknown'
                            }
                            file.seek(0)  # Reset pour la suite du traitement
                        else:
                            files_info[key] = 'empty_file'
                    current_app.logger.info(f"📎 [{request_id}] Files: {json.dumps(files_info, indent=2, ensure_ascii=False)}")
                
                # JSON Data (si applicable)
                if request.is_json and request.get_json(silent=True):
                    json_data = request.get_json()
                    current_app.logger.info(f"📊 [{request_id}] JSON Body: {json.dumps(json_data, indent=2, ensure_ascii=False)}")
        
        except Exception as e:
            current_app.logger.warning(f"⚠️ [{request_id}] Erreur lecture body requête: {str(e)}")
        
        # === EXÉCUTION DE LA FONCTION ===
        try:
            response = f(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # === LOGGING RÉPONSE ===
            current_app.logger.info(f"✅ [{request_id}] === RÉPONSE GÉNÉRÉE ===")
            
            # Status Code
            if isinstance(response, tuple):
                response_data, status_code = response
                current_app.logger.info(f"📊 [{request_id}] Status Code: {status_code}")
            else:
                response_data = response
                status_code = 200
                current_app.logger.info(f"📊 [{request_id}] Status Code: {status_code} (default)")
            
            # Corps de la réponse
            try:
                if isinstance(response_data, str):
                    # Tenter de parser comme JSON
                    try:
                        parsed_json = json.loads(response_data)
                        current_app.logger.info(f"📤 [{request_id}] Response Body: {json.dumps(parsed_json, indent=2, ensure_ascii=False)}")
                    except:
                        current_app.logger.info(f"📤 [{request_id}] Response Body (text): {response_data}")
                else:
                    # Flask Response object ou dict
                    if hasattr(response_data, 'get_json'):
                        json_response = response_data.get_json()
                        current_app.logger.info(f"📤 [{request_id}] Response Body: {json.dumps(json_response, indent=2, ensure_ascii=False)}")
                    elif hasattr(response_data, 'data'):
                        current_app.logger.info(f"📤 [{request_id}] Response Body: {response_data.data.decode('utf-8')}")
                    else:
                        current_app.logger.info(f"📤 [{request_id}] Response Body: {str(response_data)}")
            except Exception as e:
                current_app.logger.warning(f"⚠️ [{request_id}] Erreur lecture response body: {str(e)}")
            
            current_app.logger.info(f"⏱️ [{request_id}] Temps d'exécution: {execution_time:.3f}s")
            current_app.logger.info(f"🏁 [{request_id}] === FIN REQUÊTE ===\n")
            
            return response
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            # === LOGGING ERREUR ===
            current_app.logger.error(f"❌ [{request_id}] === ERREUR SURVENUE ===")
            current_app.logger.error(f"💥 [{request_id}] Exception: {type(e).__name__}: {str(e)}")
            current_app.logger.error(f"⏱️ [{request_id}] Temps avant erreur: {execution_time:.3f}s")
            current_app.logger.error(f"🏁 [{request_id}] === FIN AVEC ERREUR ===\n")
            
            # Re-raise l'exception
            raise
    
    return decorated_function

# ===== DÉCORATEUR COMBINÉ =====

def admin_with_logging():
    """Décorateur combinant admin_required et logging"""
    def decorator(f):
        @admin_required()
        @log_request_response
        @wraps(f)
        def decorated_function(*args, **kwargs):
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- GESTION DES CATEGORIES ---

@products_admin_bp.route('/categories', methods=['POST'])
@admin_with_logging()
def create_categorie():
    current_app.logger.info("🏗️ POST /api/admin/categories - Début de la création.")
    try:
        data = request.form.to_dict()
        image_url = None
        if 'image' in request.files and request.files['image'].filename != '':
            image_file = request.files['image']
            try:
                upload_result = upload(image_file, folder="benin_luxe_cajou/categories")
                image_url = upload_result['secure_url']
                data['image_url'] = image_url
                current_app.logger.info(f"📸 Image uploadée sur Cloudinary: {image_url}")
            except CloudinaryError as e:
                current_app.logger.error(f"☁️ Erreur Cloudinary: {e.message}")
                return jsonify({"error": f"Erreur lors de l'upload: {e.message}"}), 500
        
        nouvelle_categorie = categorie_schema.load(data, session=db.session)
        db.session.add(nouvelle_categorie)
        db.session.commit()
        current_app.logger.info(f"✅ Catégorie créée avec ID: {nouvelle_categorie.id}")
        return jsonify(categorie_schema.dump(nouvelle_categorie)), 201
    except ValidationError as err:
        current_app.logger.error(f"❌ Erreur de validation: {err.messages}")
        return jsonify(err.messages), 400

@products_admin_bp.route('/categories/<int:id>', methods=['PUT'])
@admin_with_logging()
def update_categorie(id):
    current_app.logger.info(f"🔄 PUT /api/admin/categories/{id} - Début de la mise à jour.")
    categorie = Categorie.query.get_or_404(id)
    current_app.logger.info(f"📂 Catégorie trouvée: {categorie.nom}")
    try:
        # --- CORRECTION : Utilisation de request.form ---
        data = request.form.to_dict()
        # Logique pour la mise à jour de l'image si un nouveau fichier est envoyé
        if 'image' in request.files and request.files['image'].filename != '':
            image_file = request.files['image']
            try:
                upload_result = upload(image_file, folder="benin_luxe_cajou/categories")
                data['image_url'] = upload_result['secure_url']
                current_app.logger.info(f"📸 Nouvelle image uploadée: {upload_result['secure_url']}")
            except CloudinaryError as e:
                current_app.logger.error(f"☁️ Erreur Cloudinary: {e.message}")
                return jsonify({"error": f"Erreur lors de l'upload: {e.message}"}), 500
        
        updated_categorie = categorie_schema.load(data, instance=categorie, partial=True, session=db.session)
        db.session.commit()
        current_app.logger.info(f"✅ Catégorie {id} mise à jour avec succès")
        return jsonify(categorie_schema.dump(updated_categorie)), 200
    except ValidationError as err:
        current_app.logger.error(f"❌ Erreur de validation: {err.messages}")
        return jsonify(err.messages), 400

# --- GESTION DES TYPES DE PRODUITS ---

@products_admin_bp.route('/product-types', methods=['POST'])
@admin_with_logging()
def create_type_produit():
    current_app.logger.info("🏗️ POST /api/admin/product-types - Début de la création.")
    try:
        data = request.form.to_dict()
        image_url = None
        if 'image' in request.files and request.files['image'].filename != '':
            image_file = request.files['image']
            try:
                upload_result = upload(image_file, folder="benin_luxe_cajou/types_produits")
                image_url = upload_result['secure_url']
                data['image_url'] = image_url
                current_app.logger.info(f"📸 Image uploadée sur Cloudinary: {image_url}")
            except CloudinaryError as e:
                current_app.logger.error(f"☁️ Erreur Cloudinary: {e.message}")
                return jsonify({"error": f"Erreur lors de l'upload: {e.message}"}), 500
        nouveau_type = type_produit_schema.load(data, session=db.session)
        db.session.add(nouveau_type)
        db.session.commit()
        current_app.logger.info(f"✅ Type produit créé avec ID: {nouveau_type.id}")
        return jsonify(type_produit_schema.dump(nouveau_type)), 201
    except ValidationError as err:
        current_app.logger.error(f"❌ Erreur de validation: {err.messages}")
        return jsonify(err.messages), 400

@products_admin_bp.route('/product-types/<int:id>', methods=['PUT'])
@admin_with_logging()
def update_type_produit(id):
    current_app.logger.info(f"🔄 PUT /api/admin/product-types/{id} - Début de la mise à jour.")
    type_produit = TypeProduit.query.get_or_404(id)
    current_app.logger.info(f"📂 Type produit trouvé: {type_produit.nom}")
    try:
        # --- CORRECTION : Utilisation de request.form ---
        data = request.form.to_dict()
        if 'image' in request.files and request.files['image'].filename != '':
            image_file = request.files['image']
            try:
                upload_result = upload(image_file, folder="benin_luxe_cajou/types_produits")
                data['image_url'] = upload_result['secure_url']
                current_app.logger.info(f"📸 Nouvelle image uploadée: {upload_result['secure_url']}")
            except CloudinaryError as e:
                current_app.logger.error(f"☁️ Erreur Cloudinary: {e.message}")
                return jsonify({"error": f"Erreur lors de l'upload: {e.message}"}), 500

        updated_type = type_produit_schema.load(data, instance=type_produit, partial=True, session=db.session)
        db.session.commit()
        current_app.logger.info(f"✅ Type produit {id} mis à jour avec succès")
        return jsonify(type_produit_schema.dump(updated_type)), 200
    except ValidationError as err:
        current_app.logger.error(f"❌ Erreur de validation: {err.messages}")
        return jsonify(err.messages), 400

# --- GESTION DES PRODUITS ---

@products_admin_bp.route('/products', methods=['POST'])
@admin_with_logging()
def create_produit():
    current_app.logger.info("🏗️ POST /api/admin/products - Début de la création.")
    try:
        # --- CORRECTION : Utilisation de request.form ---
        data = request.form.to_dict()
        nouveau_produit = produit_schema.load(data, session=db.session)
        db.session.add(nouveau_produit)
        db.session.commit()
        current_app.logger.info(f"✅ Produit créé avec ID: {nouveau_produit.id}")
        return jsonify(produit_schema.dump(nouveau_produit)), 201
    except ValidationError as err:
        current_app.logger.error(f"❌ Erreur de validation: {err.messages}")
        return jsonify(err.messages), 400

@products_admin_bp.route('/products/<int:id>', methods=['PUT'])
@admin_with_logging()
def update_produit(id):
    current_app.logger.info(f"🔄 PUT /api/admin/products/{id} - Début de la mise à jour.")
    produit = Produit.query.get_or_404(id)
    current_app.logger.info(f"📂 Produit trouvé: {produit.nom}")
    
    try:
        # Récupérer les données JSON au lieu de form data
        data = request.get_json()
        
        if not data:
            return jsonify({"msg": "Aucune donnée fournie"}), 400
            
        # Debug : voir ce qu'on reçoit réellement
        current_app.logger.info(f"📊 Données reçues: {data}")
        
        # Validation avec Marshmallow
        produit_schema.load(data, partial=True)
        
        # Mise à jour des champs
        for key, value in data.items():
            if hasattr(produit, key):
                current_app.logger.info(f"🔄 Mise à jour {key}: {getattr(produit, key)} -> {value}")
                setattr(produit, key, value)
        
        db.session.commit()
        current_app.logger.info(f"✅ Produit {id} mis à jour avec succès")
        return jsonify(produit_schema.dump(produit)), 200
        
    except ValidationError as err:
        current_app.logger.error(f"❌ Erreur de validation: {err.messages}")
        return jsonify(err.messages), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Erreur inattendue: {str(e)}", exc_info=True)
        return jsonify({"msg": "Erreur interne du serveur"}), 500

# --- ROUTES DE LECTURE ET GESTION DES IMAGES DE PRODUIT (Inchangées car déjà correctes) ---

@products_admin_bp.route('/categories', methods=['GET'])
@admin_with_logging()
def get_categories():
    current_app.logger.info("📋 GET /api/admin/categories - Récupération des catégories")
    categories = Categorie.query.all()
    current_app.logger.info(f"📊 {len(categories)} catégories trouvées")
    return jsonify(categories_schema.dump(categories)), 200

@products_admin_bp.route('/product-types', methods=['GET'])
@admin_with_logging()
def get_types_produits():
    current_app.logger.info("📋 GET /api/admin/product-types - Récupération des types")
    types = TypeProduit.query.all()
    current_app.logger.info(f"📊 {len(types)} types de produits trouvés")
    return jsonify(types_produits_schema.dump(types)), 200

@products_admin_bp.route('/products', methods=['GET'])
@admin_with_logging()
def get_produits():
    current_app.logger.info("📋 GET /api/admin/products - Récupération des produits")
    produits = Produit.query.order_by(Produit.id.desc()).all()
    current_app.logger.info(f"📊 {len(produits)} produits trouvés")
    return jsonify(produits_schema.dump(produits)), 200

@products_admin_bp.route('/products/<int:id>', methods=['GET'])
@admin_with_logging()
def get_produit_detail(id):
    current_app.logger.info(f"📋 GET /api/admin/products/{id} - Récupération détail produit")
    produit = Produit.query.get_or_404(id)
    current_app.logger.info(f"📂 Produit trouvé: {produit.nom}")
    return jsonify(produit_schema.dump(produit)), 200

@products_admin_bp.route('/products/<int:id>/images', methods=['POST'])
@admin_with_logging()
def upload_product_image(id):
    current_app.logger.info(f"📸 POST /api/admin/products/{id}/images - Upload image produit")
    produit = Produit.query.get_or_404(id)
    current_app.logger.info(f"📂 Produit trouvé: {produit.nom}")
    
    if 'image' not in request.files:
        current_app.logger.warning("⚠️ Aucun fichier image dans la requête")
        return jsonify({"error": "Aucun fichier image n'a été envoyé"}), 400
    
    file_to_upload = request.files['image']
    current_app.logger.info(f"📎 Fichier à uploader: {file_to_upload.filename}")
    
    try:
        upload_result = upload(file_to_upload, folder="benin_luxe_cajou/produits")
        current_app.logger.info(f"☁️ Upload Cloudinary réussi: {upload_result['secure_url']}")
        
        nouvelle_image = ImageProduit(produit_id=id, url_image=upload_result['secure_url'], alt_text=produit.nom)
        if not produit.images:
            nouvelle_image.est_principale = True
            current_app.logger.info("🏷️ Définie comme image principale (première image)")
        
        db.session.add(nouvelle_image)
        db.session.commit()
        current_app.logger.info(f"✅ Image produit créée avec ID: {nouvelle_image.id}")
        return jsonify(image_produit_schema.dump(nouvelle_image)), 201
    except CloudinaryError as e:
        current_app.logger.error(f"☁️ Erreur Cloudinary: {e.message}")
        return jsonify({"error": f"Erreur Cloudinary : {e.message}"}), 500

@products_admin_bp.route('/images/<int:image_id>/set-primary', methods=['POST'])
@admin_with_logging()
def set_primary_image(image_id):
    current_app.logger.info(f"🏷️ POST /api/admin/images/{image_id}/set-primary - Définir image principale")
    image_a_definir = ImageProduit.query.get_or_404(image_id)
    produit_id = image_a_definir.produit_id
    current_app.logger.info(f"📂 Image trouvée pour produit ID: {produit_id}")
    
    # Réinitialiser toutes les images comme non-principales
    nb_updated = ImageProduit.query.filter_by(produit_id=produit_id).update({'est_principale': False})
    current_app.logger.info(f"🔄 {nb_updated} images réinitialisées comme non-principales")
    
    # Définir la nouvelle image principale
    image_a_definir.est_principale = True
    db.session.commit()
    current_app.logger.info(f"✅ Image {image_id} définie comme principale")
    return jsonify({"message": "Image principale définie avec succès"}), 200
