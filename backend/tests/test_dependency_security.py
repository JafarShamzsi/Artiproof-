"""Application exposure guards, NOT evidence that advisory packages are fixed.

See docs/DEPENDENCY-SECURITY.md for residual advisories and deployment caveats.
Only synthetic keys/data are used; no broker, filesystem or provider requests.
"""

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app.services.report_engine.assets import embedded_resource_fetcher
from app.utils import auth


def test_hmac_auth_rejects_a_token_outside_the_configured_algorithm(monkeypatch):
    # Relevant to GHSA-3qf3-8w2g-rqmx: never let the token choose algorithms.
    # This does not claim that python-jose's DER-key defect is patched.
    secret = "dependencies-01-synthetic-hmac-key-not-a-public-key"
    monkeypatch.setattr(auth.settings, "JWT_SECRET", secret)
    monkeypatch.setattr(auth.settings, "JWT_ALGORITHM", "HS256")
    token = jwt.encode({"sub": "synthetic-user"}, secret, algorithm="HS384")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as error:
        auth._decode_token(credentials)
    assert error.value.status_code == 401


def test_default_hmac_issuance_does_not_use_ecdsa_signing(monkeypatch):
    # GHSA-wj6h-64fc-37mp affects ECDSA signing, not HS256.
    from ecdsa import SigningKey

    def unexpected_signing(*args, **kwargs):
        pytest.fail("HMAC auth must not call ECDSA signing")

    monkeypatch.setattr(SigningKey, "sign_digest", unexpected_signing)
    monkeypatch.setattr(auth.settings, "JWT_SECRET", "synthetic-hmac-only-key")
    monkeypatch.setattr(auth.settings, "JWT_ALGORITHM", "HS256")
    token = auth.create_access_token("synthetic-user", "user@example.invalid")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    assert auth._decode_token(credentials)["sub"] == "synthetic-user"


@pytest.mark.parametrize(
    "url",
    [
        "data:application/postscript;base64,JSFQUy1BZG9iZQ==",
        "data:image/x-eps;base64,JSFQUy1BZG9iZQ==",
        "data:image/png;base64,JSFQUy1BZG9iZQ==",
        "file:///synthetic-not-read.xmp",
        "https://example.invalid/synthetic.css",
    ],
)
def test_report_fetcher_rejects_interpreter_and_external_inputs(url):
    # Relevant to the WeasyPrint EPS advisory. No Ghostscript is invoked.
    with pytest.raises(ValueError):
        embedded_resource_fetcher(url)


def test_renderer_does_not_forward_stylesheet_or_xmp_options(monkeypatch):
    # GHSA-jf6q-chmf-3h3v bypasses a restrictive fetcher via these options.
    # Exercise the application call boundary even where native Pango is absent.
    from app.services.report_engine import pdf_generator

    class Renderer:
        def __init__(self, **kwargs):
            assert kwargs == {"string": "<p>synthetic</p>", "url_fetcher": embedded_resource_fetcher}

        def write_pdf(self, *args, **kwargs):
            assert not args and not kwargs
            return b"synthetic-pdf"

    monkeypatch.setattr(pdf_generator, "WEASYPRINT_AVAILABLE", True)
    monkeypatch.setattr(pdf_generator, "_WEASYPRINT_HTML", Renderer)
    assert pdf_generator.html_to_pdf("<p>synthetic</p>") == (b"synthetic-pdf", "weasyprint")
