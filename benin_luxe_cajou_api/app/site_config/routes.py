# app/site_config/routes.py

from flask import Blueprint, request, jsonify, current_app
from marshmallow import ValidationError
from app.extensions import db
from app.models import ZoneLivraison, Coupon
from app.admin.admin_auth import admin_required
from app.schemas import (
    zone_livraison_schema, zones_livraison_schema,
    coupon_schema, coupons_schema
)

site_config_bp = Blueprint('site_config', __name__)

# --- GESTION DES ZONES DE LIVRAISON ---

@site_config_bp.route('/delivery-zones', methods=['POST'])
@admin_required()
def create_delivery_zone():
    """Crée une nouvelle zone de livraison."""
    data = request.form.to_dict()
    try:
        new_zone = zone_livraison_schema.load(data, session=db.session)
        db.session.add(new_zone)
        db.session.commit()
        return jsonify(zone_livraison_schema.dump(new_zone)), 201
    except ValidationError as err:
        return jsonify(err.messages), 400

@site_config_bp.route('/delivery-zones', methods=['GET'])
@admin_required()
def get_delivery_zones():
    """Liste toutes les zones de livraison."""
    zones = ZoneLivraison.query.all()
    return jsonify(zones_livraison_schema.dump(zones)), 200

@site_config_bp.route('/delivery-zones/<int:id>', methods=['PUT'])
@admin_required()
def update_delivery_zone(id):
    """Met à jour une zone de livraison."""
    zone = ZoneLivraison.query.get_or_404(id)
    data = request.form.to_dict()
    try:
        updated_zone = zone_livraison_schema.load(data, instance=zone, partial=True, session=db.session)
        db.session.commit()
        return jsonify(zone_livraison_schema.dump(updated_zone)), 200
    except ValidationError as err:
        return jsonify(err.messages), 400

@site_config_bp.route('/delivery-zones/<int:id>', methods=['DELETE'])
@admin_required()
def delete_delivery_zone(id):
    """Supprime une zone de livraison."""
    zone = ZoneLivraison.query.get_or_404(id)
    db.session.delete(zone)
    db.session.commit()
    return jsonify({"message": "Zone de livraison supprimée avec succès"}), 200


# --- GESTION DES COUPONS DE RÉDUCTION ---

@site_config_bp.route('/coupons', methods=['POST'])
@admin_required()
def create_coupon():
    """Crée un nouveau coupon de réduction."""
    data = request.form.to_dict()
    try:
        new_coupon = coupon_schema.load(data, session=db.session)
        db.session.add(new_coupon)
        db.session.commit()
        return jsonify(coupon_schema.dump(new_coupon)), 201
    except ValidationError as err:
        return jsonify(err.messages), 400

@site_config_bp.route('/coupons', methods=['GET'])
@admin_required()
def get_coupons():
    """Liste tous les coupons."""
    coupons = Coupon.query.all()
    return jsonify(coupons_schema.dump(coupons)), 200

@site_config_bp.route('/coupons/<int:id>', methods=['PUT'])
@admin_required()
def update_coupon(id):
    """Met à jour un coupon."""
    coupon = Coupon.query.get_or_404(id)
    data = request.form.to_dict()
    try:
        updated_coupon = coupon_schema.load(data, instance=coupon, partial=True, session=db.session)
        db.session.commit()
        return jsonify(coupon_schema.dump(updated_coupon)), 200
    except ValidationError as err:
        return jsonify(err.messages), 400

@site_config_bp.route('/coupons/<int:id>', methods=['DELETE'])
@admin_required()
def delete_coupon(id):
    """Supprime un coupon."""
    coupon = Coupon.query.get_or_404(id)
    db.session.delete(coupon)
    db.session.commit()
    return jsonify({"message": "Coupon supprimé avec succès"}), 200
