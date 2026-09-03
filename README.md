# Handoff

**Handoff** is a prototype AI computer-use agent that lets you control a computer using natural-language instructions.

You give Handoff a task such as:

> "Open the browser, search for the latest Python release, and save the result."

The agent sends the current screen to a Gemini computer-use-supported model, receives the next actions to perform, and executes them using the mouse and keyboard.

The goal is simple: **let an AI interact with a computer the way a human does.**

> **Status:** Prototype
> **Platform:** Windows
> **Model:** Gemini models supporting computer use through the Interactions API

---

## How It Works

Handoff operates as a continuous **see → decide → act → see again** loop.

```text
Natural-language task
        │
        ▼
   Gemini API
        │
        │  screenshot + task
        ▼
  Computer-use model
        │
        │  action(s)
        ▼
   Handoff dispatcher
        │
        ▼
 Mouse / Keyboard
        │
        ▼
 Updated computer screen
        │
        └───────────────► Gemini
```

At a high level:

1. You provide a task in natural language.
2. Handoff captures the current screen.
3. The screenshot and task are sent to Gemini.
4. Gemini decides what computer action should happen next.
5. Handoff dispatches that action to the appropriate function.
6. The action is performed using PyAutoGUI.
7. The resulting screen is captured and sent back to the model.
8. The process continues until the model ends the interaction.

Handoff maintains the Gemini interaction ID between turns so the model can continue working with the conversation context.

---

## Features

### Natural-language computer control

Give Handoff a task instead of manually describing every individual action.

### Mouse and keyboard automation

The execution layer currently supports:

* Click
* Double-click
* Triple-click
* Left/right/middle mouse actions
* Mouse movement
* Mouse button down/up
* Drag and drop
* Scrolling
* Typing text
* Key presses
* Key down/up
* Keyboard shortcuts
* Waiting

These actions are exposed through a central dispatch table that maps Gemini function calls to local execution functions.

### Screenshot-based interaction

Handoff captures the current display as a PNG, keeps it in memory, and encodes it as Base64 for use in the Gemini request. It can also load an existing image from disk for reproducible testing.

### Safety gate

Certain actions can require explicit human approval before they are executed.

When Gemini requests confirmation:

* **Shift** → approve the action
* **Ctrl** → deny the action

Actions explicitly marked as blocked by the safety decision are rejected automatically.

The safety layer is implemented as a central gate before computer actions are executed.

### Audible feedback

Handoff uses different beep patterns to communicate important events, including:

* Errors
* Iteration completion
* Task completion / transition
* Confirmation requests
* Blocked actions

This makes important events noticeable even when the user is not watching the terminal.

### Conversation logging

Each run creates a Markdown log inside `convo_history/`.

The log contains the assigned task and the model interactions returned during execution. This is useful for:

* Debugging
* Understanding why the agent took a particular action
* Reviewing failed runs
* Inspecting the model's interaction history

---

## Requirements

Handoff currently runs on **Windows**.

You need:

* Python
* A Gemini API key
* The Python dependencies listed in `requirements.txt`

Install the dependencies with:

```bash
pip install -r requirements.txt
```

---

