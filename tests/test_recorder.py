import json
import threading
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
