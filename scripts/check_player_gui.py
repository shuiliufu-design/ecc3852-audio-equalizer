"""Opt-in Tk widget smoke test with a fake player; no audio/device access.

This checks the application's own widget tree and handlers, not desktop input
automation or a screenshot. Keep separate from headless numerical tests.
"""

from dataclasses import asdict
from datetime import datetime
import argparse
import json
from pathlib import Path
import sys
import time
import tkinter as tk
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ecc3852.equalizer import EQSettings
from ecc3852.gui import PlayerWindow


class FakePlayer:
    def __init__(self, settings, **kwargs):
        self.block_size = 512
        self.closed = False
        self.last_settings = settings
        self.submissions = []
        self.view = dict(state="empty", path=None, sample_rate_hz=None, channels=None,
                         position_samples=0, total_samples=0, volume_db=-18,
                         peak_before_limit=0, limited_samples=0, underflows=0,
                         latency_s=None, device=None, error=None, settings=asdict(settings))

    def load(self, path):
        self.view.update(state="stopped", path=str(Path(path).resolve()), sample_rate_hz=44100,
                         channels=2, total_samples=529200, position_samples=0)

    def snapshot(self):
        return dict(self.view)

    def set_settings(self, settings):
        self.last_settings = settings
        self.submissions.append((time.monotonic(), settings))

    def play(self):
        self.view["state"] = "playing"

    def pause(self):
        self.view["state"] = "paused"

    def stop(self):
        self.view.update(state="stopped", position_samples=0)

    def close(self):
        self.closed = True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/player/gui_check.json",
                        help="Write widget-check evidence here; use a new path to preserve earlier records")
    args = parser.parse_args(argv)
    root = tk.Tk()
    root.withdraw()
    report = dict(timestamp=datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).isoformat(),
                  kind="Tk widget smoke test with fake audio backend", checks=[], result="failed",
                  screenshot_review="not_performed: widget-tree checks only")
    try:
        with patch("ecc3852.gui.AudioPlayer", FakePlayer):
            window = PlayerWindow(root, EQSettings(), initial_path=ROOT / "audio/demo/synthetic_demo.wav")
        root.update_idletasks()
        assert "synthetic" in window.info_text.get().lower()
        assert str(window.play_button["state"]) == "normal"
        assert str(window.pause_button["state"]) == "disabled"
        report["checks"].append("demo metadata and stopped controls")
        for key, value in zip(window.gain_vars, (12, -6, 9)):
            window.gain_vars[key].set(value)
            window._slider_changed(key)
        window._commit_settings()
        assert window.player.last_settings == EQSettings(bass_db=12, mid_db=-6, treble_db=9)
        saved_gains = {key: variable.get() for key, variable in window.gain_vars.items()}
        window.bypass_var.set(True)
        window._bypass_changed()
        assert window.player.last_settings == EQSettings()
        assert {key: variable.get() for key, variable in window.gain_vars.items()} == saved_gains
        window.gain_vars["mid_db"].set(-9)
        window._slider_changed("mid_db")
        window._commit_settings()
        assert window.player.last_settings == EQSettings()
        window.bypass_var.set(False)
        window._bypass_changed()
        assert window.player.last_settings == EQSettings(bass_db=12, mid_db=-9, treble_db=9)
        report["checks"].append("bypass submits flat settings, preserves sliders and restores the latest gains")
        window.reset()
        assert window.player.last_settings == EQSettings()
        assert all(var.get() == 0 for var in window.gain_vars.values())
        report["checks"].append("three independent gains and reset handler")
        window.player.submissions.clear()
        drag_times = []
        def drag(value):
            drag_times.append(time.monotonic())
            window.gain_vars["bass_db"].set(value)
            window._slider_changed("bass_db")
        for index in range(12):
            root.after(index * 10, lambda i=index: drag(i))
        root.after(180, root.quit)
        root.mainloop()
        assert len(window.player.submissions) >= 2
        assert window.player.submissions[0][0] < drag_times[-1]
        assert window.player.last_settings.bass_db == 11
        window.reset()
        report["checks"].append("continuous dragging submits gains before the drag ends")
        with patch("ecc3852.gui.ensure_listening_demo", return_value=ROOT / "audio/demo/eq_listening_demo.wav"):
            window.load_demo()
        window._poll()
        assert "synthetic" in window.info_text.get().lower()
        assert "steady" in window.guidance_text.get().lower()
        assert "not pitch" in window.guidance_text.get()
        report["checks"].append("listening demo selection and fixed-pitch comparison guidance")
        window.player.view.update(state="ended", position_samples=window.player.view["total_samples"])
        window._poll()
        assert "replay" in window.state_text.get().lower()
        report["checks"].append("ended state explains that playback must restart to hear changes")
        window.player.view.update(state="playing", position_samples=22050,
                                  device={"name": "test device"}, latency_s=0.05,
                                  limited_samples=17, underflows=2)
        window._poll()
        assert str(window.play_button["state"]) == "disabled"
        assert str(window.pause_button["state"]) == "normal"
        assert "17" in window.safety_text.get() and "2" in window.safety_text.get()
        assert "test device" in window.device_text.get()
        report["checks"].append("playing controls, output device and overload status")
        window.player.view.update(state="error", error="Device disconnected")
        window._poll()
        assert window.error_text.get() == "Device disconnected"
        assert str(window.play_button["state"]) == "normal"
        report["checks"].append("error display and retry controls")
        for width, height in ((820, 720), (720, 700)):
            root.geometry(f"{width}x{height}")
            root.update_idletasks()
            # Use requested layout size to detect overflow, even while hidden.
            frame = root.winfo_children()[0]
            required = (frame.winfo_reqwidth(), frame.winfo_reqheight())
            report.setdefault("layout_sizes", []).append(dict(window=[width, height], required=list(required)))
            assert required[0] <= width and required[1] <= height, f"layout overflow: {required} in {width}x{height}"
        report["checks"].append("requested layout fits default and minimum window sizes")
        window.close()
        assert window.player.closed
        report["checks"].append("window close closes player")
        report["result"] = "passed"
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        try:
            root.destroy()
        except tk.TclError:
            pass
    path = args.output.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["result"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
