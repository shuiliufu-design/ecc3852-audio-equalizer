"""Inspect time-domain samples and channel-averaged audio power spectra.

The spectrogram contains only windows fully inside the recording. Powers are
averaged across channels, rather than averaging waveforms, so opposite stereo
phases cannot cancel. PSD units are sample-amplitude squared per Hz.
"""

from dataclasses import dataclass
import math

import numpy as np
from scipy.signal import ShortTimeFFT, welch, windows


@dataclass(frozen=True)
class AnalysisSettings:
    window_ms: float = 30.0
    overlap_fraction: float = 0.75
    significance_threshold_db: float = -40.0
    band_edges_hz: tuple[float, float] = (200.0, 4000.0)

    def validate(self, sample_rate: float) -> None:
        if isinstance(sample_rate, bool) or not np.isfinite(sample_rate) or sample_rate <= 0:
            raise ValueError("sample_rate must be finite and positive")
        if not np.isfinite(self.window_ms) or self.window_ms <= 0:
            raise ValueError("window_ms must be finite and positive")
        if not np.isfinite(self.overlap_fraction) or not 0 <= self.overlap_fraction < 1:
            raise ValueError("overlap_fraction must satisfy 0 <= overlap < 1")
        if not np.isfinite(self.significance_threshold_db) or not -300 <= self.significance_threshold_db <= 0:
            raise ValueError("significance_threshold_db must be between -300 and 0")
        if len(self.band_edges_hz) != 2:
            raise ValueError("band_edges_hz must contain two ordered frequencies")
        low, high = self.band_edges_hz
        if not np.all(np.isfinite([low, high])) or not 0 < low < high < sample_rate / 2:
            raise ValueError("band edges must satisfy 0 < low < high < Nyquist")


@dataclass(frozen=True)
class SpectralData:
    frequencies_hz: np.ndarray
    times_s: np.ndarray
    power_psd: np.ndarray
    welch_frequencies_hz: np.ndarray
    welch_psd: np.ndarray


