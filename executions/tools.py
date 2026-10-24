"""Tools the model can call: the declarations sent to the API, plus the
handlers for tools Handoff implements itself (the computer_use actions are
handled in hands.py).

Also holds the per-turn limits for batched actions, because both the system
prompt (what we tell the model) and main.py (what we enforce) need them.
"""
import textwrap

from .dialogs import prompt_user_input
from .results import Outcome, Result

# ---- per-turn limits (batched function calls) -----------------------------
MAX_ACTIONS_PER_TURN = 6   # actions beyond this in one turn are not executed
ACTION_GAP_SECONDS = 1   # pause between actions of the same turn (UI needs a moment)

# ---- return_control -------------------------------------------------------
RETURN_CONTROL = "return_control"

STATUS_DONE = "done"
STATUS_NEED_INPUT = "need_input"
STATUS_STUCK = "stuck"
STATUSES = (STATUS_DONE, STATUS_NEED_INPUT, STATUS_STUCK)

RETURN_CONTROL_TOOL = {
    "type": "function",
    "name": RETURN_CONTROL,
    "description": (
        "Hand control back to the human user. Use when the task is complete, "
        "when you need information or a decision only the human can give, or "
        "when you are stuck. The message is shown to the user in a dialog, so "
        "write it for them. Call it alone, never together with other actions."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": list(STATUSES),
                "description": (
                    "done = the task is finished; need_input = you need "
                    "information or a decision from the user; stuck = you "
                    "cannot make progress."
                ),
            },
            "message": {
                "type": "string",
                "description": (
                    "1-3 sentences for the user: what finished, exactly what "
                    "you need from them, or what is blocking you."
                ),
            },
        },
        "required": ["status", "message"],
    },
}

# status -> (dialog title, heading above the message, line under the message)
_STATUS_UI = {
    STATUS_DONE: (
        "Handoff: Task Complete",
        "The agent says the task is complete:",
        "Enter a follow-up task (leave blank to finish):",
    ),
    STATUS_NEED_INPUT: (
        "Handoff: Input Needed",
        "The agent needs your input:",
        "Your reply (leave blank to end the run):",
    ),
    STATUS_STUCK: (
        "Handoff: Agent Stuck",
        "The agent is stuck:",
        "Tell it what to do next (leave blank to end the run):",
    ),
}


def return_control(status=STATUS_NEED_INPUT, message="", **_ignored):
    """Show the model's message to the user and ask what to do next.

    Returns RETURN_CONTROL with the user's reply as the message, or END_RUN
    when the user leaves the box blank / cancels.
    """
    title, heading, footer = _STATUS_UI.get(status, _STATUS_UI[STATUS_NEED_INPUT])
    message = (message or "").strip() or "(the agent gave no message)"
    print(f"[{RETURN_CONTROL}] status={status} | {message}")

    # simpledialog does not wrap long lines, so wrap the model's text ourselves.
    reply = prompt_user_input(
        f"{heading}\n\n{textwrap.fill(message, width=70)}\n\n{footer}",
        title=title,
    )
    reply = (reply or "").strip()
    if not reply:
        return Result(Outcome.END_RUN)
    return Result(Outcome.RETURN_CONTROL, f"The user replied: {reply}")


# Handlers for the tools above, keyed by tool name. main.py merges these into
# its dispatch table; each takes the model's arguments dict, returns a Result.
HANDLERS = {
    RETURN_CONTROL: lambda kwargs: return_control(**(kwargs or {})),
}

TOOLS = [
    {"type": "computer_use", "environment": "desktop"},
    RETURN_CONTROL_TOOL,
]
