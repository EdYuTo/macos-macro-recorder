import json
import time
import threading
import Quartz
from Quartz import (
    CGEventGetLocation,
    CGEventGetIntegerValueField,
    kCGEventLeftMouseDown,
    kCGEventLeftMouseUp,
    kCGEventRightMouseDown,
    kCGEventRightMouseUp,
    kCGEventMouseMoved,
    kCGEventLeftMouseDragged,
    kCGEventRightMouseDragged,
    kCGEventScrollWheel,
    kCGEventKeyDown,
    kCGEventKeyUp,
    kCGScrollWheelEventDeltaAxis1,
    kCGScrollWheelEventDeltaAxis2,
    kCGKeyboardEventKeycode,
    kCGEventFlagsChanged,
    CGEventCreateMouseEvent,
    CGEventCreateKeyboardEvent,
    CGEventCreateScrollWheelEvent,
    CGEventPost,
    kCGHIDEventTap,
    kCGSessionEventTap,
    kCGEventTapOptionListenOnly,
    CGEventMaskBit,
    CGEventTapCreate,
    CGEventTapEnable,
    CFMachPortCreateRunLoopSource,
    CFRunLoopAddSource,
    CFRunLoopGetCurrent,
    CFRunLoopRun,
    CFRunLoopStop,
    kCFRunLoopDefaultMode,
    kCGScrollWheelEventIsContinuous,
)


# Mouse button constants
MOUSE_BUTTON_LEFT = "left"
MOUSE_BUTTON_RIGHT = "right"

# Map CGEvent types to our event types
_MOUSE_DOWN_MAP = {
    kCGEventLeftMouseDown: MOUSE_BUTTON_LEFT,
    kCGEventRightMouseDown: MOUSE_BUTTON_RIGHT,
}
_MOUSE_UP_MAP = {
    kCGEventLeftMouseUp: MOUSE_BUTTON_LEFT,
    kCGEventRightMouseUp: MOUSE_BUTTON_RIGHT,
}

# Quartz mouse button IDs for CGEventCreateMouseEvent
_QUARTZ_BUTTON = {
    MOUSE_BUTTON_LEFT: Quartz.kCGMouseButtonLeft,
    MOUSE_BUTTON_RIGHT: Quartz.kCGMouseButtonRight,
}
_QUARTZ_DOWN_EVENT = {
    MOUSE_BUTTON_LEFT: kCGEventLeftMouseDown,
    MOUSE_BUTTON_RIGHT: kCGEventRightMouseDown,
}
_QUARTZ_UP_EVENT = {
    MOUSE_BUTTON_LEFT: kCGEventLeftMouseUp,
    MOUSE_BUTTON_RIGHT: kCGEventRightMouseUp,
}


