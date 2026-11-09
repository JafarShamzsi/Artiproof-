import socket

import pytest


def test_unit_outbound_connections_are_denied():
    with socket.socket() as client:
        with pytest.raises(RuntimeError, match="Showcase tests forbid"):
            client.connect(("198.51.100.1", 443))


def test_unit_service_connections_are_denied():
    with socket.socket() as client:
        with pytest.raises(RuntimeError, match="Showcase tests forbid"):
            client.connect(("127.0.0.1", 5432))


def test_asyncio_internal_socketpair_is_allowed():
    left, right = socket.socketpair()
    try:
        left.sendall(b"synthetic")
        assert right.recv(9) == b"synthetic"
    finally:
        left.close()
        right.close()
