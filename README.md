# Handoff

Handoff is a prototype AI agent that operates your desktop for you. You give it a task in plain English; it looks at the screen, decides what to do, and does it with the mouse and keyboard.

> "Open the browser, search for the latest Python release, and save the result."

It uses a Gemini model through the **Interactions API** with the built-in `computer_use` tool (desktop environment). The model never sees pixel coordinates; it works in a normalized 0-999 space that Handoff converts to your real screen resolution.

> **Status:** prototype
> **Platform:** developed and tested on Windows only; no Windows-specific code remains, but other platforms are untested
> **Model:** configurable in `config.py` (default `gemini-3.8-flash`)

---

## How it works

Handoff runs a **see → decide → act → see again** loop.

```text
task (Tk dialog)
      │
      ▼
screenshot + text ──► Gemini ──► steps (text and/or function calls)
      ▲                                   │
      │                                   ▼
      │                      run_turn: execute calls in order
      │                       (safety gate → PyAutoGUI)
      │                                   │
      └──── feedback text + new screenshot ◄┘
```

1. You enter a task in a dialog.
2. Handoff captures the screen and sends it with the task to Gemini.
3. Gemini replies with steps. Function-call steps are actions; one turn can contain several (a batch).
4. `run_turn` runs the actions in order, with a short pause between them. Each goes through the safety gate before it reaches PyAutoGUI.
5. Handoff captures a new screenshot and sends it back, along with text describing anything that did not go as planned (denied, blocked, skipped actions, the user's replies).
6. Repeat until the user ends the run.

The interaction ID is carried from one request to the next, so Gemini keeps the earlier turns as context. Each turn sends only the new screenshot and feedback.

The run ends only when the user leaves the `return_control` dialog blank or cancels it, or when an unhandled error occurs (see [Limitations](#limitations)). A model reply with no function calls does not end the run; Handoff just sends a fresh screenshot.

---

## Setup

You need Python, a Gemini API key, and the packages in `requirements.txt`:

```bash
pip install -r requirements.txt
```

`requirements.txt` lists `google-genai`, `PyAutoGUI` and `python-dotenv`. Handoff's dialogs use `tkinter`, which ships with the standard Python installer on Windows (on some Linux distributions it is a separate package).

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key
```

`main.py` stops at startup with a `RuntimeError` if `GEMINI_API_KEY` is missing.

## Running

```bash
python main.py
```

A dialog asks for the task. After you submit it, Handoff waits 5 seconds (so you can get the screen into the state you want), rings the system bell, and starts the loop. Leaving the task blank exits.

Handoff controls your real mouse and keyboard while it runs. Do not use the computer at the same time.

---

## Configuration

Settings live in `config.py`:

| Name | Default | Meaning |
|---|---|---|
| `MODEL` | `"gemini-3.8-flash"` | Gemini model used for every request. |
| `THINKING_LVL` | `"low"` | Thinking level sent as `generation_config.thinking_level`. Options noted in the file: `"low"`, `"medium"`, `"high"`. Lower is faster; higher may give better actions. |
| `PREVIOUS_INTERACTION_ID` | `None` | If set, the first request continues that earlier Gemini interaction instead of starting fresh. |

`main.py` also always sends `thinking_summaries: "auto"`.

**Continuing a previous run.** To pick up from an earlier interaction, replace `None` with that interaction's ID, as a string:

```python
PREVIOUS_INTERACTION_ID = "your_last_interaction_id"
```

Use the ID of the last interaction of the earlier run (the `id` field of the last entry in that run's log in `convo_history/`). The first request of the new run is linked to it, so Gemini keeps that conversation as context; Handoff still asks for a new task and sends a fresh screenshot. Set it back to `None` to start fresh.

Two per-turn limits are defined at the top of `executions/tools.py`:

| Name | Default | Meaning |
|---|---|---|
| `MAX_ACTIONS_PER_TURN` | `6` | Actions beyond this in one turn are not executed; the model is told which ones were dropped. |
| `ACTION_GAP_SECONDS` | `1` | Pause between actions of the same turn, so the UI can react. |

---

## Project structure

```text
Handoff/
├── main.py                  # loop, API calls, dispatch table, run_turn
├── config.py                # MODEL, THINKING_LVL, PREVIOUS_INTERACTION_ID
├── requirements.txt
├── executions/
│   ├── __init__.py          # re-exports the public pieces below
│   ├── hands.py             # mouse/keyboard actions + safety gate
│   ├── results.py           # Outcome enum and Result dataclass
│   ├── tools.py             # tool declarations, return_control, turn limits
│   ├── prompts.py           # system instruction sent to the model
│   ├── vision.py            # screenshot capture and image loading
│   └── dialogs.py           # Tk dialogs and the system bell
├── tests/                   # offline unit tests (see Tests)
└── convo_history/           # per-run logs (generated)
```

### `main.py`

- `input_blocks(text, image)` builds the request input: an optional text block and an optional screenshot block (`image/png`, base64).
- `get_interaction(text, image)` calls `client.interactions.create(...)` with the model, input, tools, system instruction and generation config, passing the previous interaction ID. It stores the new interaction's ID for the next call and returns the interaction.
- `DISPATCH` maps each function name the model can call to a handler. The handlers are the actions in `hands.py`, `take_screenshot`, and the tools Handoff implements itself (`HANDLERS` from `tools.py`).
- `run_turn(steps, max_actions, gap)` executes one turn's function calls (see [Turns and results](#turns-and-results)).
- `main()` loads the API key, asks for the task, creates the log file, and runs the loop.

### `executions/hands.py`

The execution layer. Converts normalized coordinates to pixels and performs the action with PyAutoGUI. Every action is wrapped by `@gated` and returns a `Result`. Screen size is read once, when the module is imported.

### `executions/results.py`

Defines `Outcome` and `Result` (see below).

### `executions/tools.py`

Declares the tools sent to the API (`TOOLS`: `computer_use` for the desktop, plus `return_control`), implements the `return_control` handler, and holds the per-turn limits.

### `executions/prompts.py`

`sys_instructions`, the system prompt, built by `build_sys_instructions(system)` for the OS reported by `platform.system()` when the module is imported. The OS name tells the model what kind of desktop it is controlling, and the address-bar tip uses `Cmd` on macOS and `Ctrl` elsewhere. For an OS it does not recognise, the prompt says just "desktop". It tells the model the per-turn output format (PROGRESS / OBSERVATION / NEXT ACTION), how to batch actions, what the system's feedback messages mean, the boundaries it must respect, and how to hand control back. The turn limit and the `return_control` name are filled in from `tools.py`, so the prompt and the code cannot drift apart.

### `executions/vision.py`

- `screen_cap(intent=None)` captures the screen with PyAutoGUI and returns it as a base64 PNG string, held in memory (no file is written).
- `get_img(path)` loads an image file from disk as base64 and raises clear errors for an empty path, a missing file, or a directory. It is meant for reproducible testing.

### `executions/dialogs.py`

Tk dialogs, all kept above other windows: `prompt_user_input`, `prompt_user_confirmation` (Yes/No), `error_message_box`, `warning_message_box`, and `bell`. A hidden Tk root is created when the module is first imported.

---

## Actions

The model can call these functions. All are gated except `take_screenshot` and `return_control`.

| Group | Functions |
|---|---|
| Mouse clicks | `click`, `double_click`, `triple_click`, `middle_click`, `right_click` |
| Mouse movement | `move`, `mouse_down`, `mouse_up`, `drag_and_drop` |
| Scrolling | `scroll` (up, down, left, right; default 3 wheel clicks) |
| Keyboard | `type` (optionally presses Enter after), `press_key`, `key_down`, `key_up`, `hotkey` |
| Timing | `wait` |
| Vision | `take_screenshot` (a no-op in practice: the model already gets a fresh screenshot every turn) |
| Control | `return_control` (see below) |

Coordinates are normalized to `0-999` and converted with:

```python
x_pixel = x / 999 * screen_width
y_pixel = y / 999 * screen_height
```

Two things to know: `type` uses `pyautogui.typewrite`, so it handles ASCII text only; and coordinates are not bounds-checked.

### `return_control`

The model uses this to hand control back to you. It takes two required arguments:

- `status`: `done` (task finished), `need_input` (it needs information or a decision from you), or `stuck` (it cannot make progress).
- `message`: 1-3 sentences written for you.

Handoff shows the message in a dialog titled for the status. If you type a reply, it is sent to the model as `The user replied: ...` and the run continues. If you leave the box blank or cancel, the run ends. The model is told to call `return_control` alone; if it batches other actions with it, the later ones are skipped and reported.

---

## Turns and results

Every action returns a `Result(outcome, message)`. The loop switches on the outcome rather than parsing text.

| Outcome | Meaning | Stops the rest of the turn? |
|---|---|---|
| `OK` | The action ran. | No |
| `DENIED` | You clicked No in the confirmation dialog. | Yes |
| `BLOCKED` | The model's own safety decision blocked the action. | Yes |
| `UNKNOWN_FUNCTION` | The model called a name Handoff has no handler for. | Yes |
| `RETURN_CONTROL` | The model handed control back and you replied. | Yes |
| `END_RUN` | You left the `return_control` dialog blank or cancelled it. | Yes (and the loop exits) |

`run_turn` rules:

- Calls run in order, `ACTION_GAP_SECONDS` apart.
- Only `OK` lets the next call run.
- When a call stops the turn, the remaining calls are not executed, and the model is told which ones were skipped.
- When a turn has more than `MAX_ACTIONS_PER_TURN` calls, the extras are not executed and the model is told which ones.
- Result messages and skipped-action notes are joined into one text block and sent with the next screenshot. The system prompt explains each message to the model.

---

## Safety

A computer-use action can carry a `safety_decision`. The `@gated` decorator checks it before the action runs:

- `require_confirmation`: a Yes/No dialog shows the model's explanation. Yes runs the action; No returns `DENIED`. The dialog has no timeout.
- `blocked`: the action does not run, a warning dialog shows the reason, and the result is `BLOCKED`.
- Any other value, or no `safety_decision`: the action runs.

The system prompt also tells the model not to invent passwords, codes or payment details, to stay within the task, and to ask when something is ambiguous. This is a prototype safety mechanism, not a security boundary: it depends on the model flagging risky actions, and the prompt is guidance, not enforcement.

---

## Logs

Each run writes `convo_history/chat_YYYYMMDD_HHMMSS.md` containing the task and, for every interaction, the full model response as JSON. These files are git-ignored. When something goes wrong, the log helps tell apart a wrong model decision, an unexpected screen state, an unsupported action, and a bug in the loop.

The console also prints the model's text output, each action with its stated intent, and the result of any action that did not return `OK`.

---

## Tests

```bash
python -m unittest discover -s tests -t . -v
```

36 tests across five files: `test_results.py`, `test_return_control.py`, `test_batching.py`, `test_loop.py` and `test_prompts.py`. `tests/stubs.py` replaces PyAutoGUI, the Tk dialogs, google-genai, python-dotenv and `config.py` before any project module is imported, so the tests need no display, API key or network and cannot move your mouse.

---

## Limitations

- **Tested on Windows only.** The code contains nothing Windows-specific, and the system prompt adapts to the detected OS, but macOS and Linux are untested. Things that may differ there: PyAutoGUI permissions (macOS accessibility and screen recording), X11 vs Wayland screenshots, modifier key names (`command` vs `ctrl`), and how far a "wheel click" scrolls (`_SCROLL_UNIT` in `hands.py`).
- **No per-action error handling yet.** If an action raises (for example `scroll` with an invalid direction), or an API call fails mid-run, the loop shows an error dialog and ends.
- **Screen-level automation.** Results depend on the screen layout, app state, UI timing and model accuracy. The full screenshot is sent every turn, so each turn costs model latency.
- **Single primary display; screen size read once** at startup.
- **Prototype safety model.** See [Safety](#safety).
- **No stuck detection.** The model is told to stop after repeating an action twice, but Handoff does not check whether the screen actually changed.

## Roadmap

Planned or under consideration:

- Per-step error handling with an `ERROR` outcome
- A benchmark to compare models and thinking levels (turns, time, success)
- Smaller screenshots (JPEG, downscaling, `media_resolution`)
- Shorter per-turn model output
- Checking how parallel function calling expects results to be returned
- Stuck detection from screenshot comparison
- Cross-platform support and stronger safety mechanisms
