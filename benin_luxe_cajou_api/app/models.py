# app/models.py

import bcrypt
from .extensions import db
from sqlalchemy.orm import relationship

class Utilisateur(db.Model):
    __tablename__ = 'utilisateurs'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    telephone = db.Column(db.String(20))
    mot_de_passe = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum('client', 'admin'), nullable=False, default='client')
    statut = db.Column(db.Enum('actif', 'inactif', 'suspendu'), nullable=False, default='actif')
    email_verifie = db.Column(db.Boolean, default=False)
    token_verification = db.Column(db.String(64))
    derniere_connexion = db.Column(db.TIMESTAMP)
    date_creation = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

    adresses = relationship('AdresseLivraison', backref='utilisateur', lazy=True, cascade="all, delete-orphan")
    commandes = relationship('Commande', backref='client', lazy=True)
    notifications = relationship('Notification', backref='utilisateur', lazy=True, cascade="all, delete-orphan")
    paniers = relationship('Panier', backref='utilisateur', lazy=True, cascade="all, delete-orphan")
    avis = relationship('AvisProduit', backref='utilisateur', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        self.mot_de_passe = pw_hash.decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.mot_de_passe.encode('utf-8'))

class Categorie(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(255))
    statut = db.Column(db.Enum('actif', 'inactif'), nullable=False, default='actif')
    types_produits = relationship('TypeProduit', backref='categorie', lazy=True)

class TypeProduit(db.Model):
    __tablename__ = 'types_produits'
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    nom = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(255))
    statut = db.Column(db.Enum('actif', 'inactif'), nullable=False, default='actif')
    produits = relationship('Produit', backref='type_produit', lazy=True)

class Produit(db.Model):
    __tablename__ = 'produits'
    id = db.Column(db.Integer, primary_key=True)
    type_produit_id = db.Column(db.Integer, db.ForeignKey('types_produits.id'), nullable=False)
    nom = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    quantite_contenant = db.Column(db.Integer, nullable=False)
    type_contenant = db.Column(db.Enum('sachet', 'boite'), default='sachet')
    prix_unitaire = db.Column(db.Numeric(10, 2), nullable=False)
    gestion_stock = db.Column(db.Enum('limite', 'illimite'), default='limite')
    stock_disponible = db.Column(db.Integer, default=0)
    stock_minimum = db.Column(db.Integer, default=5)
    statut = db.Column(db.Enum('actif', 'inactif', 'rupture_stock'), nullable=False, default='actif')
    images = relationship('ImageProduit', backref='produit', lazy=True, cascade="all, delete-orphan")
    avis = relationship('AvisProduit', backref='produit', lazy=True, cascade="all, delete-orphan")

class ImageProduit(db.Model):
    __tablename__ = 'images_produits'
    id = db.Column(db.Integer, primary_key=True)
    produit_id = db.Column(db.Integer, db.ForeignKey('produits.id'), nullable=False)
    url_image = db.Column(db.String(255), nullable=False)
    alt_text = db.Column(db.String(255))
    ordre_affichage = db.Column(db.Integer, default=1)
    est_principale = db.Column(db.Boolean, default=False)

class AdresseLivraison(db.Model):
    __tablename__ = 'adresses_livraison'
    id = db.Column(db.Integer, primary_key=True)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey('utilisateurs.id'), nullable=False)
    nom_destinataire = db.Column(db.String(100))
    telephone_destinataire = db.Column(db.String(20), nullable=False)
    ville = db.Column(db.String(100), nullable=False)
    quartier = db.Column(db.String(100))
    description_adresse = db.Column(db.Text, nullable=False)
    point_repere = db.Column(db.String(255))
    latitude = db.Column(db.Numeric(10, 8))
    longitude = db.Column(db.Numeric(11, 8))
    precision_gps = db.Column(db.Integer)
    type_adresse = db.Column(db.Enum('manuelle', 'gps_actuelle', 'gps_choisie'), nullable=False)
    est_defaut = db.Column(db.Boolean, default=False)

class Commande(db.Model):
    __tablename__ = 'commandes'
    id = db.Column(db.Integer, primary_key=True)
    numero_commande = db.Column(db.String(50), unique=True, nullable=False)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey('utilisateurs.id'), nullable=False)
    adresse_livraison_id = db.Column(db.Integer, db.ForeignKey('adresses_livraison.id'), nullable=False)
    statut = db.Column(db.Enum('en_attente', 'confirmee', 'en_preparation', 'expedie', 'livree', 'annulee'), nullable=False, default='en_attente')
    sous_total = db.Column(db.Numeric(10, 2), nullable=False)
    frais_livraison = db.Column(db.Numeric(8, 2), default=0)
    coupon_id = db.Column(db.Integer, db.ForeignKey('coupons.id'))
    montant_reduction = db.Column(db.Numeric(10, 2), default=0)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    statut_paiement = db.Column(db.Enum('en_attente', 'paye', 'echoue', 'rembourse'), nullable=False, default='en_attente')
    notes_client = db.Column(db.Text)
    notes_admin = db.Column(db.Text)
    date_commande = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())
    date_livraison_prevue = db.Column(db.Date)
    date_livraison_effective = db.Column(db.DateTime)
    
    details = relationship('DetailsCommande', back_populates='commande', cascade="all, delete-orphan")
    suivi = relationship('SuiviCommande', backref='commande', lazy=True, cascade="all, delete-orphan")
    paiements = relationship('Paiement', backref='commande', lazy=True, cascade="all, delete-orphan")
    adresse_livraison = relationship('AdresseLivraison')
    coupon = relationship('Coupon')

