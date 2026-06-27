# Global Abort Hotkey for Playback

## Problem

During playback the recorder moves and clicks the mouse and the app has no
focus, so the user cannot reliably click the Stop button or send a keystroke to
the Tkinter window to abort. We need an abort that works regardless of which
application is focused.

## Approach

Poll the **physical** keyboard state from inside the playback loop using
`Quartz.CGEventSourceKeyState(kCGEventSourceStateHIDSystemState, keycode)`. This
reads real hardware key state, so the synthetic key events the player posts
(including a replayed Esc inside a macro) do not register as the abort key —
only the user's actual physical press does.

Abort key: **Esc** (keycode 53).

Latency target: abort detected within ~50ms by chunking the inter-event sleeps.

No new dependencies. Accessibility permission is already required for recording.

### Alternatives considered

- **Second `CGEventTap` listener thread** (instant keydown callback). Rejected:
  more moving parts (extra thread + run loop), and replayed macro keys flow
  through the tap, risking a false abort unless filtered.

## Changes

### recorder.py

- New imports: `CGEventSourceKeyState`, `kCGEventSourceStateHIDSystemState`.
- Constant `ESC_KEYCODE = 53`.
- `self.aborted` flag, initialized in `__init__` and reset to `False` at the
  start of `play` and `play_playlist`, so the UI can distinguish a user abort
  from a natural finish.
- `_abort_key_pressed()` → returns
  `bool(CGEventSourceKeyState(kCGEventSourceStateHIDSystemState, ESC_KEYCODE))`.
- `_interruptible_sleep(seconds)`: sleeps in chunks of at most 50ms. Before and
  after each chunk it checks `_stop_playback` and `_abort_key_pressed()`. If the
  abort key is down it sets `self._stop_playback = True` and `self.aborted =
  True` and returns early. Returns early if `_stop_playback` is already set.
- `_play_once`: at the top of each event iteration, poll the abort key (covers
  bursts of zero-delay events); replace `time.sleep(delay)` with
  `_interruptible_sleep(delay)`.

The existing `while` loops in `play` and `play_playlist` already break on
`_stop_playback`, so no further change there beyond resetting `aborted`.

### app.py

- Playback status strings mention the hotkey, e.g. `"Playing (... ) — Esc to
  abort"`.
- `_reset_play_buttons` sets status to `"Playback aborted"` when
  `self.recorder.aborted` is true, otherwise `"Playback finished"`.

### tests/test_recorder.py

- Monkeypatch `_abort_key_pressed` to return `True` partway through playback;
  assert the event loop stops early and `aborted` is set.
- Assert `_interruptible_sleep` returns early once `_stop_playback` flips, and
  completes the full duration when neither flag nor key is set.

## Out of scope

- Configurable abort key (hardcoded Esc for now).
- Pause/resume.
- Visual on-screen overlay during playback.
