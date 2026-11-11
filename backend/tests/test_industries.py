"""Industries: one active at a time, chosen at login; each camera (and its zones and events) belongs
to one industry, and every list, dashboard and report shows only the active industry."""

import pytest

from app.config import settings
from app.db import SessionLocal
from app.services.app_settings import get_settings
from tests.test_alerts import after_subscribed, read_messages
from tests.test_detection_api import isolate_detection, wait_for  # noqa: F401 (isolate_detection is an autouse fixture)


@pytest.fixture(autouse=True)
def restaurant_afterwards():
    """Other tests expect the restaurant industry, so always switch back."""
    yield
    with SessionLocal() as db:
        get_settings(db).active_industry = "restaurant"
        db.commit()


def login(client, industry=None) -> dict:
    body = {"username": "admin", "password": "admin123", **({"industry": industry} if industry else {})}
    r = client.post("/api/auth/login", json=body)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_login_page_lists_industries_without_a_login(client):
    r = client.get("/api/industries")
    assert r.status_code == 200
    body = r.json()
    assert [i["key"] for i in body["industries"]] == ["restaurant", "cement"]
    assert body["active"] == "restaurant" and body["locked"] is False
    assert client.get("/api/industry").status_code == 401  # the full profile needs a login


def test_profiles(client, auth):
    p = client.get("/api/industry", headers=auth).json()
    assert p["key"] == "restaurant" and p["score_label"] == "Hygiene score"
    assert [c["key"] for c in p["ppe_checks"]] == ["no_hair_cover", "no_mask", "no_gloves", "no_apron"]
    assert [r["key"] for r in p["zone_rules"]] == ["handwash_skipped", "handwash_short", "table_not_cleared"]
    assert {"key": "sink", "label": "Hand-wash sink", "colour": "#3987e5"} in p["zone_types"]

    c = client.put("/api/industry", headers=auth, json={"industry": "cement"}).json()
    assert c["key"] == "cement" and c["score_label"] == "Safety score"
    assert [(x["key"], x["missing"]) for x in c["ppe_checks"]] == [("no_helmet", "No helmet"), ("no_vest", "No vest")]
    assert [r["key"] for r in c["zone_rules"]] == ["restricted_area", "conveyor_spillage", "bag_count"] and "Damaged cement bag detection" in c["planned"]
    assert "restricted" in [z["key"] for z in c["zone_types"]]
    assert client.put("/api/industry", headers=auth, json={"industry": "bakery"}).status_code == 422


def test_login_chooses_the_industry_only_with_the_right_password(client):
    assert client.post("/api/auth/login", json={"username": "admin", "password": "nope", "industry": "cement"}).status_code == 401
    assert client.get("/api/industries").json()["active"] == "restaurant"
    login(client, "cement")
    assert client.get("/api/industries").json()["active"] == "cement"
    login(client)  # no industry: keeps the current one
    assert client.get("/api/industries").json()["active"] == "cement"


