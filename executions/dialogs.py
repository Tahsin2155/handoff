"""Tk dialogs for user input, confirmation, and notifications."""
from tkinter import Tk, simpledialog, messagebox

_root = Tk()
_root.withdraw()
_root.attributes("-topmost", True)  # keep dialogs above the app being controlled


def prompt_user_input(prompt: str, title: str = "Input Required") -> str | None:
    return simpledialog.askstring(title, prompt, parent=_root)


def prompt_user_confirmation(prompt: str, title: str = "Confirmation Required") -> bool:
    return messagebox.askyesno(title, prompt, parent=_root)


def error_message_box(message: str, title: str = "Error") -> None:
    messagebox.showerror(title, message, parent=_root)


def warning_message_box(message: str, title: str = "Warning") -> None:
    messagebox.showwarning(title, message, parent=_root)


def bell() -> None:
    _root.bell()