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
