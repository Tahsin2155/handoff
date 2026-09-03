"""
executions/hands.py
=======================

Automation execution module for computer-use tasks.

This module is the "hands" of the computer-use agent: it takes the
normalized (x, y) coordinates and function-call arguments returned by a
computer-use model (e.g. Gemini's `computer_use` tool) and turns them into
real mouse actions on the local machine via `pyautogui`.

It also implements a **safety gate**: before certain actions run, the model
may attach a `safety_decision` describing whether the action needs explicit
user confirmation or should be blocked outright. This module is responsible
for enforcing that gate before touching the mouse.

Dependencies:
    - pyautogui: cross-platform mouse/keyboard automation
    - keyboard:  low-level global key press detection (used for the
                 confirm/block gate)
    - winsound:  Windows-only audible beep, used to alert the user that
                 input is required (NOTE: this ties the module to Windows;
                 see "Portability" below)

Portability:
    `winsound` is part of the Python standard library but is Windows-only.
    Running this module on macOS/Linux will raise an ImportError. If you
    need cross-platform beeps, swap in a package like `playsound` or
    `simpleaudio`, or guard the import with a try/except per-OS branch.
"""

import pyautogui, keyboard, winsound
from time import sleep
from . import beep_action_blocked, beep_require_confirmation

# Screen dimensions, fetched once at import time. Used to convert the
# model's normalized 0-999 coordinate space into actual pixel coordinates
# for this specific screen.
WIDTH, HEIGHT = pyautogui.size()



def denormalize_coordinates(x, y):
    """
    Convert normalized coordinates (0-999) to actual screen coordinates.

    Computer-use models typically describe click targets in a
    resolution-independent 0-999 range rather than raw pixels, so that the
    same model output works regardless of the actual screen size. This
    function maps that back to real pixel coordinates for `pyautogui`.

    Args:
        x (int | float): Normalized x coordinate, expected in [0, 999].
        y (int | float): Normalized y coordinate, expected in [0, 999].

    Returns:
        tuple[float, float]: Actual (x, y) screen coordinates in pixels,
        scaled to the current display's WIDTH and HEIGHT.

    Note:
        No bounds-checking is performed here — a value outside [0, 999]
        will silently produce a coordinate outside the visible screen.
    """
    return x / 999 * WIDTH, y / 999 * HEIGHT


def needs_gate(safety_decision):
    """
    Enforce a safety gate before an automation action is allowed to run.

    Every risky action (click, double-click, etc.) can carry a
    `safety_decision` payload from the model explaining whether it's safe
    to proceed automatically, needs human confirmation, or must be blocked.
    This function is the single choke point that interprets that payload.

    Behavior by `decision` value:
        - "require_confirmation":
            Emits identifiable beep pattern to get user's attention,
            then blocks execution in a polling loop until the user presses:
                * Shift -> approve the action (returns False, i.e. "don't block")
                * Ctrl  -> deny the action (returns True, i.e. "block it")
        - "blocked":
            The model itself has decided the action is unsafe. Emits
            identifiable beep pattern as an audible signal, then blocks
            the action unconditionally (returns True). No user input read.
        - anything else (e.g. "allow" or missing key):
            No gate is applied; the action is allowed to proceed
            (returns False).

    Args:
        safety_decision (dict): Expected shape:
            {
                "decision": "require_confirmation" | "blocked" | <other>,
                "explanation": str  # optional, human-readable reason
            }

    Returns:
        bool: True if the calling action should be **blocked** (not
        executed), False if it is cleared to run.

    Caveats:
        - The `keyboard` module's `is_pressed` polling loop here polls
          every 0.1 seconds to avoid pegging the CPU while waiting.
        - `keyboard.is_pressed` on some platforms requires elevated
          privileges (e.g. root on Linux) to read global key state.
    """
    decision = safety_decision.get("decision")
    explanation = safety_decision.get("explanation", "No explanation provided")
    print(f"[Safety] {explanation}")

    if decision == "require_confirmation":
        beep_require_confirmation()  # Two medium-high beeps pattern
        print("[Safety] Confirmation required. Press Shift to approve or Ctrl to deny.")
        while True:
            if keyboard.is_pressed('shift'):
                sleep(0.2)
                print("[Safety] Approved by user.")
                return False
            if keyboard.is_pressed('ctrl'):
                sleep(0.2)
                print("[Safety] Denied by user.")
                return "Denied by user."
            sleep(0.1)  # Avoid CPU pegging while polling
    elif decision == "blocked":
        beep_action_blocked()  # Three low-frequency slow beats pattern
        print(f"[Safety] Blocked: {explanation}")
        return f"Blocked: {explanation}"

    return False


