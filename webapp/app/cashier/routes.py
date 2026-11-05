from datetime import datetime

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.cashier import bp
from app.decorators import role_required
from app.extensions import db
from app.models import Sale, ROLE_CASHIER, SALE_STATUS_PAID, SALE_STATUS_COMPLETED


@bp.before_request
@login_required
@role_required(ROLE_CASHIER)
def guard():
    pass


@bp.route("/dashboard")
def dashboard():
    return render_template("cashier/dashboard.html")


@bp.route("/lookup", methods=["POST"])
def lookup():
    exit_code = request.form.get("exit_code", "").strip().upper()

    if not exit_code:
        flash("Please enter an exit code.", "error")
        return redirect(url_for("cashier.dashboard"))

    sale = Sale.query.filter_by(exit_code=exit_code).first()

    if not sale:
        flash(f'No order found for exit code "{exit_code}".', "error")
        return redirect(url_for("cashier.dashboard"))

    if sale.status == SALE_STATUS_COMPLETED:
        flash("This exit code has already been used and verified.", "info")
        return render_template("cashier/bill.html", sale=sale, already_verified=True)

    if sale.status != SALE_STATUS_PAID:
        flash("This order has not been paid for.", "error")
        return redirect(url_for("cashier.dashboard"))

    return render_template("cashier/bill.html", sale=sale, already_verified=False)


@bp.route("/complete/<int:sale_id>", methods=["POST"])
def complete(sale_id):
    sale = Sale.query.get_or_404(sale_id)

    if sale.status == SALE_STATUS_COMPLETED:
        flash("This order was already verified.", "info")
        return render_template("cashier/thank_you.html", sale=sale)

    if sale.status != SALE_STATUS_PAID:
        flash("This order cannot be verified.", "error")
        return redirect(url_for("cashier.dashboard"))

    sale.status = SALE_STATUS_COMPLETED
    sale.verified_at = datetime.utcnow()
    sale.verified_by_id = current_user.id
    db.session.commit()

    return render_template("cashier/thank_you.html", sale=sale)
