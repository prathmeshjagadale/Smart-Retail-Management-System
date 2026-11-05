from datetime import datetime

from flask import (
    render_template, redirect, url_for, flash, request, jsonify,
    current_app, session
)
from flask_login import login_required, current_user

from app.customer import bp
from app.decorators import role_required
from app.extensions import db
from app.models import (
    Product, CartItem, Sale, SaleItem, generate_exit_code,
    ROLE_CUSTOMER, SALE_STATUS_PAID,
)

CHECKOUT_SESSION_KEY = "pending_checkout"


@bp.before_request
@login_required
@role_required(ROLE_CUSTOMER)
def guard():
    pass


@bp.route("/dashboard")
def dashboard():
    cart_count = CartItem.query.filter_by(customer_id=current_user.id).count()
    recent_orders = (
        Sale.query.filter_by(customer_id=current_user.id)
        .order_by(Sale.created_at.desc())
        .limit(3)
        .all()
    )
    return render_template("customer/dashboard.html", cart_count=cart_count, recent_orders=recent_orders)


# --------------------------------------------------------------------------
# QR scan + product detail
# --------------------------------------------------------------------------
@bp.route("/scan")
def scan():
    return render_template("customer/scan.html")


@bp.route("/product/<qr_token>")
def product_detail(qr_token):
    product = Product.query.filter_by(qr_token=qr_token, is_active=True).first()
    if not product:
        flash("This product could not be found. It may have been removed from the shelf.", "error")
        return redirect(url_for("customer.dashboard"))
    return render_template("customer/product_detail.html", product=product)


# --------------------------------------------------------------------------
# Cart
# --------------------------------------------------------------------------
@bp.route("/cart/add", methods=["POST"])
def cart_add():
    product_id = request.form.get("product_id", type=int)
    quantity = request.form.get("quantity", default=1, type=int)

    product = Product.query.filter_by(id=product_id, is_active=True).first()
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("customer.dashboard"))

    if quantity < 1:
        quantity = 1
    if product.stock_quantity <= 0:
        flash(f'"{product.name}" is currently out of stock.', "error")
        return redirect(url_for("customer.product_detail", qr_token=product.qr_token))

    quantity = min(quantity, product.stock_quantity)

    item = CartItem.query.filter_by(customer_id=current_user.id, product_id=product.id).first()
    if item:
        item.quantity = min(item.quantity + quantity, product.stock_quantity)
    else:
        item = CartItem(customer_id=current_user.id, product_id=product.id, quantity=quantity)
        db.session.add(item)

    db.session.commit()
    flash(f'Added "{product.name}" to your cart.', "success")
    return redirect(url_for("customer.cart"))


@bp.route("/cart")
def cart():
    items = CartItem.query.filter_by(customer_id=current_user.id).all()
    total = round(sum(item.subtotal for item in items), 2)
    return render_template("customer/cart.html", items=items, total=total)


@bp.route("/cart/update/<int:item_id>", methods=["POST"])
def cart_update(item_id):
    item = CartItem.query.filter_by(id=item_id, customer_id=current_user.id).first_or_404()
    quantity = request.form.get("quantity", type=int)

    if quantity is None or quantity < 1:
        db.session.delete(item)
        db.session.commit()
        total = round(sum(i.subtotal for i in CartItem.query.filter_by(customer_id=current_user.id).all()), 2)
        return jsonify({"removed": True, "cart_total": total})

    quantity = min(quantity, max(item.product.stock_quantity, 0))
    if quantity < 1:
        db.session.delete(item)
        db.session.commit()
        total = round(sum(i.subtotal for i in CartItem.query.filter_by(customer_id=current_user.id).all()), 2)
        return jsonify({"removed": True, "cart_total": total})

    item.quantity = quantity
    db.session.commit()

    total = round(sum(i.subtotal for i in CartItem.query.filter_by(customer_id=current_user.id).all()), 2)
    return jsonify({"removed": False, "quantity": item.quantity, "subtotal": item.subtotal, "cart_total": total})


