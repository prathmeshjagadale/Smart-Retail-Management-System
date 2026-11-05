import os
import secrets
import string
from datetime import datetime, timedelta

from flask import (
    render_template, redirect, url_for, flash, request, jsonify,
    send_from_directory, current_app, abort
)
from flask_login import login_required, current_user
from sqlalchemy import func

from app.super_admin import bp
from app.decorators import role_required
from app.extensions import db
from app.models import (
    User, Shelf, Product, Sale, SaleItem,
    ROLE_SUPER_ADMIN, ROLE_CASHIER,
    SALE_STATUS_PAID, SALE_STATUS_COMPLETED,
)
from app.mqtt_client import get_live_weight
from app.utils import generate_product_qr


@bp.before_request
@login_required
@role_required(ROLE_SUPER_ADMIN)
def guard():
    pass


@bp.route("/dashboard")
def dashboard():
    shelves = Shelf.query.order_by(Shelf.load_cell_index).all()
    total_products = Product.query.filter_by(is_active=True).count()
    total_stock_value = db.session.query(
        func.coalesce(func.sum(Product.price * Product.stock_quantity), 0.0)
    ).filter(Product.is_active.is_(True)).scalar()

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    todays_sales = Sale.query.filter(
        Sale.status.in_([SALE_STATUS_PAID, SALE_STATUS_COMPLETED]),
        Sale.paid_at >= today_start,
    )
    todays_revenue = sum(s.total_amount for s in todays_sales)
    todays_count = todays_sales.count()

    total_cashiers = User.query.filter_by(role=ROLE_CASHIER).count()

    return render_template(
        "super_admin/dashboard.html",
        shelves=shelves,
        total_products=total_products,
        total_stock_value=total_stock_value,
        todays_revenue=todays_revenue,
        todays_count=todays_count,
        total_cashiers=total_cashiers,
    )


# --------------------------------------------------------------------------
# Shelves & Products
# --------------------------------------------------------------------------
@bp.route("/shelves")
def shelves():
    all_shelves = Shelf.query.order_by(Shelf.load_cell_index).all()
    return render_template("super_admin/shelves.html", shelves=all_shelves)


@bp.route("/shelves/status")
def shelves_status():
    """AJAX polling endpoint used by the shelves page to keep weight/qty live."""
    all_shelves = Shelf.query.order_by(Shelf.load_cell_index).all()
    data = []
    for shelf in all_shelves:
        product = shelf.active_product
        live = get_live_weight(shelf.load_cell_index)
        data.append({
            "shelf_id": shelf.id,
            "load_cell_index": shelf.load_cell_index,
            "live_weight": live["weight"],
            "product": {
                "id": product.id,
                "name": product.name,
                "stock_quantity": product.stock_quantity,
                "current_weight_grams": product.current_weight_grams,
                "unit_weight_grams": product.unit_weight_grams,
                "price": product.price,
            } if product else None,
        })
    return jsonify({"shelves": data})


