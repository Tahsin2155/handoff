"""Gemini Computer-Use Agent: Main orchestration module.

This module coordinates the Gemini API client with the computer-use tool,
managing the interaction loop, function dispatch, and screenshot capture
for desktop automation tasks.
"""

import json
import os
from datetime import datetime
from time import sleep
from pprint import pprint

from dotenv import load_dotenv

from google import genai
from executions import hands, sys_instructions, screen_cap, prompt_user_input, error_message_box, bell
from executions.tools import TOOLS, RETURN_CONTROL

# ============================================================================
# CONFIGURATION: API Key & Client Setup
# ============================================================================
# Initialized by main() before the command-line workflow starts.
client = None


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
previous_interaction_id = None

def get_interaction(text=None, image=False, model="gemini-3.8-flash"):
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
        model=model,
        input=input_blocks(text=text, image=image),
        tools=TOOLS,
        previous_interaction_id=previous_interaction_id,  # Link to prior message for context
        system_instruction=sys_instructions
    )
    previous_interaction_id = interaction.id  # Update for next call
    return interaction



# ============================================================================
# FUNCTION DISPATCH TABLE
# ============================================================================
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
    "take_screenshot": lambda kwargs: screen_cap(**kwargs),
    "return_control": lambda kwargs=None: "return_control"
}



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
    end_interaction = False

    try:
        interaction = get_interaction(text=task_assigned, image=True)
    except Exception as e:
        print(f"An error occurred while getting the initial interaction: {e}")
        error_message_box(f"An error occurred while getting the initial interaction:\n\n{e}", title="Handoff: Error")
        return

    chat_iteration = 0

    try:
        while True:
            text = None
            chat_iteration += 1
            with open(history_path, "a", encoding="utf-8") as f:
                f.write(f"## Interaction {chat_iteration}\n\n")
                f.write("```json\n")
                f.write(json.dumps(interaction.model_dump(), indent=2))
                f.write("\n```\n---\n\n")

            print(f"Interaction output: {interaction.output_text}")
            print("==============================================\n")

            # Process each step returned by the model
            for i, step in enumerate(interaction.steps):
                if step.type == "function_call":
                    # Model requested an automation action (click, type, scroll, etc.)
                    func = DISPATCH.get(step.name)
                    if func:
                        # Execute the function and capture any return value
                        result = func(step.arguments)
                        if result:
                            print(f"Function call {step.name} returned: {result}")
                            
                            if result == "return_control":
                                # Model signaled task completion
                                print("=============================================")
                                print("Ending interaction as requested by the model.")
                                print("=============================================")
                                # Prompt user to continue or exit
                                if bool(next_text := (prompt_user_input("Enter text to continue the interaction (leave blank or cancel to end):", title="Handoff: Continue?") or "").strip()):
                                    text = next_text
                                    sleep(2)
                                else:
                                    end_interaction = True
                            elif result == "Denied by user.":
                                # User blocked a safety-gated action; report back to model
                                text = result
                            elif result.startswith("Blocked:"):
                                # Action was blocked by safety gate; report reason to model
                                text = result
                    else:
                        # Unknown function name - likely a typo or missing handler in DISPATCH
                        print(f"Unknown function call: {step.name}")
                        

            print("\n==============================================\n")
            if end_interaction:
                break

            bell()
            sleep(1.5)
            interaction = get_interaction(text=text, image=True)

    except Exception as e:
        print(f"An error occurred during the interaction loop: {e}")
        error_message_box(f"An error occurred during the interaction loop:\n\n{e}", title="Handoff: Error")


if __name__ == "__main__":
    main()

