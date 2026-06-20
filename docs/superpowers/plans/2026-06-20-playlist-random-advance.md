# Playlist with Random Advance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a playlist of saved recordings that plays continuously, picking a random recording each time the previous one finishes, until Stop.

**Architecture:** Refactor `recorder.py` so a single event-list run is a reusable method (`_play_once`), then build both the existing `play` and a new `play_playlist` on top of it. One player is active at a time, sharing `_stop_playback`/`playing` state. `app.py` gains a Playlist section (listbox + Add/Remove/Clear/Play Playlist/Stop) beside the existing controls.

**Tech Stack:** Python 3.12+, Tkinter, pyobjc/Quartz, pytest (new dev dependency).

## Global Constraints

- macOS only (Quartz event taps); Python 3.12+.
- Random-pick advance only — no sequential/shuffle-toggle modes, no listbox reordering, no playlist persistence between runs.
- Speed multiplier applies per recording; playlist has no per-item repeat count and loops until Stop.
- Existing single-recording `play(speed, repeat, on_done)` behavior must stay unchanged.
- Tests must NOT post real Quartz events — mock `_execute_event` / `_play_once`.
- Run python/pytest via the venv: `env/bin/python`, `env/bin/pytest`.

---

### Task 1: Test scaffold + `load_events`

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_recorder.py`
- Modify: `requirements.txt` (add `pytest==8.3.4`)
- Modify: `recorder.py` (add `load_events` staticmethod)

**Interfaces:**
- Produces: `MacroRecorder.load_events(filepath: str) -> list` — reads JSON, returns event list, does NOT mutate `self.events`.

- [ ] **Step 1: Add pytest to requirements and install**

Add this line to the end of `requirements.txt`:

```
pytest==8.3.4
```

Run: `env/bin/pip install pytest==8.3.4`
Expected: pytest installed.

- [ ] **Step 2: Create empty test package init**

Create `tests/__init__.py` (empty file).

- [ ] **Step 3: Write the failing test**

Create `tests/test_recorder.py`:

```python
import json
from recorder import MacroRecorder


def test_load_events_returns_without_mutating(tmp_path):
    rec = MacroRecorder()
    rec.events = [{"type": "move", "x": 1, "y": 2, "time": 0}]

    p = tmp_path / "macro.json"
    p.write_text(json.dumps([{"type": "key_press", "keycode": 5, "time": 0}]))

    loaded = MacroRecorder.load_events(str(p))

    assert loaded == [{"type": "key_press", "keycode": 5, "time": 0}]
    assert rec.events == [{"type": "move", "x": 1, "y": 2, "time": 0}]
```

- [ ] **Step 4: Run test to verify it fails**

Run: `env/bin/pytest tests/test_recorder.py::test_load_events_returns_without_mutating -v`
Expected: FAIL — `AttributeError: ... has no attribute 'load_events'`.

- [ ] **Step 5: Implement `load_events`**

In `recorder.py`, inside class `MacroRecorder`, in the `# ── Save / Load ──` section after `load`, add:

```python
    @staticmethod
    def load_events(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `env/bin/pytest tests/test_recorder.py::test_load_events_returns_without_mutating -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt tests/__init__.py tests/test_recorder.py recorder.py
git commit -m "Add pytest scaffold and load_events staticmethod"
```

---

### Task 2: Extract `_play_once`, refactor `play`

**Files:**
- Modify: `recorder.py` (`play` method ~lines 179-204)
- Test: `tests/test_recorder.py`

**Interfaces:**
- Consumes: existing `_execute_event`, `_stop_playback`, `playing`, `_pressed_button`.
- Produces:
  - `MacroRecorder._play_once(events: list, speed: float) -> None` — runs one pass through `events`, sleeping `(event["time"] - last_time) / speed` between events, calling `_execute_event`, breaking on `_stop_playback`.
  - `play(speed=1.0, repeat=1, on_done=None)` — unchanged behavior, now loops calling `_play_once(self.events, speed)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_recorder.py`:

```python
import threading


def test_play_once_executes_each_event(monkeypatch):
    rec = MacroRecorder()
    executed = []
    monkeypatch.setattr(rec, "_execute_event", lambda e: executed.append(e))

    events = [{"time": 0}, {"time": 0}, {"time": 0}]
    rec._play_once(events, speed=1.0)

    assert executed == events