@bp.route("/shelves/<int:shelf_id>/add-product", methods=["GET", "POST"])
def add_product(shelf_id):
    shelf = Shelf.query.get_or_404(shelf_id)

    if shelf.active_product:
        flash("This shelf already has an active product. Remove it first to add a new one.", "error")
        return redirect(url_for("super_admin.shelves"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "")
        unit_weight = request.form.get("unit_weight_grams", "")

        errors = []
        if not name:
            errors.append("Product name is required.")
        try:
            price = float(price)
            if price <= 0:
                errors.append("Price must be greater than 0.")
        except (TypeError, ValueError):
            errors.append("Price must be a valid number.")
            price = 0
        try:
            unit_weight = float(unit_weight)
            if unit_weight <= 0:
                errors.append("Captured unit weight must be greater than 0 grams. "
                               "Place one item on the load cell and capture the reading.")
        except (TypeError, ValueError):
            errors.append("Unit weight is missing — capture the live weight first.")
            unit_weight = 0

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("super_admin/add_product.html", shelf=shelf, form=request.form)

        product = Product(
            shelf_id=shelf.id,
            name=name,
            description=description or None,
            price=price,
            unit_weight_grams=unit_weight,
        )
        db.session.add(product)
        db.session.commit()

        qr_rel_path = generate_product_qr(current_app, product, request.url_root)
        product.qr_code_path = qr_rel_path
        db.session.commit()

        flash(f'Product "{product.name}" registered on {shelf.name}. Download the QR code and stick it on the shelf.', "success")
        return redirect(url_for("super_admin.product_detail", product_id=product.id))

    return render_template("super_admin/add_product.html", shelf=shelf, form={})


@bp.route("/products/<int:product_id>")
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template("super_admin/product_detail.html", product=product)


@bp.route("/products/<int:product_id>/qr-download")
def download_qr(product_id):
    product = Product.query.get_or_404(product_id)
    if not product.qr_code_path:
        abort(404)
    directory = current_app.static_folder
    rel_dir, filename = os.path.split(product.qr_code_path)
    return send_from_directory(
        os.path.join(directory, rel_dir),
        filename,
        as_attachment=True,
        download_name=f"{product.name.replace(' ', '_')}_QR.png",
    )


@bp.route("/products/<int:product_id>/remove", methods=["POST"])
def remove_product(product_id):
    product = Product.query.get_or_404(product_id)
    product.is_active = False
    db.session.commit()
    flash(f'"{product.name}" was removed from its shelf.', "info")
    return redirect(url_for("super_admin.shelves"))


# --------------------------------------------------------------------------
# Cashier management
# --------------------------------------------------------------------------
@bp.route("/cashiers", methods=["GET", "POST"])
def cashiers():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()

        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not username or len(username) < 3:
            errors.append("Username must be at least 3 characters.")
        if User.query.filter_by(username=username).first():
            errors.append("Username already taken.")
        if email and User.query.filter_by(email=email).first():
            errors.append("Email already in use.")

        if errors:
            for e in errors:
                flash(e, "error")
        else:
            alphabet = string.ascii_letters + string.digits
            generated_password = "".join(secrets.choice(alphabet) for _ in range(10))

            cashier = User(
                username=username,
                email=email or None,
                full_name=full_name,
                role=ROLE_CASHIER,
                created_by_id=current_user.id,
            )
            cashier.set_password(generated_password)
            cashier.plain_password = generated_password
            db.session.add(cashier)
            db.session.commit()

            flash(f'Cashier account created for "{username}". Password is shown in the table below.', "success")
        return redirect(url_for("super_admin.cashiers"))

    all_cashiers = User.query.filter_by(role=ROLE_CASHIER).order_by(User.created_at.desc()).all()
    return render_template("super_admin/cashiers.html", cashiers=all_cashiers)


@bp.route("/cashiers/<int:user_id>/toggle", methods=["POST"])
def toggle_cashier(user_id):
    cashier = User.query.filter_by(id=user_id, role=ROLE_CASHIER).first_or_404()
    cashier.is_active_account = not cashier.is_active_account
    db.session.commit()
    state = "activated" if cashier.is_active_account else "deactivated"
    flash(f"Cashier {cashier.username} {state}.", "info")
    return redirect(url_for("super_admin.cashiers"))


@bp.route("/cashiers/<int:user_id>/change-password", methods=["POST"])
def change_cashier_password(user_id):
    cashier = User.query.filter_by(id=user_id, role=ROLE_CASHIER).first_or_404()
    new_password = request.form.get("new_password", "").strip()

    if not new_password:
        alphabet = string.ascii_letters + string.digits
        new_password = "".join(secrets.choice(alphabet) for _ in range(10))
    elif len(new_password) < 6:
        flash("Password must be at least 6 characters.", "error")
        return redirect(url_for("super_admin.cashiers"))

    cashier.set_password(new_password)
    cashier.plain_password = new_password
    db.session.commit()

    flash(f'Password for "{cashier.username}" updated to: {new_password}', "success")
    return redirect(url_for("super_admin.cashiers"))


# --------------------------------------------------------------------------
# Sales report & payments
# --------------------------------------------------------------------------
@bp.route("/sales")
def sales_report():
    date_from = request.args.get("from", "")
    date_to = request.args.get("to", "")

    query = Sale.query.filter(Sale.status.in_([SALE_STATUS_PAID, SALE_STATUS_COMPLETED]))

    if date_from:
        try:
            dt_from = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(Sale.paid_at >= dt_from)
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Sale.paid_at < dt_to)
        except ValueError:
            pass

    sales = query.order_by(Sale.paid_at.desc()).all()
    total_revenue = sum(s.total_amount for s in sales)

    product_totals = {}
    for sale in sales:
        for item in sale.items:
            key = item.product_name
            product_totals.setdefault(key, {"quantity": 0, "revenue": 0.0})
            product_totals[key]["quantity"] += item.quantity
            product_totals[key]["revenue"] += item.subtotal

    return render_template(
        "super_admin/sales_report.html",
        sales=sales,
        total_revenue=total_revenue,
        product_totals=product_totals,
        date_from=date_from,
        date_to=date_to,
    )


@bp.route("/payments")
def payments():
    all_sales = Sale.query.filter(
        Sale.status.in_([SALE_STATUS_PAID, SALE_STATUS_COMPLETED])
    ).order_by(Sale.paid_at.desc()).all()
    return render_template("super_admin/payments.html", sales=all_sales)


# --------------------------------------------------------------------------
# Account
# --------------------------------------------------------------------------
@bp.route("/account", methods=["GET", "POST"])
def account():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not current_user.check_password(current_password):
            flash("Current password is incorrect.", "error")
        elif len(new_password) < 6:
            flash("New password must be at least 6 characters.", "error")
        elif new_password != confirm_password:
            flash("New passwords do not match.", "error")
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash("Password updated successfully.", "success")
        return redirect(url_for("super_admin.account"))

    return render_template("super_admin/account.html")
