import numpy as np
import pytest

from app.detection.regions import LEL, LEYE, LHIP, LSH, LWR, NOSE, REL, REYE, RHIP, RSH, RWR, regions_for
from app.detection.rules import GRACE_S, CheckTracker, camera_observation
from app.detection.types import Analysis, CheckResult, PersonResult, state_from_probability

W, H = 640, 480
PERSON = (100, 40, 540, 480)


def keypoints(**visible_points) -> np.ndarray:
    kp = np.zeros((17, 3), np.float32)
    for idx, (x, y) in visible_points.items():
        kp[int(idx)] = (x, y, 0.95)
    return kp


FRONT_FACE = {str(NOSE): (320, 150), str(LEYE): (300, 130), str(REYE): (340, 130)}


def kp_of(points: dict) -> np.ndarray:
    return keypoints(**points)


def test_face_visible_gives_hair_and_mask_regions():
    r = regions_for(kp_of(FRONT_FACE), PERSON, W, H)
    assert set(r) == {"head", "face"}
    (hx0, hy0, hx1, hy1), = r["head"]
    (mx0, my0, mx1, my1), = r["face"]
    assert hy0 < 130 < hy1  # hair region reaches above the eyes
    assert my0 < 150 < my1  # mask region covers the nose
    assert hx0 < 320 < hx1 and mx0 < 320 < mx1


def test_hidden_face_gives_nothing():
    assert regions_for(kp_of({}), PERSON, W, H) == {}
    # Nose without eyes (e.g. seen from behind) is not enough to judge a mask.
    assert "face" not in regions_for(kp_of({str(NOSE): (320, 150)}), PERSON, W, H)


def test_hands_from_wrists_and_elbows():
    pts = {**FRONT_FACE, str(LWR): (250, 350), str(LEL): (250, 280), str(RWR): (400, 350)}
    r = regions_for(kp_of(pts), PERSON, W, H)
    assert len(r["hands"]) == 2
    left = r["hands"][0]
    assert left[1] < 350 + 28 < left[3]  # extends beyond the wrist, away from the elbow


def test_apron_needs_shoulders_and_hips():
    shoulders = {str(LSH): (250, 220), str(RSH): (390, 220)}
    assert "torso" not in regions_for(kp_of({**FRONT_FACE, **shoulders}), PERSON, W, H)
    r = regions_for(kp_of({**FRONT_FACE, **shoulders, str(LHIP): (270, 400), str(RHIP): (370, 400)}), PERSON, W, H)
    x0, y0, x1, y1 = r["torso"][0]
    assert y0 == 220 and y1 > 400 and x0 < 250 and x1 > 390


def test_regions_are_clipped_to_the_frame():
    edge = {str(NOSE): (5, 10), str(LEYE): (2, 5), str(REYE): (15, 5)}
    for boxes in regions_for(kp_of(edge), (0, 0, 100, 200), W, H).values():
        for x0, y0, x1, y1 in boxes:
            assert 0 <= x0 < x1 <= W and 0 <= y0 < y1 <= H


@pytest.mark.parametrize("p, expected", [(0.9, "ok"), (0.6, "ok"), (0.45, "unknown"), (0.3, "violation"), (0.01, "violation")])
def test_state_thresholds(p, expected):
    assert state_from_probability(p, 0.6, 0.3) == expected


def analysis(*states: str) -> Analysis:
    persons = [
        PersonResult(box=(0, 0, 10, 10), score=0.9, checks={"no_mask": CheckResult(state=s, p_present={"ok": 0.9, "violation": 0.1, "unknown": 0.5}[s])})
        for s in states
    ]
    return Analysis(width=W, height=H, persons=persons, inference_ms=1)


def test_camera_observation_any_violation_wins():
    assert camera_observation(analysis("ok", "violation"), "no_mask") == ("violation", 0.1)
    assert camera_observation(analysis("ok", "unknown"), "no_mask") == ("ok", 0.9)
    assert camera_observation(analysis("unknown"), "no_mask") == ("unknown", None)
    assert camera_observation(analysis(), "no_mask") == ("unknown", None)


def test_tracker_fires_after_min_duration_then_cools_down():
    t = CheckTracker()
    fires = [t.update("violation", 0.1, now, min_duration_s=5, cooldown_s=60) for now in range(0, 8)]
    assert fires == [False] * 5 + [True, False, False]  # fires once at 5s
    assert t.confidence == 0.9
    assert not t.update("violation", 0.1, 30, 5, 60)  # still in cooldown
    assert t.update("violation", 0.1, 66, 5, 60)  # cooldown over, violation ongoing


def test_tracker_ok_resets_timer():
    t = CheckTracker()
    for now in range(0, 4):
        t.update("violation", 0.1, now, 5, 60)
    t.update("ok", 0.9, 4, 5, 60)
    assert not any(t.update("violation", 0.1, now, 5, 60) for now in range(5, 9))  # timer restarted at 5
    assert t.update("violation", 0.1, 10, 5, 60)


def test_tracker_short_gaps_are_tolerated_long_gaps_reset():
    t = CheckTracker()
    t.update("violation", 0.1, 0, 5, 60)
    t.update("unknown", None, 2, 5, 60)  # looked away briefly
    assert t.update("violation", 0.1, 5, 5, 60)  # still counts from 0

    t2 = CheckTracker()
    t2.update("violation", 0.1, 0, 5, 60)
    t2.update("unknown", None, GRACE_S + 1, 5, 60)  # gone too long
    assert not t2.update("violation", 0.1, 6, 5, 60)
