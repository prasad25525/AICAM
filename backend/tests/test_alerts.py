import json
import threading
import time

import pytest

from app.db import SessionLocal
from app.models import Camera
from app.services.alerts import alerts
from app.services.events import create_event


@pytest.fixture
def cam(client, auth, test_video) -> dict:
    return client.post("/api/cameras", headers=auth, json={"name": "Prep 1", "source_url": test_video}).json()


@pytest.fixture
def media_token(client, auth) -> str:
    return client.post("/api/auth/media-token", headers=auth).json()["access_token"]


def read_messages(client, url: str) -> list[dict]:
    out = []
    with client.stream("GET", url) as r:
        assert r.status_code == 200, r.read()
        assert r.headers["content-type"].startswith("text/event-stream")
        for line in r.iter_lines():
            if line.startswith("data: "):
                out.append(json.loads(line[6:]))
    return out


def after_subscribed(action):
    """Run `action` in another thread once the stream has subscribed (like the detection thread does)."""
    before = alerts.subscriber_count

    def run():
        deadline = time.monotonic() + 5
        while alerts.subscriber_count <= before and time.monotonic() < deadline:
            time.sleep(0.02)
        action()

    t = threading.Thread(target=run)
    t.start()
    return t


def test_stream_requires_token(client):
    assert client.get("/api/events/stream?limit=1").status_code == 401


def test_new_event_is_pushed(client, cam, media_token):
    def make_event():
        with SessionLocal() as db:
            create_event(db, camera=db.get(Camera, cam["id"]), event_type="no_gloves", confidence=0.8)

    t = after_subscribed(make_event)
    messages = read_messages(client, f"/api/events/stream?limit=1&token={media_token}")
    t.join()

    assert messages[0] == {"type": "hello"}
    created = messages[1]
    assert created["type"] == "created"
    e = created["event"]
    assert e["event_type"] == "no_gloves" and e["type_label"] == "No gloves" and e["severity"] == "critical"
    assert e["camera_name"] == "Prep 1" and e["confidence"] == 0.8 and e["simulated"] is False


def test_changes_are_pushed(client, auth, cam, media_token):
    event_id = client.post("/api/events/test", headers=auth, json={"camera_id": cam["id"], "event_type": "no_mask"}).json()["id"]
    t = after_subscribed(lambda: client.patch(f"/api/events/{event_id}", headers=auth, json={"status": "resolved"}))
    messages = read_messages(client, f"/api/events/stream?limit=1&token={media_token}")
    t.join()
    assert messages[1] == {"type": "changed", "ids": [event_id]}


def test_unsubscribes_when_done(client, media_token):
    before = alerts.subscriber_count
    t = after_subscribed(lambda: alerts.publish("changed", {"ids": []}))
    read_messages(client, f"/api/events/stream?limit=1&token={media_token}")
    t.join()
    assert alerts.subscriber_count == before


def test_event_ids_routes_still_work(client, auth):
    # /events/stream must not be swallowed by /events/{id}, and ids stay numeric-only.
    assert client.get("/api/events/99999", headers=auth).status_code == 404
    assert client.get("/api/events/abc", headers=auth).status_code == 404
