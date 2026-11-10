"""Measure slider gain at the actual worker output, without any audio device."""

from dataclasses import asdict
from pathlib import Path
import json
import sys
import threading
import time

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from ecc3852.equalizer import EQSettings
from ecc3852.player import AudioPlayer


class CapturingStream:
    latency = 0.05

    def __init__(self, **kwargs):
        self.fs = kwargs["samplerate"]
        self.blocks = []
        self.closed = False

    def start(self):
        pass

    def write(self, block):
        self.blocks.append(np.array(block, copy=True))
        # Pacing gives the real worker command queue time to accept live input.
        time.sleep(len(block) / self.fs)
        return False

    def stop(self):
        pass

    def abort(self):
        pass

    def close(self):
        self.closed = True


def wait_for(player, predicate, timeout=5):
    deadline = time.monotonic() + timeout
    event = threading.Event()
    while time.monotonic() < deadline:
        view = player.snapshot()
        if view["state"] == "error":
            raise RuntimeError(view["error"])
        if predicate(view):
            return view
        event.wait(0.005)
    raise RuntimeError(f"Timed out: {player.snapshot()}")


def amplitude(samples, fs, frequency, first_sample):
    phase = 2 * np.pi * frequency * (np.arange(len(samples)) + first_sample) / fs
    basis = np.column_stack((np.sin(phase), np.cos(phase), np.ones(len(samples))))
    fitted, *_ = np.linalg.lstsq(basis, samples, rcond=None)
    return float(np.hypot(fitted[0], fitted[1]))


def main():
    output = ROOT / "outputs/audibility"
    fs = 44100
    time_axis = np.arange(5 * fs) / fs
    source = np.repeat((0.12 * np.sin(2 * np.pi * 1000 * time_axis))[:, None], 2, axis=1)
    source_path = output / "diagnostic_1000hz.wav"
    sf.write(source_path, source, fs, subtype="PCM_24")
    decoded, _ = sf.read(source_path, always_2d=True)
    streams = []
    def factory(**kwargs):
        stream = CapturingStream(**kwargs)
        streams.append(stream)
        return stream
    player = AudioPlayer(EQSettings(), volume_db=-18, stream_factory=factory)
    stages = [{"label": "flat", "expected_eq_db": 0.0,
               "measurement_start_sample": int(0.2 * fs), "measurement_end_sample": int(0.4 * fs)}]
    try:
        player.load(source_path)
        wait_for(player, lambda v: v["state"] == "stopped")
        player.play()
        wait_for(player, lambda v: v["position_samples"] >= int(0.5 * fs))
        for value in (12.0, -12.0):
            before = player.snapshot()
            request_at = before["position_samples"]
            player.set_settings(EQSettings(mid_db=value))
            settled = wait_for(player, lambda v: v["settings"]["mid_db"] == value
                               and not v["transitioning"]
                               and v["position_samples"] >= request_at + int(0.6 * fs))
            stages.append({"label": f"mid_{value:+g}_db", "expected_eq_db": value,
                           "requested_at_sample": request_at,
                           "requested_settings": settled["requested_settings"],
                           "applied_settings": settled["settings"],
                           "measurement_start_sample": request_at + int(0.2 * fs),
                           "measurement_end_sample": request_at + int(0.5 * fs)})
        final_view = player.snapshot()
    finally:
        player.close()
    rendered = np.concatenate(streams[0].blocks)
    playback_gain = 10 ** (-18 / 20)
    for stage in stages:
        first, last = stage["measurement_start_sample"], stage["measurement_end_sample"]
        incoming = amplitude(decoded[first:last, 0], fs, 1000, first)
        outgoing = amplitude(rendered[first:last, 0], fs, 1000, first)
        stage["input_tone_amplitude_fs"] = incoming
        stage["written_float32_tone_amplitude_fs"] = outgoing
        stage["measured_eq_db_after_removing_fixed_playback_gain"] = float(20 * np.log10(outgoing / incoming / playback_gain))
        assert abs(stage["measured_eq_db_after_removing_fixed_playback_gain"] - stage["expected_eq_db"]) < 0.001
    report = {"kind": "Worker output diagnosis with paced capturing stream; no audio device",
              "sample_rate_hz": fs, "frequency_hz": 1000, "fixed_playback_gain_db": -18,
              "measurement_method": "Least-squares sinusoid amplitude on settled output slices, away from crossfades and ramps",
              "stages": stages, "last_snapshot": final_view,
              "measured_boost_to_cut_difference_db": stages[1]["measured_eq_db_after_removing_fixed_playback_gain"] - stages[2]["measured_eq_db_after_removing_fixed_playback_gain"],
              "human_listening_performed": False, "actual_audio_device_accessed": False,
              "result": "passed"}
    (output / "worker_slider_diagnostic.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
