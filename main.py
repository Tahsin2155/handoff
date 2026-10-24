"""Gemini Computer-Use Agent: Main orchestration module.

This module coordinates the Gemini API client with the computer-use tool,
managing the interaction loop, function dispatch, and screenshot capture
for desktop automation tasks.
"""

import json
import os
from datetime import datetime
from time import sleep

from dotenv import load_dotenv

from google import genai
from executions import hands, sys_instructions, screen_cap, prompt_user_input, error_message_box, bell
from executions.results import OK, Outcome, Result
from executions.tools import ACTION_GAP_SECONDS, HANDLERS, MAX_ACTIONS_PER_TURN, TOOLS

# ============================================================================
# CONFIGURATION: API Key & Client Setup
# ============================================================================
# Initialized by main() before the command-line workflow starts.
client = None

from config import MODEL, THINKING_LVL, PREVIOUS_INTERACTION_ID


# ============================================================================
# INPUT BLOCK CONSTRUCTION
# ============================================================================
def input_blocks(text=None, image=False) -> list:
    """Build a list of input content blocks for the Gemini API.
    
    Each block represents a piece of input data: text instruction, screenshot,
    or result from a previous function call. The model uses these to make
    decisions about which automation action to take next.
    
    Args:
        text (str, optional): Text instruction or prompt for the model.
        image (bool, optional): If True, capture current screen and include as image.
        function_result (dict, optional): Result from a previous function execution.
    
    Returns:
        list: List of content blocks ready to send to Gemini API.
    """
    input_block = []
    if text:
        input_block.append(
            {
                "type": "text",
                "text": text
            }
        )
    if image:
        input_block.append(
            {
                "type": "image",
                "data": screen_cap(),  # Capture live screenshot
                "mime_type": "image/png"
            }
        )
    return input_block

# ============================================================================
# INTERACTION STATE & API CALLS
# ============================================================================
# Tracks the conversation ID for multi-turn interactions (maintains context)
previous_interaction_id = PREVIOUS_INTERACTION_ID

def get_interaction(text=None, image=False):
    """Send a request to the Gemini API and get back the next interaction step(s).
    
    This is the core loop: send input (text + screenshot + prior results),
    and receive back a list of steps the model wants to execute (function calls
    or text output).
    
    Args:
        text (str, optional): Task instruction or continuation text.
        image (bool, optional): Include current screenshot in request.
        model (str): Which Gemini model to use.
        function_result (dict, optional): Result from previous function execution.
    
    Returns:
        tuple: (interaction object, interaction_id) for tracking conversation.
    """
    global previous_interaction_id

    interaction = client.interactions.create(
        model=MODEL,
        input=input_blocks(text=text, image=image),
        tools=TOOLS,
        previous_interaction_id=previous_interaction_id,  # Link to prior message for context
        system_instruction=sys_instructions,
        generation_config={
            "thinking_level": THINKING_LVL,
            "thinking_summaries": "auto"
        }
    )
    previous_interaction_id = interaction.id  # Update for next call
    return interaction



# ============================================================================
# FUNCTION DISPATCH TABLE
# ============================================================================
# Every handler takes the model's arguments dict and returns a Result.
def _take_screenshot(kwargs):
    screen_cap(**kwargs)  # the model already gets a fresh screenshot every turn
    return OK


# Maps function names from Gemini API to executable functions in exe_func module.
# When the model requests an action (e.g., "click at x=500, y=300"), this table
# routes it to the correct handler function.
DISPATCH = {
    # Mouse click operations
    "click": lambda kwargs: hands.click(**kwargs),
    "double_click": lambda kwargs: hands.double_click(**kwargs),
    "triple_click": lambda kwargs: hands.triple_click(**kwargs),
    "middle_click": lambda kwargs: hands.middle_click(**kwargs),
    "right_click": lambda kwargs: hands.right_click(**kwargs),
    
    # Mouse movement & pressure
    "mouse_down": lambda kwargs: hands.mouse_down(**kwargs),
    "mouse_up": lambda kwargs: hands.mouse_up(**kwargs),
    "move": lambda kwargs: hands.move(**kwargs),
    
    # Keyboard & text input
    "type": lambda kwargs: hands.types(**kwargs),
    "press_key": lambda kwargs: hands.press_key(**kwargs),
    "key_down": lambda kwargs: hands.key_down(**kwargs),
    "key_up": lambda kwargs: hands.key_up(**kwargs),
    "hotkey": lambda kwargs: hands.hotkey(**kwargs),
    
    # Advanced operations
    "drag_and_drop": lambda kwargs: hands.drag_and_drop(**kwargs),
    "scroll": lambda kwargs: hands.scroll(**kwargs),
    "wait": lambda kwargs: hands.wait(**kwargs),
    
    # Vision & control flow
    "take_screenshot": _take_screenshot,

    # Tools Handoff implements itself (return_control, ...), see tools.py
    **HANDLERS,
}


