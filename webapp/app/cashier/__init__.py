from flask import Blueprint

bp = Blueprint("cashier", __name__, template_folder="../templates/cashier")

from app.cashier import routes  # noqa: E402,F401
