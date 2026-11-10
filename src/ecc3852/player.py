"""Desktop playback; shared DSP stays in equalizer.py.

A single worker owns transport, processors and the blocking PortAudio stream.
There is no Python audio callback: design, warm-up and NumPy allocations happen
in this worker, not in a high-priority callback. This is best-effort real time.
"""

from dataclasses import asdict
from numbers import Integral
from pathlib import Path
import queue
import threading
import time

import numpy as np

from .audio_io import as_channels, load_audio
from .equalizer import EQSettings, EqualizerProcessor


def _positive_int(name, value):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


class RealtimeEqualizer:
    """Stateful, sample-counted EQ with coalesced 30 ms linear crossfades.

    A new processor is warmed with preceding input (at least 250 ms when
    available, extended using pole decay to 1e-8, capped at 2 seconds). This is
    finite-history initialization, not an exact infinite-history guarantee.
    During a fade both fixed-setting processors retain their own state. Rapid
    requests replace only the pending target; an in-progress fade completes.
    No output gain or clipping is hidden here.
    """

    def __init__(self, audio, sample_rate, settings=EQSettings(), crossfade_ms=30.0):
        if (isinstance(crossfade_ms, bool) or not np.isfinite(crossfade_ms)
                or not 0 < crossfade_ms <= 1000):
            raise ValueError("crossfade_ms must be in (0, 1000]")
        self.audio = np.array(as_channels(audio), copy=True)
        self.audio.flags.writeable = False
        self.channels = self.audio.shape[1]
        self._current = EqualizerProcessor(sample_rate, settings, self.channels)
        self.sample_rate = self._current.sample_rate
        self.fade_frames = max(1, round(self.sample_rate * crossfade_ms / 1000))
        self.position = 0
        self._target = settings
        self._next = None
        self._fade_position = 0

    @property
    def settings(self):
        return self._next.settings if self._next is not None else self._current.settings

    @property
    def target_settings(self):
        return self._target

    @property
    def finished(self):
        return self.position >= len(self.audio)

    @property
    def transitioning(self):
        return self._next is not None or self._current.settings != self._target

    def set_settings(self, settings):
        # Validate before accepting a request, without touching live state.
        EqualizerProcessor(self.sample_rate, settings, self.channels)
        self._target = settings

    def reset(self):
        self._current = EqualizerProcessor(self.sample_rate, self._target, self.channels)
        self._next = None
        self._fade_position = 0
        self.position = 0

    def _start_transition(self):
        if self._next is not None or self._current.settings == self._target:
            return
        self._next = EqualizerProcessor(self.sample_rate, self._target, self.channels)
        radius = max(float(np.max(np.abs(np.roots(row[3:])))) for row in self._next.sos)
        decay_frames = int(np.ceil(np.log(1e-8) / np.log(radius))) if 0 < radius < 1 else 0
        history = min(self.position, int(2 * self.sample_rate),
                      max(int(0.25 * self.sample_rate), decay_frames))
        if history:
            self._next.process(self.audio[self.position - history:self.position])
        self._fade_position = 0

    def render(self, frames):
        frames = _positive_int("frames", frames)
        remaining = min(frames, len(self.audio) - self.position)
        if not remaining:
            return np.empty((0, self.channels), dtype=np.float64)
        parts = []
        while remaining:
            self._start_transition()
            count = min(remaining, self.fade_frames - self._fade_position) if self._next else remaining
            block = self.audio[self.position:self.position + count]
            output = self._current.process(block)
            if self._next is not None:
                new = self._next.process(block)
                weight = (np.arange(count) + self._fade_position + 1) / self.fade_frames
                output = output * (1 - weight[:, None]) + new * weight[:, None]
                self._fade_position += count
                if self._fade_position == self.fade_frames:
                    self._current, self._next = self._next, None
            parts.append(output)
            self.position += count
            remaining -= count
        return parts[0] if len(parts) == 1 else np.concatenate(parts)


