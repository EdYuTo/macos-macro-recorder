# Playlist with Random Advance — Design

Date: 2026-06-20

## Goal

Let the user build a list of saved recordings and play them continuously.
After each recording finishes, a random recording is picked next (may repeat
the same one). Playback loops endlessly until Stop.

## Scope

- Playlist items are loaded from saved `.json` recordings on disk.
- Random pick after each item finishes (random per advance, repeats allowed).
- Speed multiplier applies to each recording. There is no per-item repeat
  count; the playlist itself loops until Stop.
- A new Playlist UI section sits beside the existing Record/Playback/File
  controls; the existing single-recording Play is unchanged.

## Non-Goals

- No sequential / shuffle-toggle modes (random-pick only).
- No reordering of the listbox.
- No persistence of the playlist between app runs.

## Architecture

One player is active at a time. Single Play and Play Playlist share the same
`_stop_playback` flag, `playing` flag, and Stop path. No second thread model.

### `recorder.py`

1. **Extract `_play_once(events, speed)`** — runs through one event list,
   respecting `_stop_playback`, sleeping `(event["time"] - last_time) / speed`
   between events, calling `_execute_event`. This is the body of the current
   per-pass loop inside `play`.

2. **`play(speed=1.0, repeat=1, on_done=None)`** — unchanged behavior.
   Refactored to loop `repeat` times (or infinite when `repeat == 0`) calling
   `_play_once(self.events, speed)`, breaking on `_stop_playback`. Resets
   `playing`, `_pressed_button`, and calls `on_done` when finished.

3. **`play_playlist(recordings, speed=1.0, on_done=None)`** — new.
   - Sets `_stop_playback = False`, `playing = True`, `_pressed_button = None`.
   - Spawns a daemon thread that loops:
     `while not _stop_playback: pick = random.choice(recordings); _play_once(pick["events"], speed)`.
   - On exit: `playing = False`, `_pressed_button = None`, call `on_done`.
   - Each `recordings` entry is a dict with at least an `"events"` key.

4. **`load_events(filepath)`** — new `@staticmethod`. Reads JSON and returns the
   event list without touching `self.events`, so adding to the playlist does not
   clobber the in-memory recording.

`stop_playback()`, `_execute_event`, `_pressed_button` drag handling, and
save/load stay as they are. `import random` added.

### `app.py`

New Playlist `LabelFrame` placed after the File frame (or before — beside the
existing sections):

- `tk.Listbox` showing recording names.
- `self.playlist` — list of `{"name": <basename>, "events": <list>}` parallel
  to listbox rows.
- Buttons:
  - **Add** — `filedialog.askopenfilename` → `MacroRecorder.load_events(path)`
    → append `{"name": os.path.basename(path), "events": events}` → insert name
    into listbox.
  - **Remove** — remove the selected listbox row and its `self.playlist` entry.
  - **Clear** — empty listbox and `self.playlist`.
  - **Play Playlist** — `_play_playlist`.
  - **Stop** — shared stop (reuses `recorder.stop_playback`).

### Playback control flow

- `_play_playlist`:
  - If `self.playlist` empty → `messagebox.showwarning`, return.
  - Parse/validate Speed via the existing validation (speed > 0).
  - Disable Add/Remove/Clear, single Play, and Play Playlist; enable Stop.
  - Status → "Playing playlist...".
  - `recorder.play_playlist(self.playlist, speed=speed, on_done=self._on_playback_done)`.
- `_on_playback_done` / `_reset_play_buttons` re-enable Add/Remove/Clear, single
  Play, and Play Playlist; disable Stop. Both single and playlist playback route
  through this.
- The existing single `_play` also disables the playlist buttons while running so
  only one player can start.

## Data Flow

disk `.json` → `load_events` → `{name, events}` appended to `self.playlist`
→ Play Playlist → `play_playlist` random-pick loop → `_play_once` → existing
`_execute_event` posts events via Quartz.

## Error Handling

- Bad/unreadable JSON on Add → `messagebox.showerror`, skip the file.
- Empty playlist on Play Playlist → `messagebox.showwarning`.
- Invalid Speed → existing error path reused.

## Testing

Unit (no real Quartz posting; mock `_play_once` / `_execute_event`):

- `play_playlist` picks entries from the supplied list and stops when
  `_stop_playback` is set (assert `_play_once` called with picked events,
  loop terminates on flag).
- `load_events` returns the file's events and does NOT mutate `self.events`.
- `play` still loops `repeat` times via the refactored `_play_once`.

Manual:

- Load 2–3 macros into the playlist, Play Playlist, confirm recordings play and
  advance to a randomly chosen next one, and Stop halts immediately.
- Remove / Clear behave correctly; buttons enable/disable as expected.
