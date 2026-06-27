# Global Abort Hotkey Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user abort playback at any time by physically pressing Esc, regardless of which app has focus.

**Architecture:** Poll the physical keyboard with `CGEventSourceKeyState(kCGEventSourceStateHIDSystemState, ESC_KEYCODE)` from inside the playback loop. Inter-event sleeps run in ≤50ms chunks so the abort key is checked within ~50ms. Reading hardware state means replayed/synthetic Esc events in a macro never trigger the abort — only a real keypress does.

**Tech Stack:** Python, Quartz (pyobjc), Tkinter, pytest.

## Global Constraints

- No new third-party dependencies.
- Abort key is Esc, keycode `53`, hardcoded.
- Abort poll chunk size: at most `0.05` seconds (50ms).
- Hardware state source: `kCGEventSourceStateHIDSystemState`.
- Existing tests must keep passing.

---

### Task 1: Abort key detection + interruptible sleep in recorder

**Files:**
- Modify: `recorder.py` (imports near lines 5-40; `__init__` lines 72-84; `_play_once` lines 182-191)
- Test: `tests/test_recorder.py`

**Interfaces:**
- Consumes: existing `self._stop_playback` flag.
- Produces:
  - `MacroRecorder.aborted: bool` — set True only on physical-Esc abort.
  - `MacroRecorder._abort_key_pressed() -> bool`
  - `MacroRecorder._interruptible_sleep(seconds: float) -> None`
  - `ESC_KEYCODE = 53` module constant.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_recorder.py`:

```python
# ── Global abort hotkey ───────────────────────────────────────────────────────

def test_abort_key_pressed_reads_hid_state(monkeypatch):
    rec = MacroRecorder()
    seen = {}

    def fake_state(source, keycode):
        seen["source"] = source
        seen["keycode"] = keycode
        return True

    monkeypatch.setattr(recorder_mod, "CGEventSourceKeyState", fake_state)

    assert rec._abort_key_pressed() is True
    assert seen["source"] == recorder_mod.kCGEventSourceStateHIDSystemState
    assert seen["keycode"] == recorder_mod.ESC_KEYCODE


