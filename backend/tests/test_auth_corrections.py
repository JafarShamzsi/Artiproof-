"""Correction-cycle HTTP/auth boundaries with synthetic claims and in-memory DB.

These are not PostgreSQL, browser, provider or real-account acceptance tests.
"""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pyotp
import pytest
from app.config import settings
from app.database import get_db
from app.main import app
from app.models.session import Session
from app.models.user import User
from app.routers import auth
from app.services import team_invites
from app.utils.auth import (
    create_access_token,
    decode_stream_ticket,
    get_current_user_optional,
)
from app.utils.rate_limit import user_bucket_key
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from httpx import ASGITransport, AsyncClient
from jose import jwt
from passlib.hash import bcrypt


@pytest.fixture
async def boundary(monkeypatch):
    from sse_starlette.sse import AppStatus
    monkeypatch.setattr(AppStatus, 'should_exit_event', None)
    now = datetime.now(UTC)
    user = SimpleNamespace(id='correction-user', email='synthetic@example.com', full_name='Synthetic',
                           role='researcher', tier='free', institution=None, organization_id=None,
                           created_at=now, deleted_at=None, deactivated_at=None, totp_enabled=False,
                           totp_secret='JBSWY3DPEHPK3PXP', totp_backup_codes=[], email_verified_at=None,
                           hashed_password=bcrypt.hash('synthetic-password'), linked_providers=None)
    sessions = {'correction-session': SimpleNamespace(id='correction-session', user_id=user.id,
                                                     revoked_at=None, last_used_at=now)}
    db = MagicMock()

    async def get(model, key):
        return sessions.get(key) if model is Session else user if model is User and key == user.id else None

    async def refresh(row):
        if isinstance(row, User):
            for key, value in {'tier': 'free', 'locale': 'en', 'created_at': now,
                               'share_activity_with_team': True, 'subscription_state': 'none'}.items():
                if getattr(row, key) is None:
                    setattr(row, key, value)

    def add(row):
        if isinstance(row, Session):
            sessions[row.id] = row

    db.get = AsyncMock(side_effect=get)
    db.refresh = AsyncMock(side_effect=refresh)
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.add.side_effect = add
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=result)
    monkeypatch.setattr(settings, 'GOOGLE_CLIENT_ID', 'synthetic.apps.googleusercontent.com')

    async def database():
        yield db

    app.dependency_overrides[get_db] = database
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        yield SimpleNamespace(user=user, sessions=sessions, db=db, client=client)
    app.dependency_overrides.clear()


def headers(user):
    return {'Authorization': 'Bearer ' + create_access_token(user.id, user.email, 'correction-session')}


@pytest.mark.parametrize('email,hd,verified', [
    ('synthetic@example.com', None, False), ('synthetic@gmail.com', None, True),
    ('synthetic@workspace.example', 'workspace.example', True),
    ('synthetic@example.com', '', False), ('synthetic@example.com', True, False),
    ('synthetic@example.com', 'https://example.com', False),
    ('synthetic@example.com', 'unrelated.example', False),
    ('synthetic@gmail.com.evil.example', None, False),
])
@pytest.mark.parametrize('operation', ['signup', 'link'])
async def test_google_current_mailbox_authority(boundary, monkeypatch, email, hd, verified, operation):
    b = boundary
    b.user.email = email
    claims = {'sub': 'synthetic-sub', 'email': email, 'email_verified': True}
    if hd is not None:
        claims['hd'] = hd
    monkeypatch.setattr(auth.google_id_token, 'verify_oauth2_token', MagicMock(return_value=claims))
    if operation == 'signup':
        monkeypatch.setattr(auth, 'issue_login_token', AsyncMock(return_value=('synthetic-bearer', None)))
        response = await b.client.post('/api/auth/google', json={'id_token': 'synthetic'})
        stored = b.db.add.call_args.args[0]
    else:
        response = await b.client.post('/api/auth/me/connections/google', headers=headers(b.user),
                                       json={'id_token': 'synthetic'})
        stored = b.user
    assert response.status_code == 200
    assert stored.linked_providers['google']['sub'] == 'synthetic-sub'
    assert (stored.email_verified_at is not None) is verified
    if not verified:
        monkeypatch.setattr(team_invites, 'lock_user', AsyncMock(return_value=stored))
        lock_org = AsyncMock()
        monkeypatch.setattr(team_invites, 'lock_org', lock_org)
        with pytest.raises(HTTPException) as error:
            await team_invites.accept_invite(b.db, user_id=stored.id, org_id='synthetic-org', token='synthetic')
        assert error.value.status_code == 403
        lock_org.assert_not_awaited()


