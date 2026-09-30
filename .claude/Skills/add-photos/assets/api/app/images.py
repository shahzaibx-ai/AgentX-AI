"""Image checks shared by the chat schema and the providers.

Images arrive as base64 in JSON. They are decoded once, the real format is read
from the file signature (the declared type is not trusted), and providers get
raw bytes, never a string. The Ollama SDK treats an image *string* as a
possible file path and reads it, so a string like "/etc/passwd" must never
reach it.
"""

import base64
import binascii
from typing import Literal

ImageMediaType = Literal["image/jpeg", "image/png", "image/webp", "image/gif"]
MEDIA_TYPES: tuple[ImageMediaType, ...] = ("image/jpeg", "image/png", "image/webp", "image/gif")

# Hard ceiling for one image, whatever the settings say (the route applies the configured limit).
ABSOLUTE_MAX_IMAGE_BYTES = 20 * 1024 * 1024


class ImageError(ValueError):
    """The image can't be used. The message is safe to show to the user."""


def sniff(data: bytes) -> ImageMediaType | None:
    """The image format from its first bytes, or None if it isn't a supported image."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def decode_image(value: str) -> tuple[bytes, ImageMediaType]:
    """Decode base64 (optionally a data: URL) and return the bytes and their real format."""
    text = value.strip()
    if text.startswith("data:"):
        _, _, text = text.partition(",")
    if len(text) > ABSOLUTE_MAX_IMAGE_BYTES * 4 // 3 + 4:
        raise ImageError("Image is too large")
    try:
        data = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ImageError("Image data is not valid base64") from exc
    media_type = sniff(data)
    if media_type is None:
        raise ImageError("Only JPEG, PNG, WebP and GIF images are supported")
    return data, media_type


def to_base64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")
