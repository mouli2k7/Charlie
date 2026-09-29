# Charlie — Voice + Text Assistant for macOS

> **Instructions for the AI coding agent (Antigravity):** This README is the full specification for the project. Read it completely before writing code. Build the project phase by phase (see [Build Phases](#build-phases)), run the tests after each phase, and do not skip ahead. Follow the [Rules & Constraints](#rules--constraints) strictly.

---

## 1. Overview

**Charlie** is a personal assistant that runs on my Mac (macOS 13+) and controls it through **voice commands** and **typed text commands**.

Charlie understands natural sentences like:

- "Open Spotify"
- "Open Amazon and search for wireless earbuds"
- "Search for running shoes on Flipkart"
- "Turn the volume up" / "Set volume to 30" / "Mute"
- "Increase brightness" / "Dim the screen"
- "Pause the music" / "Next song"

It converts the sentence into a **structured action**, runs that action on the Mac, and confirms the result by text and speech.

## 2. Goals

1. Accept input by **text** (terminal now, small popup window later) and **voice** (microphone).
2. Understand **flexible phrasing**, not only fixed sentences.
3. Reliably perform the core Mac actions listed below.
4. Be **safe**: only run actions from a fixed whitelist. Never execute arbitrary shell commands produced by an AI model.
5. Work **offline for basic commands** (rule-based parser) and get smarter when an LLM API key is provided.
6. Be easy to extend: adding a new action should mean adding one file and one schema entry.

## 3. Features

### 3.1 Core actions (required)

| Action | Example phrases | Behaviour |
|---|---|---|
| `open_app` | "open safari", "launch notes", "start spotify" | Opens the named macOS app. Fuzzy-match the name against installed apps in `/Applications`, `/System/Applications` and `~/Applications` (e.g. "vs code" -> "Visual Studio Code"). |
| `close_app` | "close chrome", "quit spotify" | Gracefully quits the app. |
| `web_search` | "open amazon and search for iPhone case", "search headphones on flipkart", "google best laptops" | Opens the default browser (or a browser I name) on the site's search results page. Default site is Google. |
| `open_url` | "open youtube", "go to github.com" | Opens the site's homepage or the given URL. |
| `volume_change` | "volume up", "turn it down a bit" | Changes volume by a step (default 10, "a bit" = 5, "a lot" = 25). |
| `volume_set` | "set volume to 40", "volume 70 percent" | Sets exact volume 0-100. |
| `mute` / `unmute` | "mute", "unmute" | Mutes or restores previous volume. |
| `brightness_change` | "brightness up", "make the screen dimmer" | Changes brightness by a step (default 10%). |
| `brightness_set` | "set brightness to 50" | Sets exact brightness 0-100. |
| `media_control` | "play", "pause", "next song", "previous track" | Sends the macOS media keys so it works with any player (Spotify, Apple Music, YouTube in the browser). |

### 3.2 Supported sites for `web_search`

Configurable in `config/sites.yaml`. Start with:

| Site key | URL template |
|---|---|
| google | `https://www.google.com/search?q={query}` |
| amazon | `https://www.amazon.in/s?k={query}` |
| flipkart | `https://www.flipkart.com/search?q={query}` |
| youtube | `https://www.youtube.com/results?search_query={query}` |
| myntra | `https://www.myntra.com/{query}` |
| meesho | `https://www.meesho.com/search?q={query}` |

The query must be URL-encoded. If the site name is unknown, fall back to Google.

### 3.3 Input modes

- **Text mode:** interactive prompt in the terminal (Phase 1). Optional menu-bar popup (Phase 4).
- **Voice mode:** push-to-talk first (type `v` + Enter, or press a hotkey), then optional wake word "Hey Charlie" (Phase 3).
- Both modes feed the **same** command pipeline.

### 3.4 Output

- Print the result in the terminal.
- Speak short confirmations using the built-in macOS `say` command (can be turned off in config).
- On failure, say what went wrong in one plain sentence ("I couldn't find an app called Photoshop").

---

## 4. Architecture

```
 ┌────────────┐   ┌──────────────┐
 │ Text input │   │ Voice input  │  (mic -> speech-to-text)
 └─────┬──────┘   └──────┬───────┘
       └────────┬────────┘
                ▼
        ┌───────────────┐
        │    Brain      │  text -> structured Action (JSON)
        │ 1. rule-based │  (offline, fast)
        │ 2. LLM (opt.) │  (fallback for unclear phrasing)
        └───────┬───────┘
                ▼
        ┌───────────────┐
        │  Validator    │  checks action is on the whitelist + params valid
        └───────┬───────┘
                ▼
        ┌───────────────┐
        │   Router      │  action name -> handler function
        └───────┬───────┘
                ▼
        ┌───────────────┐        ┌──────────────┐
        │  Action       │  ───►  │  Speaker /   │
        │  handlers     │        │  console     │
        └───────────────┘        └──────────────┘
```

### 4.1 Action schema

Every command becomes one JSON object:

```json
{
  "action": "web_search",
  "params": { "site": "amazon", "query": "wireless earbuds", "browser": null },
  "confidence": 0.95
}
```

Allowed `action` values and their `params`:

| action | params |
|---|---|
| `open_app` | `app` (string) |
| `close_app` | `app` (string) |
| `web_search` | `site` (string, default "google"), `query` (string), `browser` (string or null) |
| `open_url` | `url` (string) or `site` (string) |
| `volume_change` | `direction` ("up"/"down"), `amount` (int, default 10) |
| `volume_set` | `level` (int 0-100) |
| `mute` / `unmute` | none |
| `brightness_change` | `direction` ("up"/"down"), `amount` (int, default 10) |
| `brightness_set` | `level` (int 0-100) |
| `media_control` | `command` ("play_pause"/"next"/"previous") |
| `unknown` | `reason` (string) |

Use **Pydantic** models for validation. Anything that fails validation becomes `unknown`.

### 4.2 Brain (two layers)

1. **Rule-based parser** (`brain/rules.py`): regex/keyword patterns for all core actions. Runs first, needs no internet, and must handle the example phrases in this README.
2. **LLM parser** (`brain/llm.py`, optional): used only if the rule-based parser returns `unknown` or low confidence AND `ANTHROPIC_API_KEY` is set.
   - Call the Anthropic Messages API with a system prompt that lists the allowed actions and schema and instructs the model to reply with **JSON only**.
   - Strip any code fences, parse the JSON, then pass it through the validator.
   - Model name comes from `.env` (`CHARLIE_MODEL`, default `claude-sonnet-5`).
   - Timeout of 8 seconds; on any error fall back to `unknown`.

The LLM only **chooses an action from the whitelist**. It never writes shell commands or code that gets executed.

---

## 5. Tech Stack

- **Language:** Python 3.11+
- **Validation:** `pydantic`
- **Config:** `python-dotenv`, `PyYAML`
- **Voice input:** `SpeechRecognition` + `PyAudio` (needs `brew install portaudio`). Optional upgrade: `faster-whisper` for offline speech-to-text.
- **Wake word (Phase 3):** `openwakeword` or `pvporcupine`
- **Mac control:** `subprocess` calling `open`, `osascript`, `say`; `pyobjc-framework-Quartz` and `pyobjc-framework-Cocoa` for media keys; the `brightness` CLI (`brew install brightness`) with an AppleScript key-code fallback
- **LLM (optional):** `anthropic` Python SDK
- **Menu bar UI (Phase 4):** `rumps`
- **Tests:** `pytest`

## 6. Project Structure

```
charlie/
├── README.md
├── requirements.txt
├── .env.example
├── config/
│   ├── settings.yaml        # step sizes, speech on/off, default browser, hotkey
│   └── sites.yaml           # site key -> URL template
├── charlie/
│   ├── __init__.py
│   ├── main.py              # entry point / main loop
│   ├── config.py            # loads settings + env
│   ├── schema.py            # Pydantic Action models
│   ├── brain/
│   │   ├── __init__.py      # parse(text) -> Action (rules first, then LLM)
│   │   ├── rules.py
│   │   └── llm.py
│   ├── router.py            # Action -> handler
│   ├── inputs/
│   │   ├── text_input.py
│   │   ├── voice_input.py
│   │   └── wake_word.py     # Phase 3
│   ├── actions/
│   │   ├── apps.py          # open/close app, fuzzy matching
│   │   ├── web.py           # web_search, open_url
│   │   ├── volume.py
│   │   ├── brightness.py
│   │   └── media.py
│   ├── output/
│   │   └── speaker.py
│   └── ui/
│       └── menubar.py       # Phase 4
└── tests/
    ├── test_rules.py
    ├── test_schema.py
    ├── test_router.py
    └── test_web.py
```

---

## 7. Implementation Details

### 7.1 Opening apps
- Build an index of installed app names at startup (scan the three Applications folders, lowercase for matching).
- Match with exact match first, then alias table (`"vs code"`, `"chrome"`, `"whatsapp"`), then fuzzy match using `difflib.get_close_matches` (cutoff 0.6).
- Open with `subprocess.run(["open", "-a", app_name])`. Use list arguments, never `shell=True`.

### 7.2 Web search
- Look up the URL template from `sites.yaml`, URL-encode the query with `urllib.parse.quote_plus`, and open it.
- If a browser is named ("in chrome"), use `open -a "Google Chrome" <url>`; otherwise use the default browser via `open <url>`.
- Handle phrasings: "open X and search for Y", "search Y on X", "search for Y" (Google), "google Y", "look up Y on X".

### 7.3 Volume
- Read: `osascript -e "output volume of (get volume settings)"`
- Set: `osascript -e "set volume output volume N"`
- Clamp to 0-100. Remember the pre-mute level in memory so `unmute` restores it.

### 7.4 Brightness
- Preferred: the `brightness` CLI (`brightness -l` to read, `brightness 0.5` to set).
- Fallback: AppleScript key codes via System Events (144 = brighter, 145 = dimmer), repeated to approximate the step.
- If neither works, tell me clearly what to install or enable.

### 7.5 Media keys
- Post system-defined NSEvents through Quartz for play/pause (key 16), next (17) and previous (18), so it controls whichever app currently owns media playback.

### 7.6 Voice input
- Push-to-talk: listen for up to 8 seconds, ambient-noise adjust first, transcribe, then send through the same pipeline as text.
- Handle "didn't catch that" and microphone errors gracefully without crashing.
- Strip an optional leading "Charlie" / "Hey Charlie" from the transcript.

### 7.7 Configuration (`config/settings.yaml`)
```yaml
speak_responses: true
volume_step: 10
brightness_step: 10
default_browser: null        # e.g. "Google Chrome"
voice_listen_seconds: 8
use_llm_fallback: true
```

### 7.8 Environment (`.env.example`)
```
ANTHROPIC_API_KEY=
CHARLIE_MODEL=claude-sonnet-5
```

---

## 8. Build Phases

Complete each phase, run its tests, and confirm it works before moving to the next.

**Phase 1 — Text-only core**
- Project skeleton, config loading, schema, rule-based brain, router, all action handlers, terminal loop, speaker output.
- Done when every example phrase in section 3.1 works from the terminal.

**Phase 2 — Voice input**
- Push-to-talk voice mode feeding the same pipeline.
- Done when I can say "open spotify" and "set volume to 30" and they run.

**Phase 3 — LLM brain + wake word**
- LLM fallback parser with strict JSON validation.
- Wake word "Hey Charlie" running in the background.
- Done when odd phrasings like "make it a bit louder" and "can you pull up youtube for me" work.

**Phase 4 — Menu-bar app (Completed)**
- `rumps` menu-bar icon with:
  - 🎙️ Push-to-Talk voice command
  - 💬 Interactive modal dialog for typing commands
  - ⚡ Real-time background "Hey Charlie" wake word toggle
  - 🔊 Spoken voice responses mute/unmute toggle
  - 🚀 Launch at login manager via LaunchAgent plist
  - 🔔 Native macOS Notification Center banner feedback
- Done when Charlie runs persistently from the menu bar without blocking the GUI.

---

## 9. Setup & Run (write this into the final README too)

```bash
# 1. Install system dependencies
brew install portaudio brightness

# 2. Create environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure
cp .env.example .env        # add GEMINI_API_KEY for the LLM brain & live search

# 4. Run options
python -m charlie.main --app        # Launch native macOS menu-bar app (Phase 4)
python -m charlie.main              # Interactive terminal loop
python -m charlie.main -c "..."     # One-shot command (e.g. "what's the temperature in Delhi")
python -m charlie.main -V           # One-shot voice command
python -m charlie.main -w           # Dedicated background wake-word listener
```

**macOS permissions to grant** (System Settings -> Privacy & Security):
- **Microphone** -> for voice input
- **Accessibility** -> for brightness/media key fallbacks
- **Automation** -> when prompted for System Events

---

## 10. Testing & Acceptance Criteria

### Automated (`pytest`)
- `test_rules.py`: at least 40 sample phrases map to the correct action and params (include typos, casing, and filler words like "please", "can you", "hey charlie").
- `test_schema.py`: invalid actions or out-of-range values become `unknown`.
- `test_router.py`: handlers are called with the right arguments (mock `subprocess`).
- `test_web.py`: URLs are built and encoded correctly (e.g. "iphone 15 case" -> `iphone+15+case`).

### Manual checklist
- [ ] "open safari" opens Safari
- [ ] "open amazon and search for wireless earbuds" opens the Amazon results page
- [ ] "search for pizza places near me" opens Google results
- [ ] "volume up" / "volume down" changes volume by the configured step
- [ ] "set volume to 25" sets exactly 25
- [ ] "mute" then "unmute" restores the previous level
- [ ] "brightness up" / "brightness down" visibly changes the screen
- [ ] "pause" / "play" / "next" control a playing song
- [ ] Gibberish input gives a friendly "I didn't understand" and does not crash
- [ ] Voice and text produce identical results for the same sentence

---

## 11. Rules & Constraints

1. **Whitelist only.** Charlie may only run actions defined in section 4.1. No `shell=True`, no `eval`/`exec`, no running commands generated by an LLM.
2. **Never hard-code secrets.** API keys come from `.env`, and `.env` is in `.gitignore`.
3. **Fail gracefully.** Every handler catches its own errors and returns a short human-readable message; the main loop never crashes.
4. **Small, typed, documented code.** Use type hints and short docstrings. One responsibility per module.
5. **No heavy dependencies** beyond those listed in section 5 without asking me first.
6. **Everything configurable** (step sizes, sites, browser) lives in the YAML files, not in code.
7. **Ask before destructive actions.** No file deletion, shutdown, restart or sleep actions in this version.
8. **Keep it macOS-only.** Do not add Windows/Linux code paths.

---

## 12. Future Ideas (do not build yet)

- Open specific files/folders ("open my Downloads folder")
- Set timers and reminders
- Wi-Fi / Bluetooth / Do Not Disturb toggles
- Screenshot and screen-recording commands
- Send a WhatsApp/iMessage through AppleScript
- Multi-step commands ("open spotify and play my liked songs")
- Conversation memory ("do that again")

---

## 13. First Message to Give the Agent

Paste this into Antigravity along with this README:

> Read README.md fully. Start with **Phase 1** only. Create the full project structure, implement everything needed for Phase 1, write the pytest tests, run them, and show me the results. Then stop and wait for my confirmation before starting Phase 2.