class MacroRecorder:
    def __init__(self):
        self.events = []
        self.recording = False
        self.playing = False
        self._stop_playback = False
        self._start_time = 0
        self._tap = None
        self._run_loop = None
        self._listener_thread = None

    # ── Recording ──────────────────────────────────────────────

    def start_recording(self):
        self.events = []
        self.recording = True
        self._start_time = time.time()

        mask = (
            CGEventMaskBit(kCGEventLeftMouseDown)
            | CGEventMaskBit(kCGEventLeftMouseUp)
            | CGEventMaskBit(kCGEventRightMouseDown)
            | CGEventMaskBit(kCGEventRightMouseUp)
            | CGEventMaskBit(kCGEventMouseMoved)
            | CGEventMaskBit(kCGEventLeftMouseDragged)
            | CGEventMaskBit(kCGEventRightMouseDragged)
            | CGEventMaskBit(kCGEventScrollWheel)
            | CGEventMaskBit(kCGEventKeyDown)
            | CGEventMaskBit(kCGEventKeyUp)
            | CGEventMaskBit(kCGEventFlagsChanged)
        )

        self._tap = CGEventTapCreate(
            kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            kCGEventTapOptionListenOnly,
            mask,
            self._event_callback,
            None,
        )

        if self._tap is None:
            raise RuntimeError(
                "Could not create event tap. "
                "Grant Accessibility permission in System Settings > "
                "Privacy & Security > Accessibility."
            )

        source = CFMachPortCreateRunLoopSource(None, self._tap, 0)

        def _run():
            self._run_loop = CFRunLoopGetCurrent()
            CFRunLoopAddSource(self._run_loop, source, kCFRunLoopDefaultMode)
            CGEventTapEnable(self._tap, True)
            CFRunLoopRun()

        self._listener_thread = threading.Thread(target=_run, daemon=True)
        self._listener_thread.start()

    def stop_recording(self):
        self.recording = False
        if self._tap:
            CGEventTapEnable(self._tap, False)
        if self._run_loop:
            CFRunLoopStop(self._run_loop)
        self._tap = None
        self._run_loop = None

    def _timestamp(self):
        return time.time() - self._start_time

    def _event_callback(self, proxy, event_type, event, refcon):
        if not self.recording:
            return event

        ts = self._timestamp()
        loc = CGEventGetLocation(event)
        x, y = loc.x, loc.y

        if event_type in (kCGEventMouseMoved, kCGEventLeftMouseDragged, kCGEventRightMouseDragged):
            self.events.append({"type": "move", "x": x, "y": y, "time": ts})

        elif event_type in _MOUSE_DOWN_MAP:
            btn = _MOUSE_DOWN_MAP[event_type]
            self.events.append({"type": "click", "x": x, "y": y, "button": btn, "pressed": True, "time": ts})

        elif event_type in _MOUSE_UP_MAP:
            btn = _MOUSE_UP_MAP[event_type]
            self.events.append({"type": "click", "x": x, "y": y, "button": btn, "pressed": False, "time": ts})

        elif event_type == kCGEventScrollWheel:
            dy = CGEventGetIntegerValueField(event, kCGScrollWheelEventDeltaAxis1)
            dx = CGEventGetIntegerValueField(event, kCGScrollWheelEventDeltaAxis2)
            self.events.append({"type": "scroll", "x": x, "y": y, "dx": dx, "dy": dy, "time": ts})

        elif event_type == kCGEventKeyDown:
            keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
            self.events.append({"type": "key_press", "keycode": keycode, "time": ts})

        elif event_type == kCGEventKeyUp:
            keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
            self.events.append({"type": "key_release", "keycode": keycode, "time": ts})

        return event

    # ── Playback ───────────────────────────────────────────────

    def play(self, speed=1.0, repeat=1, on_done=None):
        self._stop_playback = False
        self.playing = True

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
            if on_done:
                on_done()

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def stop_playback(self):
        self._stop_playback = True

    def _execute_event(self, event):
        etype = event["type"]

        if etype == "move":
            point = Quartz.CGPointMake(event["x"], event["y"])
            ev = CGEventCreateMouseEvent(None, kCGEventMouseMoved, point, Quartz.kCGMouseButtonLeft)
            CGEventPost(kCGHIDEventTap, ev)

        elif etype == "click":
            point = Quartz.CGPointMake(event["x"], event["y"])
            btn = event["button"]
            if event["pressed"]:
                ev_type = _QUARTZ_DOWN_EVENT[btn]
            else:
                ev_type = _QUARTZ_UP_EVENT[btn]
            ev = CGEventCreateMouseEvent(None, ev_type, point, _QUARTZ_BUTTON[btn])
            CGEventPost(kCGHIDEventTap, ev)

        elif etype == "scroll":
            ev = CGEventCreateScrollWheelEvent(None, kCGScrollWheelEventIsContinuous, 2, event["dy"], event["dx"])
            CGEventPost(kCGHIDEventTap, ev)

        elif etype == "key_press":
            ev = CGEventCreateKeyboardEvent(None, event["keycode"], True)
            CGEventPost(kCGHIDEventTap, ev)

        elif etype == "key_release":
            ev = CGEventCreateKeyboardEvent(None, event["keycode"], False)
            CGEventPost(kCGHIDEventTap, ev)

    # ── Save / Load ────────────────────────────────────────────

    def save(self, filepath):
        with open(filepath, "w") as f:
            json.dump(self.events, f, indent=2)

    def load(self, filepath):
        with open(filepath, "r") as f:
            self.events = json.load(f)

    def trim_tail(self, seconds):
        if not self.events:
            return
        cutoff = self.events[-1]["time"] - seconds
        self.events = [e for e in self.events if e["time"] <= cutoff]

    @property
    def event_count(self):
        return len(self.events)
