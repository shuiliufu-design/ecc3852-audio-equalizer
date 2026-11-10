"""Tk desktop controls for the worker-owned music equalizer."""

from dataclasses import replace
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk

from .demo import ensure_listening_demo
from .player import AudioPlayer


ROOT = Path(__file__).resolve().parents[2]


def _clock(samples, rate):
    seconds = int(samples / rate) if rate else 0
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


class PlayerWindow:
    def __init__(self, root, settings, *, initial_path=None, device=None, volume_db=-18.0):
        self.root = root
        self.base_settings = settings
        self.player = AudioPlayer(settings, device=device, volume_db=volume_db)
        self._slider_job = None
        self._poll_job = None
        self._closed = False
        root.title("ECC3852 · Real-time three-band equalizer")
        root.geometry("820x720")
        root.minsize(720, 700)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        frame = ttk.Frame(root, padding=24)
        frame.grid(sticky="nsew")
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text="ECC3852  /  AUDIO EQUALIZER", font=("Helvetica", 12)).grid(sticky="w")
        ttk.Label(frame, text="Real-time three-band equalizer", font=("Helvetica", 25, "bold")).grid(sticky="w", pady=(6, 16))

        self.file_text = tk.StringVar(value="Open an audio file or load the synthetic demo")
        self.info_text = tk.StringVar(value="")
        self.state_text = tk.StringVar(value="No audio loaded")
        self.guidance_text = tk.StringVar(value="EQ changes band levels, not pitch. Use Bypass EQ to compare.")
        self.bypass_var = tk.BooleanVar(value=False)
        ttk.Label(frame, textvariable=self.file_text, font=("Helvetica", 13, "bold"),
                  wraplength=650).grid(sticky="w")
        ttk.Label(frame, textvariable=self.info_text).grid(sticky="w", pady=(4, 12))
        ttk.Label(frame, textvariable=self.guidance_text, wraplength=650).grid(sticky="w", pady=(0, 8))

        controls = ttk.Frame(frame)
        controls.grid(sticky="ew", pady=(0, 12))
        self.open_button = ttk.Button(controls, text="Open audio…", command=self.open_file)
        self.open_button.grid(row=0, column=0, padx=(0, 8))
        self.demo_button = ttk.Button(controls, text="Synthetic demo", command=self.load_demo)
        self.demo_button.grid(row=0, column=1, padx=(0, 20))
        self.play_button = ttk.Button(controls, text="Play / Resume", command=self.player.play)
        self.play_button.grid(row=0, column=2, padx=(0, 8))
        self.pause_button = ttk.Button(controls, text="Pause", command=self.player.pause)
        self.pause_button.grid(row=0, column=3, padx=(0, 8))
        self.stop_button = ttk.Button(controls, text="Stop", command=self.player.stop)
        self.stop_button.grid(row=0, column=4)

        timeline = ttk.Frame(frame)
        timeline.grid(sticky="ew")
        timeline.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(timeline, maximum=1)
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 16))
        self.time_text = tk.StringVar(value="00:00 / 00:00")
        ttk.Label(timeline, textvariable=self.time_text).grid(row=0, column=1)
        ttk.Label(frame, textvariable=self.state_text).grid(sticky="w", pady=(6, 12))

        bands = ttk.Frame(frame)
        bands.grid(sticky="ew")
        self.gain_vars = {}
        self.gain_labels = {}
        for column, (key, name, frequency) in enumerate((
            ("bass_db", "Bass", settings.bass_hz),
            ("mid_db", "Mid", settings.mid_hz),
            ("treble_db", "Treble", settings.treble_hz),
        )):
            bands.columnconfigure(column, weight=1, uniform="bands")
            card = ttk.LabelFrame(bands, text=name, padding=14)
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 6, 0 if column == 2 else 6))
            card.columnconfigure(0, weight=1)
            ttk.Label(card, text=f"{frequency:g} Hz", font=("Helvetica", 12)).grid()
            value = tk.DoubleVar(value=getattr(settings, key))
            label = tk.StringVar(value=f"{value.get():+.1f} dB")
            self.gain_vars[key] = value
            self.gain_labels[key] = label
            ttk.Label(card, textvariable=label, font=("Helvetica", 18, "bold")).grid(pady=(6, 4))
            scale = ttk.Scale(card, from_=12, to=-12, orient="vertical", length=100,
                              variable=value, command=lambda _, k=key: self._slider_changed(k))
            scale.grid()
            ttk.Label(card, text="+12 to −12 dB").grid(pady=(6, 0))
        comparison = ttk.Frame(frame)
        comparison.grid(sticky="ew", pady=(12, 10))
        ttk.Button(comparison, text="Reset all bands to 0 dB", command=self.reset).grid(row=0, column=0)
        self.bypass_button = ttk.Checkbutton(comparison, text="Bypass EQ (original sound)",
                                             variable=self.bypass_var, command=self._bypass_changed)
        self.bypass_button.grid(row=0, column=1, padx=(16, 0))

        self.safety_text = tk.StringVar(value=f"Playback gain {volume_db:+.1f} dB · Peak protection at 0.95 FS")
        self.device_text = tk.StringVar(value="The output device opens when playback starts; no recording")
        ttk.Label(frame, textvariable=self.safety_text, wraplength=650).grid(sticky="w")
        ttk.Label(frame, textvariable=self.device_text, wraplength=650).grid(sticky="w", pady=(4, 0))
        self.error_text = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.error_text, foreground="#b42318", wraplength=650).grid(sticky="w", pady=(6, 0))
        if initial_path is not None:
            self.player.load(initial_path)
        self._poll()

    def open_file(self):
        path = filedialog.askopenfilename(title="Open audio (original file is preserved)", filetypes=[
            ("Audio", "*.wav *.flac *.aiff *.aif *.ogg *.mp3"), ("All files", "*")])
        if path:
            self.player.load(path)

    def load_demo(self):
        self.player.load(ensure_listening_demo())

    def _slider_changed(self, key):
        value = round(self.gain_vars[key].get() * 2) / 2
        self.gain_labels[key].set(f"{value:+.1f} dB")
        # Throttle, rather than debounce: continuous dragging must still
        # submit the latest values every ~40 ms while the mouse is moving.
        if self._slider_job is None:
            self._slider_job = self.root.after(40, self._commit_settings)

    def _commit_settings(self):
        self._slider_job = None
        gains = {key: round(var.get() * 2) / 2 for key, var in self.gain_vars.items()}
        if self.bypass_var.get():
            gains = {key: 0.0 for key in gains}
        self.player.set_settings(replace(self.base_settings, **gains))

    def _bypass_changed(self):
        # Keep slider positions while comparing against the flat response.
        if self._slider_job is not None:
            self.root.after_cancel(self._slider_job)
            self._slider_job = None
        self._commit_settings()

    def reset(self):
        if self._slider_job is not None:
            self.root.after_cancel(self._slider_job)
            self._slider_job = None
        for key, var in self.gain_vars.items():
            var.set(0)
            self.gain_labels[key].set("+0.0 dB")
        self._commit_settings()

    def _poll(self):
        if self._closed:
            return
        view = self.player.snapshot()
        state = view["state"]
        names = {"empty": "No audio loaded", "loading": "Loading audio…", "stopped": "Stopped",
                 "playing": "Playing", "paused": "Paused",
                 "ended": "Playback ended — press Play / Resume to replay", "error": "Error"}
        self.state_text.set(names.get(state, state))
        self.error_text.set(view["error"] or "")
        if view["path"]:
            path = Path(view["path"])
            demo_paths = {ROOT / "audio/demo/synthetic_demo.wav", ROOT / "audio/demo/eq_listening_demo.wav"}
            kind = "Synthetic demo" if path in demo_paths else "Loaded audio"
            self.file_text.set(path.name)
            self.info_text.set(f"{kind} · {view['sample_rate_hz']} Hz · {view['channels']} channels")
            if path == ROOT / "audio/demo/eq_listening_demo.wav":
                self.guidance_text.set("Steady bass, mid and treble play together. EQ changes band levels, not pitch.")
            elif path == ROOT / "audio/demo/synthetic_demo.wav":
                self.guidance_text.set("This short demo changes pitch by design. Load Synthetic demo for a steady mix.")
            else:
                self.guidance_text.set("EQ changes band levels, not pitch. Use Bypass EQ to compare with the original.")
        self.progress["value"] = view["position_samples"] / max(1, view["total_samples"])
        self.time_text.set(f"{_clock(view['position_samples'], view['sample_rate_hz'])} / "
                           f"{_clock(view['total_samples'], view['sample_rate_hz'])}")
        loaded = view["path"] is not None and state != "loading"
        self.play_button["state"] = "normal" if loaded and state != "playing" else "disabled"
        self.pause_button["state"] = "normal" if state == "playing" else "disabled"
        self.stop_button["state"] = "normal" if loaded else "disabled"
        self.open_button["state"] = self.demo_button["state"] = "disabled" if state == "loading" else "normal"
        count = view["limited_samples"]
        guard = f"Protected {count} channel samples" if count else "Protection not triggered"
        self.safety_text.set(f"Playback gain {view['volume_db']:+.1f} dB · Peak before protection "
                             f"{view['peak_before_limit']:.3f} FS · {guard} · Underflows: {view['underflows']}")
        if view["device"]:
            self.device_text.set(f"Output: {view['device']['name']} · Block size: {self.player.block_size} samples · "
                                 f"Device-reported latency: {view['latency_s'] * 1000:.0f} ms")
        self._poll_job = self.root.after(100, self._poll)

    def close(self):
        self._closed = True
        for job in (self._slider_job, self._poll_job):
            if job is not None:
                self.root.after_cancel(job)
        try:
            self.player.close()
        finally:
            self.root.destroy()


def launch(settings, initial_path=None, device=None, volume_db=-18.0):
    root = tk.Tk()
    PlayerWindow(root, settings, initial_path=initial_path, device=device, volume_db=volume_db)
    root.mainloop()
