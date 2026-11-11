"""PPE engine: YOLO11-pose finds people and body parts, SigLIP 2 answers "is this item worn?" per region."""

import time
from pathlib import Path

import cv2
import numpy as np

from app.detection.regions import regions_for
from app.detection.types import Analysis, CheckResult, PersonResult, state_from_probability
from app.detection.zone_rules import TableObject
from app.detection.zones import ZoneShape, point_in_zone
from app.industries import ALL_PPE_CHECKS, ALL_ZONE_RULES

MAX_PERSONS = 6
PERSON_CONF = 0.4
OBJECT_CONF = 0.3
# Things that mean "a table hasn't been cleared". Found by name with YOLO-World (open vocabulary):
# the usual COCO models have no "plate" class, and plates are what's left on most tables.
TABLEWARE = ["plate", "bowl", "cup", "glass", "bottle", "spoon", "fork"]
TABLEWARE_WEIGHTS = "yolov8s-worldv2.pt"
TABLEWARE_BAKED = "yolov8s-worldv2-tableware.pt"  # the same model with TABLEWARE built in (no CLIP needed to load)
CROP_MARGIN = 0.08  # widen each table crop a little so items on the edge aren't cut

# For each check: prompts describing the item worn vs. not worn (from the industry packs). The
# best-matching prompt on each side is compared, giving P(item present) = sigmoid(best_worn - best_not_worn).
PROMPTS: dict[str, tuple[list[str], list[str]]] = {k: (list(c.worn), list(c.not_worn)) for k, c in ALL_PPE_CHECKS.items()}


DUPLICATE_OVERLAP = 0.6  # a box mostly inside a bigger one is the same person seen twice


def dedupe_people(boxes: np.ndarray) -> list[int]:
    """Indices of person boxes, largest first, dropping duplicates: the pose model sometimes returns
    a second, partial box (e.g. upper body only) for one person. A box is dropped when most of it
    lies inside a larger kept box."""
    areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    kept: list[int] = []
    for i in np.argsort(-areas):
        duplicate = False
        for k in kept:
            ix = max(0.0, min(boxes[i, 2], boxes[k, 2]) - max(boxes[i, 0], boxes[k, 0]))
            iy = max(0.0, min(boxes[i, 3], boxes[k, 3]) - max(boxes[i, 1], boxes[k, 1]))
            if areas[i] > 0 and ix * iy / areas[i] >= DUPLICATE_OVERLAP:
                duplicate = True
                break
        if not duplicate:
            kept.append(int(i))
    return kept