async def test_external_google_link_does_not_revoke_existing_platform_verification(boundary, monkeypatch):
    b = boundary
    original = b.user.email_verified_at = datetime.now(UTC) - timedelta(days=1)
    monkeypatch.setattr(auth.google_id_token, 'verify_oauth2_token', MagicMock(return_value={
        'sub': 'synthetic-sub', 'email': b.user.email, 'email_verified': True,
    }))
    response = await b.client.post('/api/auth/me/connections/google', headers=headers(b.user),
                                   json={'id_token': 'synthetic'})
    assert response.status_code == 200 and b.user.email_verified_at == original


@pytest.mark.parametrize('payload_extra', [
    {'type': 'stream', 'kind': 'source_check', 'rid': 'synthetic-check'},
    {'type': 'org_invite'}, {'type': 'unknown'}, {'type': None},
    {'kind': 'source_check', 'rid': 'synthetic-check'},
    {'type': 'access', 'rid': 'synthetic-check'}, {'org_id': 'synthetic-org'},
])
async def test_capabilities_rejected_by_all_account_dependencies(boundary, payload_extra):
    b = boundary
    token = jwt.encode(dict(sub=b.user.id, email=b.user.email, tier='pro',
                            exp=datetime.now(UTC) + timedelta(minutes=1), **payload_extra),
                       settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    bearer = {'Authorization': 'Bearer ' + token}
    for method, path in [('GET', '/api/auth/me'), ('POST', '/api/auth/refresh'),
                         ('POST', '/api/auth/logout'), ('POST', '/api/auth/me/reactivate')]:
        response = await b.client.request(method, path, headers=bearer)
        assert response.status_code == 401
    request = Request({'type': 'http', 'headers': [(b'authorization', ('Bearer ' + token).encode())],
                       'client': ('127.0.0.1', 12345)})
    credentials = HTTPAuthorizationCredentials(scheme='Bearer', credentials=token)
    assert await get_current_user_optional(request, credentials, b.db) is None
    assert user_bucket_key(request).startswith('ip:')
    b.db.get.assert_not_awaited()


async def test_password_login_refresh_and_logout_real_dependencies_fake_storage(boundary):
    b = boundary
    b.db.execute.return_value.scalar_one_or_none.return_value = b.user
    response = await b.client.post('/api/auth/login', json={'email': b.user.email, 'password': 'synthetic-password'})
    assert response.status_code == 200
    token = response.json()['access_token']
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    assert payload.get('type') == 'access' and payload['jti'] in b.sessions
    refresh = await b.client.post('/api/auth/refresh', headers={'Authorization': 'Bearer ' + token})
    assert refresh.status_code == 200
    refreshed = refresh.json()['access_token']
    assert jwt.decode(refreshed, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])['jti'] == payload['jti']
    assert (await b.client.post('/api/auth/logout', headers={'Authorization': 'Bearer ' + refreshed})).status_code == 204
    assert (await b.client.get('/api/auth/me', headers={'Authorization': 'Bearer ' + token})).status_code == 401


