"""One-command demo: add the demo videos as cameras, draw their zones, switch detection on.

Needs the backend running (python main.py). From the backend folder:

    .\.venv\Scripts\python.exe scripts\setup_demo.py              # set up / refresh the demo
    .\.venv\Scripts\python.exe scripts\setup_demo.py --clear-events   # also delete the demo cameras' old events
    .\.venv\Scripts\python.exe scripts\setup_demo.py --off         # stop detection on demo cameras (frees the GPU)
    .\.venv\Scripts\python.exe scripts\setup_demo.py --remove      # delete the demo cameras (their events are kept)
    .\.venv\Scripts\python.exe scripts\setup_demo.py --industry cement   # the cement plant demo (any option above works too)

Safe to run again: existing demo cameras are updated, not duplicated. Your other cameras are not touched.
"""

import argparse
import sys
from pathlib import Path

import httpx

DATA = Path(__file__).resolve().parent.parent / "data"
PPE = ["no_hair_cover", "no_mask", "no_gloves", "no_apron"]

# Zones were placed by running scripts/analyze_videos.py and checking where people stand.
SINK = {"name": "Hand sink", "zone_type": "sink", "polygon": [[0.20, 0.62], [0.43, 0.62], [0.43, 1.0], [0.20, 1.0]]}
PREP = {"name": "Prep table", "zone_type": "raw_prep", "polygon": [[0.56, 0.60], [0.85, 0.60], [0.85, 1.0], [0.56, 1.0]]}
TABLE = {"name": "Table 1", "zone_type": "dining_table", "polygon": [[0.36, 0.44], [0.62, 0.44], [0.66, 0.78], [0.32, 0.78]]}

# Demo timings: alerts come quickly, and the same alert repeats at most every 2 minutes per camera
# (the videos loop every 10 s, so shorter would flood the Events page during a presentation).
DEMO_TIMING = {"min_duration_s": 3, "cooldown_s": 120, "interval_s": 1.0, "handwash_min_s": 20, "wash_valid_min": 30, "table_clear_min": 0.5}

DEMOS = [
    # file, camera name, area, zones, checks. The apron check is off where the white apron over
    # white clothes fools the zero-shot model (see the accuracy table from analyze_videos.py).
    ("01_compliant_chef.mp4", "Demo 1 · Compliant chef", "kitchen", [], PPE),
    ("02_no_ppe_cook.mp4", "Demo 2 · No PPE cook", "kitchen", [], PPE),
    ("03_mixed_team.mp4", "Demo 3 · Mixed team", "kitchen", [], PPE),
    ("04_handwash_short.mp4", "Demo 4 · Short hand wash", "kitchen", [SINK, PREP],
     ["no_hair_cover", "no_mask", "no_gloves", "handwash_short", "handwash_skipped"]),
    ("05_handwash_skipped.mp4", "Demo 5 · Skipped hand wash", "kitchen", [SINK, PREP],
     ["no_hair_cover", "no_mask", "no_gloves", "handwash_short", "handwash_skipped"]),
    ("06_dirty_table.mp4", "Demo 6 · Dining table", "dining", [TABLE], ["table_not_cleared"]),
]

# Cement plant. The danger zone follows the yellow-and-black floor line around the crusher in video 04
# (checked against where the worker's feet are: outside at 2.5 s, inside 3.0-7.5 s).
CEMENT_PPE = ["no_helmet", "no_vest"]
DANGER = {"name": "Crusher danger area", "zone_type": "restricted",
          "polygon": [[0.33, 0.47], [0.57, 0.91], [1.0, 0.58], [1.0, 0.30], [0.55, 0.30]]}
# Floor under the conveyor in videos 05/06 (below the belt frame, right of the steel column).
BELT_FLOOR = {"name": "Floor under conveyor", "zone_type": "conveyor_floor",
              "polygon": [[0.30, 0.68], [0.95, 0.68], [0.95, 1.0], [0.30, 1.0]]}
# The loader belt in video 07, tight over the bags' height; its counting line lands at x = 0.64,
# just before the worker lifts each bag off (5 bags counted per 10-second loop).
LOADER_BELT = {"name": "Loader belt", "zone_type": "packing_line",
               "polygon": [[0.0, 0.30], [0.85, 0.30], [0.85, 0.50], [0.0, 0.50]]}
CEMENT_DEMOS = [
    ("01_ppe_compliant.mp4", "Cement 1 · PPE compliant", "production", [], CEMENT_PPE),
    ("02_no_ppe_worker.mp4", "Cement 2 · No helmet or vest", "production", [], CEMENT_PPE),
    ("03_mixed_crew.mp4", "Cement 3 · Mixed crew", "production", [], CEMENT_PPE),
    ("04_restricted_area.mp4", "Cement 4 · Restricted area", "production", [DANGER], CEMENT_PPE + ["restricted_area"]),
    ("05_conveyor_spillage.mp4", "Cement 5 · Conveyor spillage", "production", [BELT_FLOOR], ["conveyor_spillage"]),
    ("06_conveyor_normal.mp4", "Cement 6 · Conveyor normal", "production", [BELT_FLOOR], ["conveyor_spillage"]),
    ("07_bag_counting.mp4", "Cement 7 · Bag counting", "packing", [LOADER_BELT], ["bag_count"]),
]