def test_cameras_zones_and_events_stay_in_their_industry(client, test_video):
    auth = login(client, "restaurant")
    kitchen = client.post("/api/cameras", headers=auth, json={"name": "Kitchen cam", "source_url": test_video}).json()
    assert kitchen["industry"] == "restaurant" and kitchen["area"] == "kitchen"
    client.post("/api/events/test", headers=auth, json={"camera_id": kitchen["id"], "event_type": "no_gloves"})

    auth = login(client, "cement")
    assert client.get("/api/cameras", headers=auth).json() == []  # the kitchen camera is not shown
    assert client.get("/api/events", headers=auth).json()["total"] == 0
    assert client.get("/api/dashboard/summary", headers=auth).json()["violations_today"] == 0

    # New cameras belong to the active industry, with its areas, zone types and checks.
    assert client.post("/api/cameras", headers=auth, json={"name": "Bad", "source_url": test_video, "area": "kitchen"}).status_code == 422
    kiln = client.post("/api/cameras", headers=auth, json={"name": "Kiln cam", "source_url": test_video}).json()
    assert kiln["industry"] == "cement" and kiln["area"] == "production"
    zone = {"name": "Kiln", "polygon": [[0, 0], [0.5, 0], [0.5, 0.5]]}
    assert client.post(f"/api/cameras/{kiln['id']}/zones", headers=auth, json={**zone, "zone_type": "sink"}).status_code == 422
    assert client.post(f"/api/cameras/{kiln['id']}/zones", headers=auth, json={**zone, "zone_type": "restricted"}).status_code == 201
    cfg = client.get(f"/api/detection/cameras/{kiln['id']}/config", headers=auth).json()
    assert cfg["checks"] == ["no_helmet", "no_vest", "restricted_area", "conveyor_spillage", "bag_count"]
    bad = client.put(f"/api/detection/cameras/{kiln['id']}/config", headers=auth, json={"enabled": False, "checks": ["no_mask"]})
    assert bad.status_code == 422
    assert [t["key"] for t in client.get("/api/events/types", headers=auth).json()][:3] == ["no_helmet", "no_vest", "restricted_area"]
    assert client.post("/api/events/test", headers=auth, json={"camera_id": kiln["id"], "event_type": "no_mask"}).status_code == 422
    e = client.post("/api/events/test", headers=auth, json={"camera_id": kiln["id"], "event_type": "no_helmet"}).json()
    assert e["type_label"] == "No safety helmet" and e["severity"] == "critical"

    events = client.get("/api/events", headers=auth).json()["items"]
    assert [x["event_type"] for x in events] == ["no_helmet"]
    assert [z["name"] for z in client.get("/api/zones", headers=auth).json()] == ["Kiln"]

    # Back to the restaurant: only its camera and event.
    auth = login(client, "restaurant")
    assert [c["name"] for c in client.get("/api/cameras", headers=auth).json()] == ["Kitchen cam"]
    assert [x["event_type"] for x in client.get("/api/events", headers=auth).json()["items"]] == ["no_gloves"]
    assert [t["event_type"] for t in client.get("/api/dashboard/summary", headers=auth, params={"tz_offset": 0}).json()["by_type"]] == ["no_gloves"]


def test_detection_runs_only_the_active_industrys_cameras(client, test_video):
    auth = login(client, "restaurant")
    cam = client.post("/api/cameras", headers=auth, json={"name": "Line cam", "source_url": test_video}).json()
    client.put(f"/api/detection/cameras/{cam['id']}/config", headers=auth, json={"enabled": True, "interval_s": 0.5})
    running = lambda: [c["camera_id"] for c in client.get("/api/detection/status", headers=auth).json()["cameras"]]  # noqa: E731
    assert wait_for(lambda: running() == [cam["id"]])

    client.put("/api/industry", headers=auth, json={"industry": "cement"})
    assert wait_for(lambda: running() == [], timeout=10)  # the restaurant camera stops
    assert client.get("/api/detection/configs", headers=auth).json() == []

    client.put("/api/industry", headers=auth, json={"industry": "restaurant"})
    assert wait_for(lambda: running() == [cam["id"]])


def test_open_pages_are_told_about_a_switch(client, auth):
    token = client.post("/api/auth/media-token", headers=auth).json()["access_token"]
    t = after_subscribed(lambda: client.put("/api/industry", headers=auth, json={"industry": "cement"}))
    messages = read_messages(client, f"/api/events/stream?limit=1&token={token}")
    t.join()
    assert messages[1] == {"type": "industry", "industry": "cement", "name": "Cement plant"}


def test_locked_installation_shows_and_allows_one_industry(client, monkeypatch):
    monkeypatch.setattr(settings, "industry_lock", "cement")
    body = client.get("/api/industries").json()
    assert [i["key"] for i in body["industries"]] == ["cement"] and body["active"] == "cement" and body["locked"] is True
    auth = login(client)
    assert client.get("/api/industry", headers=auth).json()["key"] == "cement"
    assert client.put("/api/industry", headers=auth, json={"industry": "restaurant"}).status_code == 409
    assert client.post("/api/auth/login", json={"username": "admin", "password": "admin123", "industry": "restaurant"}).status_code == 409
