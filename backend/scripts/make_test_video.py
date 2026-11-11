"""Generate a short test-pattern video to use as a camera source without real hardware.

Usage: python scripts/make_test_video.py [output.mp4]   (default: data/test_pattern.mp4)
"""

import sys
from pathlib import Path

import cv2
import numpy as np

WIDTH, HEIGHT, FPS, SECONDS = 640, 360, 10, 3


def make_test_video(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))
    if not writer.isOpened():
        raise RuntimeError(f"Could not create {path}")
    bar_colors = [(255, 255, 255), (0, 255, 255), (255, 255, 0), (0, 255, 0), (255, 0, 255), (0, 0, 255), (255, 0, 0)]
    bar_w = WIDTH // len(bar_colors)
    for i in range(FPS * SECONDS):
        frame = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
        for b, color in enumerate(bar_colors):
            frame[:, b * bar_w : (b + 1) * bar_w] = color
        cv2.rectangle(frame, (0, HEIGHT - 70), (WIDTH, HEIGHT), (18, 29, 10), -1)
        cv2.putText(frame, f"AICAM TEST  frame {i:03d}", (20, HEIGHT - 25), cv2.FONT_HERSHEY_SIMPLEX, 1, (61, 242, 181), 2)
        writer.write(frame)
    writer.release()
    return path


if __name__ == "__main__":
    default = Path(__file__).resolve().parent.parent / "data" / "test_pattern.mp4"
    out = make_test_video(Path(sys.argv[1]) if len(sys.argv) > 1 else default)
    print(out)
