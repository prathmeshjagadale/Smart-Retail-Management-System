import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "SQLALCHEMY_DATABASE_URI",
        "sqlite:///" + os.path.join(BASE_DIR, "instance", "store.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"timeout": 15}}

    WTF_CSRF_TIME_LIMIT = None

    # --- MQTT / HiveMQ public broker ---
    MQTT_BROKER = os.environ.get("MQTT_BROKER", "broker.hivemq.com")
    MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
    MQTT_TOPIC_PREFIX = os.environ.get("MQTT_TOPIC_PREFIX", "retailstore/retailstore_8f3k2")
    MQTT_DATA_TOPIC = f"{MQTT_TOPIC_PREFIX}/loadcell/data"
    MQTT_CLIENT_ID = os.environ.get("MQTT_CLIENT_ID", "flask-store-backend")

    # --- Shelves / hardware mapping ---
    NUM_SHELVES = 3
    STALE_READING_SECONDS = 10  # if no MQTT message in this long, mark shelf offline

    # --- Razorpay (test mode) ---
    RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
    PAYMENT_MODE = "razorpay" if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET else "simulate"
    CURRENCY = os.environ.get("CURRENCY", "INR")

    # --- Default super admin (seeded on first run) ---
    DEFAULT_SUPER_ADMIN_USERNAME = os.environ.get("DEFAULT_SUPER_ADMIN_USERNAME", "admin")
    DEFAULT_SUPER_ADMIN_PASSWORD = os.environ.get("DEFAULT_SUPER_ADMIN_PASSWORD", "Admin@123")
    DEFAULT_SUPER_ADMIN_EMAIL = os.environ.get("DEFAULT_SUPER_ADMIN_EMAIL", "admin@store.local")

    DEBUG = _bool(os.environ.get("FLASK_DEBUG"), True)
