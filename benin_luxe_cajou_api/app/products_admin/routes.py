# app/products_admin/routes.py

from flask import Blueprint, request, jsonify
from cloudinary.uploader import upload
from cloudinary.exceptions import Error as CloudinaryError
from datetime import datetime

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
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    route_name = "CREATE_CATEGORIE"
    
    print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🚀 DÉBUT - IP: {client_ip}")
    
    try:
        data = request.get_json()
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📥 Données reçues: {list(data.keys()) if data else 'None'}")
        
        if not data:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⚠️ ÉCHEC - Aucune donnée JSON - IP: {client_ip}")
            return jsonify({"error": "Données JSON requises"}), 400
        
        nom_categorie = data.get('nom', 'Non spécifié')
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📂 Création catégorie: {nom_categorie}")
        
        nouvelle_categorie = categorie_schema.load(data, session=db.session)
        db.session.add(nouvelle_categorie)
        db.session.commit()
        
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ SUCCÈS - Catégorie créée: {nouvelle_categorie.nom} - ID: {nouvelle_categorie.id} - IP: {client_ip}")
        return jsonify(categorie_schema.dump(nouvelle_categorie)), 201
        
    except Exception as e:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ ERREUR - IP: {client_ip} - {str(e)}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    
    finally:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🏁 FIN - IP: {client_ip}")

@products_admin_bp.route('/categories', methods=['GET'])
@admin_required()
def get_categories():
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    route_name = "GET_CATEGORIES"
    
    print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🚀 DÉBUT - IP: {client_ip}")
    
    try:
        categories = Categorie.query.all()
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📊 {len(categories)} catégories trouvées")
        
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ SUCCÈS - Liste des catégories récupérée - IP: {client_ip}")
        return jsonify(categories_schema.dump(categories)), 200
        
    except Exception as e:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ ERREUR - IP: {client_ip} - {str(e)}")
        return jsonify({"error": "Erreur lors de la récupération des catégories"}), 500
    
    finally:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🏁 FIN - IP: {client_ip}")

@products_admin_bp.route('/categories/<int:id>', methods=['PUT'])
@admin_required()
def update_categorie(id):
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    route_name = "UPDATE_CATEGORIE"
    
    print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🚀 DÉBUT - Catégorie ID: {id} - IP: {client_ip}")
    
    try:
        categorie = Categorie.query.get_or_404(id)
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📂 Catégorie trouvée: {categorie.nom}")
        
        data = request.get_json()
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📥 Données de mise à jour: {list(data.keys()) if data else 'None'}")
        
        ancien_nom = categorie.nom
        categorie.nom = data.get('nom', categorie.nom)
        categorie.description = data.get('description', categorie.description)
        categorie.statut = data.get('statut', categorie.statut)
        
        db.session.commit()
        
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ SUCCÈS - Catégorie mise à jour: {ancien_nom} → {categorie.nom} - ID: {id} - IP: {client_ip}")
        return jsonify(categorie_schema.dump(categorie)), 200
        
    except Exception as e:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ ERREUR - ID: {id} - IP: {client_ip} - {str(e)}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    
    finally:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🏁 FIN - ID: {id} - IP: {client_ip}")

# --- GESTION DES TYPES DE PRODUITS ---

@products_admin_bp.route('/product-types', methods=['POST'])
@admin_required()
def create_type_produit():
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    route_name = "CREATE_TYPE_PRODUIT"
    
    print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🚀 DÉBUT - IP: {client_ip}")
    
    try:
        data = request.get_json()
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📥 Données reçues: {list(data.keys()) if data else 'None'}")
        
        if not data:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⚠️ ÉCHEC - Aucune donnée JSON - IP: {client_ip}")
            return jsonify({"error": "Données JSON requises"}), 400
        
        nom_type = data.get('nom', 'Non spécifié')
        category_id = data.get('category_id')
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🏷️ Création type produit: {nom_type} - Catégorie ID: {category_id}")
        
        nouveau_type = type_produit_schema.load(data, session=db.session)
        db.session.add(nouveau_type)
        db.session.commit()
        
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ SUCCÈS - Type produit créé: {nouveau_type.nom} - ID: {nouveau_type.id} - IP: {client_ip}")
        return jsonify(type_produit_schema.dump(nouveau_type)), 201
        
    except Exception as e:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ ERREUR - IP: {client_ip} - {str(e)}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    
    finally:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🏁 FIN - IP: {client_ip}")

