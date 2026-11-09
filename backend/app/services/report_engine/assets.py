"""Prefetch bounded raster logos; PDF renderers never fetch external resources."""

import base64
import io
import logging
import warnings

from PIL import Image

from app.utils.public_http import UnsafeURL, fetch_public

logger = logging.getLogger(__name__)


async def embed_report_logo(url: str | None) -> str | None:
    if not url:
        return None
    try:
        response = await fetch_public(url, purpose="image")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(response.content)) as image:
                if image.format not in {"PNG", "JPEG"} or image.width * image.height > 4_000_000:
                    raise UnsafeURL("Logo must be a small PNG or JPEG")
                # Decode and re-encode pixels, stripping metadata and preventing
                # SVG, external resource references or polyglot files in PDFs.
                image.thumbnail((800, 800))
                output = io.BytesIO()
                image.convert("RGBA").save(output, format="PNG")
        return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")
    except Exception as exc:
        logger.warning("Report logo unavailable: %s", type(exc).__name__)
        return None  # Existing name/color branding remains visible.


def embedded_resource_fetcher(url: str, *args, **kwargs) -> dict:
    """No network, filesystem, SVG, fonts or arbitrary data URI in the renderer."""
    prefix = "data:image/png;base64,"
    if not url.startswith(prefix) or len(url) > 4 * 1024 * 1024:
        raise ValueError("Only embedded report raster assets are allowed")
    content = base64.b64decode(url[len(prefix):], validate=True)
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Invalid embedded report image")
    return {"string": content, "mime_type": "image/png"}
