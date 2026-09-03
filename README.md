# Handoff

Handoff is a Windows desktop automation agent that combines Google's Gemini computer-use interactions with PyAutoGUI. You describe a task in natural language, Gemini observes a screenshot, and the agent executes the returned mouse and keyboard actions on the local desktop.

The project is intentionally human-in-the-loop. Actions that Gemini marks as requiring confirmation pause until you approve them with **Shift** or deny them with **Ctrl**. Actions marked as blocked are never executed.

> **Warning:** Handoff can move the real mouse and type into the active application. Run it only in a controlled desktop session, review tasks carefully, and do not use it with sensitive applications or data until you understand its behavior.

## Requirements

- Windows (the project imports `winsound` and uses Windows/global keyboard behavior).
- Python 3.12 or a compatible modern Python 3 release.
- A Gemini API key with access to the interactions API and computer-use capability.
- An interactive desktop session. The machine must remain unlocked and the target application must be visible when Handoff is running.

Windows is the only supported platform at present. Cross-platform support is a
future scope item and will require platform-specific implementations for
audible notifications, global keyboard detection, desktop automation, display
scaling, permissions, packaging, and platform-level testing.

The checked-in `requirements.txt` is a pip freeze from the development environment. It includes the direct packages and their resolved dependencies.

## Installation