class DetailsCommande(db.Model):
    __tablename__ = 'details_commande'
    id = db.Column(db.Integer, primary_key=True)
    commande_id = db.Column(db.Integer, db.ForeignKey('commandes.id'), nullable=False)
    produit_id = db.Column(db.Integer, db.ForeignKey('produits.id'), nullable=False)
    quantite = db.Column(db.Integer, nullable=False)
    prix_unitaire = db.Column(db.Numeric(10, 2), nullable=False)
    sous_total = db.Column(db.Numeric(10, 2), nullable=False)
    
    commande = relationship('Commande', back_populates='details')
    produit = relationship('Produit')

class SuiviCommande(db.Model):
    __tablename__ = 'suivi_commandes'
    id = db.Column(db.Integer, primary_key=True)
    commande_id = db.Column(db.Integer, db.ForeignKey('commandes.id'), nullable=False)
    statut = db.Column(db.Enum('en_attente', 'confirmee', 'en_preparation', 'expedie', 'livree', 'annulee'), nullable=False)
    message = db.Column(db.Text)
    modifie_par = db.Column(db.Integer, db.ForeignKey('utilisateurs.id'))
    date_changement = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

class Paiement(db.Model):
    __tablename__ = 'paiements'
    id = db.Column(db.Integer, primary_key=True)
    commande_id = db.Column(db.Integer, db.ForeignKey('commandes.id'), nullable=False)
    fedapay_transaction_id = db.Column(db.String(100), nullable=False)
    montant = db.Column(db.Numeric(10, 2), nullable=False)
    devise = db.Column(db.String(10), default='XOF')
    statut = db.Column(db.Enum('pending', 'approved', 'declined', 'canceled'), nullable=False)
    methode_paiement = db.Column(db.String(50))
    reference_paiement = db.Column(db.String(100))
    callback_data = db.Column(db.JSON)
    date_paiement = db.Column(db.TIMESTAMP)

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey('utilisateurs.id'), nullable=False)
    type = db.Column(db.Enum('nouvelle_commande', 'statut_commande', 'paiement', 'livraison', 'promotion'), nullable=False)
    titre = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    est_lu = db.Column(db.Boolean, default=False)
    date_lecture = db.Column(db.TIMESTAMP)

class Panier(db.Model):
    __tablename__ = 'paniers'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100))
    utilisateur_id = db.Column(db.Integer, db.ForeignKey('utilisateurs.id'))
    produit_id = db.Column(db.Integer, db.ForeignKey('produits.id'), nullable=False)
    quantite = db.Column(db.Integer, nullable=False)
    produit = relationship('Produit')

class AvisProduit(db.Model):
    __tablename__ = 'avis_produits'
    id = db.Column(db.Integer, primary_key=True)
    produit_id = db.Column(db.Integer, db.ForeignKey('produits.id'), nullable=False)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey('utilisateurs.id'), nullable=False)
    commande_id = db.Column(db.Integer, db.ForeignKey('commandes.id'), nullable=False)
    note = db.Column(db.Integer, nullable=False)
    commentaire = db.Column(db.Text)
    statut = db.Column(db.Enum('en_attente', 'approuve', 'rejete'), default='en_attente')

class Coupon(db.Model):
    __tablename__ = 'coupons'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text)
    type_reduction = db.Column(db.Enum('pourcentage', 'montant_fixe'), nullable=False)
    valeur_reduction = db.Column(db.Numeric(10, 2), nullable=False)
    montant_minimum_commande = db.Column(db.Numeric(10, 2), default=0)
    date_debut = db.Column(db.DateTime)
    date_fin = db.Column(db.DateTime)
    limite_utilisation = db.Column(db.Integer)
    utilisations_actuelles = db.Column(db.Integer, default=0)
    statut = db.Column(db.Enum('actif', 'inactif'), default='actif')

class ParametreSite(db.Model):
    __tablename__ = 'parametres_site'
    id = db.Column(db.Integer, primary_key=True)
    cle = db.Column(db.String(100), unique=True, nullable=False)
    valeur = db.Column(db.Text)
    description = db.Column(db.String(255))
    type = db.Column(db.Enum('string', 'number', 'boolean', 'json'), nullable=False)

class ZoneLivraison(db.Model):
    __tablename__ = 'zones_livraison'
    id = db.Column(db.Integer, primary_key=True)
    nom_zone = db.Column(db.String(100), nullable=False)
    villes = db.Column(db.Text)
    tarif_livraison = db.Column(db.Numeric(8, 2), nullable=False)
    delai_livraison_jours = db.Column(db.Integer, default=3)
    actif = db.Column(db.Boolean, default=True)