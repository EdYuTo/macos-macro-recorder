import tkinter as tk
from tkinter import filedialog, messagebox
from recorder import MacroRecorder


class MacroRecorderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Macro Recorder")
        self.root.resizable(False, False)
        self.recorder = MacroRecorder()

        self._build_ui()
        self._update_status("Ready")

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        # -- Status --
        self.status_var = tk.StringVar(value="Ready")
        status_label = tk.Label(
            self.root, textvariable=self.status_var,
            font=("Helvetica", 13, "bold"), anchor="center",
        )
        status_label.pack(fill="x", pady=(10, 4))

        self.event_count_var = tk.StringVar(value="Events: 0")
        tk.Label(self.root, textvariable=self.event_count_var).pack()

        # -- Record controls --
        rec_frame = tk.LabelFrame(self.root, text="Record", padx=8, pady=6)
        rec_frame.pack(fill="x", padx=10, pady=6)

        self.btn_record = tk.Button(rec_frame, text="Record", width=12, command=self._toggle_record)
        self.btn_record.pack(side="left", **pad)

        tk.Label(rec_frame, text="Trim tail (s):").pack(side="left", padx=(12, 0))
        self.trim_var = tk.StringVar(value="0.5")
        tk.Entry(rec_frame, textvariable=self.trim_var, width=5).pack(side="left", padx=4)

        # -- Playback controls --
        play_frame = tk.LabelFrame(self.root, text="Playback", padx=8, pady=6)
        play_frame.pack(fill="x", padx=10, pady=6)

        row1 = tk.Frame(play_frame)
        row1.pack(fill="x", pady=2)

        tk.Label(row1, text="Speed:").pack(side="left")
        self.speed_var = tk.StringVar(value="1.0")
        tk.Entry(row1, textvariable=self.speed_var, width=5).pack(side="left", padx=4)

        tk.Label(row1, text="Repeat:").pack(side="left", padx=(12, 0))
        self.repeat_var = tk.StringVar(value="1")
        tk.Entry(row1, textvariable=self.repeat_var, width=5).pack(side="left", padx=4)
        tk.Label(row1, text="(0 = infinite)").pack(side="left")

        row2 = tk.Frame(play_frame)
        row2.pack(fill="x", pady=4)

        self.btn_play = tk.Button(row2, text="Play", width=12, command=self._play)
        self.btn_play.pack(side="left", **pad)

        self.btn_stop = tk.Button(row2, text="Stop", width=12, command=self._stop_playback, state="disabled")
        self.btn_stop.pack(side="left", **pad)

        # -- File controls --
        file_frame = tk.LabelFrame(self.root, text="File", padx=8, pady=6)
        file_frame.pack(fill="x", padx=10, pady=6)

        tk.Button(file_frame, text="Save", width=12, command=self._save).pack(side="left", **pad)
        tk.Button(file_frame, text="Load", width=12, command=self._load).pack(side="left", **pad)

    def _update_status(self, text):
        self.status_var.set(text)
        self.event_count_var.set(f"Events: {self.recorder.event_count}")

    def _toggle_record(self):
        if not self.recorder.recording:
            self.recorder.start_recording()
            self.btn_record.config(text="Stop Recording", bg="#ff6666")
            self._update_status("Recording...")
            self._poll_event_count()
        else:
            self.recorder.stop_recording()
            try:
                trim = float(self.trim_var.get())
                if trim > 0:
                    self.recorder.trim_tail(trim)
            except ValueError:
                pass
            self.btn_record.config(text="Record", bg="SystemButtonFace")
            self._update_status("Stopped")

    def _poll_event_count(self):
        if self.recorder.recording:
            self.event_count_var.set(f"Events: {self.recorder.event_count}")
            self.root.after(500, self._poll_event_count)

    def _play(self):
        if self.recorder.event_count == 0:
            messagebox.showwarning("No events", "Nothing to play. Record or load a macro first.")
            return
        try:
            speed = float(self.speed_var.get())
            repeat = int(self.repeat_var.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Speed must be a number and repeat must be an integer.")
            return
        if speed <= 0:
            messagebox.showerror("Invalid input", "Speed must be greater than 0.")
            return
        if repeat < 0:
            messagebox.showerror("Invalid input", "Repeat must be 0 (infinite) or a positive integer.")
            return

        self.btn_play.config(state="disabled")
        self.btn_stop.config(state="normal")
        self._update_status(f"Playing ({'infinite' if repeat == 0 else repeat}x @ {speed}x)...")

        self.recorder.play(speed=speed, repeat=repeat, on_done=self._on_playback_done)

    def _on_playback_done(self):
        self.root.after(0, self._reset_play_buttons)

    def _reset_play_buttons(self):
        self.btn_play.config(state="normal")
        self.btn_stop.config(state="disabled")
        self._update_status("Playback finished")

    def _stop_playback(self):
        self.recorder.stop_playback()
        self._reset_play_buttons()
        self._update_status("Playback stopped")

    def _save(self):
        if self.recorder.event_count == 0:
            messagebox.showwarning("No events", "Nothing to save.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.recorder.save(path)
            self._update_status(f"Saved ({self.recorder.event_count} events)")

    def _load(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            try:
                self.recorder.load(path)
                self._update_status(f"Loaded ({self.recorder.event_count} events)")
            except Exception as e:
                messagebox.showerror("Load error", str(e))


def main():
    root = tk.Tk()
    MacroRecorderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