INDUSTRY_DEMOS = {"restaurant": (DATA / "demo", DEMOS), "cement": (DATA / "demo_cement", CEMENT_DEMOS)}


LITE_SIZE = (1280, 720)
LITE_FPS = 12


def make_lite(src: Path) -> Path:
    """A 12 fps copy of a demo video at full 1280x720. Decoding six 720p/24fps videos at once
    saturates a laptop CPU; halving the frame rate halves that. The picture size is kept because
    hands are small: 640x360 cut glove accuracy from 100% to 87%, 960x540 to 94%."""
    import cv2

    lite_dir = src.parent / "lite"
    dst = lite_dir / src.name
    if dst.is_file() and dst.stat().st_mtime >= src.stat().st_mtime:
        probe = cv2.VideoCapture(str(dst))
        size_ok = (int(probe.get(cv2.CAP_PROP_FRAME_WIDTH)), int(probe.get(cv2.CAP_PROP_FRAME_HEIGHT))) == LITE_SIZE
        probe.release()
        if size_ok:
            return dst
    lite_dir.mkdir(exist_ok=True)
    cap = cv2.VideoCapture(str(src))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 24
    out = cv2.VideoWriter(str(dst), cv2.VideoWriter_fourcc(*"mp4v"), LITE_FPS, LITE_SIZE)
    keep_every = src_fps / LITE_FPS
    i, next_keep = 0, 0.0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i >= next_keep:
            out.write(cv2.resize(frame, LITE_SIZE, interpolation=cv2.INTER_AREA))
            next_keep += keep_every
        i += 1
    out.release()
    return dst


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:8000", help="backend address")
    ap.add_argument("--username", default="admin")
    ap.add_argument("--password", default="admin123")
    ap.add_argument("--clear-events", action="store_true", help="delete existing events of the demo cameras first")
    ap.add_argument("--off", action="store_true", help="switch detection off on the demo cameras")
    ap.add_argument("--remove", action="store_true", help="delete the demo cameras")
    ap.add_argument("--full", action="store_true", help="use the original full-size videos (needs a strong CPU)")
    ap.add_argument("--industry", choices=list(INDUSTRY_DEMOS), default="restaurant", help="which demo to set up")
    args = ap.parse_args()
    demo_dir, demos = INDUSTRY_DEMOS[args.industry]

    api = httpx.Client(base_url=f"{args.url}/api", timeout=60)
    try:
        # Switch to the demo's industry: cameras belong to the active one.
        r = api.post("/auth/login", json={"username": args.username, "password": args.password, "industry": args.industry})
    except httpx.ConnectError:
        sys.exit(f"Backend not reachable at {args.url}. Start it first: python main.py")
    r.raise_for_status()
    api.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    cameras = {c["name"]: c for c in api.get("/cameras").json()}
    names = {name for _, name, *_ in demos}

    if args.remove:
        for name in names & cameras.keys():
            api.delete(f"/cameras/{cameras[name]['id']}").raise_for_status()
            print(f"Removed {name}")
        return

    if args.off:
        for name in names & cameras.keys():
            cid = cameras[name]["id"]
            cfg = api.get(f"/detection/cameras/{cid}/config").json()
            cfg.pop("camera_id")
            api.put(f"/detection/cameras/{cid}/config", json={**cfg, "enabled": False}).raise_for_status()
            print(f"Detection off: {name}")
        return

    missing = [f for f, *_ in demos if not (demo_dir / f).is_file()]
    if missing:
        sys.exit(f"Missing videos in {demo_dir}: {', '.join(missing)}")

    for file, name, area, zones, checks in demos:
        source = demo_dir / file if args.full else make_lite(demo_dir / file)
        body = {"name": name, "area": area, "source_url": str(source), "location": "Demo video", "enabled": True}
        if name in cameras:
            cam = api.patch(f"/cameras/{cameras[name]['id']}", json=body)
        else:
            cam = api.post("/cameras", json=body)
        cam.raise_for_status()
        cid = cam.json()["id"]

        for z in api.get(f"/cameras/{cid}/zones").json():  # replace zones with the known-good ones
            api.delete(f"/zones/{z['id']}").raise_for_status()
        for z in zones:
            api.post(f"/cameras/{cid}/zones", json=z).raise_for_status()

        if args.clear_events:
            ids = [e["id"] for e in api.get("/events", params={"camera_id": cid, "limit": 200}).json()["items"]]
            if ids:
                api.post("/events/bulk-delete", json={"ids": ids}).raise_for_status()

        api.put(f"/detection/cameras/{cid}/config", json={"enabled": bool(checks), "checks": checks, **DEMO_TIMING}).raise_for_status()
        print(f"Ready: {name:30s} zones: {', '.join(z['name'] for z in zones) or '-':22s} checks: {', '.join(checks)}")

    print("\nOpen http://127.0.0.1:5173/live — the models load in ~15-30 s the first time, then boxes and alerts appear.")
    print("Tip: on a GTX 1650 laptop the 6 cameras share one GPU and CPU, so each is checked every few seconds;")
    print("     alerts appear 5-10 s after a violation starts. Show fewer cameras (--off, then enable 2-3) for snappier boxes.")


if __name__ == "__main__":
    main()
