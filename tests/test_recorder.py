import json
import threading
import pytest
import recorder as recorder_mod
from recorder import MacroRecorder


def test_load_events_returns_without_mutating(tmp_path):
    rec = MacroRecorder()
    rec.events = [{"type": "move", "x": 1, "y": 2, "time": 0}]

    p = tmp_path / "macro.json"
    p.write_text(json.dumps([{"type": "key_press", "keycode": 5, "time": 0}]))

    loaded = MacroRecorder.load_events(str(p))

    assert loaded == [{"type": "key_press", "keycode": 5, "time": 0}]
    assert rec.events == [{"type": "move", "x": 1, "y": 2, "time": 0}]


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


def test_play_playlist_loops_repeat_times(monkeypatch):
    rec = MacroRecorder()
    recordings = [{"name": "a", "events": [{"time": 0}]}]

    monkeypatch.setattr("recorder.random.choice", lambda seq: seq[0])

    calls = []
    monkeypatch.setattr(rec, "_play_once", lambda ev, sp: calls.append((ev, sp)))

    done = threading.Event()
    rec.play_playlist(recordings, speed=1.0, repeat=3, on_done=done.set)

    assert done.wait(2)
    assert len(calls) == 3
    assert rec.playing is False


# ── Fix 2: _release_pressed_button ────────────────────────────────────────────

def test_release_pressed_button_posts_up_event_and_clears(monkeypatch):
    rec = MacroRecorder()
    rec._pressed_button = "left"

    posted = []
    fake_event = object()

    # _release_pressed_button calls Quartz.CGEventCreate and CGEventGetLocation
    # (both imported from Quartz), CGEventCreateMouseEvent, CGEventPost
    monkeypatch.setattr(recorder_mod.Quartz, "CGEventCreate", lambda src: object())
    monkeypatch.setattr(recorder_mod, "CGEventGetLocation", lambda ev: object())
    monkeypatch.setattr(recorder_mod, "CGEventCreateMouseEvent", lambda src, ev_type, pt, btn: fake_event)
    monkeypatch.setattr(recorder_mod, "CGEventPost", lambda tap, ev: posted.append(ev))

    rec._release_pressed_button()

    assert len(posted) == 1
    assert posted[0] is fake_event
    assert rec._pressed_button is None


def test_release_pressed_button_noop_when_none(monkeypatch):
    rec = MacroRecorder()
    rec._pressed_button = None

    posted = []
    monkeypatch.setattr(recorder_mod, "CGEventPost", lambda tap, ev: posted.append(ev))

    rec._release_pressed_button()

    assert posted == []
    assert rec._pressed_button is None


# ── Fix 3: exception in _play_once propagates cleanup ─────────────────────────

@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_play_calls_on_done_and_clears_playing_on_exception(monkeypatch):
    rec = MacroRecorder()
    rec.events = [{"type": "key_press", "keycode": 1, "time": 0}]

    def raising_play_once(ev, sp):
        raise RuntimeError("boom")

    monkeypatch.setattr(rec, "_play_once", raising_play_once)
    monkeypatch.setattr(rec, "_release_pressed_button", lambda: None)

    done = threading.Event()
    rec.play(speed=1.0, repeat=1, on_done=done.set)

    assert done.wait(2), "on_done was never called after exception"
    assert rec.playing is False
