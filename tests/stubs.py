"""Shared test setup. Import this module BEFORE importing `main` or `executions`.

It replaces pyautogui, the Tk dialogs, google-genai, dotenv and your local
config.py with harmless fakes, so the tests need no display, network or API
key and can never move your mouse or open a window. The replacements are
forced (not setdefault) on purpose: a real pyautogui must never be used here.
"""
import sys
import types
import unittest
from types import SimpleNamespace
from unittest import mock

actions = []  # every fake pyautogui call lands here as (name, args, kwargs)

_pyautogui = types.ModuleType("pyautogui")
_pyautogui.size = lambda: (1000, 1000)
_pyautogui.screenshot = lambda: (_ for _ in ()).throw(AssertionError("screenshot not expected"))
for _name in ("click", "doubleClick", "middleClick", "rightClick", "mouseDown", "mouseUp",
              "moveTo", "dragTo", "scroll", "hscroll", "typewrite", "press",
              "keyDown", "keyUp", "hotkey"):
    setattr(_pyautogui, _name, lambda *a, _n=_name, **k: actions.append((_n, a, k)))
sys.modules["pyautogui"] = _pyautogui

fake_dialogs = types.ModuleType("executions.dialogs")
fake_dialogs.confirm_answer = True   # what the user "clicks" in Yes/No dialogs
fake_dialogs.input_answer = None     # what the user "types" in text prompts (a list = one answer per prompt)
fake_dialogs.shown = []              # (kind, message) for every dialog shown
fake_dialogs.prompt_user_confirmation = lambda prompt, title="": (
    fake_dialogs.shown.append(("confirm", prompt)) or fake_dialogs.confirm_answer)


def _next_input(prompt, title=""):
    fake_dialogs.shown.append(("input", prompt))
    answer = fake_dialogs.input_answer
    if isinstance(answer, list):
        return answer.pop(0) if answer else None
    return answer


fake_dialogs.prompt_user_input = _next_input
fake_dialogs.warning_message_box = lambda message, title="": fake_dialogs.shown.append(("warning", message))
fake_dialogs.error_message_box = lambda message, title="": fake_dialogs.shown.append(("error", message))
fake_dialogs.bell = lambda: None
sys.modules["executions.dialogs"] = fake_dialogs

_genai = types.ModuleType("google.genai")
_google = types.ModuleType("google")
_google.genai = _genai
sys.modules["google"] = _google
sys.modules["google.genai"] = _genai

_dotenv = types.ModuleType("dotenv")
_dotenv.load_dotenv = lambda *a, **k: None
sys.modules["dotenv"] = _dotenv

_config = types.ModuleType("config")  # your real config.py is not needed (or read)
_config.MODEL = "test-model"
_config.THINKING_LVL = "low"
_config.PREVIOUS_INTERACTION_ID = None
sys.modules["config"] = _config


# ---- helpers for building fake model steps ---------------------------------
def call(name, **arguments):
    return SimpleNamespace(type="function_call", name=name, arguments=arguments)


def click(**extra):
    return call("click", x=500, y=500, intent="test", **extra)


def return_control(status="done", message="All finished."):
    return call("return_control", status=status, message=message)


def require_confirmation():
    return {"decision": "require_confirmation", "explanation": "Risky click"}


def blocked():
    return {"decision": "blocked", "explanation": "Not allowed"}


class Base(unittest.TestCase):
    """Resets the fakes before each test and records main.sleep() calls."""

    def setUp(self):
        import main  # imported lazily so the stubs above are always installed first
        actions.clear()
        fake_dialogs.shown.clear()
        fake_dialogs.confirm_answer = True
        fake_dialogs.input_answer = None
        self.sleeps = []
        patcher = mock.patch.object(main, "sleep", lambda seconds: self.sleeps.append(seconds))
        patcher.start()
        self.addCleanup(patcher.stop)
