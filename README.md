# Macro Recorder

A lightweight macOS desktop application to record and replay mouse movements, clicks, scrolls, and keystrokes. Built with Python, Tkinter, and native macOS Quartz event taps.

![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)
![macOS](https://img.shields.io/badge/platform-macOS-lightgrey)

## Features

- **Record** mouse movement, clicks, scrolls, and keyboard input
- **Replay** macros at configurable speed (0.5x, 1x, 2x, etc.)
- **Loop playback** a set number of times or infinitely
- **Trim tail** automatically removes the last N seconds of a recording to discard the "stop" button click
- **Save & Load** macros as JSON files for reuse
- **Minimal UI** built with Tkinter — no extra dependencies beyond pyobjc

## Requirements

- macOS (uses Quartz event taps)
- Python 3.12+
- **Accessibility permissions** — your terminal or IDE must be granted access in **System Settings > Privacy & Security > Accessibility**

## Installation

```bash
# Clone the repository
git clone https://github.com/edyuto/macro-recorder.git
cd macro-recorder

# Create a virtual environment
python3 -m venv env
source env/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
source env/bin/activate
python app.py
```

### Controls

| Control | Description |
|---|---|
| **Record / Stop Recording** | Start or stop capturing mouse and keyboard events |
| **Trim tail (s)** | Seconds to trim from the end of a recording (default `0.5`) to remove the stop-button click |
| **Speed** | Playback speed multiplier (e.g. `2.0` = twice as fast) |
| **Repeat** | Number of times to replay (`0` = infinite loop) |
| **Play** | Start playback |
| **Stop** | Interrupt playback at any time |
| **Save** | Export the current macro to a JSON file |
| **Load** | Import a previously saved macro |

## Project Structure

```
macro-recorder/
├── app.py             # Tkinter UI
├── recorder.py        # Core recording and playback engine (Quartz)
├── requirements.txt   # Python dependencies
└── README.md
```

## How It Works

- **Recording** — Creates a Quartz `CGEventTap` in listen-only mode to capture all HID events (mouse and keyboard) with timestamps.
- **Playback** — Replays events using `CGEventPost` to synthesize mouse and keyboard input at the OS level, respecting the original timing scaled by the speed multiplier.
- **Trim** — On stop, removes all events within the last N seconds of the recording to cleanly cut off the stop-button interaction.