class OutputSafety:
    """Fixed playback attenuation followed by an explicit hard peak guard.

    No per-block normalization. Guard activity is distortion and is counted,
    not described as transparent limiting. Does not affect offline exports.
    """

    def __init__(self, volume_db=-18.0, ceiling=0.95):
        if (isinstance(volume_db, bool) or not np.isfinite(volume_db)
                or not -60 <= volume_db <= 0):
            raise ValueError("volume_db must be in [-60, 0]")
        if isinstance(ceiling, bool) or not np.isfinite(ceiling) or not 0 < ceiling < 1:
            raise ValueError("ceiling must be in (0, 1)")
        self.volume_db = float(volume_db)
        self.gain = 10 ** (self.volume_db / 20)
        self.ceiling = float(ceiling)
        self.reset()

    def reset(self):
        self.peak_before_limit = 0.0
        self.limited_samples = 0

    def process(self, block):
        samples = as_channels(block) * self.gain
        self.peak_before_limit = max(self.peak_before_limit, float(np.max(np.abs(samples))))
        self.limited_samples += int(np.count_nonzero(np.abs(samples) > self.ceiling))
        return np.clip(samples, -self.ceiling, self.ceiling)


def _sounddevice():
    try:
        import sounddevice as sd
    except (ImportError, OSError) as exc:
        raise RuntimeError("Install requirements-player.txt; sounddevice/PortAudio is unavailable") from exc
    return sd


def output_devices():
    sd = _sounddevice()
    return [dict(device, index=i) for i, device in enumerate(sd.query_devices())
            if device["max_output_channels"] > 0]