class PPEEngine:
    name = "YOLO11n-pose + SigLIP 2"

    def __init__(self, models_dir: Path):
        import torch
        from transformers import AutoModel, AutoProcessor
        from ultralytics import YOLO

        self._torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.pose = YOLO(str(models_dir / "ultralytics" / "yolo11n-pose.pt"))
        self.pose.to(self.device)
        self._models_dir = models_dir
        self._objects = None  # tableware detector, loaded the first time a table rule needs it

        siglip_dir = models_dir / "hf" / "siglip2-base-patch16-224"
        self.processor = AutoProcessor.from_pretrained(siglip_dir)
        self.siglip = AutoModel.from_pretrained(siglip_dir).to(self.device).eval()

        # Text side never changes: embed all prompts once (PPE checks, and image checks on zones).
        texts: list[str] = []
        self._spans: dict[str, tuple[int, int, int]] = {}
        for check, (worn, not_worn) in PROMPTS.items():
            self._spans[check] = (len(texts), len(worn), len(not_worn))
            texts += worn + not_worn
        zone_texts: list[str] = []
        self._zone_spans: dict[str, tuple[int, int, int]] = {}
        for key, rule in ALL_ZONE_RULES.items():
            if rule.is_visual:
                self._zone_spans[key] = (len(zone_texts), len(rule.look_for), len(rule.normal))
                zone_texts += list(rule.look_for) + list(rule.normal)
        self._text = self._embed_texts(texts)
        self._zone_text = self._embed_texts(zone_texts) if zone_texts else None
        self._scale = float(self.siglip.logit_scale.exp())  # SigLIP's learned temperature

        self.analyze(np.zeros((240, 320, 3), np.uint8), list(PROMPTS), 0.6, 0.3)  # warm-up (first CUDA call is slow)

    def _embed_texts(self, texts: list[str]):
        with self._torch.no_grad():
            t = self.processor(text=texts, padding="max_length", max_length=64, return_tensors="pt").to(self.device)
            emb = self.siglip.get_text_features(**t)
            emb = getattr(emb, "pooler_output", emb)
            return emb / emb.norm(dim=-1, keepdim=True)

    def zone_probabilities(self, frame: np.ndarray, items: list[tuple[str, ZoneShape]]) -> list[float]:
        """P(problem) for each (image zone rule, zone): the zone's bounding box is cropped and compared
        with the rule's prompts, e.g. "spilled material on the floor" vs "clean empty floor"."""
        height, width = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        crops, kept = [], []
        for i, (_, zone) in enumerate(items):
            xs, ys = [p[0] for p in zone.polygon], [p[1] for p in zone.polygon]
            x0, x1 = int(max(0.0, min(xs)) * width), int(min(1.0, max(xs)) * width)
            y0, y1 = int(max(0.0, min(ys)) * height), int(min(1.0, max(ys)) * height)
            if x1 - x0 >= 16 and y1 - y0 >= 16:
                crops.append(rgb[y0:y1, x0:x1])
                kept.append(i)
        probs = [0.5] * len(items)  # too small to judge = unsure
        if not crops or self._zone_text is None:
            return probs
        with self._torch.no_grad():
            inputs = self.processor(images=crops, return_tensors="pt").to(self.device)
            emb = self.siglip.get_image_features(**inputs)
            emb = getattr(emb, "pooler_output", emb)
            emb = emb / emb.norm(dim=-1, keepdim=True)
            logits = (emb @ self._zone_text.T).float().cpu().numpy()
        for row, i in zip(logits, kept):
            s, n_look, n_normal = self._zone_spans[items[i][0]]
            margin = (row[s : s + n_look].max() - row[s + n_look : s + n_look + n_normal].max()) * self._scale
            probs[i] = float(1 / (1 + np.exp(-margin)))
        return probs

    def analyze(self, frame: np.ndarray, checks: list[str], present_th: float, absent_th: float) -> Analysis:
        torch = self._torch
        start = time.perf_counter()
        height, width = frame.shape[:2]
        result = self.pose.predict(frame, conf=PERSON_CONF, verbose=False, device=self.device)[0]

        persons: list[PersonResult] = []
        crops, owners = [], []  # owners[i] = (person index, check, region)
        if result.keypoints is not None and len(result.boxes):
            boxes = result.boxes.xyxy.cpu().numpy()
            scores = result.boxes.conf.cpu().numpy()
            kps = result.keypoints.data.cpu().numpy()
            order = dedupe_people(boxes)[:MAX_PERSONS]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            for idx in order:
                box = tuple(int(v) for v in boxes[idx])
                person = PersonResult(box=box, score=float(scores[idx]), checks={})
                regions = regions_for(kps[idx], box, width, height)
                for check in checks:
                    if check not in PROMPTS:
                        continue
                    boxes_for_check = regions.get(ALL_PPE_CHECKS[check].region, [])
                    person.checks[check] = CheckResult(state="unknown", regions=boxes_for_check)
                    for r in boxes_for_check:
                        crops.append(rgb[r[1] : r[3], r[0] : r[2]])
                        owners.append((len(persons), check))
                persons.append(person)

        if crops:
            with torch.no_grad():
                inputs = self.processor(images=crops, return_tensors="pt").to(self.device)
                emb = self.siglip.get_image_features(**inputs)
                emb = getattr(emb, "pooler_output", emb)
                emb = emb / emb.norm(dim=-1, keepdim=True)
                logits = (emb @ self._text.T).float().cpu().numpy()
            # Per person and check, keep the worst region (e.g. one bare hand is a violation).
            for row, (pi, check) in zip(logits, owners):
                s, n_worn, n_not = self._spans[check]
                margin = (row[s : s + n_worn].max() - row[s + n_worn : s + n_worn + n_not].max()) * self._scale
                p = float(1 / (1 + np.exp(-margin)))
                current = persons[pi].checks[check]
                if current.p_present is None or p < current.p_present:
                    current.p_present = p
            for person in persons:
                for c in person.checks.values():
                    if c.p_present is not None:
                        c.state = state_from_probability(c.p_present, present_th, absent_th)

        return Analysis(width=width, height=height, persons=persons, inference_ms=(time.perf_counter() - start) * 1000)

    def _tableware_model(self):
        if self._objects is None:
            from ultralytics import YOLO

            folder = self._models_dir / "ultralytics"
            if (folder / TABLEWARE_BAKED).exists():
                model = YOLO(str(folder / TABLEWARE_BAKED))
            else:
                model = YOLO(str(folder / TABLEWARE_WEIGHTS))
                model.set_classes(TABLEWARE)  # uses CLIP once to embed the names
                model.save(str(folder / TABLEWARE_BAKED))
            model.to(self.device)
            self._objects = model
        return self._objects

    def detect_objects(self, frame: np.ndarray, zones: list[ZoneShape]) -> list[TableObject]:
        """Tableware on the given table zones. Each zone is cropped and searched on its own: zoomed
        in, plates and cups are found far more reliably than in the whole picture."""
        model = self._tableware_model()
        height, width = frame.shape[:2]
        found: list[TableObject] = []
        for zone in zones:
            xs, ys = [p[0] for p in zone.polygon], [p[1] for p in zone.polygon]
            mx, my = (max(xs) - min(xs)) * CROP_MARGIN, (max(ys) - min(ys)) * CROP_MARGIN
            x0, x1 = int(max(0, min(xs) - mx) * width), int(min(1, max(xs) + mx) * width)
            y0, y1 = int(max(0, min(ys) - my) * height), int(min(1, max(ys) + my) * height)
            if x1 - x0 < 16 or y1 - y0 < 16:
                continue
            # agnostic_nms: one label per object (a small bowl is otherwise also reported as a cup).
            r = model.predict(frame[y0:y1, x0:x1], conf=OBJECT_CONF, imgsz=640, agnostic_nms=True, verbose=False, device=self.device)[0]
            for b, c in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.cls.cpu().numpy()):
                box = (int(b[0]) + x0, int(b[1]) + y0, int(b[2]) + x0, int(b[3]) + y0)
                # Only what actually sits inside the zone (the crop is a rectangle around it).
                if point_in_zone((box[0] + box[2]) / 2 / width, (box[1] + box[3]) / 2 / height, zone):
                    found.append(TableObject(label=TABLEWARE[int(c)], box=box))
        return found


