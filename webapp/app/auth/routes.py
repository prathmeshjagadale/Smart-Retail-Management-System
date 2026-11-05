from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from app.auth import bp
from app.extensions import db
from app.models import User, ROLE_CUSTOMER

PANELS = {
    "customer": {"label": "Customer", "heading": "Welcome back", "subtitle": "Sign in to shop at Smart Retail Store"},
    "cashier": {"label": "Cashier", "heading": "Cashier Login", "subtitle": "Sign in to verify customer exit codes"},
    "admin": {"label": "Super Admin", "heading": "Super Admin Login", "subtitle": "Sign in to manage shelves, staff and sales"},
}


def _panel_context(panel):
    return {"panel": panel, "panel_info": PANELS.get(panel, PANELS["customer"])}


@bp.route("/login", methods=["GET", "POST"], defaults={"panel": "customer"})
@bp.route("/login/<panel>", methods=["GET", "POST"])
def login(panel):
    if panel not in PANELS:
        panel = "customer"

    if current_user.is_authenticated:
        from app import _home_for_role
        return redirect(_home_for_role(current_user.role))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()

        if not user or not user.check_password(password):
            flash("Invalid username or password.", "error")
            return render_template("auth/login.html", **_panel_context(panel)), 401

        if not user.is_active_account:
            flash("This account has been deactivated. Contact the store admin.", "error")
            return render_template("auth/login.html", **_panel_context(panel)), 403

        login_user(user)
        from app import _home_for_role
        next_url = request.args.get("next")
        return redirect(next_url or _home_for_role(user.role))

    return render_template("auth/login.html", **_panel_context(panel))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        from app import _home_for_role
        return redirect(_home_for_role(current_user.role))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not username or len(username) < 3:
            errors.append("Username must be at least 3 characters.")
        if not email or "@" not in email:
            errors.append("A valid email is required.")
        if not password or len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm_password:
            errors.append("Passwords do not match.")
        if User.query.filter_by(username=username).first():
            errors.append("Username already taken.")
        if User.query.filter_by(email=email).first():
            errors.append("Email already registered.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("auth/register.html", form=request.form), 400

        user = User(
            username=username,
            email=email,
            full_name=full_name,
            phone=phone or None,
            role=ROLE_CUSTOMER,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash(f"Welcome, {user.full_name}! Your account has been created.", "success")
        return redirect(url_for("customer.dashboard"))

    return render_template("auth/register.html", form={})


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
