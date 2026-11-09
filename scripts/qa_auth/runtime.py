"""Test-only configuration and email sink. Never changes auth dependencies."""

import hashlib
import ipaddress
import json
import os
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"


def configure():
    """Import real settings with dotenv loading explicitly disabled."""
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(BACKEND))
    from pydantic_settings import BaseSettings

    original = BaseSettings.__init__

    def without_dotenv(self, *args, **kwargs):
        kwargs["_env_file"] = None
        original(self, *args, **kwargs)

    with patch.object(BaseSettings, "__init__", without_dotenv):
        from app.config import settings
    if (settings.DATABASE_URL != "postgresql+asyncpg://qa01:qa01-synthetic@127.0.0.1:55443/qa01"
            or settings.DATABASE_URL_SYNC != "postgresql://qa01:qa01-synthetic@127.0.0.1:55443/qa01"
            or settings.REDIS_URL != "redis://127.0.0.1:56443/0"
            or settings.ENVIRONMENT != "test"):
        raise RuntimeError("QA-01 refuses non-test or non-owned database/Redis configuration")
    return settings


def local_network_only():
    """Best-effort Python getaddrinfo/connect tripwire, NOT an egress sandbox.

    Does not mediate native SDK sockets, connect_ex, UDP, subprocesses, Node,
    browsers or OS traffic. Exact test endpoints/stripped keys are separate
    controls. Broader OS/network isolation requires separately approved scope.
    """
    original = socket.getaddrinfo

    def resolve(host, *args, **kwargs):
        if host not in (None, "localhost"):
            try:
                allowed = ipaddress.ip_address(host).is_loopback
            except ValueError:
                allowed = False
            if not allowed:
                raise OSError(f"QA-01 forbids external network destination: {host}")
        return original(host, *args, **kwargs)

    socket.getaddrinfo = resolve
    original_connect = socket.socket.connect

    def connect(sock, address):
        if isinstance(address, tuple) and not ipaddress.ip_address(address[0]).is_loopback:
            raise OSError("QA-01 forbids external socket connections")
        return original_connect(sock, address)

    socket.socket.connect = connect


def email_sink():
    import app.services.email as email

    async def deliver(*, to, subject, html, text=None, **kwargs):
        # Only the delivery boundary is replaced; token issuance/rendering is real.
        directory = Path(os.environ["QA_AUTH_ARTIFACTS"]) / "mail"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (hashlib.sha256(to.lower().encode()).hexdigest() + ".json")
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"to": to, "subject": subject, "html": html, "text": text}), encoding="utf-8")
        temporary.replace(path)
        return True

    email.send_email = deliver


if __name__ == "__main__":
    configure()
    local_network_only()
    action = sys.argv[1]
    if action == "migrate":
        from alembic import command
        from alembic.config import Config

        config = Config(str(BACKEND / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND / "alembic"))
        command.upgrade(config, "head")
        command.current(config)
    elif action == "api":
        email_sink()
        import uvicorn

        uvicorn.run("app.main:app", host="127.0.0.1", port=8203, access_log=False)
    elif action == "pytest":
        import pytest

        raise SystemExit(pytest.main(["-c", str(BACKEND / "pytest.ini"), *sys.argv[2:]]))
    else:
        raise SystemExit(f"Unknown action: {action}")