@products_admin_bp.route('/product-types', methods=['GET'])
@admin_required()
def get_types_produits():
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    route_name = "GET_TYPES_PRODUITS"
    
    print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🚀 DÉBUT - IP: {client_ip}")
    
    try:
        types = TypeProduit.query.all()
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📊 {len(types)} types de produits trouvés")
        
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ SUCCÈS - Liste des types récupérée - IP: {client_ip}")
        return jsonify(types_produits_schema.dump(types)), 200
        
    except Exception as e:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ ERREUR - IP: {client_ip} - {str(e)}")
        return jsonify({"error": "Erreur lors de la récupération des types de produits"}), 500
    
    finally:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🏁 FIN - IP: {client_ip}")

@products_admin_bp.route('/product-types/<int:id>', methods=['PUT'])
@admin_required()
def update_type_produit(id):
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    route_name = "UPDATE_TYPE_PRODUIT"
    
    print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🚀 DÉBUT - Type ID: {id} - IP: {client_ip}")
    
    try:
        type_produit = TypeProduit.query.get_or_404(id)
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🏷️ Type trouvé: {type_produit.nom}")
        
        data = request.get_json()
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📥 Données de mise à jour: {list(data.keys()) if data else 'None'}")
        
        ancien_nom = type_produit.nom
        type_produit.nom = data.get('nom', type_produit.nom)
        type_produit.description = data.get('description', type_produit.description)
        type_produit.statut = data.get('statut', type_produit.statut)
        type_produit.category_id = data.get('category_id', type_produit.category_id)
        
        db.session.commit()
        
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ SUCCÈS - Type mis à jour: {ancien_nom} → {type_produit.nom} - ID: {id} - IP: {client_ip}")
        return jsonify(type_produit_schema.dump(type_produit)), 200
        
    except Exception as e:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ ERREUR - ID: {id} - IP: {client_ip} - {str(e)}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    
    finally:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🏁 FIN - ID: {id} - IP: {client_ip}")

# --- GESTION DES PRODUITS ---

@products_admin_bp.route('/products', methods=['POST'])
@admin_required()
def create_produit():
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    route_name = "CREATE_PRODUIT"
    
    print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🚀 DÉBUT - IP: {client_ip}")
    
    try:
        data = request.get_json()
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📥 Données reçues: {list(data.keys()) if data else 'None'}")
        
        if not data:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⚠️ ÉCHEC - Aucune donnée JSON - IP: {client_ip}")
            return jsonify({"error": "Données JSON requises"}), 400
        
        nom_produit = data.get('nom', 'Non spécifié')
        prix = data.get('prix', 0)
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🛍️ Création produit: {nom_produit} - Prix: {prix}")
        
        nouveau_produit = produit_schema.load(data, session=db.session)
        db.session.add(nouveau_produit)
        db.session.commit()
        
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ SUCCÈS - Produit créé: {nouveau_produit.nom} - ID: {nouveau_produit.id} - IP: {client_ip}")
        return jsonify(produit_schema.dump(nouveau_produit)), 201
        
    except Exception as e:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ ERREUR - IP: {client_ip} - {str(e)}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    
    finally:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🏁 FIN - IP: {client_ip}")

@products_admin_bp.route('/products', methods=['GET'])
@admin_required()
def get_produits():
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    route_name = "GET_PRODUITS"
    
    print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🚀 DÉBUT - IP: {client_ip}")
    
    try:
        produits = Produit.query.order_by(Produit.id.desc()).all()
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📊 {len(produits)} produits trouvés")
        
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ SUCCÈS - Liste des produits récupérée - IP: {client_ip}")
        return jsonify(produits_schema.dump(produits)), 200
        
    except Exception as e:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ ERREUR - IP: {client_ip} - {str(e)}")
        return jsonify({"error": "Erreur lors de la récupération des produits"}), 500
    
    finally:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🏁 FIN - IP: {client_ip}")

@products_admin_bp.route('/products/<int:id>', methods=['GET'])
@admin_required()
def get_produit_detail(id):
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    route_name = "GET_PRODUIT_DETAIL"
    
    print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🚀 DÉBUT - Produit ID: {id} - IP: {client_ip}")
    
    try:
        produit = Produit.query.get_or_404(id)
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🛍️ Produit trouvé: {produit.nom}")
        
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ SUCCÈS - Détails produit récupérés - ID: {id} - IP: {client_ip}")
        return jsonify(produit_schema.dump(produit)), 200
        
    except Exception as e:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ ERREUR - ID: {id} - IP: {client_ip} - {str(e)}")
        return jsonify({"error": "Produit non trouvé"}), 404
    
    finally:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🏁 FIN - ID: {id} - IP: {client_ip}")

