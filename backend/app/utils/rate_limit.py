"""Shared rate limiter instance used across routers.

Configured here so every router decorates against the same limiter
that's also wired into the FastAPI app state in ``main.py``.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