def test_play_once_stops_on_flag(monkeypatch):
    rec = MacroRecorder()
    executed = []

    def fake_exec(e):
        executed.append(e)
        rec._stop_playback = True

    monkeypatch.setattr(rec, "_execute_event", fake_exec)

    events = [{"time": 0}, {"time": 0}, {"time": 0}]
    rec._play_once(events, speed=1.0)

    assert len(executed) == 1


def test_play_loops_repeat_times(monkeypatch):
    rec = MacroRecorder()
    calls = []
    monkeypatch.setattr(rec, "_play_once", lambda ev, sp: calls.append((ev, sp)))

    rec.events = [{"time": 0}]
    done = threading.Event()
    rec.play(speed=2.0, repeat=3, on_done=done.set)

    assert done.wait(2)
    assert len(calls) == 3
    assert all(sp == 2.0 for _, sp in calls)
    assert rec.playing is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `env/bin/pytest tests/test_recorder.py -v -k "play_once or loops_repeat"`
Expected: FAIL — `_play_once` does not exist.

- [ ] **Step 3: Implement `_play_once` and refactor `play`**

In `recorder.py`, replace the entire current `play` method:

```python
    def play(self, speed=1.0, repeat=1, on_done=None):
        self._stop_playback = False
        self.playing = True
        self._pressed_button = None

        def _run():
            count = 0
            infinite = repeat == 0
            while (infinite or count < repeat) and not self._stop_playback:
                last_time = 0
                for event in self.events:
                    if self._stop_playback:
                        break
                    delay = (event["time"] - last_time) / speed
                    if delay > 0:
                        time.sleep(delay)
                    last_time = event["time"]
                    self._execute_event(event)
                count += 1
            self.playing = False
            self._pressed_button = None
            if on_done:
                on_done()

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
```

with:

```python
    def _play_once(self, events, speed):
        last_time = 0
        for event in events:
            if self._stop_playback:
                break
            delay = (event["time"] - last_time) / speed
            if delay > 0:
                time.sleep(delay)
            last_time = event["time"]
            self._execute_event(event)

    def play(self, speed=1.0, repeat=1, on_done=None):
        self._stop_playback = False
        self.playing = True
        self._pressed_button = None

        def _run():
            count = 0
            infinite = repeat == 0
            while (infinite or count < repeat) and not self._stop_playback:
                self._play_once(self.events, speed)
                count += 1
            self.playing = False
            self._pressed_button = None
            if on_done:
                on_done()

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `env/bin/pytest tests/test_recorder.py -v`
Expected: PASS (all tests, including Task 1).

- [ ] **Step 5: Commit**

```bash
git add recorder.py tests/test_recorder.py
git commit -m "Extract _play_once and refactor play on top of it"
```

---

### Task 3: `play_playlist`

**Files:**
- Modify: `recorder.py` (add `import random`; add `play_playlist` after `play`)
- Test: `tests/test_recorder.py`

**Interfaces:**
- Consumes: `_play_once`, `_stop_playback`, `playing`, `_pressed_button`.
- Produces: `MacroRecorder.play_playlist(recordings: list[dict], speed=1.0, on_done=None) -> None` — spawns a daemon thread that loops `while not _stop_playback: pick = random.choice(recordings); _play_once(pick["events"], speed)`. Each `recordings` entry is a dict with an `"events"` key. On exit sets `playing=False`, resets `_pressed_button`, calls `on_done`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_recorder.py`:

