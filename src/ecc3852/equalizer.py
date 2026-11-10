"""Inspectable, causal three-band IIR equalizer for the ECC3852 assignment.

The cascade uses Robert Bristow-Johnson's Audio EQ Cookbook biquads: a low
shelf, a peaking filter, and a high shelf. Shelf slope S is fixed at 1. Each
SOS row stores [b0, b1, b2, 1, a1, a2], representing
H(z) = (b0 + b1*z^-1 + b2*z^-2) / (1 + a1*z^-1 + a2*z^-2).
No normalization, limiter, or sample clipping is hidden in the filter.

Coefficient reference: https://www.w3.org/TR/audio-eq-cookbook/
"""

from dataclasses import dataclass
from numbers import Integral, Real

import numpy as np
from scipy.signal import sosfilt, sosfreqz


def _finite_real(name, value):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    if not np.isfinite(value):
        raise ValueError(f"{name} must be a finite real number")
    return float(value)


@dataclass(frozen=True)
class EQSettings:
    """User controls; frequencies are Hz and gains are dB.

    Shelf frequencies mark each shelf's midpoint in dB. mid_hz is the peaking
    filter center, and mid_q controls its bandwidth. These frequencies are
    design choices, not sharp, nonoverlapping boundaries between bands.
    """

    bass_db: float = 0.0
    mid_db: float = 0.0
    treble_db: float = 0.0
    bass_hz: float = 200.0
    mid_hz: float = 1000.0
    treble_hz: float = 4000.0
    mid_q: float = 1.0

    def __post_init__(self):
        for name in ("bass_db", "mid_db", "treble_db"):
            value = _finite_real(name, getattr(self, name))
            if not -12.0 <= value <= 12.0:
                raise ValueError(f"{name} must be between -12 and +12 dB")
        for name in ("bass_hz", "mid_hz", "treble_hz", "mid_q"):
            if _finite_real(name, getattr(self, name)) <= 0:
                raise ValueError(f"{name} must be positive")
        if not self.bass_hz < self.mid_hz < self.treble_hz:
            raise ValueError("frequencies must satisfy bass_hz < mid_hz < treble_hz")


def _sample_rate(sample_rate, settings):
    fs = _finite_real("sample_rate", sample_rate)
    if fs <= 0:
        raise ValueError("sample_rate must be positive")
    if not isinstance(settings, EQSettings):
        raise TypeError("settings must be an EQSettings instance")
    if settings.treble_hz >= fs / 2.0:
        raise ValueError("all EQ frequencies must be below the Nyquist frequency")
    return fs


def _biquad(kind, frequency, gain_db, sample_rate, q=1.0):
    # Explicit identity guarantees an exact flat setting without cancellation.
    if gain_db == 0:
        return np.array([1.0, 0.0, 0.0, 1.0, 0.0, 0.0])
    amplitude = 10.0 ** (gain_db / 40.0)
    omega = 2.0 * np.pi * frequency / sample_rate
    cosine, sine = np.cos(omega), np.sin(omega)
    if kind == "peak":
        alpha = sine / (2.0 * q)
        b = [1.0 + alpha * amplitude, -2.0 * cosine, 1.0 - alpha * amplitude]
        a = [1.0 + alpha / amplitude, -2.0 * cosine, 1.0 - alpha / amplitude]
    else:
        # RBJ shelf alpha = sin(w0)/2 * sqrt((A + 1/A)*(1/S - 1) + 2).
        # For shelf slope S=1, this reduces to sin(w0)/sqrt(2).
        alpha = sine / np.sqrt(2.0)
        beta = 2.0 * np.sqrt(amplitude) * alpha
        plus, minus = amplitude + 1.0, amplitude - 1.0
        if kind == "low":
            b = [amplitude * (plus - minus * cosine + beta),
                 2.0 * amplitude * (minus - plus * cosine),
                 amplitude * (plus - minus * cosine - beta)]
            a = [plus + minus * cosine + beta,
                 -2.0 * (minus + plus * cosine),
                 plus + minus * cosine - beta]
        else:
            b = [amplitude * (plus + minus * cosine + beta),
                 -2.0 * amplitude * (minus + plus * cosine),
                 amplitude * (plus + minus * cosine - beta)]
            a = [plus - minus * cosine + beta,
                 2.0 * (minus - plus * cosine),
                 plus - minus * cosine - beta]
    return np.asarray(b + a, dtype=np.float64) / a[0]


