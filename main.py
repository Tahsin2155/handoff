"""Gemini Computer-Use Agent: Main orchestration module.

This module coordinates the Gemini API client with the computer-use tool,
managing the interaction loop, function dispatch, and screenshot capture
for desktop automation tasks.
"""

import os, json, winsound
from dotenv import load_dotenv

from google import genai
# Import automation functions and beep utilities
from executions import hands, screen_cap, get_img, beep_iteration_complete, beep_task_end_or_next, beep_alert_error
from time import sleep
from pprint import pprint

# ============================================================================
# CONFIGURATION: API Key & Client Setup
# ============================================================================
# Load the API key from the local .env file.
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY", "")
if not api_key:
    raise RuntimeError(
        "GEMINI_API_KEY is not set. Export it in your shell before launching "
        "Jupyter, or set it here for local testing only (do not commit a real key)."
    )

# Initialize Gemini API client
client = genai.Client(api_key=api_key)


# ============================================================================
# INPUT BLOCK CONSTRUCTION
# ============================================================================
def input_blocks(text=None, image=False, function_result=None) -> list:
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
    if function_result:
        input_block.append(
            {
                "type": "function_result",
                "data": function_result  # Report execution result back to model
            }
        )
    return input_block

# ============================================================================
# INTERACTION STATE & API CALLS
# ============================================================================
# Tracks the conversation ID for multi-turn interactions (maintains context)
previous_interaction_id = None

def get_interaction(text=None, image=False, model="gemini-3.5-flash-lite", function_result=None):
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
    global previous_interaction_id  # Update global state for next turn
    
    interaction = client.interactions.create(
        model=model,
        input=input_blocks(text=text, image=image, function_result=function_result),
        tools=[
            {
                # Computer-use tool: allows model to control mouse, keyboard, see screen
                "type": "computer_use",
                "environment": "desktop"
            },
            {
                # Custom function: model can signal when task is done
                "type": "function",
                "name": "end_of_interaction",
                "description": "Request to end the current interaction. Use this when the task is complete and no further actions are needed, stuck somewhere, or when the model is unable to proceed. This will stop the interaction and return control to the user."
            }
        ],
        previous_interaction_id=previous_interaction_id  # Link to prior message for context
    )
    return interaction, interaction.id



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
    "type": lambda kwargs: hands.type(**kwargs),
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
    "end_of_interaction": lambda kwargs=None: "end_of_interaction"  # Signal end of task
}



# ============================================================================
# TASK & INITIALIZATION
# ============================================================================

# Get task from user input
task_assigned = input("Enter the task you want to assign to the model: ")

with open(history_path := "./convo_history/chat1.md", "w", encoding="utf-8") as f:
    f.write("# Chat History Log\n\n")
    f.write(f"Task assigned: {task_assigned}\n\n")
    f.write("=============================================================================\n\n")

# Brief pause before starting automation
sleep(5)

end_interaction = False

# Send initial task to model with screenshot
try:
    interaction, previous_interaction_id = get_interaction(text=task_assigned, image=True)
except Exception as e:
    print(f"An error occurred while getting the initial interaction: {e}")
    # Alert user of error with identifiable beep pattern
    beep_alert_error()  

chat_iteration = 0  # Track number of iterations for logging/debugging

try:
    # ============================================================================
    # MAIN INTERACTION LOOP
    # ============================================================================
    while True:
        # Prepare for next iteration
        text = None
        
        chat_iteration += 1
        # Log the entire interaction to file for debugging/auditing
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(f"## Interaction {chat_iteration}\n\n")
            f.write("```json\n")
            f.write(json.dumps(interaction.model_dump(), indent=2))
            f.write("\n```\n---\n\n")

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
                        
                        if result == "end_of_interaction":
                            # Model signaled task completion
                            print("=============================================")
                            print("Ending interaction as requested by the model.")
                            print("=============================================")
                            # Identifiable beep pattern to signal task end/transition
                            beep_task_end_or_next()
                            
                            # Prompt user to continue or exit
                            if bool(next_text := input("Enter text to continue the interaction (or leave blank to end): ").strip()):
                                text = next_text
                                sleep(2)
                            else:
                                end_interaction = True
                        elif result == "Denied by user.":
                            # User blocked a safety-gated action; report back to model
                            text = result
                        elif result[0:7] == "Blocked:":
                            # Action was blocked by safety gate; report reason to model
                            text = result
                else:
                    # Unknown function name - likely a typo or missing handler in DISPATCH
                    print(f"Unknown function call: {step.name}")
                    
            elif step.type == "model_output":
                # Model generated text output (thinking, explanations, etc.)
                print(f"Model output:")
                pprint(step.content)
                print()

        # Display model's response text summary
        print(f"Interaction output: {interaction.output_text}")
        print("\n==============================================\n")

        # Check if user requested to end the interaction
        if end_interaction:
            break

        # Identifiable beep pattern to indicate one iteration complete
        beep_iteration_complete()
        sleep(1.5)

        # Request next set of steps from the model
        interaction, previous_interaction_id = get_interaction(text=text, image=True)

except Exception as e:
    # Error handler for unexpected issues during the main loop
    print(f"An error occurred during the interaction loop: {e}")
    # Alert user of error with identifiable beep pattern
    beep_alert_error()      

    