class AudioPlayer:
    """Asynchronous command API; GUI never touches worker-owned DSP/stream.

    load/play/pause/stop/set_settings enqueue commands. snapshot() supplies UI
    state; position counts submitted source samples, not a DAC timestamp.
    pause drains queued sound and retains EQ state; stop aborts and resets.
    """

    def __init__(self, settings=EQSettings(), *, device=None, block_size=512,
                 volume_db=-18.0, stream_factory=None):
        self.block_size = _positive_int("block_size", block_size)
        if not isinstance(settings, EQSettings):
            raise TypeError("settings must be EQSettings")
        self.device = device
        self._settings = settings
        self._safety = OutputSafety(volume_db)
        self._factory = stream_factory
        self._commands = queue.Queue()
        self._lock = threading.Lock()
        self._engine = None
        self._stream = None
        self._playing = False
        self._ramp_in = 0
        self._closed = False
        self._view = dict(state="empty", path=None, sample_rate_hz=None, channels=None,
                          position_samples=0, total_samples=0, volume_db=volume_db,
                          peak_before_limit=0.0, limited_samples=0, underflows=0,
                          latency_s=None, device=None, error=None, settings=asdict(settings),
                          max_processing_s=0.0, source=None, transitioning=False,
                          requested_settings=asdict(settings))
        self._thread = threading.Thread(target=self._run, name="ECC3852-audio", daemon=True)
        self._thread.start()

    def snapshot(self):
        with self._lock:
            return dict(self._view)

    def _publish(self, **changes):
        with self._lock:
            self._view.update(changes)

    def _send(self, command, value=None):
        if self._closed:
            raise RuntimeError("player is closed")
        self._commands.put((command, value))

    def load(self, path):
        self._send("load", Path(path))

    def play(self):
        self._send("play")

    def pause(self):
        self._send("pause")

    def stop(self):
        self._send("stop")

    def set_settings(self, settings):
        if not isinstance(settings, EQSettings):
            raise TypeError("settings must be EQSettings")
        self._send("settings", settings)

    def close(self):
        if not self._closed:
            self._commands.put(("close", None))
            self._closed = True
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                raise RuntimeError("audio worker did not close within five seconds")

    def _close_stream(self, abort=False):
        self._playing = False
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.abort() if abort else stream.stop()
            finally:
                stream.close()

    def _open_stream(self):
        kwargs = dict(samplerate=self._engine.sample_rate, channels=self._engine.channels,
                      dtype="float32", blocksize=self.block_size, latency=0.05,
                      device=self.device, clip_off=True)
        if self._factory is None:
            sd = _sounddevice()
            sd.check_output_settings(device=self.device, channels=self._engine.channels,
                                     dtype="float32", samplerate=self._engine.sample_rate)
            factory = sd.OutputStream
            info = dict(sd.query_devices(self.device, "output"))
        else:
            factory = self._factory
            info = {"name": "test stream"}
        self._stream = factory(**kwargs)
        self._stream.start()
        self._ramp_in = max(1, round(self._engine.sample_rate * 0.01))
        self._publish(latency_s=float(self._stream.latency), device=info)
        self._playing = True

    def _write(self, frames, fade_out=False):
        started = time.perf_counter()
        output = self._engine.render(frames)
        count = len(output)
        if not count:
            return
        ramp = max(1, round(self._engine.sample_rate * 0.01))
        if self._ramp_in:
            n = min(count, self._ramp_in)
            output[:n] *= ((np.arange(n) + ramp - self._ramp_in + 1) / ramp)[:, None]
            self._ramp_in -= n
        if fade_out:
            output *= np.linspace(1.0, 0.0, count)[:, None]
        else:
            # Fade the final 10 ms across block boundaries, before stopping.
            distance_to_end = len(self._engine.audio) - self._engine.position + np.arange(count, 0, -1) - 1
            output *= np.minimum(1.0, distance_to_end / ramp)[:, None]
        # sosfilt may return Fortran-ordered channel arrays; PortAudio's
        # blocking write requires C-contiguous frames x channels float32.
        safe = np.ascontiguousarray(self._safety.process(output), dtype=np.float32)
        elapsed = time.perf_counter() - started
        underflow = bool(self._stream.write(safe))
        view = self.snapshot()
        self._publish(position_samples=self._engine.position,
                      peak_before_limit=self._safety.peak_before_limit,
                      limited_samples=self._safety.limited_samples,
                      underflows=view["underflows"] + int(underflow),
                      max_processing_s=max(view["max_processing_s"], elapsed),
                      settings=asdict(self._engine.settings), transitioning=self._engine.transitioning)

    def _handle(self, command, value):
        if command == "close":
            try:
                self._close_stream(abort=True)
            except Exception as exc:
                self._publish(error=f"Device close failed: {exc}")
            finally:
                self._publish(state="closed")
            return False
        if command == "load":
            self._close_stream(abort=True)
            self._publish(state="loading", error=None)
            audio, fs, source = load_audio(value)
            self._engine = RealtimeEqualizer(audio, fs, self._settings)
            self._safety.reset()
            self._publish(state="stopped", path=str(value.resolve()), source=source,
                          sample_rate_hz=fs, channels=audio.shape[1], total_samples=len(audio),
                          position_samples=0, limited_samples=0, peak_before_limit=0.0,
                          underflows=0, max_processing_s=0.0, settings=asdict(self._settings),
                          transitioning=False, requested_settings=asdict(self._settings))
        elif command == "settings":
            if self._engine is not None:
                self._engine.set_settings(value)
            self._settings = value
            self._publish(requested_settings=asdict(value),
                          transitioning=self._engine.transitioning if self._engine else False)
        elif command == "play":
            if self._engine is None:
                raise RuntimeError("Load an audio file first")
            if not self._playing:
                if self._engine.finished:
                    self._engine.reset()
                    self._safety.reset()
                    self._publish(position_samples=0, limited_samples=0, peak_before_limit=0.0)
                self._open_stream()
                self._publish(state="playing", error=None)
        elif command == "pause" and self._playing:
            self._write(max(1, round(self._engine.sample_rate * 0.01)), fade_out=True)
            self._close_stream()
            self._publish(state="ended" if self._engine.finished else "paused")
        elif command == "stop":
            self._close_stream(abort=True)
            if self._engine is not None:
                self._engine.reset()
                self._safety.reset()
                self._publish(state="stopped", position_samples=0, limited_samples=0,
                              peak_before_limit=0.0, settings=asdict(self._engine.settings),
                              transitioning=False, error=None)
        return True

    def _run(self):
        running = True
        while running:
            try:
                try:
                    command, value = self._commands.get(timeout=0 if self._playing else 0.05)
                except queue.Empty:
                    command = None
                if command is not None:
                    # Coalesce adjacent slider events, preserving transport order.
                    if command == "settings":
                        while True:
                            try:
                                following = self._commands.get_nowait()
                            except queue.Empty:
                                break
                            if following[0] == "settings":
                                value = following[1]
                            else:
                                running = self._handle(command, value)
                                command, value = following
                                break
                    running = self._handle(command, value)
                if running and self._playing:
                    self._write(self.block_size)
                    if self._engine.finished:
                        self._close_stream()
                        self._publish(state="ended")
            except Exception as exc:
                try:
                    self._close_stream(abort=True)
                except Exception:
                    pass
                self._publish(state="error", error=f"{type(exc).__name__}: {exc}")
