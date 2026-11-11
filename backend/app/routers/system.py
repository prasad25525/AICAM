import torch
from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/info")
def info():
    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    models = {
        "ultralytics": sorted(p.name for p in (settings.models_dir / "ultralytics").glob("*.pt")),
        "huggingface": sorted(p.name for p in (settings.models_dir / "hf").iterdir() if p.is_dir()),
    }
    return {"torch": torch.__version__, "cuda": gpu is not None, "gpu": gpu, "models": models}