def run_turn(steps, max_actions=MAX_ACTIONS_PER_TURN, gap=ACTION_GAP_SECONDS):
    """Execute the model's function calls in order, stopping early when needed.

    The model may batch several calls in one turn. They run one after another
    with a short pause between them; a denied/blocked/unknown/return_control
    result stops the rest, and calls beyond `max_actions` are not executed.

    Returns (feedback, stopped_by):
      feedback   - lines to send back to the model on the next turn
      stopped_by - the Result that ended the turn early, or None
    """
    calls = [step for step in steps if step.type == "function_call"]
    feedback = []
    for i, step in enumerate(calls):
        if i >= max_actions:
            feedback.append(
                f"Not executed because only {max_actions} actions run per turn: "
                + ", ".join(call.name for call in calls[i:])
            )
            return feedback, None
        if i > 0:
            sleep(gap)  # let the UI react to the previous action

        func = DISPATCH.get(step.name)
        if func is None:
            result = Result(
                Outcome.UNKNOWN_FUNCTION,
                f"No function named '{step.name}' exists, so it was not executed.",
            )
        else:
            result = func(step.arguments)

        if result.outcome is not Outcome.OK:
            print(f"[{step.name}] {result.outcome.value}" + (f": {result.message}" if result.message else ""))
        if result.message:
            feedback.append(f"{step.name}: {result.message}")

        if result.stops_turn:
            skipped = [call.name for call in calls[i + 1:]]
            if skipped:
                feedback.append("Not executed because the turn stopped early: " + ", ".join(skipped))
            return feedback, result
    return feedback, None



def main():
    """Run the interactive desktop automation workflow."""
    global client

    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to a .env file in the project root."
        )

    client = genai.Client(api_key=api_key)
    task_assigned = prompt_user_input("Enter the task you want to assign to the model:", title="Handoff: New Task")
    if not task_assigned or not task_assigned.strip():
        print("No task entered. Exiting.")
        return

    os.makedirs("convo_history", exist_ok=True)
    history_path = f"./convo_history/chat_{datetime.now():%Y%m%d_%H%M%S}.md"
    with open(history_path, "w", encoding="utf-8") as f:
        f.write("# Chat History Log\n\n")
        f.write(f"Task assigned: {task_assigned}\n\n")
        f.write("=============================================================================\n\n")

    sleep(5)
    bell()

    try:
        interaction = get_interaction(text=task_assigned, image=True)
    except Exception as e:
        print(f"An error occurred while getting the initial interaction: {e}")
        error_message_box(f"An error occurred while getting the initial interaction:\n\n{e}", title="Handoff: Error")
        return

    chat_iteration = 0

    try:
        while True:
            chat_iteration += 1
            with open(history_path, "a", encoding="utf-8") as f:
                f.write(f"## Interaction {chat_iteration}\n\n")
                f.write("```json\n")
                f.write(json.dumps(interaction.model_dump(), indent=2))
                f.write("\n```\n---\n\n")

            print(f"Interaction output: {interaction.output_text}")
            print("==============================================\n")

            # Run the model's actions (possibly a batch). A denied/blocked/unknown/
            # return_control step stops the rest of the turn.
            feedback, stopped_by = run_turn(interaction.steps)

            if stopped_by is not None:
                if stopped_by.outcome is Outcome.END_RUN:
                    break  # the user ended the run in the return_control dialog
                if stopped_by.outcome is Outcome.RETURN_CONTROL:
                    sleep(2)  # let the dialog close and the screen settle

            text = "\n".join(feedback) or None

            print("\n==============================================\n")
            bell()
            sleep(1.5)
            interaction = get_interaction(text=text, image=True)

    except Exception as e:
        print(f"An error occurred during the interaction loop: {e}")
        error_message_box(f"An error occurred during the interaction loop:\n\n{e}", title="Handoff: Error")


if __name__ == "__main__":
    main()

