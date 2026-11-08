import base64
import io
from unittest.mock import AsyncMock

import httpx
import pytest
from PIL import Image

from app.services.report_engine import assets, pdf_generator


def png(width=20, height=10):
    image = Image.new("RGB", (width, height), "red")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


@pytest.mark.asyncio
async def test_logo_prefetched_and_embedded_as_sanitized_pixels(monkeypatch):
    fetch = AsyncMock(return_value=httpx.Response(200, content=png()))
    monkeypatch.setattr(assets, "fetch_public", fetch)
    result = await assets.embed_report_logo("https://cdn.example/logo.png")
    fetch.assert_awaited_once_with("https://cdn.example/logo.png", purpose="image")
    assert result.startswith("data:image/png;base64,")
    data = assets.embedded_resource_fetcher(result)
    with Image.open(io.BytesIO(data["string"])) as image:
        assert image.size == (20, 10)
        assert image.format == "PNG"


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [b'<svg><image href="http://127.0.0.1/"/></svg>', b"not an image", png(2001, 2000)], ids=["svg", "invalid", "too-many-pixels"])
async def test_invalid_or_excessive_logo_keeps_name_branding_without_image(monkeypatch, content):
    monkeypatch.setattr(assets, "fetch_public", AsyncMock(return_value=httpx.Response(200, content=content)))
    assert await assets.embed_report_logo("https://cdn.example/logo") is None


@pytest.mark.asyncio
async def test_blocked_logo_is_omitted(monkeypatch):
    from app.utils.public_http import UnsafeURL
    monkeypatch.setattr(assets, "fetch_public", AsyncMock(side_effect=UnsafeURL("Private destination")))
    assert await assets.embed_report_logo("https://cdn.example/logo") is None


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://169.254.169.254/", "https://example.com/logo.png", "data:image/svg+xml,<svg/>", "data:text/plain,hello"])
def test_renderer_blocks_every_non_embedded_raster_resource(url):
    with pytest.raises(ValueError):
        assets.embedded_resource_fetcher(url)


def test_renderer_rejects_disguised_png():
    with pytest.raises(ValueError):
        assets.embedded_resource_fetcher("data:image/png;base64," + base64.b64encode(b"<svg/>").decode())


def test_weasyprint_receives_restricted_fetcher(monkeypatch):
    seen = {}
    class Renderer:
        def __init__(self, **kwargs):
            seen.update(kwargs)
        def write_pdf(self):
            return b"test-pdf"
    monkeypatch.setattr(pdf_generator, "WEASYPRINT_AVAILABLE", True)
    monkeypatch.setattr(pdf_generator, "_WEASYPRINT_HTML", Renderer)
    assert pdf_generator.html_to_pdf("<p>Report</p>") == (b"test-pdf", "weasyprint")
    assert seen["url_fetcher"] is assets.embedded_resource_fetcher
