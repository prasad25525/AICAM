"""Download the AI models VigilSiddhi uses into backend/models (they are too large for git).

    .venv\Scripts\python.exe scripts\download_models.py      (from the backend folder; install.bat runs it)

- yolo11n-pose.pt                  people and body keypoints (Ultralytics)
- siglip2-base-patch16-224         "is this item worn / is this floor clean?" image checks (Google, Hugging Face)
- yolov8s-worldv2.pt               finds tableware by name (Ultralytics YOLO-World)
- yolov8s-worldv2-tableware.pt     the same with the tableware names built in (made here once; needs CLIP)

About 2 GB. Files already present are skipped, so it is safe to run again.
"""

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.config import settings  # noqa: E402

ULTRA = settings.models_dir / "ultralytics"
SIGLIP = settings.models_dir / "hf" / "siglip2-base-patch16-224"
SIGLIP_REPO = "google/siglip2-base-patch16-224"


def yolo(name: str) -> Path:
    """Ultralytics downloads a known model name into the current folder."""
    from ultralytics import YOLO

    path = ULTRA / name
    if path.is_file():
        print(f"  have {name}")
        return path
    print(f"  downloading {name} ...")
    ULTRA.mkdir(parents=True, exist_ok=True)
    here = Path.cwd()
    os.chdir(ULTRA)
    try:
        YOLO(name)
    finally:
        os.chdir(here)
    if not path.is_file():
        sys.exit(f"Could not download {name}")
    return path


def siglip() -> None:
    if (SIGLIP / "model.safetensors").is_file():
        print("  have SigLIP 2")
        return
    from huggingface_hub import snapshot_download

    print(f"  downloading {SIGLIP_REPO} (about 1.5 GB) ...")
    snapshot_download(SIGLIP_REPO, local_dir=SIGLIP)


def tableware() -> None:
    from app.detection.engine import TABLEWARE, TABLEWARE_BAKED, TABLEWARE_WEIGHTS

    baked = ULTRA / TABLEWARE_BAKED
    if baked.is_file():
        print(f"  have {TABLEWARE_BAKED}")
        return
    from ultralytics import YOLO

    print(f"  building {TABLEWARE_BAKED} (downloads the CLIP text model once) ...")
    model = YOLO(str(yolo(TABLEWARE_WEIGHTS)))
    model.set_classes(TABLEWARE)
    model.save(str(baked))


if __name__ == "__main__":
    print(f"Models folder: {settings.models_dir}")
    yolo("yolo11n-pose.pt")
    siglip()
    yolo("yolov8s-worldv2.pt")
    tableware()
    print("All models ready.")