def click(x, y, intent, safety_decision=None):
    """
    Perform a single mouse click at normalized coordinates, optionally
    gated by a safety decision.

    Typical caller: the loop in the notebook that walks
    `interaction.steps` and dispatches `function_call` steps named
    "click" by unpacking the model's arguments directly into this
    function (`exe_func.click(**step.arguments)`).

    Args:
        x (int | float): Normalized x coordinate (0-999), converted to a
            real screen pixel via `denormalize_coordinates`.
        y (int | float): Normalized y coordinate (0-999), converted to a
            real screen pixel via `denormalize_coordinates`.
        intent (str): Human-readable description of *why* this click is
            happening (e.g. "close the rate limit tab"). Used only for
            logging here, but useful for audit trails of what the agent
            did and why.
        safety_decision (dict, optional): If provided, passed to
            `needs_gate()` before the click executes. If the gate returns
            True (blocked/denied), the click is skipped entirely and the
            function returns without raising.

    Returns:
        None
    """
    if safety_decision and (decision := needs_gate(safety_decision)):
        return decision  # Exit if action is blocked or confirmation denied

    x, y = denormalize_coordinates(x, y)
    pyautogui.click(x, y)
    print(f"[click] intent={intent} | pos=({x:.2f}, {y:.2f})")



def double_click(x, y, intent, safety_decision=None):
    """
    Perform a double-click at normalized coordinates, optionally gated by
    a safety decision.

    Mirrors `click()` above but issues a double-click via
    `pyautogui.doubleClick`. See `click()` docstring for the meaning of
    each argument and the gating behavior.

    Args:
        x (int | float): Normalized x coordinate (0-999).
        y (int | float): Normalized y coordinate (0-999).
        intent (str): Human-readable description of the action's purpose,
            used for logging.
        safety_decision (dict, optional): Passed to `needs_gate()`; if the
            action is blocked or denied, the double-click is skipped.

    Returns:
        None
    """
    if safety_decision and (decision := needs_gate(safety_decision)):
        return decision  # Exit if action is blocked or confirmation denied

    x, y = denormalize_coordinates(x, y)
    pyautogui.doubleClick(x, y)
    print(f"[double_click] intent={intent} | pos=({x:.2f}, {y:.2f})")



def triple_click(x, y, intent, safety_decision=None):
    """
    Perform a triple-click at normalized coordinates, optionally gated by
    a safety decision.

    Mirrors `click()` above but issues a triple-click via
    `pyautogui.click` with `clicks=3`. See `click()` docstring for the
    meaning of each argument and the gating behavior.

    Args:
        x (int | float): Normalized x coordinate (0-999).
        y (int | float): Normalized y coordinate (0-999).
        intent (str): Human-readable description of the action's purpose,
            used for logging.
        safety_decision (dict, optional): Passed to `needs_gate()`; if the
            action is blocked or denied, the triple-click is skipped.
    """
    if safety_decision and (decision := needs_gate(safety_decision)):
        return decision  # Exit if action is blocked or confirmation denied

    x, y = denormalize_coordinates(x, y)
    pyautogui.click(x, y, clicks=3)
    print(f"[triple_click] intent={intent} | pos=({x:.2f}, {y:.2f})")



