import os

import qrcode

QR_DIR_NAME = "qrcodes"


def qr_static_dir(app):
    path = os.path.join(app.static_folder, QR_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def generate_product_qr(app, product, base_url):
    """Generate a QR PNG that encodes the customer-facing product URL.
    Works both with the in-app camera scanner and a phone's native camera app.
    Returns the path relative to the static folder.
    """
    url = f"{base_url.rstrip('/')}/customer/product/{product.qr_token}"

    img = qrcode.make(url)
    filename = f"{product.qr_token}.png"
    folder = qr_static_dir(app)
    full_path = os.path.join(folder, filename)
    img.save(full_path)

    return f"{QR_DIR_NAME}/{filename}"


def format_currency(amount, currency="INR"):
    symbol = "₹" if currency == "INR" else currency + " "
    return f"{symbol}{amount:,.2f}"
