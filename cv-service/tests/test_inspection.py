from pathlib import Path

import cv2
import numpy as np
import pytest

from app.main import inspect


def test_inspects_synthetic_video() -> None:
    """Generate and clean up a tiny fixture instead of storing footage in Git."""
    path = Path(__file__).with_name("generated-inspection-test.mp4")
    try:
        writer = cv2.VideoWriter(
            str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (32, 24)
        )
        assert writer.isOpened()
        writer.write(np.zeros((24, 32, 3), dtype=np.uint8))
        writer.release()

        metadata = inspect(path)

        assert metadata["width"] == 32
        assert metadata["height"] == 24
        assert metadata["frame_count"] == 1
        assert metadata["fps"] == 10
    finally:
        path.unlink(missing_ok=True)


def test_rejects_invalid_video() -> None:
    path = Path(__file__).with_name("generated-invalid-inspection-test.mp4")
    try:
        path.write_bytes(b"not a video")
        with pytest.raises(ValueError):
            inspect(path)
    finally:
        path.unlink(missing_ok=True)