@products_admin_bp.route('/products/<int:id>', methods=['PUT'])
@admin_required()
def update_produit(id):
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    route_name = "UPDATE_PRODUIT"
    
    print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🚀 DÉBUT - Produit ID: {id} - IP: {client_ip}")
    
    try:
        produit = Produit.query.get_or_404(id)
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🛍️ Produit trouvé: {produit.nom}")
        
        data = request.get_json()
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📥 Données de mise à jour: {list(data.keys()) if data else 'None'}")
        
        ancien_nom = produit.nom
        champs_modifies = []
        
        # Simple mise à jour champ par champ avec tracking
        for key, value in data.items():
            if hasattr(produit, key):
                ancienne_valeur = getattr(produit, key)
                setattr(produit, key, value)
                if ancienne_valeur != value:
                    champs_modifies.append(f"{key}: {ancienne_valeur} → {value}")
        
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔄 Champs modifiés: {', '.join(champs_modifies) if champs_modifies else 'Aucun'}")
        
        db.session.commit()
        
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ SUCCÈS - Produit mis à jour: {ancien_nom} → {produit.nom} - ID: {id} - IP: {client_ip}")
        return jsonify(produit_schema.dump(produit)), 200
        
    except Exception as e:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ ERREUR - ID: {id} - IP: {client_ip} - {str(e)}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    
    finally:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🏁 FIN - ID: {id} - IP: {client_ip}")

# --- GESTION DES IMAGES DE PRODUITS ---

@products_admin_bp.route('/products/<int:id>/images', methods=['POST'])
@admin_required()
def upload_product_image(id):
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    route_name = "UPLOAD_PRODUCT_IMAGE"
    
    print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🚀 DÉBUT - Produit ID: {id} - IP: {client_ip}")
    
    try:
        produit = Produit.query.get_or_404(id)
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🛍️ Produit trouvé: {produit.nom}")
        
        if 'image' not in request.files:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⚠️ ÉCHEC - Aucun fichier image - IP: {client_ip}")
            return jsonify({"error": "Aucun fichier image n'a été envoyé"}), 400
            
        file_to_upload = request.files['image']
        filename = file_to_upload.filename
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📁 Fichier reçu: {filename}")
        
        try:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ☁️ Upload vers Cloudinary en cours...")
            # Envoi de l'image à Cloudinary
            upload_result = upload(
                file_to_upload,
                folder=f"benin_luxe_cajou/produits",
                public_id=f"prod_{id}_{filename}"
            )
            
            cloudinary_url = upload_result['secure_url']
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ Upload Cloudinary réussi: {cloudinary_url}")
            
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
                print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🌟 Première image - Définie comme principale")
            else:
                print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📷 Image supplémentaire - {images_existantes} images existantes")

            db.session.add(nouvelle_image)
            db.session.commit()
            
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ SUCCÈS - Image ajoutée: {filename} - Produit: {produit.nom} - ID: {nouvelle_image.id} - IP: {client_ip}")
            return jsonify(image_produit_schema.dump(nouvelle_image)), 201

        except CloudinaryError as e:
            print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ ERREUR CLOUDINARY - IP: {client_ip} - {str(e)}")
            return jsonify({"error": f"Erreur Cloudinary : {e.message}"}), 500
            
    except Exception as e:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ ERREUR CRITIQUE - ID: {id} - IP: {client_ip} - {str(e)}")
        db.session.rollback()
        return jsonify({"error": f"Erreur interne : {str(e)}"}), 500
    
    finally:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🏁 FIN - ID: {id} - IP: {client_ip}")

@products_admin_bp.route('/images/<int:image_id>/set-primary', methods=['POST'])
@admin_required()
def set_primary_image(image_id):
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    route_name = "SET_PRIMARY_IMAGE"
    
    print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🚀 DÉBUT - Image ID: {image_id} - IP: {client_ip}")
    
    try:
        image_a_definir = ImageProduit.query.get_or_404(image_id)
        produit_id = image_a_definir.produit_id
        
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📷 Image trouvée - Produit ID: {produit_id}")
        
        # Compter les images actuelles du produit
        images_produit = ImageProduit.query.filter_by(produit_id=produit_id).all()
        ancienne_principale = next((img for img in images_produit if img.est_principale), None)
        
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔄 Changement image principale - Ancienne: {ancienne_principale.id if ancienne_principale else 'Aucune'} → Nouvelle: {image_id}")

        # Retirer le statut "principal" de toutes les autres images de ce produit
        ImageProduit.query.filter_by(produit_id=produit_id).update({'est_principale': False})
        
        # Définir la nouvelle image comme principale
        image_a_definir.est_principale = True
        
        db.session.commit()
        
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ SUCCÈS - Image principale définie: ID {image_id} - Produit ID: {produit_id} - IP: {client_ip}")
        return jsonify({"message": "Image principale définie avec succès"}), 200
        
    except Exception as e:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ ERREUR - Image ID: {image_id} - IP: {client_ip} - {str(e)}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    
    finally:
        print(f"[{route_name}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🏁 FIN - Image ID: {image_id} - IP: {client_ip}")
