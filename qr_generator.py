"""
QR code generation utilities.

Generates a PNG image (in memory) from a validated string. The image is
returned as ``bytes`` so the bot can upload it directly to Telegram without
touching the disk. This avoids any path traversal or temp-file race issues.

Uses qrcode's pure-Python PNG factory (``qrcode.image.pure.PyImage``), so we
do not depend on Pillow / any C extension. This means the project installs
cleanly on Python 3.14+ on Windows without a C compiler or native libraries.
"""

from __future__ import annotations

import io

import qrcode
from qrcode.image.pure import PyPNGImage

from config import Settings
from validators import InvalidInputError


def generate_qr_png(payload: str, settings: Settings) -> bytes:
    """
    Render ``payload`` as a PNG image and return the bytes.

    Raises ``InvalidInputError`` if the payload is empty or too large for the
    chosen error-correction level.
    """

    if not payload:
        raise InvalidInputError("Nothing to encode.")

    qr = qrcode.QRCode(
        version=None,  # auto-fit the smallest version that fits
        error_correction=settings.qr_error_correction,
        box_size=settings.qr_box_size,
        border=settings.qr_border,
    )
    qr.add_data(payload)

    try:
        qr.make(fit=True)
    except qrcode.exceptions.DataOverflowError as exc:  # too much data
        raise InvalidInputError(
            "Content is too long to fit into a single QR code."
        ) from exc

    # PyPNGImage is the pure-Python PNG factory. It does not need Pillow.
    # It renders a 1-bit greyscale image (black modules on white background)
    # which is exactly what a QR code should be. The returned object exposes
    # a ``save(stream)`` method that writes the PNG bytes to a stream.
    img = qr.make_image(image_factory=PyPNGImage)

    buffer = io.BytesIO()
    img.save(buffer)
    png_bytes = buffer.getvalue()
    buffer.close()

    if not png_bytes:
        raise InvalidInputError("Failed to render QR image.")

    return png_bytes