Run these commands from the project directory in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
```

If PowerShell blocks activation scripts, either adjust the execution policy for your user account or invoke the environment's Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create a `.env` file in the project root. The file is ignored by Git and must never contain a committed or shared secret:

```dotenv
GEMINI_API_KEY=your-gemini-api-key
```

Create the history directory before the first run. `main.py` writes to this path but does not create it automatically:

```powershell
New-Item -ItemType Directory -Force .\convo_history
```

## Running Handoff

Launch from the project root so relative paths resolve correctly:

```powershell
.\.venv\Scripts\python.exe .\main.py
```

The program will:

1. Ask for a natural-language task.
2. Wait briefly, capture the current primary-screen screenshot, and send the task plus screenshot to Gemini.
3. Execute the computer-use function calls returned by Gemini.
4. Capture and print model output and function results.
5. Write each interaction to `convo_history/chat1.md`.
6. Repeat until Gemini requests `end_of_interaction`.
7. Ask whether to continue with another instruction. Enter a new task to continue, or leave the response blank to exit.

Example task input:

```text
Open Notepad and type a short draft titled Meeting Notes.
```

Keep the target application focused and avoid touching the mouse or keyboard while an action is being executed. Handoff sends screenshots of the primary display to Gemini.

## Safety controls

Gemini can attach a `safety_decision` to an action. `executions.hands.needs_gate()` enforces that decision before PyAutoGUI is called:

| Decision | Behavior |
| --- | --- |
| `allow` or missing decision | The action proceeds immediately. |
| `require_confirmation` | Handoff beeps and waits for **Shift** to approve or **Ctrl** to deny. |
| `blocked` | Handoff beeps, prints the explanation, and skips the action. |

When an action is denied or blocked, the result is passed back into the interaction loop so Gemini can react. Audible signals are also used for errors, completed iterations, task transitions, confirmation requests, and blocked actions.

The keyboard confirmation listener uses the `keyboard` package to poll global key state. Windows security software, permissions, remote sessions, or another application may affect global key detection.

## Coordinate system

Gemini computer-use coordinates are expected in the normalized range `0` to `999`. The agent converts them to pixel coordinates using the primary display size captured when `executions.hands` is imported:

```text
pixel_x = normalized_x / 999 * screen_width
pixel_y = normalized_y / 999 * screen_height
```

The display size is not refreshed during a run. Changing display configuration, scaling, or the primary monitor after startup can therefore make coordinates inaccurate. Values outside `0` to `999` are not clamped.


# Project Structure

```
handoff/                    
├── convo_history           Runtime conversation log; create before first run
├── executions              
│   ├── __init__.py         Screenshot, image encoding, and audible feedback
│   └── hands.py            Coordinate conversion, safety gate, and PyAutoGUI actions
├── main.py                 Gemini client, dispatch table, and interaction loop
├── README.md               
└── requirements.txt        Pinned development-environment dependencies
```



### `main.py`

- Loads `GEMINI_API_KEY` with `python-dotenv`.
- Creates a `google.genai.Client`.
- Builds text, screenshot, and function-result input blocks.
- Maintains the Gemini `previous_interaction_id` for multi-turn context.
- Registers the desktop `computer_use` tool and an `end_of_interaction` function.
- Dispatches returned function calls to `executions.hands`.
- Logs serialized interaction objects as Markdown/JSON.
- Provides the command-line task prompt and continuation prompt.

The default model passed to `get_interaction()` is `gemini-3.5-flash-lite`. To use another model, change the default or pass a different model from Python code before the initial request.

### `executions/__init__.py`

This module provides the visual and audible utilities:

- `screen_cap(intent=None)`: captures the primary screen as a base64-encoded PNG.
- `get_img(path)`: reads an existing file and returns its base64 contents. It checks that the path is a non-empty string, exists, and is a file, but does not validate the image format.
- `beep_alert_error()`: one long low-frequency error beep.
- `beep_iteration_complete()`: one iteration-complete beep.
- `beep_task_end_or_next()`: three short transition beeps.
- `beep_require_confirmation()`: two confirmation-request beeps.
- `beep_action_blocked()`: three blocked-action beeps.

### `executions/hands.py`

All action functions accept Gemini-style arguments and log the action intent. Mouse coordinates are normalized as described above. Most actions accept an optional `safety_decision`.

| Function | Effect |
| --- | --- |
| `denormalize_coordinates(x, y)` | Converts normalized coordinates to screen pixels. |
| `click(x, y, intent, safety_decision=None)` | Single left click. |
| `double_click(...)` | Double left click. |
| `triple_click(...)` | Triple left click. |
| `middle_click(...)` | Middle click. |
| `right_click(...)` | Right click. |
| `mouse_down(...)` | Presses a mouse button. |
| `mouse_up(...)` | Releases a mouse button. |
| `move(...)` | Moves the pointer. |
| `type(text, intent, press_enter=False, safety_decision=None)` | Types text and optionally presses Enter. |
| `drag_and_drop(start_x, start_y, end_x, end_y, intent, safety_decision=None)` | Drags between two normalized positions. |
| `wait(intent, seconds=1, safety_decision=None)` | Pauses for a number of seconds. |
| `press_key(key, intent, safety_decision=None)` | Presses one key. |
| `key_down(key, intent, safety_decision=None)` | Holds one key down. |
| `key_up(key, intent, safety_decision=None)` | Releases one key. |
| `hotkey(keys, intent, safety_decision=None)` | Presses a list of keys together. |
| `scroll(x, y, direction, intent, magnitude_in_wheel_clicks=3, safety_decision=None)` | Moves to a position and scrolls up, down, left, or right. |

## Conversation history

At startup, `main.py` overwrites `convo_history/chat1.md` with the task text. Each interaction is then appended as formatted JSON. The log is useful for debugging and auditing, but screenshots or model payloads may contain sensitive desktop information. Treat the directory as sensitive and do not commit it.

The current implementation always uses the filename `chat1.md`; starting a new run replaces the previous log.

## Notebook status

`test.ipynb` is currently an empty Jupyter notebook with a `.venv (3.12.10)` kernel metadata entry. It is not part of the executable workflow and contains no tests or examples yet.

## Troubleshooting

### `GEMINI_API_KEY is not set`

Confirm that `.env` is in the same directory from which `main.py` is launched and contains `GEMINI_API_KEY=...`. Do not put quotes around the variable unless they are intended to be part of the value.

### `FileNotFoundError` for `convo_history/chat1.md`

Create the directory from the project root:

```powershell
New-Item -ItemType Directory -Force .\convo_history
```

### PyAutoGUI acts on the wrong location

Keep the same primary display configuration throughout the run. Make sure the intended application is visible and focused, and account for Windows display scaling or multiple monitors.

### Confirmation keys do not work

Ensure the terminal and desktop session permit global keyboard detection. Try running in a local, unlocked Windows session and check whether security software is restricting the `keyboard` package.

### The program stops with a model/API error

Check the API key, network connection, enabled Gemini API access, selected model availability, and the serialized interaction entry in `convo_history/chat1.md`.

## Development notes

- Do not commit `.env`, API keys, conversation history, or screenshots.
- Test automation against harmless applications first.
- Keep the target desktop stable during an interaction.
- The code currently performs work at module import time: importing `main.py` prompts for a task and starts the agent. Use the script entry point for normal operation.
- There is no automated test suite in the repository yet.

## Future scope

The project is currently Windows-only. A future release may extend Handoff to
macOS and Linux. That work will likely include replacing or abstracting the
Windows-only `winsound` notifications, validating cross-platform global
keyboard input, adapting PyAutoGUI behavior and permissions, handling display
scaling and multi-monitor differences, and adding platform-specific automated
tests and installation instructions.