def test_interruptible_sleep_returns_early_on_stop_flag(monkeypatch):
    rec = MacroRecorder()
    slept = []
    monkeypatch.setattr(recorder_mod.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(rec, "_abort_key_pressed", lambda: False)

    rec._stop_playback = True
    rec._interruptible_sleep(1.0)

    assert slept == []  # returned before sleeping


def test_interruptible_sleep_aborts_on_key(monkeypatch):
    rec = MacroRecorder()
    slept = []
    monkeypatch.setattr(recorder_mod.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(rec, "_abort_key_pressed", lambda: True)

    rec._interruptible_sleep(1.0)

    assert rec._stop_playback is True
    assert rec.aborted is True
    assert len(slept) <= 1  # stopped at the first chunk


def test_interruptible_sleep_completes_full_duration(monkeypatch):
    rec = MacroRecorder()
    slept = []
    monkeypatch.setattr(recorder_mod.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(rec, "_abort_key_pressed", lambda: False)

    rec._interruptible_sleep(0.12)

    assert rec._stop_playback is False
    assert abs(sum(slept) - 0.12) < 1e-9
    assert all(s <= 0.05 + 1e-9 for s in slept)


def test_play_once_aborts_on_key(monkeypatch):
    rec = MacroRecorder()
    executed = []
    monkeypatch.setattr(rec, "_execute_event", lambda e: executed.append(e))
    # abort fires after the first event is executed
    states = iter([False, True, True, True])
    monkeypatch.setattr(rec, "_abort_key_pressed", lambda: next(states))

    events = [{"time": 0}, {"time": 0}, {"time": 0}]
    rec._play_once(events, speed=1.0)

    assert len(executed) == 1
    assert rec.aborted is True
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `pytest tests/test_recorder.py -k "abort or interruptible" -v`
Expected: FAIL (`AttributeError` / `ImportError`: `_abort_key_pressed`, `_interruptible_sleep`, `aborted`, `ESC_KEYCODE`, `CGEventSourceKeyState` not defined).

- [ ] **Step 3: Add imports and constant**

In `recorder.py`, add to the `from Quartz import (...)` block (anywhere inside the parens, e.g. after `kCGScrollWheelEventIsContinuous,`):

```python
    CGEventSourceKeyState,
    kCGEventSourceStateHIDSystemState,
```

After the import block, alongside the other module constants (near `MOUSE_BUTTON_LEFT`), add:

```python
# Abort hotkey: physical Esc key
ESC_KEYCODE = 53
```

- [ ] **Step 4: Add `aborted` flag**

In `MacroRecorder.__init__`, after `self._stop_playback = False`:

```python
        self.aborted = False
```

- [ ] **Step 5: Add abort + interruptible-sleep methods**

In `recorder.py`, just above `_play_once`, add:

```python
    def _abort_key_pressed(self):
        return bool(
            CGEventSourceKeyState(kCGEventSourceStateHIDSystemState, ESC_KEYCODE)
        )

    def _interruptible_sleep(self, seconds):
        remaining = seconds
        while remaining > 0:
            if self._stop_playback:
                return
            if self._abort_key_pressed():
                self._stop_playback = True
                self.aborted = True
                return
            step = remaining if remaining < 0.05 else 0.05
            time.sleep(step)
            remaining -= step
```

- [ ] **Step 6: Use them in `_play_once`**

Replace the body of `_play_once` (lines ~182-191) with:

```python
    def _play_once(self, events, speed):
        last_time = 0
        for event in events:
            if self._stop_playback:
                break
            if self._abort_key_pressed():
                self._stop_playback = True
                self.aborted = True
                break
            delay = (event["time"] - last_time) / speed
            if delay > 0:
                self._interruptible_sleep(delay)
                if self._stop_playback:
                    break
            last_time = event["time"]
            self._execute_event(event)
```

- [ ] **Step 7: Run tests, verify they pass**

Run: `pytest tests/test_recorder.py -k "abort or interruptible" -v`
Expected: PASS (5 tests).

- [ ] **Step 8: Commit**

```bash
git add recorder.py tests/test_recorder.py
git commit -m "Add physical-Esc abort polling to playback"
```

---

### Task 2: Reset `aborted` on each playback start

**Files:**
- Modify: `recorder.py` (`play` lines ~202-207; `play_playlist` lines ~226-231)
- Test: `tests/test_recorder.py`

**Interfaces:**
- Consumes: `self.aborted` from Task 1.
- Produces: `aborted` is `False` after a clean (non-Esc) playback run.

- [ ] **Step 1: Write failing test**

Add to `tests/test_recorder.py`:

```python
def test_play_resets_aborted_flag(monkeypatch):
    rec = MacroRecorder()
    rec.aborted = True  # stale from a previous run
    monkeypatch.setattr(rec, "_play_once", lambda ev, sp: None)

    rec.events = [{"time": 0}]
    done = threading.Event()
    rec.play(speed=1.0, repeat=1, on_done=done.set)

    assert done.wait(2)
    assert rec.aborted is False


def test_play_playlist_resets_aborted_flag(monkeypatch):
    rec = MacroRecorder()
    rec.aborted = True
    monkeypatch.setattr("recorder.random.choice", lambda seq: seq[0])
    monkeypatch.setattr(rec, "_play_once", lambda ev, sp: None)

    done = threading.Event()
    rec.play_playlist([{"name": "a", "events": [{"time": 0}]}],
                      speed=1.0, repeat=1, on_done=done.set)

    assert done.wait(2)
    assert rec.aborted is False
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `pytest tests/test_recorder.py -k "resets_aborted" -v`
Expected: FAIL (`aborted` stays `True` — not reset).

- [ ] **Step 3: Reset in `play`**

In `play`, after `self._stop_playback = False`:

```python
        self.aborted = False
```

- [ ] **Step 4: Reset in `play_playlist`**

In `play_playlist`, after `self._stop_playback = False`:

```python
        self.aborted = False
```

- [ ] **Step 5: Run tests, verify they pass**

Run: `pytest tests/test_recorder.py -k "resets_aborted" -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add recorder.py tests/test_recorder.py
git commit -m "Reset aborted flag on playback start"
```

---

### Task 3: Surface abort in the UI

**Files:**
- Modify: `app.py` (`_play` line ~157; `_reset_play_buttons` lines ~165-172; `_play_playlist` line ~256)

**Interfaces:**
- Consumes: `self.recorder.aborted` from Task 1.
- Produces: status text tells the user Esc aborts, and reports "Playback aborted" vs "Playback finished".

No automated test — Tkinter UI strings are verified manually (`run` skill / launch app).

- [ ] **Step 1: Mention hotkey in single-macro play status**

In `app.py` `_play`, replace:

```python
        self._update_status(f"Playing ({'infinite' if repeat == 0 else repeat}x @ {speed}x)...")
```

with:

```python
        self._update_status(
            f"Playing ({'infinite' if repeat == 0 else repeat}x @ {speed}x) — Esc to abort"
        )
```

- [ ] **Step 2: Mention hotkey in playlist play status**

In `_play_playlist`, replace:

```python
        self._update_status(f"Playing playlist ({len(self.playlist)} items, {reps} @ {speed}x)...")
```

with:

```python
        self._update_status(
            f"Playing playlist ({len(self.playlist)} items, {reps} @ {speed}x) — Esc to abort"
        )
```

- [ ] **Step 3: Report aborted vs finished**

In `_reset_play_buttons`, replace:

```python
        self._update_status("Playback finished")
```

with:

```python
        if self.recorder.aborted:
            self._update_status("Playback aborted")
        else:
            self._update_status("Playback finished")
```

- [ ] **Step 4: Manual smoke check**

Run: `python app.py`
Record a short macro, Play, press physical Esc mid-run. Expected: playback stops within ~50ms, status reads "Playback aborted". Let another run finish on its own; status reads "Playback finished".

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "Show Esc-abort hint and aborted status in UI"
```

---

### Task 4: Full regression run

**Files:** none (verification only).

- [ ] **Step 1: Run the whole suite**

Run: `pytest -v`
Expected: all tests pass, including the pre-existing ones.

- [ ] **Step 2: Commit only if something needed fixing**

If a pre-existing test broke and you corrected it, commit that fix with a clear message. Otherwise nothing to commit.
