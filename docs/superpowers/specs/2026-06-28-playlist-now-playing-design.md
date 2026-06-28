# Show Currently-Playing Recording Name

## Problem

When playing a playlist with random advance, the user cannot tell which
recording is currently playing. The UI shows a cycle counter but not the name
of the active item.

## Approach

The playback worker thread already picks a random `recording` per cycle in
`play_playlist`. Expose the picked name on the recorder as `current_name`, and
have the existing UI poll (`_poll_cycles`) render it in a new dedicated label.

Single-macro `play()` has no associated name, so it sets `current_name` to
`None` and the label stays blank.

String attribute assignment is atomic under the GIL — consistent with the
existing `_stop_playback` / `aborted` flag pattern. No lock needed. No new
dependencies.

## Changes

### recorder.py

- `__init__`: initialize `self.current_name = None`.
- `play()`: set `self.current_name = None` at the start (alongside the other
  per-run resets), since single playback has no name.
- `play_playlist()`: set `self.current_name = None` at the start; inside the
  loop, set `self.current_name = pick["name"]` immediately before
  `_play_once(pick["events"], speed)`.

### app.py

- Add a `now_playing_var` `StringVar` and a `Label` placed directly below the
  existing cycle-counter label.
- In `_poll_cycles`: when `self.recorder.playing` and
  `self.recorder.current_name`, set the label to
  `f"Now playing: {self.recorder.current_name}"`; otherwise set it to `""`.
  This mirrors how `cycle_var` already self-clears when playback stops.

### tests/test_recorder.py

- Assert `play_playlist` sets `current_name` to the picked recording's name
  (monkeypatch `random.choice` to a known item and `_play_once` to capture
  `current_name` at call time).
- Assert `play()` sets `current_name` to `None`.

## Out of scope

- Highlighting the item in the playlist Listbox.
- Showing a history of played items.
- Naming single-macro playback.
