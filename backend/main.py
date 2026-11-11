"""Start the AICAM backend: python main.py"""

from pathlib import Path

import uvicorn

from app.config import settings

BACKEND_DIR = Path(__file__).resolve().parent

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        app_dir=str(BACKEND_DIR),
        reload_dirs=[str(BACKEND_DIR / "app")],
        timeout_graceful_shutdown=3,  # open live streams never finish on their own; don't block reloads
    )
