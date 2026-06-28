# Playlist Now-Playing Label Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the name of the recording currently playing from a playlist in the UI.

**Architecture:** The playback worker thread in `play_playlist` already picks a random recording per cycle. Expose its name as `MacroRecorder.current_name`; the existing `_poll_cycles` UI poll renders it in a new dedicated label. Single `play()` clears the name so the label stays blank.

**Tech Stack:** Python, Tkinter, pytest.

## Global Constraints

- No new third-party dependencies.
- Codebase uses no type hints — follow that pattern.
- `current_name` is a plain attribute (atomic assignment under the GIL, like the existing `_stop_playback`/`aborted` flags) — no lock.
- Existing tests must keep passing.

---

### Task 1: Expose `current_name` on the recorder

**Files:**
- Modify: `recorder.py` (`__init__` ~line 78-84; `play` ~line 232-234; `play_playlist` ~line 257-271)
- Test: `tests/test_recorder.py`

**Interfaces:**
- Produces: `MacroRecorder.current_name` — `None` when no named playback is active, otherwise the picked recording's `name` string. Set to the picked `name` inside the `play_playlist` loop immediately before each `_play_once` call; set to `None` at the start of both `play` and `play_playlist`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_recorder.py`:

```python
def test_play_playlist_sets_current_name(monkeypatch):
    rec = MacroRecorder()
    recordings = [
        {"name": "alpha.json", "events": [{"time": 0}]},
        {"name": "beta.json", "events": [{"time": 0}]},
    ]
    monkeypatch.setattr("recorder.random.choice", lambda seq: seq[1])

    seen = []

    def fake_once(events, speed):
        seen.append(rec.current_name)
        rec._stop_playback = True

    monkeypatch.setattr(rec, "_play_once", fake_once)

    done = threading.Event()
    rec.play_playlist(recordings, speed=1.0, on_done=done.set)

    assert done.wait(2)
    assert seen == ["beta.json"]


def test_play_clears_current_name(monkeypatch):
    rec = MacroRecorder()
    rec.current_name = "stale.json"  # leftover from a previous playlist run
    monkeypatch.setattr(rec, "_play_once", lambda ev, sp: None)

    rec.events = [{"time": 0}]
    done = threading.Event()
    rec.play(speed=1.0, repeat=1, on_done=done.set)

    assert done.wait(2)
    assert rec.current_name is None
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `pytest tests/test_recorder.py -k "current_name" -v`
Expected: FAIL (`AttributeError: 'MacroRecorder' object has no attribute 'current_name'`, and the playlist test sees `None` instead of `"beta.json"`).

- [ ] **Step 3: Initialize the attribute**

In `recorder.py` `__init__`, after `self.aborted = False` (line ~83):

```python
        self.current_name = None
```

- [ ] **Step 4: Clear it in `play`**

In `play`, after `self.aborted = False` (line ~234):

```python
        self.current_name = None
```

- [ ] **Step 5: Set it in `play_playlist`**

In `play_playlist`, after `self.aborted = False` (line ~259):

```python
        self.current_name = None
```

Then in the `play_playlist` worker loop, change:

```python
                    pick = random.choice(recordings)
                    self._play_once(pick["events"], speed)
```

to:

```python
                    pick = random.choice(recordings)
                    self.current_name = pick["name"]
                    self._play_once(pick["events"], speed)
```

- [ ] **Step 6: Run tests, verify they pass**

Run: `pytest tests/test_recorder.py -k "current_name" -v`
Expected: PASS (2 tests).

- [ ] **Step 7: Run full suite**

Run: `pytest -v`
Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add recorder.py tests/test_recorder.py
git commit -m "Expose current_name of playing playlist item"
```

---

### Task 2: Show the now-playing label in the UI

**Files:**
- Modify: `app.py` (`_build_ui` cycle label ~line 31-32; `_poll_cycles` ~line 125-135)

**Interfaces:**
- Consumes: `self.recorder.current_name` (`None` or a name string) and `self.recorder.playing` from Task 1.

No automated test — Tkinter UI strings are verified manually (launch the app). The implementer should confirm `pytest -v` still passes (app.py must still import) and skip launching the GUI.

- [ ] **Step 1: Add the label widget**

In `app.py` `_build_ui`, directly after the cycle label (line ~31-32):

```python
        self.cycle_var = tk.StringVar(value="")
        tk.Label(self.root, textvariable=self.cycle_var).pack()
```

add:

```python
        self.now_playing_var = tk.StringVar(value="")
        tk.Label(self.root, textvariable=self.now_playing_var).pack()
```

- [ ] **Step 2: Render it in `_poll_cycles`**

Replace the `_poll_cycles` method (line ~125-135) with:

```python
    def _poll_cycles(self):
        if self.recorder.playing:
            total = self.recorder.repeat_total
            done = self.recorder.repeat_done
            if total == 0:
                self.cycle_var.set(f"Cycle {done + 1} (infinite)")
            else:
                self.cycle_var.set(f"Cycles left: {total - done}")
            if self.recorder.current_name:
                self.now_playing_var.set(f"Now playing: {self.recorder.current_name}")
            else:
                self.now_playing_var.set("")
            self.root.after(200, self._poll_cycles)
        else:
            self.cycle_var.set("")
            self.now_playing_var.set("")
```

- [ ] **Step 3: Confirm the suite still passes**

Run: `pytest -v`
Expected: all tests pass (app.py imports cleanly).

- [ ] **Step 4: Manual smoke check**

Run: `python app.py`
Add ≥2 recordings to the playlist, Play Playlist. Expected: a "Now playing: <name>" line appears and updates as the random advance moves between items; it clears when playback stops. Run a single-macro Play: the line stays blank.

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "Show now-playing recording name in UI"
```

---

### Task 3: Full regression run

**Files:** none (verification only).

- [ ] **Step 1: Run the whole suite**

Run: `pytest -v`
Expected: all tests pass.

- [ ] **Step 2: Commit only if something needed fixing**

If a pre-existing test broke and you corrected it, commit that fix with a clear message. Otherwise nothing to commit.
