# app/__init__.py

from flask import Flask
import cloudinary
from config import Config
from .extensions import db, migrate, jwt, ma, mail
import logging
from logging.handlers import RotatingFileHandler
import os

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # --- CONFIGURATION DU LOGGING (LA BONNE MÉTHODE) ---
    if not app.debug and not app.testing:
        # Configuration pour logger dans les logs de Render (stdout)
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

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(products_admin_bp, url_prefix='/api/admin')

    return app
