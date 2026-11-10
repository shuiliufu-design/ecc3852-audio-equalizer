"""Deterministic test audio; deliberately not a substitute for music."""

import json
from pathlib import Path

import numpy as np
from scipy.signal import chirp


def synthetic_demo(sample_rate=44100):
    """12 seconds: bass, mid and treble segments over a quiet frequency sweep."""
    duration = 12.0
    time = np.arange(int(sample_rate * duration)) / sample_rate
    audio = np.zeros((len(time), 2), dtype=np.float64)
    segments = []
    for start, end, frequency, amplitude in (
            (0, 4, 100, 0.15), (4, 8, 1000, 0.11), (8, 12, 8000, 0.07)):
        sl = slice(int(start * sample_rate), int(end * sample_rate))
        local_time = np.arange(sl.stop - sl.start) / sample_rate
        envelope = np.ones(len(local_time))
        fade = int(0.05 * sample_rate)
        ramp = np.sin(np.linspace(0, np.pi / 2, fade)) ** 2
        envelope[:fade], envelope[-fade:] = ramp, ramp[::-1]
        audio[sl, 0] += amplitude * envelope * np.sin(2 * np.pi * frequency * local_time)
        audio[sl, 1] += 0.8 * amplitude * envelope * np.sin(2 * np.pi * frequency * local_time + 0.4)
        segments.append({"start_s": start, "end_s": end, "frequency_hz": frequency,
                         "left_amplitude": amplitude, "right_amplitude": amplitude * 0.8})
    sweep = 0.015 * chirp(time, f0=250, t1=duration, f1=10000, method="linear")
    sweep *= np.sin(np.pi * np.minimum(time / 0.05, 1) / 2) ** 2
    sweep *= np.sin(np.pi * np.minimum((duration - time) / 0.05, 1) / 2) ** 2
    audio[:, 0] += sweep
    audio[:, 1] += sweep
    return audio, sample_rate, {
        "signal_kind": "synthetic_demo", "is_music": False,
        "description": "Known-frequency segments plus quiet 250-10000 Hz linear chirp",
        "duration_s": duration, "sample_rate_hz": sample_rate, "channels": 2,
        "segments": segments, "purpose": "Implementation verification only; no song results",
    }


def listening_demo(sample_rate=44100, duration_s=60.0):
    """Steady simultaneous tones for hearing EQ changes without a pitch sweep.

    This is a listening aid, not music or a replacement for the original
    segmented diagnostic fixture. The three components remain present for the
    entire recording, apart from short fades at its boundaries.
    """
    if (isinstance(sample_rate, bool) or not isinstance(sample_rate, (int, np.integer))
            or sample_rate <= 12000):
        raise ValueError("sample_rate must be an integer above 12000 Hz")
    if (isinstance(duration_s, bool) or not np.isfinite(duration_s)
            or not 0.25 <= duration_s <= 300):
        raise ValueError("duration_s must be between 0.25 and 300 seconds")
    count = round(sample_rate * duration_s)
    time = np.arange(count) / sample_rate
    audio = np.zeros((count, 2), dtype=np.float64)
    components = []
    for name, frequency, amplitude in (
            ("bass", 120.0, 0.13), ("mid", 1000.0, 0.10), ("treble", 6000.0, 0.06)):
        audio[:, 0] += amplitude * np.sin(2 * np.pi * frequency * time)
        audio[:, 1] += 0.8 * amplitude * np.sin(2 * np.pi * frequency * time + 0.4)
        components.append({"band": name, "frequency_hz": frequency,
                           "left_amplitude": amplitude, "right_amplitude": 0.8 * amplitude})
    fade = min(round(0.05 * sample_rate), count // 2)
    envelope = np.ones(count)
    ramp = np.sin(np.linspace(0, np.pi / 2, fade)) ** 2
    envelope[:fade], envelope[-fade:] = ramp, ramp[::-1]
    audio *= envelope[:, None]
    return audio, sample_rate, {
        "schema_version": 1, "signal_kind": "synthetic_listening_demo", "is_music": False,
        "description": "Steady simultaneous 120, 1000 and 6000 Hz tones; no frequency sweep",
        "duration_s": count / sample_rate, "sample_rate_hz": sample_rate, "channels": 2,
        "components": components, "boundary_fade_ms": 50,
        "purpose": "Audible A/B comparison of band levels; not formal music evidence",
    }


def ensure_listening_demo(directory=None):
    """Create the separate listening aid if absent, preserving baseline audio."""
    from .audio_io import save_audio

    directory = (Path(directory) if directory is not None
                 else Path(__file__).resolve().parents[2] / "audio/demo")
    path = directory / "eq_listening_demo.wav"
    manifest_path = directory / "eq_listening_manifest.json"
    if not path.is_file() or not manifest_path.is_file():
        audio, sample_rate, manifest = listening_demo()
        directory.mkdir(parents=True, exist_ok=True)
        save_audio(path, audio, sample_rate)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path
