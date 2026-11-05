import threading

from werkzeug.serving import run_simple

from app import create_app

app = create_app()

HTTP_PORT = 5000
HTTPS_PORT = 5443


def _run_https():
    # Self-signed "adhoc" cert (requires pyOpenSSL). Browsers only allow camera
    # access (getUserMedia, used by the QR scanner) on a secure context — that
    # means HTTPS, or the literal hostname "localhost". A phone opening the
    # PC's LAN IP over plain HTTP will never be allowed to use the camera, no
    # matter what the page does, so we also serve HTTPS here as the fix.
    run_simple(
        "0.0.0.0", HTTPS_PORT, app,
        ssl_context="adhoc",
        threaded=True,
        use_reloader=False,
        use_debugger=app.debug,
    )


if __name__ == "__main__":
    threading.Thread(target=_run_https, daemon=True).start()

    print("=" * 60)
    print(f" HTTP  (no camera on phones): http://0.0.0.0:{HTTP_PORT}")
    print(f" HTTPS (camera works here):   https://0.0.0.0:{HTTPS_PORT}")
    print(" The HTTPS certificate is self-signed - your browser will warn")
    print(' "connection is not private" the first time. Tap Advanced ->')
    print(" Proceed to continue. This only needs to be accepted once per device.")
    print("=" * 60)

    run_simple(
        "0.0.0.0", HTTP_PORT, app,
        threaded=True,
        use_reloader=False,
        use_debugger=app.debug,
    )