def middle_click(x, y, intent, safety_decision=None):
    """
    Perform a middle-click at normalized coordinates, optionally gated by
    a safety decision.

    Mirrors `click()` above but issues a middle-click via
    `pyautogui.middleClick`. See `click()` docstring for the meaning of
    each argument and the gating behavior.

    Args:
        x (int | float): Normalized x coordinate (0-999).
        y (int | float): Normalized y coordinate (0-999).
        intent (str): Human-readable description of the action's purpose,
            used for logging.
        safety_decision (dict, optional): Passed to `needs_gate()`; if the
            action is blocked or denied, the middle-click is skipped.
    """
    if safety_decision and (decision := needs_gate(safety_decision)):
        return decision  # Exit if action is blocked or confirmation denied

    x, y = denormalize_coordinates(x, y)
    pyautogui.middleClick(x, y)
    print(f"[middle_click] intent={intent} | pos=({x:.2f}, {y:.2f})")



def right_click(x, y, intent, safety_decision=None):
    """
    Perform a right-click at normalized coordinates, optionally gated by
    a safety decision.

    Mirrors `click()` above but issues a right-click via
    `pyautogui.rightClick`. See `click()` docstring for the meaning of
    each argument and the gating behavior.

    Args:
        x (int | float): Normalized x coordinate (0-999).
        y (int | float): Normalized y coordinate (0-999).
        intent (str): Human-readable description of the action's purpose,
            used for logging.
        safety_decision (dict, optional): Passed to `needs_gate()`; if the
            action is blocked or denied, the right-click is skipped.
    """
    if safety_decision and (decision := needs_gate(safety_decision)):
        return decision  # Exit if action is blocked or confirmation denied

    x, y = denormalize_coordinates(x, y)
    pyautogui.rightClick(x, y)
    print(f"[right_click] intent={intent} | pos=({x:.2f}, {y:.2f})")



def mouse_down(x, y, intent, safety_decision=None):
    """
    Perform a mouse button press (mouse down) at normalized coordinates,
    optionally gated by a safety decision.

    Mirrors `click()` above but issues a mouse button press via
    `pyautogui.mouseDown`. See `click()` docstring for the meaning of each
    argument and the gating behavior.

    Args:
        x (int | float): Normalized x coordinate (0-999).
        y (int | float): Normalized y coordinate (0-999).
        intent (str): Human-readable description of the action's purpose,
            used for logging.
        safety_decision (dict, optional): Passed to `needs_gate()`; if the
            action is blocked or denied, the mouse down is skipped.
    """
    if safety_decision and (decision := needs_gate(safety_decision)):
        return decision  # Exit if action is blocked or confirmation denied

    x, y = denormalize_coordinates(x, y)
    pyautogui.mouseDown(x, y)
    print(f"[mouse_down] intent={intent} | pos=({x:.2f}, {y:.2f})")



def mouse_up(x, y, intent, safety_decision=None):
    """
    Perform a mouse button release (mouse up) at normalized coordinates,
    optionally gated by a safety decision.

    Mirrors `click()` above but issues a mouse button release via
    `pyautogui.mouseUp`. See `click()` docstring for the meaning of each
    argument and the gating behavior.

    Args:
        x (int | float): Normalized x coordinate (0-999).
        y (int | float): Normalized y coordinate (0-999).
        intent (str): Human-readable description of the action's purpose,
            used for logging.
        safety_decision (dict, optional): Passed to `needs_gate()`; if the
            action is blocked or denied, the mouse up is skipped.
    """
    if safety_decision and (decision := needs_gate(safety_decision)):
        return decision  # Exit if action is blocked or confirmation denied

    x, y = denormalize_coordinates(x, y)
    pyautogui.mouseUp(x, y)
    print(f"[mouse_up] intent={intent} | pos=({x:.2f}, {y:.2f})")



