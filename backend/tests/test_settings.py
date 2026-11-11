"""App-wide switches: stop saving events, and stop (or filter) pop-up notifications."""

import pytest
from sqlalchemy import delete

from app.db import SessionLocal
from app.models import AppSettings, Camera
from app.services.app_settings import get_settings
from app.services.events import create_event
from tests.test_alerts import after_subscribed, read_messages
from tests.test_detection_api import enable, wait_for


@pytest.fixture(autouse=True)
def default_settings():
    """Every test starts (and leaves) with the defaults: everything on."""
    with SessionLocal() as db:
        db.execute(delete(AppSettings))
        db.commit()
    yield
    with SessionLocal() as db:
        db.execute(delete(AppSettings))
        db.commit()


@pytest.fixture
def cam(client, auth, test_video) -> dict:
    return client.post("/api/cameras", headers=auth, json={"name": "Prep 2", "source_url": test_video}).json()


def test_first_use_from_two_threads_at_once():
    """The detection thread and a request may both create the settings row: neither may fail."""
    import threading

    barrier, errors, rows = threading.Barrier(8), [], []

    def first_use():
        try:
            with SessionLocal() as db:
                barrier.wait()
                rows.append(get_settings(db).id)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=first_use) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == [] and rows == [1] * 8


def test_defaults_and_update(client, auth):
    assert client.get("/api/settings").status_code == 401
    assert client.get("/api/settings", headers=auth).json() == {
        "events_enabled": True, "notifications_enabled": True, "notify_severities": ["critical", "warning", "info"],
    }
    r = client.put("/api/settings", headers=auth, json={"notifications_enabled": False, "notify_severities": ["info", "critical", "info"]})
    assert r.json() == {"events_enabled": True, "notifications_enabled": False, "notify_severities": ["critical", "info"]}
    assert client.get("/api/settings", headers=auth).json() == r.json()
    assert client.put("/api/settings", headers=auth, json={"notify_severities": ["loud"]}).status_code == 422


def _pushed_after_creating(client, auth, cam, event_type: str) -> dict:
    token = client.post("/api/auth/media-token", headers=auth).json()["access_token"]

    def make_event():
        with SessionLocal() as db:
            create_event(db, camera=db.get(Camera, cam["id"]), event_type=event_type)

    t = after_subscribed(make_event)
    messages = read_messages(client, f"/api/events/stream?limit=1&token={token}")
    t.join()
    return messages[1]


def test_notifications_off_sends_no_popup_but_lists_still_refresh(client, auth, cam):
    client.put("/api/settings", headers=auth, json={"notifications_enabled": False})
    msg = _pushed_after_creating(client, auth, cam, "no_gloves")
    assert msg["type"] == "changed" and len(msg["ids"]) == 1
    assert client.get("/api/events", headers=auth).json()["total"] == 1  # still saved


def test_only_chosen_severities_pop_up(client, auth, cam):
    client.put("/api/settings", headers=auth, json={"notify_severities": ["critical"]})
    assert _pushed_after_creating(client, auth, cam, "no_apron")["type"] == "changed"  # info
    assert _pushed_after_creating(client, auth, cam, "no_gloves")["type"] == "created"  # critical


def test_events_off_detection_keeps_running_but_saves_nothing(client, auth, cam):
    client.put("/api/settings", headers=auth, json={"events_enabled": False})
    enable(client, auth, cam["id"])
    # The fake engine reports "no mask": the live view still sees it...
    latest = wait_for(lambda: (r := client.get(f"/api/detection/cameras/{cam['id']}/latest", headers=auth)).status_code == 200 and r.json())
    assert latest["persons"][0]["checks"]["no_mask"]["state"] == "violation"
    wait_for(lambda: False, timeout=2.5)  # past min_duration_s (1s) with room to spare
    assert client.get("/api/events", headers=auth).json()["total"] == 0  # ...but no event is saved

    # Switched back on: the next violation is recorded again (cooldown was never started).
    client.put("/api/settings", headers=auth, json={"events_enabled": True})
    client.put(f"/api/detection/cameras/{cam['id']}/config", headers=auth, json={"enabled": False})
    assert wait_for(lambda: client.get("/api/detection/status", headers=auth).json()["cameras"] == [])
    enable(client, auth, cam["id"])
    assert wait_for(lambda: client.get("/api/events", headers=auth).json()["total"] == 1)
    client.put(f"/api/detection/cameras/{cam['id']}/config", headers=auth, json={"enabled": False})
