"""
Execution layer ("hands"): turns the model's normalized (0-999) coordinates and
function-call args into real mouse/keyboard actions via pyautogui.

Every action goes through @gated and returns a `Result` (see results.py).
If the model attached a `safety_decision`, the gate runs first; a blocked or
denied action returns a DENIED/BLOCKED result instead of executing. An action
that ran returns OK.
"""
from functools import wraps
from time import sleep

import pyautogui

from .dialogs import prompt_user_confirmation, warning_message_box
from .results import OK, Outcome, Result

WIDTH, HEIGHT = pyautogui.size()
_NORM_MAX = 999


def denormalize_coordinates(x, y):
    """Map the model's 0-999 space to real pixels. No bounds checking."""
    return x / _NORM_MAX * WIDTH, y / _NORM_MAX * HEIGHT


def needs_gate(safety_decision: dict) -> Result | None:
    """Return a DENIED/BLOCKED Result if the action must NOT run, else None."""
    decision = safety_decision.get("decision")
    explanation = safety_decision.get("explanation", "No explanation provided")
    print(f"[Safety] {explanation}")

    if decision == "require_confirmation":
        approved = prompt_user_confirmation(
            f"{explanation}\n\nAllow the agent to proceed with this action?",
            title="Handoff: Confirmation Required",  # blocks, no timeout
        )
        if approved:
            print("[Safety] Approved by user.")
            return None
        print("[Safety] Denied by user.")
        return Result(Outcome.DENIED, "Denied by user.")

    if decision == "blocked":
        print(f"[Safety] Blocked: {explanation}")
        warning_message_box(explanation, title="Handoff: Action Blocked")
        return Result(Outcome.BLOCKED, f"Blocked: {explanation}")

    return None


def gated(action):
    """Run the safety gate before `action`; skip the action if it says no.

    The wrapped function returns a Result: the gate's DENIED/BLOCKED result, or
    OK once the action has run.
    """
    @wraps(action)
    def wrapper(*args, safety_decision=None, **kwargs):
        if safety_decision and (refusal := needs_gate(safety_decision)):
            return refusal
        action(*args, **kwargs)
        return OK
    return wrapper


def _log(name, intent, **details):
    extra = " | ".join(f"{k}={v}" for k, v in details.items())
    print(f"[{name}] intent={intent}" + (f" | {extra}" if extra else ""))


def _px(x, y):
    px, py = denormalize_coordinates(x, y)
    return px, py, f"({px:.2f}, {py:.2f})"


# ---- mouse ---------------------------------------------------------------
@gated
def click(x, y, intent):
    px, py, pos = _px(x, y)
    pyautogui.click(px, py)
    _log("click", intent, pos=pos)


@gated
def double_click(x, y, intent):
    px, py, pos = _px(x, y)
    pyautogui.doubleClick(px, py)
    _log("double_click", intent, pos=pos)


@gated
def triple_click(x, y, intent):
    px, py, pos = _px(x, y)
    pyautogui.click(px, py, clicks=3)
    _log("triple_click", intent, pos=pos)


@gated
def middle_click(x, y, intent):
    px, py, pos = _px(x, y)
    pyautogui.middleClick(px, py)
    _log("middle_click", intent, pos=pos)


@gated
def right_click(x, y, intent):
    px, py, pos = _px(x, y)
    pyautogui.rightClick(px, py)
    _log("right_click", intent, pos=pos)


@gated
def mouse_down(x, y, intent):
    px, py, pos = _px(x, y)
    pyautogui.mouseDown(px, py)
    _log("mouse_down", intent, pos=pos)


@gated
def mouse_up(x, y, intent):
    px, py, pos = _px(x, y)
    pyautogui.mouseUp(px, py)
    _log("mouse_up", intent, pos=pos)


@gated
def move(x, y, intent):
    px, py, pos = _px(x, y)
    pyautogui.moveTo(px, py)
    _log("move", intent, pos=pos)


@gated
def drag_and_drop(start_x, start_y, end_x, end_y, intent):
    sx, sy, spos = _px(start_x, start_y)
    ex, ey, epos = _px(end_x, end_y)
    pyautogui.moveTo(sx, sy)
    pyautogui.dragTo(ex, ey, duration=0.5)
    _log("drag_and_drop", intent, path=f"{spos} -> {epos}")


_SCROLL_UNIT = 100


@gated
def scroll(x, y, direction, intent, magnitude_in_wheel_clicks=3):
    px, py, pos = _px(x, y)
    pyautogui.moveTo(px, py)
    amount = magnitude_in_wheel_clicks * _SCROLL_UNIT
    actions = {
        "up": lambda: pyautogui.scroll(amount),
        "down": lambda: pyautogui.scroll(-amount),
        "left": lambda: pyautogui.hscroll(-amount),
        "right": lambda: pyautogui.hscroll(amount),
    }
    if direction not in actions:
        raise ValueError("Direction must be 'up', 'down', 'left', or 'right'.")
    actions[direction]()
    _log("scroll", intent, direction=direction, pos=pos, magnitude=amount)


# ---- keyboard ------------------------------------------------------------
@gated
def types(text, intent, press_enter=False):
    pyautogui.typewrite(text)  # ASCII only
    if press_enter:
        pyautogui.press("enter")
    _log("type", intent, text=repr(text))


@gated
def press_key(key, intent):
    pyautogui.press(key)
    _log("press_key", intent, key=key)


@gated
def key_down(key, intent):
    pyautogui.keyDown(key)
    _log("key_down", intent, key=key)


@gated
def key_up(key, intent):
    pyautogui.keyUp(key)
    _log("key_up", intent, key=key)


@gated
def hotkey(keys, intent):
    pyautogui.hotkey(*keys)
    _log("hotkey", intent, keys=keys)


# ---- misc ----------------------------------------------------------------
@gated
def wait(intent, seconds=1):
    _log("wait", intent, seconds=seconds)
    sleep(seconds)