"""Tool declarations sent to the model, plus the names the dispatcher matches on."""

RETURN_CONTROL = "return_control"

RETURN_CONTROL_TOOL = {
    "type": "function",
    "name": RETURN_CONTROL,
    "description": (
        "Hand control back to the human user. Use when the task is complete, "
        "when you need information or a decision only the human can give, or "
        "when you are stuck. Always write a STATUS line in your text output "
        "before calling this."
    ),
}

TOOLS = [
    {"type": "computer_use", "environment": "desktop"},
    RETURN_CONTROL_TOOL,
]