class FakeEngine:
    """Scripted results for tests and demos: one person in the middle of the frame; the configured
    checks are violated, the rest are worn. No GPU or model files needed."""

    name = "Fake engine (testing)"
    device = "none"

    def __init__(self, violations: list[str], person_box: list[float] | None = None, objects: list[list] | None = None):
        self.violations = set(violations)
        self.person_box = person_box  # normalised [x0, y0, x1, y1]; None = centre of the frame
        self.objects = objects or []  # [[label, x0, y0, x1, y1], ...] normalised

    def zone_probabilities(self, frame: np.ndarray, items: list[tuple[str, ZoneShape]]) -> list[float]:
        """Image zone rules listed in AICAM_FAKE_ZONE_HITS see their problem (read on every call, so
        a test can switch it on and off); all others see a clear zone."""
        from app.config import settings

        return [0.95 if key in settings.fake_zone_hits else 0.05 for key, _ in items]

    def detect_objects(self, frame: np.ndarray, zones: list[ZoneShape]) -> list[TableObject]:
        """The configured objects that lie inside the given zones (like the real engine)."""
        h, w = frame.shape[:2]
        return [
            TableObject(label=o[0], box=(int(o[1] * w), int(o[2] * h), int(o[3] * w), int(o[4] * h)))
            for o in self.objects
            if any(point_in_zone((o[1] + o[3]) / 2, (o[2] + o[4]) / 2, z) for z in zones)
        ]

    def analyze(self, frame: np.ndarray, checks: list[str], present_th: float, absent_th: float) -> Analysis:
        h, w = frame.shape[:2]
        if self.person_box:
            x0, y0, x1, y1 = self.person_box
            box = (int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h))
        else:
            box = (w // 4, h // 8, 3 * w // 4, h - 1)
        head = (3 * w // 8, h // 8, 5 * w // 8, h // 3)
        person = PersonResult(box=box, score=0.9, checks={})
        for check in checks:
            p = 0.05 if check in self.violations else 0.95
            person.checks[check] = CheckResult(state=state_from_probability(p, present_th, absent_th), p_present=p, regions=[head])
        return Analysis(width=w, height=h, persons=[person], inference_ms=1.0)