## Setup

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key
```

Handoff reads this value using `python-dotenv`. The application will stop at startup if `GEMINI_API_KEY` is not available.

---

## Running Handoff

From the project directory:

```bash
python main.py
```

You will be prompted to enter a task:

```text
Enter the task you want to assign to the model:
```

Enter a natural-language instruction and Handoff will begin the computer-use loop.

---

## Safety Controls

Handoff does not blindly execute every action returned by the model.

A computer-use action may include a `safety_decision`. The execution layer checks this decision before allowing the action to reach PyAutoGUI.

### Confirmation required

When an action requires confirmation, Handoff emits an audible alert and waits for a key press.

```text
Shift → Approve
Ctrl  → Deny
```

### Blocked action

When the safety decision is `blocked`, the action is not executed and the reason is reported back to the interaction loop.

This allows the model and the local execution layer to participate in a safety boundary rather than giving the model unrestricted control of the machine.

---

## Project Structure

```text
Handoff/
│
├── convo_history/
│   └── # Generated interaction logs
│
├── executions/
│   ├── __init__.py
│   └── hands.py
│
├── main.py
├── README.md
└── requirements.txt
```

### `main.py`

The main orchestration layer.

It is responsible for:

* Loading configuration
* Creating the Gemini client
* Building API input blocks
* Sending screenshots and instructions to Gemini
* Maintaining interaction state
* Receiving model outputs
* Dispatching computer-use actions
* Handling task completion
* Writing conversation logs

The Gemini request uses the `computer_use` tool with the `desktop` environment, along with a custom `end_of_interaction` function for ending an interaction.

### `executions/__init__.py`

This module provides the **vision/input side** of Handoff.

It contains functions for:

* Capturing the screen
* Encoding screenshots as Base64
* Loading existing images
* Producing audible status signals

The screenshot capture uses PyAutoGUI and writes the PNG into an in-memory buffer rather than creating a temporary screenshot file.

### `executions/hands.py`

This module provides the **action/execution side** of Handoff.

Think of it as the agent's hands.

It receives the normalized coordinates and arguments produced by the computer-use model and translates them into real mouse and keyboard operations through PyAutoGUI.

---

## Coordinate System

Computer-use models operate using normalized coordinates in the range:

```text
0 → 999
```

Handoff converts these coordinates into actual screen pixels based on the current display resolution.

```python
x_pixel = x / 999 * screen_width
y_pixel = y / 999 * screen_height
```

This allows model-generated coordinates to remain independent of the user's actual screen resolution.

---

## Interaction Lifecycle

A simplified version of the internal flow looks like this:

```plaintext
task
  ↓
capture screenshot
  ↓
send task + screenshot to Gemini
  ↓
receive interaction steps
  ↓
for each step:
    ├── model output → display it
    │
    └── function call
          ↓
       dispatch action
          ↓
       safety gate
          ↓
       PyAutoGUI
          ↓
       report result
  ↓
capture new screenshot
  ↓
continue interaction
```

The dispatcher is intentionally centralized, making it straightforward to add or replace executable actions.

---

## Supported Gemini Models

Handoff is designed around Gemini's **computer-use capability through the Interactions API** rather than being tied to a single model (Default to `gemini-3.5-flash-lite`). 

The model is passed when creating an interaction, so the configured model can be changed without changing the execution architecture.

---

## Current Limitations

Handoff is still a prototype.

### Windows only

The current implementation relies on Windows-specific functionality such as Python's `winsound` module, so it is not currently portable to macOS or Linux.

There is future scope for replacing the platform-specific pieces with cross-platform implementations.

### Screen-level automation

Handoff interacts with applications through the computer's graphical interface rather than through application-specific APIs.

That makes the system flexible, but also means performance depends on factors such as:

* Screen layout
* Application state
* Visual changes
* Model accuracy
* Timing of UI updates

### Prototype safety model

The current confirmation mechanism is intentionally simple: the user can approve or deny a gated action through global keyboard input.

It should be treated as a prototype safety mechanism rather than a complete security boundary.

---

## Why Handoff?

Traditional automation usually requires you to explicitly describe the steps:

```text
1. Open the browser
2. Click the address bar
3. Type the URL
4. Press Enter
5. Click the button
...
```

Handoff instead aims for:

```text
"Open the website and complete the task."
```

The model determines the intermediate actions from what it sees on the screen.

That makes the automation layer more flexible and potentially applicable to applications that do not expose convenient APIs.

---

## Development

The project is intentionally structured around three main responsibilities:

```text
Vision
  └── screenshots and image encoding

Reasoning
  └── Gemini computer-use model

Execution
  └── mouse and keyboard control
```

Keeping these responsibilities separate makes it easier to experiment with different models, execution methods, and safety mechanisms without rewriting the entire agent.

---

## Debugging

When something goes wrong, check the generated files in:

```text
convo_history/
```

Each run creates a timestamped Markdown file containing the task and interaction data returned by Gemini.

This is often the easiest way to determine whether a failure came from:

* The model's decision
* An unexpected screen state
* An unsupported action
* The execution layer
* The interaction loop

---

## Roadmap

Handoff is currently a prototype, so the architecture is expected to evolve.

Potential future work includes:

* Cross-platform computer control
* More robust safety mechanisms
* Better error recovery
* Improved state handling
* More execution primitives
* Better observability and debugging
* More reliable long-running task execution

---