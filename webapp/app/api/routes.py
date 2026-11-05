from flask import jsonify, current_app
from flask_login import login_required, current_user

from app.api import bp
from app.mqtt_client import get_live_weight, get_all_live_weights, is_broker_connected
from app.models import ROLE_SUPER_ADMIN, ROLE_CASHIER, ROLE_CUSTOMER


def _is_stale(entry):
    if entry["last_update"] == 0:
        return True
    return entry["age_seconds"] is not None and entry["age_seconds"] > current_app.config["STALE_READING_SECONDS"]


@bp.route("/live-weight/<int:shelf_index>")
@login_required
def live_weight(shelf_index):
    if shelf_index not in (1, 2, 3):
        return jsonify({"error": "invalid shelf index"}), 400
    entry = get_live_weight(shelf_index)
    entry["online"] = is_broker_connected() and not _is_stale(entry)
    return jsonify(entry)


@bp.route("/live-weight")
@login_required
def live_weight_all():
    data = get_all_live_weights()
    for idx, entry in data.items():
        entry["online"] = is_broker_connected() and not _is_stale(entry)
    return jsonify({
        "broker_connected": is_broker_connected(),
        "shelves": data,
    })