@bp.route("/cart/remove/<int:item_id>", methods=["POST"])
def cart_remove(item_id):
    item = CartItem.query.filter_by(id=item_id, customer_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash("Item removed from cart.", "info")
    return redirect(url_for("customer.cart"))


# --------------------------------------------------------------------------
# Checkout & Payment (Razorpay test mode, with demo fallback)
# --------------------------------------------------------------------------
def _unique_exit_code():
    for _ in range(20):
        code = generate_exit_code()
        if not Sale.query.filter_by(exit_code=code).first():
            return code
    raise RuntimeError("Could not generate a unique exit code")


def _finalize_sale(items_snapshot, total, payment_mode, razorpay_order_id=None,
                    razorpay_payment_id=None, razorpay_signature=None):
    sale = Sale(
        customer_id=current_user.id,
        total_amount=total,
        status=SALE_STATUS_PAID,
        payment_mode=payment_mode,
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
        razorpay_signature=razorpay_signature,
        exit_code=_unique_exit_code(),
        paid_at=datetime.utcnow(),
    )
    db.session.add(sale)
    db.session.flush()

    for entry in items_snapshot:
        db.session.add(SaleItem(
            sale_id=sale.id,
            product_id=entry["product_id"],
            product_name=entry["name"],
            unit_price=entry["price"],
            quantity=entry["quantity"],
            subtotal=entry["subtotal"],
        ))
        product = Product.query.get(entry["product_id"])
        if product:
            product.stock_quantity = max(0, product.stock_quantity - entry["quantity"])

    CartItem.query.filter_by(customer_id=current_user.id).delete()
    db.session.commit()
    return sale


@bp.route("/checkout")
def checkout():
    cart_items = CartItem.query.filter_by(customer_id=current_user.id).all()
    if not cart_items:
        flash("Your cart is empty.", "error")
        return redirect(url_for("customer.cart"))

    for item in cart_items:
        if item.quantity > item.product.stock_quantity:
            flash(
                f'Only {item.product.stock_quantity} of "{item.product.name}" left in stock. '
                f"Please update your cart.", "error"
            )
            return redirect(url_for("customer.cart"))

    items_snapshot = [
        {
            "product_id": item.product.id,
            "name": item.product.name,
            "price": item.product.price,
            "quantity": item.quantity,
            "subtotal": item.subtotal,
        }
        for item in cart_items
    ]
    total = round(sum(e["subtotal"] for e in items_snapshot), 2)

    session[CHECKOUT_SESSION_KEY] = {"items": items_snapshot, "total": total}

    payment_mode = current_app.config["PAYMENT_MODE"]

    if payment_mode == "razorpay":
        import razorpay
        client = razorpay.Client(auth=(
            current_app.config["RAZORPAY_KEY_ID"], current_app.config["RAZORPAY_KEY_SECRET"]
        ))
        order = client.order.create({
            "amount": int(round(total * 100)),
            "currency": current_app.config["CURRENCY"],
            "payment_capture": 1,
        })
        session[CHECKOUT_SESSION_KEY]["razorpay_order_id"] = order["id"]

        return render_template(
            "customer/checkout.html",
            items=items_snapshot, total=total,
            razorpay_order_id=order["id"],
            razorpay_key_id=current_app.config["RAZORPAY_KEY_ID"],
        )

    return render_template("customer/checkout.html", items=items_snapshot, total=total,
                            razorpay_order_id=None, razorpay_key_id=None)


@bp.route("/payment/callback", methods=["POST"])
def payment_callback():
    pending = session.get(CHECKOUT_SESSION_KEY)
    if not pending:
        flash("Your checkout session expired. Please try again.", "error")
        return redirect(url_for("customer.cart"))

    razorpay_payment_id = request.form.get("razorpay_payment_id")
    razorpay_order_id = request.form.get("razorpay_order_id")
    razorpay_signature = request.form.get("razorpay_signature")

    if pending.get("razorpay_order_id") != razorpay_order_id:
        flash("Payment verification failed (order mismatch).", "error")
        return redirect(url_for("customer.cart"))

    import razorpay
    client = razorpay.Client(auth=(
        current_app.config["RAZORPAY_KEY_ID"], current_app.config["RAZORPAY_KEY_SECRET"]
    ))
    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature,
        })
    except razorpay.errors.SignatureVerificationError:
        flash("Payment verification failed. No charge was recorded.", "error")
        return redirect(url_for("customer.cart"))

    sale = _finalize_sale(
        pending["items"], pending["total"], payment_mode="razorpay",
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
        razorpay_signature=razorpay_signature,
    )
    session.pop(CHECKOUT_SESSION_KEY, None)
    return redirect(url_for("customer.order_success", sale_id=sale.id))


@bp.route("/payment/simulate", methods=["POST"])
def payment_simulate():
    if current_app.config["PAYMENT_MODE"] == "razorpay":
        flash("Simulated payments are disabled while Razorpay live test keys are configured.", "error")
        return redirect(url_for("customer.cart"))

    pending = session.get(CHECKOUT_SESSION_KEY)
    if not pending:
        flash("Your checkout session expired. Please try again.", "error")
        return redirect(url_for("customer.cart"))

    sale = _finalize_sale(pending["items"], pending["total"], payment_mode="simulate")
    session.pop(CHECKOUT_SESSION_KEY, None)
    return redirect(url_for("customer.order_success", sale_id=sale.id))


@bp.route("/order/<int:sale_id>/success")
def order_success(sale_id):
    sale = Sale.query.filter_by(id=sale_id, customer_id=current_user.id).first_or_404()
    return render_template("customer/order_success.html", sale=sale)


@bp.route("/order/<int:sale_id>/status")
def order_status(sale_id):
    sale = Sale.query.filter_by(id=sale_id, customer_id=current_user.id).first_or_404()
    return jsonify({
        "status": sale.status,
        "verified_at": sale.verified_at.isoformat() if sale.verified_at else None,
    })


@bp.route("/orders")
def orders():
    all_orders = (
        Sale.query.filter_by(customer_id=current_user.id)
        .filter(Sale.status.in_(["paid", "completed"]))
        .order_by(Sale.created_at.desc())
        .all()
    )
    return render_template("customer/orders.html", orders=all_orders)