def move(x, y, intent, safety_decision=None):
    """
    Move the mouse cursor to normalized coordinates, optionally gated by a
    safety decision.

    Mirrors `click()` above but issues a mouse move via
    `pyautogui.moveTo`. See `click()` docstring for the meaning of each
    argument and the gating behavior.

    Args:
        x (int | float): Normalized x coordinate (0-999).
        y (int | float): Normalized y coordinate (0-999).
        intent (str): Human-readable description of the action's purpose,
            used for logging.
        safety_decision (dict, optional): Passed to `needs_gate()`; if the
            action is blocked or denied, the mouse move is skipped.
    """
    if safety_decision and (decision := needs_gate(safety_decision)):
        return decision  # Exit if action is blocked or confirmation denied

    x, y = denormalize_coordinates(x, y)
    pyautogui.moveTo(x, y)
    print(f"[move] intent={intent} | pos=({x:.2f}, {y:.2f})")



def type(text, intent, press_enter=False, safety_decision=None):
    """
    Type a string of text at the current cursor location, optionally gated
    by a safety decision.

    Mirrors `click()` above but issues keyboard input via
    `pyautogui.typewrite`. See `click()` docstring for the meaning of each
    argument and the gating behavior.

    Args:
        text (str): The string of text to type.
        intent (str): Human-readable description of the action's purpose,
            used for logging.
        press_enter (bool): If True, press the Enter key after typing the text.
        safety_decision (dict, optional): Passed to `needs_gate()`; if the
            action is blocked or denied, the text typing is skipped.
    """
    if safety_decision and (decision := needs_gate(safety_decision)):
        return decision  # Exit if action is blocked or confirmation denied

    pyautogui.typewrite(text)
    if press_enter:
        pyautogui.press("enter")
    print(f"[type] intent={intent} | text={text!r}")



def drag_and_drop(start_x, start_y, end_x, end_y, intent, safety_decision=None):
    """
    Perform a drag-and-drop operation from normalized start coordinates to
    normalized end coordinates, optionally gated by a safety decision.

    Mirrors `click()` above but issues a drag-and-drop via
    `pyautogui.dragTo`. See `click()` docstring for the meaning of each
    argument and the gating behavior.

    Args:
        start_x (int | float): Normalized starting x coordinate (0-999).
        start_y (int | float): Normalized starting y coordinate (0-999).
        end_x (int | float): Normalized ending x coordinate (0-999).
        end_y (int | float): Normalized ending y coordinate (0-999).
        intent (str): Human-readable description of the action's purpose,
            used for logging.
        safety_decision (dict, optional): Passed to `needs_gate()`; if the
            action is blocked or denied, the drag-and-drop is skipped.
    """
    if safety_decision and (decision := needs_gate(safety_decision)):
        return decision  # Exit if action is blocked or confirmation denied

    start_x, start_y = denormalize_coordinates(start_x, start_y)
    end_x, end_y = denormalize_coordinates(end_x, end_y)
    pyautogui.moveTo(start_x, start_y)
    pyautogui.dragTo(end_x, end_y, duration=0.5)
    print(f"[drag_and_drop] intent={intent} | from=({start_x:.2f}, {start_y:.2f}) -> ({end_x:.2f}, {end_y:.2f})")



def wait(intent, seconds=1, safety_decision=None):
    """
    Wait for a specified number of seconds, optionally gated by a safety decision.

    Args:
        seconds (float): The number of seconds to wait, default is 1.
        intent (str): Human-readable description of the action's purpose,
            used for logging.
        safety_decision (dict, optional): Passed to `needs_gate()`; if the
            action is blocked or denied, the wait is skipped.
    """
    if safety_decision and (decision := needs_gate(safety_decision)):
        return decision  # Exit if action is blocked or confirmation denied

    print(f"[wait] intent={intent} | seconds={seconds}")
    sleep(seconds)



