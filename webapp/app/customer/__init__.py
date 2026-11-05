from flask import Blueprint

bp = Blueprint("customer", __name__, template_folder="../templates/customer")

from app.customer import routes  # noqa: E402,F401
