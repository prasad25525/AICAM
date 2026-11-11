"""Run the real detector over video files: what it sees, and how accurate it is.

Usage: python scripts/analyze_videos.py [folder] [industry]   (default: data/demo, restaurant;
       a folder named like "demo_cement" picks the cement industry)

Prints, per video: people seen, the verdict per PPE check (ok / missing / unknown), where people's
feet were over time (to place zones), and tableware found. If the folder has a ground_truth.json
(true = item worn), it also prints an accuracy table per check.
"""

import json
import sys
from collections import Counter
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.detection.engine import PPEEngine  # noqa: E402
from app.detection.zones import ZoneShape  # noqa: E402
from app.industries import INDUSTRIES, Industry  # noqa: E402

SAMPLE_EVERY_S = 0.5


def analyse(engine, path: Path, industry: Industry) -> dict:
    checks = [c.key for c in industry.ppe_checks]
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, int(fps * SAMPLE_EVERY_S))
    people = Counter()
    verdicts: dict[str, dict[str, Counter]] = {}  # slot -> check -> Counter(state)
    feet, objects = [], Counter()
    for idx in range(0, total, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            break
        h, w = frame.shape[:2]
        a = engine.analyze(frame, checks, settings.present_threshold, settings.absent_threshold)
        people[len(a.persons)] += 1
        ordered = sorted(a.persons, key=lambda p: p.box[0])  # left to right
        for i, p in enumerate(ordered):
            slot = "P" if len(ordered) == 1 else ("L" if i == 0 else "R" if i == len(ordered) - 1 else f"M{i}")
            for check, c in p.checks.items():
                verdicts.setdefault(slot, {}).setdefault(check, Counter())[c.state] += 1
        if ordered:
            x0, _, x1, y1 = ordered[0].box
            feet.append((idx / fps, round((x0 + x1) / 2 / w, 2), round(y1 / h, 2)))
        if industry.key == "restaurant":  # tableware only matters for the table rule
            whole = ZoneShape(0, "Whole frame", ((0, 0), (1, 0), (1, 1), (0, 1)), "dining_table")
            objects.update(o.label for o in engine.detect_objects(frame, [whole]))
    return {"frames": sum(people.values()), "people": people, "verdicts": verdicts, "feet": feet, "objects": objects}


def main(folder: Path, industry: Industry) -> None:
    PPE_CHECKS = [c.key for c in industry.ppe_checks]
    ITEM = {c.key: c.item for c in industry.ppe_checks}
    print(f"Industry: {industry.name}  checks: {', '.join(PPE_CHECKS)}")
    engine = PPEEngine(settings.models_dir)
    truth_file = folder / "ground_truth.json"
    truth = json.loads(truth_file.read_text(encoding="utf-8")) if truth_file.exists() else {}
    scores = {c: Counter() for c in PPE_CHECKS}  # correct / wrong / unknown per check

    for path in sorted(folder.glob("*.mp4")):
        r = analyse(engine, path, industry)
        print(f"\n=== {path.name}  ({r['frames']} frames analysed) ===")
        print("  people per frame:", dict(sorted(r["people"].items())))
        for slot, checks in sorted(r["verdicts"].items()):
            for check, v in sorted(checks.items()):
                print(f"  {slot} {check:14s} ok={v['ok']:2d}  missing={v['violation']:2d}  unknown={v['unknown']:2d}")
                expected = truth.get(path.name, {}).get(slot, {}).get(check)
                if expected is not None:
                    right, wrong = ("ok", "violation") if expected else ("violation", "ok")
                    scores[check].update({"correct": v[right], "wrong": v[wrong], "unknown": v["unknown"]})
        if r["feet"]:
            print("  feet (t s, x, y):", " ".join(f"{t:.1f}:({x},{y})" for t, x, y in r["feet"]))
        if industry.key == "restaurant":
            print("  tableware seen (frames):", dict(r["objects"]) or "none")

    if truth:
        print("\n=== ACCURACY vs ground_truth.json (per analysed frame and person) ===")
        print(f"  {'Item':16s} {'Accuracy':>9s} {'Decided':>8s}   correct / wrong / unsure")
        for check in PPE_CHECKS:
            s = scores[check]
            judged = s["correct"] + s["wrong"]
            total = judged + s["unknown"]
            if not total:
                continue
            acc = f"{100 * s['correct'] / judged:.0f}%" if judged else "-"
            print(f"  {ITEM[check]:16s} {acc:>9s} {100 * judged / total:7.0f}%   {s['correct']} / {s['wrong']} / {s['unknown']}")
        print("  Accuracy = correct among decided answers. Decided = share of frames where the model gave an answer instead of 'unsure'.")


if __name__ == "__main__":
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "data" / "demo"
    key = sys.argv[2] if len(sys.argv) > 2 else ("cement" if "cement" in folder.name else "restaurant")
    main(folder, INDUSTRIES[key])