def press_key(key, intent, safety_decision=None):
    """
    Press a single key on the keyboard, optionally gated by a safety decision.

    Args:
        key (str): The key to press (e.g., 'enter', 'a', 'ctrl').
        intent (str): Human-readable description of the action's purpose,
            used for logging.
        safety_decision (dict, optional): Passed to `needs_gate()`; if the
            action is blocked or denied, the key press is skipped.
    """
    if safety_decision and (decision := needs_gate(safety_decision)):
        return decision  # Exit if action is blocked or confirmation denied

    pyautogui.press(key)
    print(f"[press_key] intent={intent} | key={key}")



def key_down(key, intent, safety_decision=None):
    """
    Press and hold a key on the keyboard, optionally gated by a safety decision.

    Args:
        key (str): The key to press and hold (e.g., 'shift', 'ctrl').
        intent (str): Human-readable description of the action's purpose,
            used for logging.
        safety_decision (dict, optional): Passed to `needs_gate()`; if the
            action is blocked or denied, the key down is skipped.
    """
    if safety_decision and (decision := needs_gate(safety_decision)):
        return decision  # Exit if action is blocked or confirmation denied

    pyautogui.keyDown(key)
    print(f"[key_down] intent={intent} | key={key}")



def key_up(key, intent, safety_decision=None):
    """
    Release a previously pressed key on the keyboard, optionally gated by a safety decision.

    Args:
        key (str): The key to release (e.g., 'shift', 'ctrl').
        intent (str): Human-readable description of the action's purpose,
            used for logging.
        safety_decision (dict, optional): Passed to `needs_gate()`; if the
            action is blocked or denied, the key up is skipped.
    """
    if safety_decision and (decision := needs_gate(safety_decision)):
        return decision  # Exit if action is blocked or confirmation denied

    pyautogui.keyUp(key)
    print(f"[key_up] intent={intent} | key={key}")



def hotkey(keys, intent, safety_decision=None):
    """
    Press a combination of keys simultaneously (hotkey), optionally gated by a safety decision.

    Args:
        keys (list[str]): A list of keys to press together (e.g., ['ctrl', 'c']).
        intent (str): Human-readable description of the action's purpose,
            used for logging.
        safety_decision (dict, optional): Passed to `needs_gate()`; if the
            action is blocked or denied, the hotkey press is skipped.
    """
    if safety_decision and (decision := needs_gate(safety_decision)):
        return decision  # Exit if action is blocked or confirmation denied

    pyautogui.hotkey(*keys)
    print(f"[hotkey] intent={intent} | keys={keys}")


def scroll(x, y, direction, intent, magnitude_in_wheel_clicks=3, safety_decision=None):
    """
    Scroll the mouse wheel by a specified amount, optionally gated by a safety decision.

    Args:
        x (int | float): Normalized x coordinate (0-999) where the scroll should occur.
        y (int | float): Normalized y coordinate (0-999) where the scroll should occur.
        direction (str): Direction of the scroll, 'up', 'down', 'left', or 'right'.
        intent (str): Human-readable description of the action's purpose,
            used for logging.
        magnitude_in_wheel_clicks (int): The magnitude of the scroll in wheel clicks. Default is 300.
        safety_decision (dict, optional): Passed to `needs_gate()`; if the
            action is blocked or denied, the scroll is skipped.
    """
    if safety_decision and (decision := needs_gate(safety_decision)):
        return decision  # Exit if action is blocked or confirmation denied

    x, y = denormalize_coordinates(x, y)
    pyautogui.moveTo(x, y)

    if direction == 'up':
        pyautogui.scroll(magnitude_in_wheel_clicks*100)
    elif direction == 'down':
        pyautogui.scroll(-magnitude_in_wheel_clicks*100)
    elif direction == 'left':
        pyautogui.hscroll(-magnitude_in_wheel_clicks*100)
    elif direction == 'right':
        pyautogui.hscroll(magnitude_in_wheel_clicks*100)
    else:
        raise ValueError("Direction must be 'up', 'down', 'left', or 'right'.")

    print(f"[scroll] intent={intent} | direction={direction} | pos=({x:.2f}, {y:.2f}) | magnitude={magnitude_in_wheel_clicks*100}")

