import os
from datetime import datetime

from flask import Flask, render_template

from config import Config
from app.extensions import db, login_manager, csrf


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(os.path.join(app.static_folder, "qrcodes"), exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # --- Blueprints ---
    from app.auth import bp as auth_bp
    from app.super_admin import bp as super_admin_bp
    from app.cashier import bp as cashier_bp
    from app.customer import bp as customer_bp
    from app.api import bp as api_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(super_admin_bp, url_prefix="/admin")
    app.register_blueprint(cashier_bp, url_prefix="/cashier")
    app.register_blueprint(customer_bp, url_prefix="/customer")
    app.register_blueprint(api_bp, url_prefix="/api")

    from flask import redirect, url_for
    from flask_login import current_user

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(_home_for_role(current_user.role))
        return redirect(url_for("auth.login"))

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    from app.utils import format_currency

    @app.context_processor
    def inject_globals():
        nav_cart_count = 0
        if current_user.is_authenticated and current_user.role == "customer":
            from app.models import CartItem
            nav_cart_count = CartItem.query.filter_by(customer_id=current_user.id).count()
        return {
            "current_year": datetime.utcnow().year,
            "payment_mode": app.config.get("PAYMENT_MODE", "simulate"),
            "currency": app.config.get("CURRENCY", "INR"),
            "format_currency": lambda amt: format_currency(amt, app.config.get("CURRENCY", "INR")),
            "nav_cart_count": nav_cart_count,
        }

    with app.app_context():
        db.create_all()
        _seed_initial_data(app)

    # run.py runs with use_reloader=False, so there's only ever one process —
    # safe to always start the MQTT listener here.
    from app.mqtt_client import init_mqtt
    init_mqtt(app)

    return app


def _home_for_role(role):
    from flask import url_for
    from app.models import ROLE_SUPER_ADMIN, ROLE_CASHIER, ROLE_CUSTOMER

    if role == ROLE_SUPER_ADMIN:
        return url_for("super_admin.dashboard")
    if role == ROLE_CASHIER:
        return url_for("cashier.dashboard")
    if role == ROLE_CUSTOMER:
        return url_for("customer.dashboard")
    return url_for("auth.login")


def _seed_initial_data(app):
    from app.extensions import db
    from app.models import User, Shelf, ROLE_SUPER_ADMIN

    if Shelf.query.count() == 0:
        for i in (1, 2, 3):
            db.session.add(Shelf(name=f"Shelf {i}", load_cell_index=i))
        db.session.commit()
        app.logger.info("Seeded 3 shelves")

    if not User.query.filter_by(role=ROLE_SUPER_ADMIN).first():
        admin = User(
            username=app.config["DEFAULT_SUPER_ADMIN_USERNAME"],
            email=app.config["DEFAULT_SUPER_ADMIN_EMAIL"],
            full_name="Store Super Admin",
            role=ROLE_SUPER_ADMIN,
        )
        admin.set_password(app.config["DEFAULT_SUPER_ADMIN_PASSWORD"])
        db.session.add(admin)
        db.session.commit()
        print("=" * 60)
        print(" Default super admin account created:")
        print(f"   username: {app.config['DEFAULT_SUPER_ADMIN_USERNAME']}")
        print(f"   password: {app.config['DEFAULT_SUPER_ADMIN_PASSWORD']}")
        print(" Please change this password after first login.")
        print("=" * 60)