```python
def test_play_playlist_picks_events_and_stops(monkeypatch):
    rec = MacroRecorder()
    recordings = [
        {"name": "a", "events": [{"time": 0}]},
        {"name": "b", "events": [{"time": 0}]},
    ]

    monkeypatch.setattr("recorder.random.choice", lambda seq: seq[0])

    picked = []

    def fake_once(events, speed):
        picked.append((events, speed))
        rec._stop_playback = True

    monkeypatch.setattr(rec, "_play_once", fake_once)

    done = threading.Event()
    rec.play_playlist(recordings, speed=1.5, on_done=done.set)

    assert done.wait(2)
    assert picked == [([{"time": 0}], 1.5)]
    assert rec.playing is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `env/bin/pytest tests/test_recorder.py::test_play_playlist_picks_events_and_stops -v`
Expected: FAIL — `play_playlist` does not exist (and `recorder.random` not importable).

- [ ] **Step 3: Add `import random`**

In `recorder.py`, add to the top-level imports (after `import threading`):

```python
import random
```

- [ ] **Step 4: Implement `play_playlist`**

In `recorder.py`, immediately after the `play` method, add:

```python
    def play_playlist(self, recordings, speed=1.0, on_done=None):
        self._stop_playback = False
        self.playing = True
        self._pressed_button = None

        def _run():
            while not self._stop_playback:
                pick = random.choice(recordings)
                self._play_once(pick["events"], speed)
            self.playing = False
            self._pressed_button = None
            if on_done:
                on_done()

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `env/bin/pytest tests/test_recorder.py -v`
Expected: PASS (all tests).

- [ ] **Step 6: Commit**

```bash
git add recorder.py tests/test_recorder.py
git commit -m "Add play_playlist with random advance"
```

---

### Task 4: Playlist UI in `app.py`

**Files:**
- Modify: `app.py` (add `import os`; add Playlist frame in `_build_ui`; add handlers; update button-enable/disable logic)

**Interfaces:**
- Consumes: `MacroRecorder.load_events`, `MacroRecorder.play_playlist`, `recorder.stop_playback`, existing `_reset_play_buttons`, `_on_playback_done`, `speed_var`.
- Produces: GUI only; no callers. Manual verification.

This task is GUI wiring (Tkinter), verified manually rather than by unit test.

- [ ] **Step 1: Add `os` import**

In `app.py`, add after the existing imports:

```python
import os
```

- [ ] **Step 2: Add the Playlist frame to `_build_ui`**

In `app.py`, at the end of `_build_ui` (after the File frame block), add:

```python
        # -- Playlist controls --
        pl_frame = tk.LabelFrame(self.root, text="Playlist", padx=8, pady=6)
        pl_frame.pack(fill="x", padx=10, pady=6)

        self.playlist = []  # list of {"name", "events"}

        self.playlist_box = tk.Listbox(pl_frame, height=5)
        self.playlist_box.pack(fill="x", padx=4, pady=4)

        pl_btns = tk.Frame(pl_frame)
        pl_btns.pack(fill="x", pady=2)

        self.btn_pl_add = tk.Button(pl_btns, text="Add", width=8, command=self._playlist_add)
        self.btn_pl_add.pack(side="left", padx=2)
        self.btn_pl_remove = tk.Button(pl_btns, text="Remove", width=8, command=self._playlist_remove)
        self.btn_pl_remove.pack(side="left", padx=2)
        self.btn_pl_clear = tk.Button(pl_btns, text="Clear", width=8, command=self._playlist_clear)
        self.btn_pl_clear.pack(side="left", padx=2)

        self.btn_pl_play = tk.Button(pl_btns, text="Play Playlist", width=14, command=self._play_playlist)
        self.btn_pl_play.pack(side="left", padx=2)
```

Note: the Playlist uses the shared **Stop** button (`self.btn_stop`) already defined in the Playback frame.

- [ ] **Step 3: Add the Add/Remove/Clear handlers**

In `app.py`, add these methods to the class (e.g. after `_load`):

```python
    def _playlist_add(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            events = MacroRecorder.load_events(path)
        except Exception as e:
            messagebox.showerror("Load error", str(e))
            return
        name = os.path.basename(path)
        self.playlist.append({"name": name, "events": events})
        self.playlist_box.insert("end", name)

    def _playlist_remove(self):
        sel = self.playlist_box.curselection()
        if not sel:
            return
        idx = sel[0]
        self.playlist_box.delete(idx)
        del self.playlist[idx]

    def _playlist_clear(self):
        self.playlist_box.delete(0, "end")
        self.playlist.clear()
```

- [ ] **Step 4: Add the `_play_playlist` handler**

In `app.py`, add this method:

```python
    def _play_playlist(self):
        if not self.playlist:
            messagebox.showwarning("Empty playlist", "Add recordings to the playlist first.")
            return
        try:
            speed = float(self.speed_var.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Speed must be a number.")
            return
        if speed <= 0:
            messagebox.showerror("Invalid input", "Speed must be greater than 0.")
            return

        self.btn_play.config(state="disabled")
        self.btn_pl_play.config(state="disabled")
        self.btn_pl_add.config(state="disabled")
        self.btn_pl_remove.config(state="disabled")
        self.btn_pl_clear.config(state="disabled")
        self.btn_stop.config(state="normal")
        self._update_status(f"Playing playlist ({len(self.playlist)} items @ {speed}x)...")

        self.recorder.play_playlist(self.playlist, speed=speed, on_done=self._on_playback_done)
```

- [ ] **Step 5: Re-enable playlist buttons on reset, and disable them during single play**

In `app.py`, edit `_reset_play_buttons` to re-enable the playlist controls. Replace:

```python
    def _reset_play_buttons(self):
        self.btn_play.config(state="normal")
        self.btn_stop.config(state="disabled")
        self._update_status("Playback finished")
```

with:

```python
    def _reset_play_buttons(self):
        self.btn_play.config(state="normal")
        self.btn_pl_play.config(state="normal")
        self.btn_pl_add.config(state="normal")
        self.btn_pl_remove.config(state="normal")
        self.btn_pl_clear.config(state="normal")
        self.btn_stop.config(state="disabled")
        self._update_status("Playback finished")
```

Then, in `_play` (single playback), after the line `self.btn_stop.config(state="normal")`, add:

```python
        self.btn_pl_play.config(state="disabled")
```

so the playlist cannot be started while a single recording plays.

- [ ] **Step 6: Verify recorder tests still pass**

Run: `env/bin/pytest tests/test_recorder.py -v`
Expected: PASS (no regressions).

- [ ] **Step 7: Manual verification**

Run: `env/bin/python app.py`

Check:
- Playlist section appears with a listbox and Add/Remove/Clear/Play Playlist buttons.
- **Add** twice with two saved `.json` macros (e.g. `recordings/test-drag.json`) → both names appear.
- **Play Playlist** → recordings play and, after each finishes, a randomly chosen next one starts. Add/Remove/Clear and both Play buttons disable; Stop enables.
- **Stop** halts immediately and re-enables all buttons.
- **Remove** deletes the selected row; **Clear** empties the list.
- **Play Playlist** with an empty list → warning dialog.

- [ ] **Step 8: Commit**

```bash
git add app.py
git commit -m "Add playlist UI with random-advance playback"
```

---

### Task 5: Update README

**Files:**
- Modify: `README.md` (Features list + Controls table)

- [ ] **Step 1: Add a Features bullet**

In `README.md`, in the Features list, add after the "Loop playback" bullet:

```markdown
- **Playlist** — queue multiple saved recordings and play them continuously, picking a random one each time the previous finishes
```

- [ ] **Step 2: Add Controls rows**

In `README.md`, in the Controls table, add these rows before the **Save** row:

```markdown
| **Add / Remove / Clear** | Manage the playlist of saved recordings |
| **Play Playlist** | Play recordings continuously, randomly picking the next each time one finishes (uses the Speed setting; Stop to halt) |
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Document playlist feature in README"
```

---

## Self-Review Notes

- **Spec coverage:** load-from-JSON (Task 1 `load_events`, Task 4 Add); random pick each advance (Task 3 `play_playlist`); speed applies / no repeat / endless until Stop (Task 3 + Task 4); new Playlist section beside existing controls (Task 4); single play unchanged (Task 2); error handling — bad JSON (Task 4 Step 3), empty playlist (Task 4 Step 4), invalid speed (Task 4 Step 4); tests for `play_playlist` + `load_events` (Tasks 1, 3). All covered.
- **Type consistency:** `play_playlist(recordings, speed, on_done)` with `pick["events"]` matches `self.playlist` entries `{"name", "events"}` built in `_playlist_add`. `load_events` returns a list, used directly as `events`. `_play_once(events, speed)` signature consistent across `play`, `play_playlist`, and tests.
- **No placeholders:** every code/test step shows full code.
