"""
executions/__init__.py
=======================

Utilities for capturing and encoding images for the computer-use pipeline.

This module supplies the "eyes" side of the loop: it turns either a live
screenshot or an existing image file on disk into a base64 string suitable
for sending to a multimodal model (e.g. as an `"image"` content block in a
Gemini `interactions.create(...)` call).

Exposed functions:
    - screen_cap(): capture the current screen live.
    - get_img(path): load and encode an existing image file from disk.
"""

import base64, winsound, pyautogui, os
from time import sleep
from io import BytesIO



__all__ = ["screen_cap", "get_img"]


def screen_cap(intent=None) -> str:
    """
    Capture the current screen and encode it as a base64 PNG string.

    Uses `pyautogui.screenshot()` to grab the entire primary display,
    writes it to an in-memory buffer as PNG (avoiding a temp file on
    disk), and base64-encodes the result so it can be embedded directly
    in a model API request.

    Returns:
        str: Base64-encoded PNG image of the current screen, as a UTF-8
        string (no data-URI prefix — just the raw base64 payload).

    Example:
        >>> img_b64 = screen_cap()
        >>> len(img_b64) > 0
        True
    """
    buf = BytesIO()
    pyautogui.screenshot().save(buf, format="PNG")
    if intent: print(f"Captured screenshot for intent: {intent}")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def get_img(path: str) -> str:
    """
    Read an image file from disk and encode it as a base64 string.

    Used when you want to feed a pre-existing screenshot (e.g. `ss.png`)
    to the model instead of capturing a fresh one — useful for
    reproducible testing/development against a fixed image.

    Args:
        path (str): Filesystem path to the image file.

    Returns:
        str: Base64-encoded contents of the file, as a UTF-8 string.

    Raises:
        ValueError: If `path` is not a string, or is empty/whitespace.
        FileNotFoundError: If no file exists at `path`.
        IsADirectoryError: If `path` points to a directory rather than a
            file.

    Note:
        This function does not validate that the file is actually a valid
        image (e.g. it will happily "succeed" on a `.txt` file) — it only
        checks that the path exists and is a file. Validate the
        `mime_type` you pass alongside this separately.
    """
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Image path must be a non-empty string.")

    if not os.path.exists(path):
        raise FileNotFoundError(f"Image file not found: {path}")

    if os.path.isdir(path):
        raise IsADirectoryError(f"Path is a directory, not an image file: {path}")

    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")



# ============================================================================
# AUDIBLE FEEDBACK: IDENTIFIABLE BEEP PATTERNS
# ============================================================================
def beep_alert_error():
    """
    Alert user of an ERROR condition.
    Pattern: One long, low-frequency beep (500 ms at 400 Hz).
    Recognizable as a serious issue.
    """
    winsound.Beep(400, 500)


def beep_iteration_complete():
    """
    Indicate one automation iteration has completed.
    Pattern: Single medium-frequency beep (500 ms at 1200 Hz).
    Recognizable as a standard loop completion.
    """
    winsound.Beep(1200, 500)


def beep_task_end_or_next():
    """
    Model has requested to end the interaction or move to the next task.
    Pattern: Three short, high-frequency beeps (150 ms each at 1800 Hz, 200 ms pause between).
    Recognizable as a milestone or transition signal.
    """
    winsound.Beep(1800, 150)
    sleep(0.2)
    winsound.Beep(1800, 150)
    sleep(0.2)
    winsound.Beep(1800, 150)


def beep_require_confirmation():
    """
    Safety gate: USER CONFIRMATION REQUIRED before proceeding.
    Pattern: Two medium-high beeps (300 ms each at 2500 Hz, 300 ms pause between).
    Recognizable as a "wait, I need your input" signal.
    User should press Shift to approve or Ctrl to deny.
    """
    winsound.Beep(2500, 300)
    sleep(0.3)
    winsound.Beep(2500, 300)


def beep_action_blocked():
    """
    Safety gate: ACTION BLOCKED by model or safety system.
    Pattern: Three low-frequency, slow beats (200 ms each at 500 Hz, 300 ms pause between).
    Recognizable as a "don't do this" warning.
    """
    winsound.Beep(500, 200)
    sleep(0.3)
    winsound.Beep(500, 200)
    sleep(0.3)
    winsound.Beep(500, 200)