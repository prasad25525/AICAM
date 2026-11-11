"""The RTSP connection checker, against a tiny fake camera on localhost (Digest login, one valid path)."""

import hashlib
import re
import socket
import threading

import pytest

from app.services.rtsp_probe import diagnose

USER, PASSWORD, REALM, NONCE = "admin", "Pa@ss", "cam", "abc123"
GOOD_PATH = "/video/live?channel=1&subtype=0"


def _md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


def _reply(request: str) -> str:
    lines = request.split("\r\n")
    method, uri, _ = lines[0].split(" ", 2)
    auth = next((line for line in lines if line.lower().startswith("authorization:")), None)
    if auth is None:
        return f'RTSP/1.0 401 Unauthorized\r\nCSeq: 1\r\nWWW-Authenticate: Digest realm="{REALM}", nonce="{NONCE}"\r\n\r\n'
    f = dict(re.findall(r'(\w+)="([^"]*)"', auth))
    ha1, ha2 = _md5(f"{USER}:{REALM}:{PASSWORD}"), _md5(f"{method}:{f.get('uri')}")
    expected = _md5(f"{ha1}:{NONCE}:{ha2}")
    if f.get("username") != USER or f.get("response") != expected:
        return f'RTSP/1.0 401 Unauthorized\r\nCSeq: 2\r\nWWW-Authenticate: Digest realm="{REALM}", nonce="{NONCE}"\r\n\r\n'
    if uri.split("554", 1)[-1] != GOOD_PATH:
        return "RTSP/1.0 404 Not Found\r\nCSeq: 2\r\n\r\n"
    return "RTSP/1.0 200 OK\r\nCSeq: 2\r\nContent-Length: 0\r\n\r\n"


@pytest.fixture
def fake_camera(monkeypatch):
    """Serves on a free localhost port; the URLs use :554, so connections are redirected there."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()
    port = server.getsockname()[1]

    def serve():
        while True:
            try:
                conn, _ = server.accept()
            except OSError:
                return
            with conn:
                conn.settimeout(2)
                try:
                    while data := conn.recv(4096):
                        conn.sendall(_reply(data.decode()).encode())
                except OSError:
                    pass

    threading.Thread(target=serve, daemon=True).start()
    real = socket.create_connection
    monkeypatch.setattr(socket, "create_connection", lambda addr, timeout=None: real(("127.0.0.1", port), timeout=timeout))
    yield
    server.close()


def test_explains_each_failure(fake_camera):
    base = "rtsp://{login}127.0.0.1:554{path}"
    assert "needs a login" in diagnose(base.format(login="", path=GOOD_PATH))
    wrong = diagnose(base.format(login="admin:nope@", path=GOOD_PATH))
    assert "Wrong username or password" in wrong and "%40" in wrong
    found = diagnose(base.format(login="admin:Pa%40ss@", path="/cam/realmonitor?channel=1&subtype=0"))
    assert "different stream path" in found and found.endswith("rtsp://admin:****@127.0.0.1:554/video/live?channel=1&subtype=0")
    assert "Pa" not in found.replace("Path", "")  # the password is never shown
    assert "no video arrived" in diagnose(base.format(login="admin:Pa%40ss@", path=GOOD_PATH))
    # Unencoded @ in the password: the login works here, but the video reader would split the address wrongly.
    assert "contains @" in diagnose(base.format(login="admin:Pa@ss@", path=GOOD_PATH))


def test_unreachable_camera():
    assert "not reachable" in diagnose("rtsp://127.0.0.1:1/x")
