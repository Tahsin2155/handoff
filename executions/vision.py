"""Screen capture and image encoding."""
import base64
import os
from io import BytesIO

import pyautogui


def screen_cap(intent: str | None = None) -> str:
    """Capture the primary display; return a raw base64 PNG string."""
    buf = BytesIO()
    pyautogui.screenshot().save(buf, format="PNG")
    if intent:
        print(f"Captured screenshot for intent: {intent}")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def get_img(path: str) -> str:
    """Load an image file from disk as a base64 string (for reproducible tests)."""
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Image path must be a non-empty string.")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Image file not found: {path}")
    if os.path.isdir(path):
        raise IsADirectoryError(f"Path is a directory, not an image file: {path}")
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")