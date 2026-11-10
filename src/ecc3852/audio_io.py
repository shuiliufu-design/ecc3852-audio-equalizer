"""Audio I/O with explicit sample ranges and no hidden normalization."""

from pathlib import Path
import hashlib

import numpy as np
import soundfile as sf


def as_channels(audio):
    data = np.asarray(audio)
    if (data.ndim not in (1, 2) or not data.shape[0]
            or (data.ndim == 2 and not data.shape[1])
            or data.dtype.kind not in "fiu" or not np.all(np.isfinite(data))):
        raise ValueError("audio must be a nonempty finite real array")
    return np.asarray(data[:, None] if data.ndim == 1 else data, dtype=np.float64)


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_audio(path, start_s=0.0, duration_s=None):
    """Decode a segment as (samples, channels); keep original file unchanged.

    Start is rounded down to a sample. A duration is rounded to a sample count
    and clipped to EOF. Metadata records actual sample-aligned source times.
    """
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Audio file not found: {path}")
    if not np.isfinite(start_s) or start_s < 0:
        raise ValueError("start_s must be finite and nonnegative")
    if duration_s is not None and (not np.isfinite(duration_s) or duration_s <= 0):
        raise ValueError("duration_s must be finite and positive")
    with sf.SoundFile(path) as source:
        sample_rate = source.samplerate
        start_frame = int(np.floor(start_s * sample_rate))
        if start_frame >= source.frames:
            raise ValueError("selected start is outside the audio file")
        count = source.frames - start_frame
        if duration_s is not None:
            count = min(count, int(round(duration_s * sample_rate)))
        if count < 2:
            raise ValueError("selected audio must contain at least two samples")
        metadata = {
            "path": str(path), "sha256": file_sha256(path),
            "format": source.format, "subtype": source.subtype,
            "original_samples": source.frames,
            "original_duration_s": source.frames / sample_rate,
            "start_sample": start_frame,
            "start_s": start_frame / sample_rate,
            "end_sample_exclusive": start_frame + count,
            "end_s_exclusive": (start_frame + count) / sample_rate,
            "sample_rate_hz": sample_rate, "channels": source.channels,
        }
        source.seek(start_frame)
        data = as_channels(source.read(count, dtype="float64", always_2d=True))
    return data, sample_rate, metadata


def save_audio(path, audio, sample_rate, subtype="PCM_24"):
    """Write normalized samples without silently clipping or changing gain."""
    data = as_channels(audio)
    if isinstance(sample_rate, bool) or int(sample_rate) != sample_rate or sample_rate <= 0:
        raise ValueError("sample_rate must be a positive integer")
    if np.max(np.abs(data)) >= 1.0:
        raise ValueError("PCM export needs peak below 1; explicitly attenuate first")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, data, int(sample_rate), format="WAV", subtype=subtype)


def common_export_gain(arrays, ceiling=0.95):
    """One attenuation for every comparison file, preserving preset gains."""
    if not np.isfinite(ceiling) or not 0 < ceiling < 1:
        raise ValueError("export peak_ceiling must be between 0 and 1")
    peaks = [float(np.max(np.abs(as_channels(a)))) for a in arrays]
    if not peaks:
        raise ValueError("at least one array is required")
    return min(1.0, ceiling / max(peaks)) if max(peaks) > 0 else 1.0
