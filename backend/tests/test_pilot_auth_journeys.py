"""Real HTTP auth/membership/access tests; only email delivery is a test sink.

Run with scripts/qa_auth/run.py api. Default unit collection excludes this
integration module. Missing owned services fail, rather than silently skip.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import uuid

import httpx
import pymupdf
import pytest

pytestmark = pytest.mark.integration
PASSWORD = "QA01-synthetic-passphrase-42"


@pytest.fixture(scope="module")
def pilot():
    directory = os.environ.get("QA_AUTH_ARTIFACTS")
    if not directory:
        pytest.fail("BLOCKED: run scripts/qa_auth/run.py api with owned disposable services")
    with httpx.Client(base_url="http://127.0.0.1:8203", timeout=30, trust_env=False) as client:
        assert client.get("/api/health").json()["services"] == {"database": "ok", "redis": "ok"}
        users = []
        for label in ("owner", "member", "outsider"):
            email = f"qa01-api-{label}-{uuid.uuid4()}@example.com"
            response = client.post("/api/auth/register", json={
                "email": email, "password": PASSWORD, "full_name": f"QA01 {label}", "role": "admin",
            })
            assert response.status_code == 201, response.text
            data = response.json()
            assert data["user"]["role"] == "researcher"
            users.append({**data, "headers": {"Authorization": f"Bearer {data['access_token']}"}})
        yield client, Path(directory), users


def link(directory, email, kind):
    name = hashlib.sha256(email.lower().encode()).hexdigest() + ".json"
    mail = json.loads((directory / "mail" / name).read_text(encoding="utf-8"))
    pattern = r"/verify-email/([a-zA-Z0-9_-]+)" if kind == "verify" else r"/register\?invite=([a-zA-Z0-9_.-]+)"
    match = re.search(pattern, mail["text"] or mail["html"])
    assert match, f"Real {kind} token absent from captured email"
    return match.group(1)


def test_real_verification_invite_consent_removal_and_resource_boundaries(pilot):
    client, directory, (owner, member, outsider) = pilot
    mh, oh, xh = member["headers"], owner["headers"], outsider["headers"]
    for user in (owner, member):
        assert client.get("/api/auth/me/email/status", headers=user["headers"]).json()["verified"] is False
    response = client.post("/api/organizations", json={"name": f"QA01 {uuid.uuid4()}"}, headers=oh)
    assert response.status_code == 201, response.text
    org = response.json()["id"]
    invited = client.post(f"/api/organizations/{org}/members/invite", json={"email": member["user"]["email"], "role": "member"}, headers=oh)
    assert invited.status_code == 201, invited.text
    token = link(directory, member["user"]["email"], "invite")
    accept = f"/api/organizations/{org}/invites/accept"
    assert client.post(accept, json={"token": token}, headers=mh).status_code == 403
    # A verified wrong recipient must still be rejected. Testing only an
    # unverified outsider would stop at the earlier verification guard.
    outsider_verify = link(directory, outsider["user"]["email"], "verify")
    assert client.post("/api/auth/email/verify", json={"token": outsider_verify}).status_code == 204
    assert client.post(accept, json={"token": token}, headers=xh).status_code == 400
    assert client.get("/api/auth/me", headers=mh).json()["organization_id"] is None
    assert client.post("/api/auth/me/email/verify/request", json={}, headers=mh).status_code == 200
    verify_token = link(directory, member["user"]["email"], "verify")
    assert client.post("/api/auth/email/verify", json={"token": verify_token}).status_code == 204
    assert client.post("/api/auth/email/verify", json={"token": verify_token}).status_code == 400
    assert client.get("/api/auth/me/email/status", headers=mh).json()["verified"] is True
    assert client.post("/api/organizations/invites/preview", json={"token": token}, headers=mh).status_code == 200
    assert client.get("/api/auth/me", headers=mh).json()["organization_id"] is None
    for _ in range(2):
        assert client.post(accept, json={"token": token}, headers=mh).status_code == 200
    me = client.get("/api/auth/me", headers=mh).json()
    # Membership does not grant a billing tier in accept_invite. Do not
    # mistake organization enrollment for paid entitlement activation.
    assert (me["organization_id"], me["org_role"], me["tier"]) == (org, "member", "free")

    source_response = client.post("/api/source-check/", json={"input_type": "text", "input_content": "Synthetic QA01 text. This checks auth and queued persistence, not provider inference."}, headers=mh)
    assert source_response.status_code == 201, source_response.text
    source = source_response.json()
    assert source["status"] == "pending"
    response = client.post("/api/reports/generate", json={"source_check_id": source["id"]}, headers=mh)
    assert response.status_code == 201, response.text
    report = response.json()
    for route in (f"/api/source-check/{source['id']}", f"/api/reports/{report['id']}", f"/api/reports/{report['id']}/download"):
        assert client.get(route, headers=mh).status_code == 200
        assert client.get(route, headers=oh).status_code == 200
        assert client.get(route, headers=xh).status_code == 403
        assert client.get(route).status_code == 401
    pdf = client.get(f"/api/reports/{report['id']}/download", headers=mh)
    assert pdf.content.startswith(b"%PDF-")
    assert pdf.headers["x-report-renderer"] in ("cached", "weasyprint", "pymupdf-fallback")
    with pymupdf.open(stream=pdf.content, filetype="pdf") as document:
        assert "unavailable" in "".join(page.get_text() for page in document).lower()
    assert client.delete(f"/api/organizations/{org}/members/{member['user']['id']}", headers=oh).status_code == 204
    assert client.get(f"/api/organizations/{org}/members", headers=mh).status_code == 403
    assert client.get("/api/auth/me", headers=mh).json()["organization_id"] is None
    assert client.post(accept, json={"token": token}, headers=mh).status_code in (400, 403, 409)
    # Revoke the real persisted session, then check all formerly readable routes.
    assert client.post("/api/auth/logout", headers=mh).status_code == 204
    for route in ("/api/auth/me", f"/api/source-check/{source['id']}", f"/api/reports/{report['id']}", f"/api/reports/{report['id']}/download"):
        assert client.get(route, headers=mh).status_code == 401


def test_password_login_and_specific_session_revocation(pilot):
    client, _, (owner, _, outsider) = pilot
    xh = outsider["headers"]
    wrong = client.post("/api/auth/login", json={"email": outsider["user"]["email"], "password": "wrong-synthetic-password"})
    assert wrong.status_code == 401
    response = client.post("/api/auth/login", json={"email": outsider["user"]["email"], "password": PASSWORD})
    assert response.status_code == 200, response.text
    fresh = {"Authorization": f"Bearer {response.json()['access_token']}"}
    sessions = client.get("/api/auth/me/sessions", headers=fresh).json()
    assert len(sessions) == 2
    current = next(item for item in sessions if item["is_current"])
    assert client.delete(f"/api/auth/me/sessions/{current['id']}", headers=owner["headers"]).status_code == 404
    assert client.get("/api/auth/me", headers=fresh).status_code == 200
    assert client.delete(f"/api/auth/me/sessions/{current['id']}", headers=xh).status_code == 204
    assert client.get("/api/auth/me", headers=fresh).status_code == 401
    assert client.get("/api/auth/me", headers=xh).status_code == 200


def test_forged_bearer_cannot_authorize(pilot):
    client, _, _ = pilot
    for token in ("not-a-jwt", "eyJhbGciOiJub25lIn0.eyJzdWIiOiJxYTAxIn0."):
        assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