def _samples(audio: np.ndarray) -> np.ndarray:
    if np.iscomplexobj(audio):
        raise ValueError("audio must be real-valued")
    x = np.asarray(audio, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    if x.ndim != 2 or x.shape[0] < 2 or x.shape[1] == 0:
        raise ValueError("audio must contain at least two samples and one channel")
    if not np.all(np.isfinite(x)):
        raise ValueError("audio contains non-finite samples")
    return x


def _peak_info(x: np.ndarray, flat_index: int, sample_rate: float) -> dict:
    sample, channel = np.unravel_index(flat_index, x.shape)
    value = float(x[sample, channel])
    return {
        "amplitude": abs(value),
        "signed_value": value,
        "sample_index": int(sample),
        "time_s": float(sample / sample_rate),
        "channel": int(channel + 1),
    }


def analyze_audio(
    audio: np.ndarray,
    sample_rate: float,
    settings: AnalysisSettings = AnalysisSettings(),
) -> tuple[dict, SpectralData]:
    """Return JSON-safe metrics and the spectra used to calculate them.

    Peak ties select the earliest sample, then the lowest channel index. The
    highest significant frequency is a threshold-dependent STFT-bin estimate,
    not a bandwidth guarantee: noise and leakage can raise it. Times of spectral
    events refer to window centers; frame spacing is not event-time accuracy.
    """
    settings.validate(sample_rate)
    x = _samples(audio)
    count, channels = x.shape
    window_samples = min(count, max(2, round(sample_rate * settings.window_ms / 1000)))
    hop = max(1, round(window_samples * (1 - settings.overlap_fraction)))
    nfft = 1 << (window_samples - 1).bit_length()
    frames = 1 + (count - window_samples) // hop
    # ShortTimeFFT normally centers frame zero at sample zero. Moving its
    # offset to half a window puts frame zero over x[0:window_samples].
    center = window_samples // 2
    transform = ShortTimeFFT(
        windows.hann(window_samples, sym=False), hop, sample_rate,
        mfft=nfft, fft_mode="onesided2X", scale_to="psd",
    )
    power = np.zeros((transform.f_pts, frames), dtype=np.float64)
    for channel in range(channels):
        power += transform.spectrogram(x[:, channel], p0=0, p1=frames, k_offset=center)
    power /= channels
    times = transform.t(count, p0=0, p1=frames, k_offset=center)
    frequencies = transform.f
    # A longer window is useful for a recording-wide dominant-frequency and
    # band-power estimate. It does not change the spectrogram's 30 ms window.
    welch_length = min(count, 8192)
    welch_frequencies, channel_welch = welch(
        x, fs=sample_rate, window="hann", nperseg=welch_length,
        noverlap=welch_length // 2, detrend=False, scaling="density", axis=0,
    )
    average_welch = np.mean(channel_welch, axis=1)
    maximum_power = float(np.max(power))
    strongest = None
    highest = None
    if maximum_power > 0:
        fi, ti = np.unravel_index(np.argmax(power), power.shape)
        strongest = {
            "frequency_hz": float(frequencies[fi]), "time_s": float(times[ti]),
            "psd": float(power[fi, ti]),
        }
        relative_threshold = 10 ** (settings.significance_threshold_db / 10)
        rows = np.flatnonzero(np.any(power / maximum_power >= relative_threshold, axis=1))
        fi = int(rows[-1])
        ti = int(np.argmax(power[fi]))
        highest = {
            "frequency_hz": float(frequencies[fi]), "time_s": float(times[ti]),
            "threshold_db_relative_to_peak": float(settings.significance_threshold_db),
            "psd": float(power[fi, ti]),
        }
    total_power = float(np.sum(average_welch))
    low, high = settings.band_edges_hz
    masks = {
        "low": welch_frequencies < low,
        "mid": (welch_frequencies >= low) & (welch_frequencies < high),
        "high": welch_frequencies >= high,
    }
    fractions = {
        band: float(np.sum(average_welch[mask]) / total_power) if total_power else None
        for band, mask in masks.items()
    }
    # Overflow is diagnosed explicitly rather than silently exporting Infinity.
    with np.errstate(over="ignore", invalid="ignore"):
        rms_per_channel = np.sqrt(np.mean(x * x, axis=0))
        rms = float(np.sqrt(np.mean(x * x)))
    if not np.isfinite(rms) or not np.all(np.isfinite(power)) or not math.isfinite(total_power):
        raise ValueError("audio magnitude is too large for finite power calculations")
    summary = {
        "sample_rate_hz": float(sample_rate),
        "channels": channels,
        "samples": count,
        "duration_s": float(count / sample_rate),
        "absolute_peak": _peak_info(x, int(np.argmax(np.abs(x))), sample_rate),
        "signed_maximum": _peak_info(x, int(np.argmax(x)), sample_rate),
        "rms": rms,
        "rms_per_channel": rms_per_channel.tolist(),
        "dc_per_channel": np.mean(x, axis=0).tolist(),
        "strongest_time_frequency_bin": strongest,
        "highest_significant_frequency": highest,
        "dominant_frequency_hz": float(welch_frequencies[np.argmax(average_welch)]) if total_power else None,
        "band_power_fraction": fractions,
        "band_edges_hz": [float(low), float(high)],
        "nyquist_hz": float(sample_rate / 2),
        "spectral_settings": {
            "window": "periodic Hann",
            "window_samples": window_samples,
            "window_ms": float(1000 * window_samples / sample_rate),
            "requested_window_ms": float(settings.window_ms),
            "hop_samples": hop,
            "overlap_fraction_actual": float(1 - hop / window_samples),
            "nfft": nfft,
            "frequency_bin_width_hz": float(sample_rate / nfft),
            "frame_step_s": float(hop / sample_rate),
            "frame_count": frames,
            "welch_window_samples": welch_length,
            "channel_aggregation": "arithmetic mean of per-channel powers; no waveform downmix",
            "time_reference": "seconds from first input sample; centers of fully contained windows",
            "threshold_definition": "PSD >= global spectrogram peak * 10**(threshold_dB/10); sensitive to noise and leakage",
            "significance_threshold_db": float(settings.significance_threshold_db),
            "psd_units": "sample_amplitude_squared_per_hz",
            "frequency_resolution_note": "FFT bin spacing is not window resolving power; zero padding interpolates the spectrum",
        },
    }
    spectra = SpectralData(frequencies, times, power, welch_frequencies, average_welch)
    return summary, spectra
