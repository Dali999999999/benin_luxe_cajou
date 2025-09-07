# app/__init__.py

from flask import Flask
from flask_cors import CORS # <<< 1. IMPORTER CORS
import cloudinary
from config import Config
from .extensions import db, migrate, jwt, ma, mail
import logging

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # --- 2. ACTIVER CORS POUR TOUTE L'APPLICATION AVEC COOKIES ---
    # Configuration CORS pour supporter les cookies (credentials: include)
    CORS(app, 
         supports_credentials=True,
         origins=[
             'http://localhost:3000',
             'http://127.0.0.1:3000', 
             'https://benin-luxe-cajou-frontend.vercel.app'
         ],
         allow_headers=['Content-Type', 'Authorization'],
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])

    # Configuration du logging
    if not app.debug and not app.testing:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        app.logger.addHandler(stream_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Benin Luxe Cajou API startup')

    if app.config.get('CLOUDINARY_URL'):
        cloudinary.config(cloud_name=app.config['CLOUDINARY_URL'].split('@')[-1],
                          api_key=app.config['CLOUDINARY_URL'].split('//')[-1].split(':')[0],
                          api_secret=app.config['CLOUDINARY_URL'].split(':')[2].split('@')[0])

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    ma.init_app(app)
    mail.init_app(app)

    with app.app_context():
        from . import models

    from .auth.routes import auth_bp
    from .admin.routes import admin_bp
    from .products_admin.routes import products_admin_bp
    from .public_api.routes import public_api_bp
    from .client_auth.routes import client_auth_bp
    from .cart.routes import cart_bp
    from .user_profile.routes import user_profile_bp
    from .site_config.routes import site_config_bp
    from .payment.routes import payment_bp
    from .orders_admin.routes import orders_admin_bp
    

    # Blueprints Admin
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(products_admin_bp, url_prefix='/api/admin')
    app.register_blueprint(site_config_bp, url_prefix='/api/admin')
    app.register_blueprint(orders_admin_bp, url_prefix='/api/admin/orders')

    # Blueprints Client
    app.register_blueprint(public_api_bp, url_prefix='/api')
    app.register_blueprint(client_auth_bp, url_prefix='/auth')
    app.register_blueprint(cart_bp, url_prefix='/api/cart')
    app.register_blueprint(user_profile_bp, url_prefix='/api/profile')
    app.register_blueprint(payment_bp, url_prefix='/api/payment')

    return app