async def test_documented_legacy_untyped_account_still_works(boundary):
    b = boundary
    token = jwt.encode({'sub': b.user.id, 'email': b.user.email, 'exp': datetime.now(UTC) + timedelta(minutes=1)},
                       settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    bearer = {'Authorization': 'Bearer ' + token}
    assert (await b.client.get('/api/auth/me', headers=bearer)).status_code == 200
    assert (await b.client.post('/api/auth/refresh', headers=bearer)).status_code == 200
    assert (await b.client.post('/api/auth/logout', headers=bearer)).status_code == 204


async def test_account_subject_cannot_borrow_another_users_session(boundary):
    b = boundary
    b.sessions['correction-session'].user_id = 'other-user'
    bearer = headers(b.user)
    assert (await b.client.get('/api/auth/me', headers=bearer)).status_code == 401
    request = Request({'type': 'http', 'headers': [], 'client': ('127.0.0.1', 12345)})
    credentials = HTTPAuthorizationCredentials(scheme='Bearer', credentials=bearer['Authorization'][7:])
    assert await get_current_user_optional(request, credentials, b.db) is None


@pytest.mark.parametrize('kind,prefix', [('source_check', '/api/source-check'), ('researcher_profile', '/api/researcher')])
async def test_resource_ticket_works_only_on_its_stream(boundary, monkeypatch, kind, prefix):
    from app.services import analysis_runs
    b = boundary
    resource = SimpleNamespace(id='synthetic-resource', user_id=b.user.id, organization_id=None,
                               deleted_at=None, current_run_id='synthetic-run')
    b.db.execute.return_value.scalar_one_or_none.return_value = resource

    async def observe(*args, **kwargs):
        yield {'event': 'message', 'data': 'synthetic-progress'}

    monkeypatch.setattr(analysis_runs, 'observe_run', observe)
    issued = await b.client.post(prefix + '/synthetic-resource/stream-ticket', headers=headers(b.user))
    assert issued.status_code == 200
    ticket = issued.json()['ticket']
    assert decode_stream_ticket(ticket, kind, resource.id) == b.user.id
    stream = await b.client.get(prefix + '/synthetic-resource/stream', params={'ticket': ticket})
    assert stream.status_code == 200 and 'synthetic-progress' in stream.text
    assert (await b.client.get('/api/auth/me', headers={'Authorization': 'Bearer ' + ticket})).status_code == 401
    assert (await b.client.get(prefix + '/other/stream', params={'ticket': ticket})).status_code == 403
    account = create_access_token(b.user.id, b.user.email, 'correction-session')
    assert (await b.client.get(prefix + '/synthetic-resource/stream', params={'ticket': account})).status_code == 401


@pytest.mark.parametrize('endpoint', ['setup', 'enable'])
async def test_google_only_totp_enrollment_denied_before_mutation(boundary, endpoint):
    b = boundary
    b.user.hashed_password = None
    original = (b.user.totp_secret, list(b.user.totp_backup_codes), b.user.totp_enabled)
    response = await b.client.post('/api/auth/me/2fa/' + endpoint, headers=headers(b.user),
                                   json={'code': pyotp.TOTP(b.user.totp_secret).now()})
    assert response.status_code == 409
    assert 'Google-only' in response.json()['detail']
    assert (b.user.totp_secret, b.user.totp_backup_codes, b.user.totp_enabled) == original
    b.db.commit.assert_not_awaited()
    status = await b.client.get('/api/auth/me/2fa', headers=headers(b.user))
    assert status.json().get('enrollment_available') is False


async def test_password_totp_enrollment_remains_supported(boundary):
    b = boundary
    status = await b.client.get('/api/auth/me/2fa', headers=headers(b.user))
    assert status.json().get('enrollment_available') is True
    response = await b.client.post('/api/auth/me/2fa/enable', headers=headers(b.user),
                                   json={'code': pyotp.TOTP(b.user.totp_secret).now()})
    assert response.status_code == 200 and response.json()['enabled'] is True
