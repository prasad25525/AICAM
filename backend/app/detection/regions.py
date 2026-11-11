"""Where to look for each item on a person, from YOLO-pose keypoints (COCO order).

A region is only returned when the body parts it depends on are clearly visible, so hidden
parts give "unknown" instead of a guess.
"""

import numpy as np

from app.detection.types import Box

NOSE, LEYE, REYE, LEAR, REAR, LSH, RSH, LEL, REL, LWR, RWR, LHIP, RHIP = range(13)
KP_CONF = 0.5
MIN_REGION_PX = 16


def _clip(x0: float, y0: float, x1: float, y1: float, w: int, h: int) -> Box | None:
    box = (int(max(0, x0)), int(max(0, y0)), int(min(w, x1)), int(min(h, y1)))
    if box[2] - box[0] < MIN_REGION_PX or box[3] - box[1] < MIN_REGION_PX:
        return None
    return box


def regions_for(kp: np.ndarray, person: Box, width: int, height: int) -> dict[str, list[Box]]:
    """kp: (17, 3) array of x, y, confidence. Returns {region: [boxes]} for the body regions that are visible:
    "head" (hat / helmet), "face" (mask), "hands" (gloves), "torso" (apron / vest)."""
    vis = kp[:, 2] >= KP_CONF
    pt = kp[:, :2]
    out: dict[str, list[Box]] = {}

    # Face scale: ear-to-ear or eye distance, falling back to a share of the person's width.
    face_w = 0.25 * (person[2] - person[0])
    if vis[LEAR] and vis[REAR]:
        face_w = float(np.linalg.norm(pt[LEAR] - pt[REAR]))
    elif vis[LEYE] and vis[REYE]:
        face_w = 2.2 * float(np.linalg.norm(pt[LEYE] - pt[REYE]))
    face_w = max(face_w, 24.0)

    face_visible = vis[NOSE] and (vis[LEYE] or vis[REYE])
    if face_visible:
        head_idx = [i for i in (NOSE, LEYE, REYE, LEAR, REAR) if vis[i]]
        hx, hy = pt[head_idx].mean(axis=0)
        nx, ny = pt[NOSE]
        if r := _clip(hx - 0.9 * face_w, hy - 1.3 * face_w, hx + 0.9 * face_w, hy + 0.3 * face_w, width, height):
            out["head"] = [r]
        if r := _clip(nx - 0.6 * face_w, ny - 0.5 * face_w, nx + 0.6 * face_w, ny + 0.8 * face_w, width, height):
            out["face"] = [r]

    hands = []
    for wrist, elbow in ((LWR, LEL), (RWR, REL)):
        if not vis[wrist]:
            continue
        # The hand sits a little beyond the wrist, along the forearm.
        centre = pt[wrist] + 0.4 * (pt[wrist] - pt[elbow]) if vis[elbow] else pt[wrist] + np.array([0, 0.25 * face_w])
        s = max(0.6 * face_w, 18.0)
        if r := _clip(centre[0] - s, centre[1] - s, centre[0] + s, centre[1] + s, width, height):
            hands.append(r)
    if hands:
        out["hands"] = hands

    hips = [i for i in (LHIP, RHIP) if vis[i]]
    if vis[LSH] and vis[RSH] and hips:
        sx0, sx1 = sorted((pt[LSH, 0], pt[RSH, 0]))
        sw = sx1 - sx0
        sy = (pt[LSH, 1] + pt[RSH, 1]) / 2
        hy = pt[hips, 1].mean()
        if r := _clip(sx0 - 0.15 * sw, sy, sx1 + 0.15 * sw, hy + 0.35 * (hy - sy), width, height):
            out["torso"] = [r]

    return out
