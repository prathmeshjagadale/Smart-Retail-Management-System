import secrets
import string
import uuid
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db

ROLE_SUPER_ADMIN = "super_admin"
ROLE_CASHIER = "cashier"
ROLE_CUSTOMER = "customer"

SALE_STATUS_PENDING = "pending"
SALE_STATUS_PAID = "paid"
SALE_STATUS_COMPLETED = "completed"  # verified & exited by cashier
SALE_STATUS_FAILED = "failed"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    # Plaintext copy kept ONLY for cashier accounts so the super admin can always
    # look it up again (cashiers have no self-service login recovery). Customers
    # and super admins never have this populated.
    plain_password = db.Column(db.String(128), nullable=True)
    role = db.Column(db.String(20), nullable=False, index=True)
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    sales = db.relationship("Sale", backref="customer", lazy="dynamic",
                             foreign_keys="Sale.customer_id")

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_active(self):
        return self.is_active_account

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class Shelf(db.Model):
    __tablename__ = "shelves"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    load_cell_index = db.Column(db.Integer, nullable=False, unique=True)  # 1, 2, 3

    products = db.relationship("Product", backref="shelf", lazy="dynamic")

    @property
    def active_product(self):
        return self.products.filter_by(is_active=True).first()

    def __repr__(self):
        return f"<Shelf {self.name} (cell {self.load_cell_index})>"


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    qr_token = db.Column(db.String(36), unique=True, nullable=False,
                          default=lambda: str(uuid.uuid4()))
    shelf_id = db.Column(db.Integer, db.ForeignKey("shelves.id"), nullable=False)

    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    price = db.Column(db.Float, nullable=False)

    unit_weight_grams = db.Column(db.Float, nullable=False)  # weight of ONE item
    current_weight_grams = db.Column(db.Float, default=0.0)  # last known total weight on shelf
    stock_quantity = db.Column(db.Integer, default=0)

    qr_code_path = db.Column(db.String(255), nullable=True)  # relative to static/
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Product {self.name} shelf={self.shelf_id}>"


class CartItem(db.Model):
    __tablename__ = "cart_items"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship("Product")

    __table_args__ = (
        db.UniqueConstraint("customer_id", "product_id", name="uix_cart_customer_product"),
    )

    @property
    def subtotal(self):
        return round(self.product.price * self.quantity, 2)


def generate_exit_code():
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


class Sale(db.Model):
    __tablename__ = "sales"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(20), default=SALE_STATUS_PENDING, nullable=False, index=True)

    razorpay_order_id = db.Column(db.String(64), nullable=True)
    razorpay_payment_id = db.Column(db.String(64), nullable=True)
    razorpay_signature = db.Column(db.String(255), nullable=True)
    payment_mode = db.Column(db.String(20), nullable=True)  # 'razorpay' or 'simulate'

    exit_code = db.Column(db.String(6), unique=True, nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    verified_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    items = db.relationship("SaleItem", backref="sale", lazy="joined",
                             cascade="all, delete-orphan")
    verified_by = db.relationship("User", foreign_keys=[verified_by_id])

    def __repr__(self):
        return f"<Sale #{self.id} status={self.status}>"


class SaleItem(db.Model):
    __tablename__ = "sale_items"

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)

    product_name = db.Column(db.String(120), nullable=False)  # snapshot
    unit_price = db.Column(db.Float, nullable=False)  # snapshot
    quantity = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)

    product = db.relationship("Product")
