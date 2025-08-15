from flask import Flask
import cloudinary
from config import Config
from .extensions import db, migrate, jwt, ma, mail # Ajout de mail

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if app.config.get('CLOUDINARY_URL'):
        cloudinary.config(cloud_name=app.config['CLOUDINARY_URL'].split('@')[-1],
                          api_key=app.config['CLOUDINARY_URL'].split('//')[-1].split(':')[0],
                          api_secret=app.config['CLOUDINARY_URL'].split(':')[2].split('@')[0])

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    ma.init_app(app)
    mail.init_app(app) # Initialisation de mail

    with app.app_context():
        from . import models

    from .auth.routes import auth_bp
    from .admin.routes import admin_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')

    return app