"""Explain why an RTSP camera won't open: unreachable, needs rtsps://, wrong login, or a bad path.

OpenCV only says "could not open". This speaks just enough RTSP (OPTIONS, then DESCRIBE with
Basic or Digest login, over plain TCP or TLS) to tell the cases apart. No video is read.
"""

import hashlib
import re
import socket
import ssl
from urllib.parse import unquote, urlsplit, urlunsplit

TIMEOUT_S = 4
# Main-stream paths used by common camera firmwares (CP Plus ships Dahua-, Uniview- and other-based ones).
KNOWN_PATHS = [
    "/video/live?channel=1&subtype=0",  # newer CP Plus firmware (e.g. CP-UNC-DA61L3C-LQ)
    "/cam/realmonitor?channel=1&subtype=0",  # Dahua, older CP Plus
    "/unicast/c1/s0/live",  # Uniview
    "/media/video1",  # Uniview (older)
    "/Streaming/Channels/101",  # Hikvision
    "/h264/ch1/main/av_stream",  # Hikvision (older)
    "/stream1",  # TP-Link Tapo and others
    "/live/ch00_0",
    "/ch01.264",
    "/profile1",
    "/11",
    "/live",
    "/",
]


def _connect(host: str, port: int, tls: bool) -> socket.socket:
    sock = socket.create_connection((host, port), timeout=TIMEOUT_S)
    if tls:
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE  # cameras use self-signed certificates
        sock = ctx.wrap_socket(sock, server_hostname=host)
    sock.settimeout(TIMEOUT_S)
    return sock


def _request(sock: socket.socket, method: str, url: str, cseq: int, extra: str = "") -> tuple[int, dict[str, str]]:
    sock.sendall(f"{method} {url} RTSP/1.0\r\nCSeq: {cseq}\r\nUser-Agent: AICAM\r\nAccept: application/sdp\r\n{extra}\r\n".encode())
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    head = data.split(b"\r\n\r\n")[0].decode(errors="replace").split("\r\n")
    if not head or not head[0].startswith("RTSP/"):
        return 0, {}
    status = int(head[0].split()[1])
    headers = {}
    for line in head[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers.setdefault(k.strip().lower(), v.strip())
    return status, headers


def _auth_header(challenge: str, user: str, password: str, method: str, url: str) -> str:
    if challenge.lower().startswith("basic"):
        import base64

        return "Authorization: Basic " + base64.b64encode(f"{user}:{password}".encode()).decode() + "\r\n"
    fields = dict(re.findall(r'(\w+)="?([^",]*)"?', challenge))
    realm, nonce = fields.get("realm", ""), fields.get("nonce", "")

    def md5(s: str) -> str:
        return hashlib.md5(s.encode()).hexdigest()  # RTSP Digest is MD5 by spec

    response = md5(f"{md5(f'{user}:{realm}:{password}')}:{nonce}:{md5(f'{method}:{url}')}")
    return f'Authorization: Digest username="{user}", realm="{realm}", nonce="{nonce}", uri="{url}", response="{response}"\r\n'


def _describe(host: str, port: int, tls: bool, url: str, user: str | None, password: str | None) -> int:
    """RTSP status of DESCRIBE (logging in if asked), or 0 if the camera didn't answer in RTSP."""
    with _connect(host, port, tls) as sock:
        status, headers = _request(sock, "DESCRIBE", url, 1)
        if status == 401 and user is not None and "www-authenticate" in headers:
            status, _ = _request(sock, "DESCRIBE", url, 2, _auth_header(headers["www-authenticate"], user, password or "", "DESCRIBE", url))
        return status


def find_path(source: str) -> str | None:
    """Try the known stream paths with the URL's own login; return the working address with the
    password masked, or None. Right password + wrong path is not a failed login, so no lockout."""
    parts = urlsplit(source)
    host, port = parts.hostname or "", parts.port or 554
    user, password = unquote(parts.username or ""), unquote(parts.password or "")
    tls = parts.scheme == "rtsps"
    # Over TLS, some cameras only accept rtsp:// inside the request; FFmpeg can't send that, so it
    # means: turn RTSP encryption off in the camera and use plain rtsp://.
    request_schemes = ["rtsps", "rtsp"] if tls else ["rtsp"]
    for path in KNOWN_PATHS:
        p, _, q = path.partition("?")
        for scheme in request_schemes:
            bare = urlunsplit((scheme, f"{host}:{port}", p, q, ""))
            try:
                status = _describe(host, port, tls, bare, user, password)
            except (OSError, ssl.SSLError):
                continue
            if status == 200:
                address = urlunsplit(("rtsp" if scheme == "rtsp" and tls else parts.scheme, f"{parts.username}:****@{host}:{port}", p, q, ""))
                if tls and scheme == "rtsp":
                    return f"{address} (first switch OFF RTSP encryption / RTSP over TLS in the camera's network settings)"
                return address
            if status == 401:
                return None  # the login itself failed: stop before the camera locks the account
    return None


def diagnose(source: str) -> str:
    """A plain-language reason the stream can't be opened (the URL's password is never included)."""
    parts = urlsplit(source)
    host, port = parts.hostname or "", parts.port or 554
    tls = parts.scheme == "rtsps"
    user = unquote(parts.username) if parts.username is not None else None
    password = unquote(parts.password) if parts.password is not None else None
    # The URL the camera sees: without the login part.
    bare = urlunsplit((parts.scheme, f"{host}:{port}", parts.path or "/", parts.query, ""))

    try:
        socket.create_connection((host, port), timeout=TIMEOUT_S).close()
    except OSError:
        return f"Camera not reachable at {host}:{port}. Check the IP address, the cable, and that this computer is on the same network."

    try:
        status = _describe(host, port, tls, bare, user, password)
    except (OSError, ssl.SSLError):
        status = 0
    if status == 0 and not tls:
        # Silent on plain RTSP: does it answer over TLS (secure RTSP)?
        try:
            if _describe(host, port, True, bare, None, None):
                return f"This camera uses secure RTSP: change the address to start with rtsps:// instead of rtsp:// (port {port})."
        except (OSError, ssl.SSLError):
            pass
        return f"Port {port} is open but the camera didn't answer as RTSP. Check that RTSP is enabled in the camera's network settings."
    if status == 0:
        return f"Port {port} is open but the camera didn't answer as secure RTSP. Try rtsp:// instead of rtsps://."
    special = "If the password has @ # : / or ? in it, write them as %40 %23 %3A %2F %3F in the address."
    if status == 401:
        if user is None:
            return "The camera needs a login: add it to the address, e.g. rtsp://admin:PASSWORD@host:554/…"
        return f"Wrong username or password (the camera refused the login for user “{user}”). {special}"
    if status == 404:
        found = find_path(source) if user is not None else None
        if found:
            return f"Login is correct, but this camera uses a different stream path. Use this address: {found}"
        return "Login is correct, but the camera doesn't know this stream path, and none of the usual paths worked. Look for the RTSP address in the camera's manual or its ONVIF settings."
    if status == 200:
        if "@" in source.rsplit("@", 1)[0].split("://", 1)[-1]:
            # Login works here, but the video reader splits user:password@host at the first @.
            return f"The password contains @, which breaks the address. {special}"
        return "Login and stream path are correct, but no video arrived in time. The camera may be slow to start: try again, or lower its resolution."
    return f"The camera answered with RTSP error {status}."
