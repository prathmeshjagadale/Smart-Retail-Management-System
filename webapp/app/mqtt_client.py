"""
Background MQTT client that connects to the public HiveMQ broker and listens
for live load-cell weight readings published by the ESP32 (see esp32_code/).

The ESP32 publishes one JSON message per second to MQTT_DATA_TOPIC:
    {"shelf1": 123.45, "shelf2": 0.0, "shelf3": 58.1, "ts": 123456}

This module keeps the latest reading for each shelf in memory (thread-safe)
so the Flask app can serve it instantly via /api/live-weight, and also
mirrors the reading into the Product table so stock quantities stay in
sync with what's physically on the shelf.
"""
import json
import threading
import time

import paho.mqtt.client as mqtt

_lock = threading.Lock()
_state = {
    1: {"weight": 0.0, "last_update": 0},
    2: {"weight": 0.0, "last_update": 0},
    3: {"weight": 0.0, "last_update": 0},
}
_connected = {"value": False}

_client = None


def get_live_weight(shelf_index):
    with _lock:
        data = _state.get(shelf_index, {"weight": 0.0, "last_update": 0})
        return {
            "shelf": shelf_index,
            "weight": data["weight"],
            "last_update": data["last_update"],
            "age_seconds": max(0, time.time() - data["last_update"]) if data["last_update"] else None,
        }


def get_all_live_weights():
    return {idx: get_live_weight(idx) for idx in (1, 2, 3)}


def is_broker_connected():
    return _connected["value"]


def _sync_product_stock(app, shelf_index, weight):
    """Best-effort: reflect the live shelf weight into the assigned product's
    stock quantity so admin dashboards stay in sync automatically."""
    from app.extensions import db
    from app.models import Shelf

    with app.app_context():
        try:
            shelf = Shelf.query.filter_by(load_cell_index=shelf_index).first()
            if not shelf:
                return
            product = shelf.active_product
            if not product:
                return
            product.current_weight_grams = round(weight, 2)
            if product.unit_weight_grams and product.unit_weight_grams > 0:
                qty = round(weight / product.unit_weight_grams)
                product.stock_quantity = max(0, int(qty))
            db.session.commit()
        except Exception:
            db.session.rollback()


def init_mqtt(app):
    """Create and start the MQTT client as a background thread.
    Safe to call once per process."""
    global _client
    if _client is not None:
        return _client

    broker = app.config["MQTT_BROKER"]
    port = app.config["MQTT_PORT"]
    topic = app.config["MQTT_DATA_TOPIC"]
    client_id = f'{app.config["MQTT_CLIENT_ID"]}-{int(time.time())}'

    def on_connect(client, userdata, flags, rc, properties=None):
        if rc == 0:
            _connected["value"] = True
            client.subscribe(topic, qos=0)
            app.logger.info(f"[MQTT] Connected to {broker}:{port}, subscribed to {topic}")
        else:
            _connected["value"] = False
            app.logger.warning(f"[MQTT] Connect failed rc={rc}")

    def on_disconnect(client, userdata, rc, *args, **kwargs):
        _connected["value"] = False
        app.logger.warning("[MQTT] Disconnected from broker")

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return

        now = time.time()
        with _lock:
            for shelf_index in (1, 2, 3):
                key = f"shelf{shelf_index}"
                if key in payload:
                    try:
                        weight = float(payload[key])
                    except (TypeError, ValueError):
                        continue
                    _state[shelf_index] = {"weight": weight, "last_update": now}

        for shelf_index in (1, 2, 3):
            key = f"shelf{shelf_index}"
            if key in payload:
                try:
                    weight = float(payload[key])
                except (TypeError, ValueError):
                    continue
                _sync_product_stock(app, shelf_index, weight)

    try:
        _client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
    except TypeError:
        _client = mqtt.Client(client_id)

    _client.on_connect = on_connect
    _client.on_disconnect = on_disconnect
    _client.on_message = on_message

    def _run():
        while True:
            try:
                _client.connect(broker, port, keepalive=30)
                _client.loop_forever(retry_first_connection=True)
            except Exception as exc:
                app.logger.warning(f"[MQTT] connection error: {exc}, retrying in 5s")
                _connected["value"] = False
                time.sleep(5)

    thread = threading.Thread(target=_run, name="mqtt-listener", daemon=True)
    thread.start()
    return _client