def design_equalizer(sample_rate, settings):
    """Return normalized SOS coefficients for low shelf -> peak -> high shelf."""
    fs = _sample_rate(sample_rate, settings)
    sos = np.vstack([
        _biquad("low", settings.bass_hz, settings.bass_db, fs),
        _biquad("peak", settings.mid_hz, settings.mid_db, fs, settings.mid_q),
        _biquad("high", settings.treble_hz, settings.treble_db, fs),
    ])
    if not np.all(np.isfinite(sos)):
        raise ValueError("parameters produce nonfinite filter coefficients")
    if any(np.any(np.abs(np.roots(row[3:])) >= 1.0) for row in sos):
        raise ValueError("parameters do not produce numerically stable biquads")
    return sos


def _audio_array(audio):
    array = np.asarray(audio)
    if array.ndim not in (1, 2) or array.shape[0] == 0:
        raise ValueError("audio must have shape (samples,) or (samples, channels) and be nonempty")
    if array.ndim == 2 and array.shape[1] == 0:
        raise ValueError("audio must contain at least one channel")
    if array.dtype.kind not in "fiu" or not np.all(np.isfinite(array)):
        raise ValueError("audio must contain finite real numeric samples")
    return array.astype(np.float64, copy=False)


def apply_equalizer(audio, sample_rate, settings):
    """Filter along the sample axis with zero initial state and preserve shape.

    This is a causal single pass, suitable for comparison with later streaming
    processing. It deliberately does not use forward/backward zero-phase filtering.
    Input amplitudes should conventionally be in [-1, 1], but floating-point
    headroom is preserved for the caller to measure and handle before WAV export.
    """
    array = _audio_array(audio)
    return sosfilt(design_equalizer(sample_rate, settings), array, axis=0)


def frequency_response(sample_rate, settings, points=4096):
    """Return frequencies (Hz, including DC/Nyquist) and magnitude response (dB)."""
    if isinstance(points, (bool, np.bool_)) or not isinstance(points, Integral) or points < 2:
        raise ValueError("points must be an integer of at least 2")
    fs = _sample_rate(sample_rate, settings)
    frequencies = np.linspace(0.0, fs / 2.0, int(points))
    frequencies, response = sosfreqz(design_equalizer(fs, settings), worN=frequencies, fs=fs)
    magnitude_db = 20.0 * np.log10(np.maximum(np.abs(response), np.finfo(float).tiny))
    return frequencies, magnitude_db


class EqualizerProcessor:
    """Fixed-setting block processor retaining independent state per channel.

    Reusing an instance across blocks gives the same result as a full causal
    pass. reset() explicitly starts a new stream. Smooth live parameter changes
    belong to the future player integration; this class never swaps coefficients
    silently in the middle of an existing stream.
    """

    def __init__(self, sample_rate, settings, channels=1):
        if (isinstance(channels, (bool, np.bool_))
                or not isinstance(channels, Integral) or channels < 1):
            raise ValueError("channels must be a positive integer")
        self.sample_rate = _sample_rate(sample_rate, settings)
        self.settings = settings
        self.channels = int(channels)
        self.sos = design_equalizer(self.sample_rate, settings)
        self.reset()

    def reset(self):
        """Clear filter delays independently for each section and channel."""
        self._state = np.zeros((len(self.sos), 2, self.channels), dtype=np.float64)

    def process(self, block):
        """Process one finite, nonempty block; preserve its 1D or 2D shape."""
        array = _audio_array(block)
        mono = array.ndim == 1
        samples = array[:, None] if mono else array
        if samples.shape[1] != self.channels:
            raise ValueError(f"expected {self.channels} channels, received {samples.shape[1]}")
        output, self._state = sosfilt(self.sos, samples, axis=0, zi=self._state)
        return output[:, 0] if mono else output
