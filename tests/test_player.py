"""Player-layer checks with synthetic arrays; no GUI or audio device required."""

from pathlib import Path
import tempfile
import threading
import time
import unittest

import numpy as np
import soundfile as sf

from ecc3852.equalizer import EQSettings, apply_equalizer
from ecc3852.player import AudioPlayer, OutputSafety, RealtimeEqualizer


class RealtimeEqualizerTests(unittest.TestCase):
    def setUp(self):
        self.fs = 44100
        self.rng = np.random.default_rng(3852)

    def test_fixed_settings_match_offline_for_irregular_blocks(self):
        settings = EQSettings(bass_db=8, mid_db=-6, treble_db=5)
        for channels in (1, 2):
            with self.subTest(channels=channels):
                audio = self.rng.normal(0, 0.04, (4301, channels))
                player = RealtimeEqualizer(audio, self.fs, settings)
                blocks = [player.render(n) for n in (1, 17, 257, 1024, 3002)]
                np.testing.assert_array_equal(
                    np.concatenate(blocks), apply_equalizer(audio, self.fs, settings)
                )
                self.assertEqual(player.position, len(audio))
                self.assertTrue(player.finished)

    def test_mono_input_has_a_channel_axis_and_flat_is_identity(self):
        audio = self.rng.normal(0, 0.1, 53)
        player = RealtimeEqualizer(audio, self.fs)
        actual = player.render(100)
        self.assertEqual(actual.shape, (53, 1))
        np.testing.assert_array_equal(actual[:, 0], audio)

    def test_stereo_channels_do_not_share_filter_history(self):
        audio = np.zeros((3000, 2))
        audio[0, 0] = 0.1
        player = RealtimeEqualizer(audio, self.fs, EQSettings(bass_db=12))
        actual = np.concatenate([player.render(333), player.render(2667)])
        np.testing.assert_array_equal(actual[:, 1], 0)
        self.assertTrue(np.any(actual[:, 0] != 0))

    def test_eof_returns_only_remaining_samples_then_empty(self):
        audio = np.arange(22, dtype=float).reshape(11, 2) / 100
        player = RealtimeEqualizer(audio, self.fs)
        self.assertFalse(player.finished)
        self.assertEqual(player.render(8).shape, (8, 2))
        self.assertFalse(player.finished)
        np.testing.assert_array_equal(player.render(8), audio[8:])
        self.assertTrue(player.finished)
        self.assertEqual(player.render(8).shape, (0, 2))
        self.assertEqual(player.position, 11)

    def test_retaining_an_instance_across_a_pause_preserves_state(self):
        # A paused output stream must simply refrain from rendering samples.
        audio = self.rng.normal(0, 0.03, (5000, 2))
        settings = EQSettings(bass_db=6, mid_db=-4, treble_db=7)
        player = RealtimeEqualizer(audio, self.fs, settings)
        before_pause = player.render(511)
        paused_position = player.position
        self.assertEqual(player.position, paused_position)
        after_pause = player.render(5000)
        np.testing.assert_array_equal(
            np.concatenate((before_pause, after_pause)),
            apply_equalizer(audio, self.fs, settings),
        )

    def test_reset_clears_position_and_filter_delays(self):
        audio = self.rng.normal(0, 0.04, (2300, 2))
        settings = EQSettings(bass_db=11, mid_db=-8, treble_db=4)
        player = RealtimeEqualizer(audio, self.fs, settings)
        player.render(1400)
        player.reset()
        self.assertEqual(player.position, 0)
        self.assertFalse(player.finished)
        np.testing.assert_array_equal(
            player.render(3000), apply_equalizer(audio, self.fs, settings)
        )

    def test_reset_adopts_latest_requested_settings_without_an_old_fade(self):
        audio = self.rng.normal(0, 0.03, (6000, 2))
        player = RealtimeEqualizer(audio, self.fs)
        player.render(1000)
        player.set_settings(EQSettings(bass_db=6))
        player.render(10)
        latest = EQSettings(mid_db=-9, treble_db=8)
        player.set_settings(latest)
        player.reset()
        self.assertEqual(player.settings, latest)
        np.testing.assert_array_equal(
            player.render(len(audio)), apply_equalizer(audio, self.fs, latest)
        )

    def test_fast_targets_do_not_interrupt_current_fade_and_latest_wins(self):
        audio = self.rng.normal(0, 0.03, (12000, 2))
        player = RealtimeEqualizer(audio, self.fs, crossfade_ms=30)
        first = EQSettings(bass_db=10)
        skipped = EQSettings(mid_db=-12)
        latest = EQSettings(treble_db=9)
        player.set_settings(first)
        player.render(100)
        self.assertEqual(player.settings, first)
        player.set_settings(skipped)
        player.set_settings(latest)
        player.render(100)
        self.assertEqual(player.settings, first)
        blocks = [player.render(211) for _ in range(30)]
        self.assertTrue(np.all(np.isfinite(np.concatenate(blocks))))
        self.assertEqual(player.settings, latest)

    def test_warmed_switch_is_continuous_and_reaches_expected_dc_gain(self):
        # Constant input makes a switching transient distinguishable from a
        # natural waveform jump; +12 dB bass has known steady-state DC gain.
        audio = np.full((10000, 1), 0.04)
        player = RealtimeEqualizer(audio, self.fs, crossfade_ms=30)
        prefix = player.render(3000)
        player.set_settings(EQSettings(bass_db=12))
        transition = np.concatenate([player.render(173) for _ in range(20)])
        joined = np.concatenate((prefix[-1:], transition))[:, 0]
        self.assertLess(float(np.max(np.abs(np.diff(joined)))), 0.001)
        expected = 0.04 * 10 ** (12 / 20)
        np.testing.assert_allclose(transition[-200:, 0], expected, atol=1e-7, rtol=0)

    def test_switch_progress_is_independent_of_render_block_boundaries(self):
        audio = self.rng.normal(0, 0.03, (6500, 2))
        target = EQSettings(bass_db=8, mid_db=-7, treble_db=6)
        whole = RealtimeEqualizer(audio, self.fs, crossfade_ms=30)
        split = RealtimeEqualizer(audio, self.fs, crossfade_ms=30)
        whole.render(2000)
        split.render(2000)
        whole.set_settings(target)
        split.set_settings(target)
        expected = whole.render(4000)
        actual = np.concatenate([split.render(n) for n in (1, 511, 17, 1999, 1472)])
        np.testing.assert_allclose(actual, expected, atol=1e-12, rtol=0)

    def test_invalid_audio_rate_fade_and_frame_count_are_rejected(self):
        invalid_audio = ([], np.zeros((0, 2)), np.zeros((4, 0)),
                         np.zeros((2, 2, 2)), [np.nan], [np.inf], [1 + 1j])
        for audio in invalid_audio:
            with self.subTest(audio=audio), self.assertRaises(ValueError):
                RealtimeEqualizer(audio, self.fs)
        for rate in (0, -1, 8000, np.nan, np.inf, True):
            with self.subTest(rate=rate), self.assertRaises(ValueError):
                RealtimeEqualizer(np.ones((10, 1)), rate)
        for fade in (-1, np.nan, np.inf, True):
            with self.subTest(fade=fade), self.assertRaises(ValueError):
                RealtimeEqualizer(np.ones((10, 1)), self.fs, crossfade_ms=fade)
        player = RealtimeEqualizer(np.ones((10, 1)), self.fs)
        for frames in (0, -1, 1.5, True):
            with self.subTest(frames=frames), self.assertRaises(ValueError):
                player.render(frames)


class OutputSafetyTests(unittest.TestCase):
    def test_fixed_volume_preserves_relative_amplitudes_without_normalizing(self):
        block = np.array([[0.1, -0.2], [0.3, -0.4]])
        safety = OutputSafety(volume_db=-6, ceiling=0.95)
        expected = block * 10 ** (-6 / 20)
        np.testing.assert_allclose(safety.process(block), expected, atol=1e-15, rtol=0)
        self.assertAlmostEqual(safety.peak_before_limit, np.max(np.abs(expected)))
        self.assertEqual(safety.limited_samples, 0)

    def test_peak_protection_and_cumulative_per_channel_element_count(self):
        safety = OutputSafety(volume_db=0, ceiling=0.95)
        actual = safety.process(np.array([[0.2, -0.7], [1.0, -2.0]]))
        np.testing.assert_array_equal(actual, [[0.2, -0.7], [0.95, -0.95]])
        self.assertEqual(safety.limited_samples, 2)
        self.assertEqual(safety.peak_before_limit, 2)
        safety.process(np.array([[2.0, -3.0]]))
        self.assertEqual(safety.limited_samples, 4)
        self.assertEqual(safety.peak_before_limit, 3)
        safety.process(np.zeros((3, 2)))
        self.assertEqual(safety.limited_samples, 4)
        self.assertEqual(safety.peak_before_limit, 3)

    def test_safety_is_independent_of_block_boundaries_and_preserves_silence(self):
        audio = np.array([[0.0, 0.0], [2.0, -3.0], [0.01, -0.2], [4.0, -5.0]])
        whole = OutputSafety(volume_db=-6)
        split = OutputSafety(volume_db=-6)
        expected = whole.process(audio)
        actual = np.concatenate([split.process(audio[:1]), split.process(audio[1:3]),
                                 split.process(audio[3:])])
        np.testing.assert_array_equal(actual, expected)
        np.testing.assert_array_equal(actual[0], 0)
        self.assertEqual(split.limited_samples, whole.limited_samples)
        self.assertEqual(split.peak_before_limit, whole.peak_before_limit)

    def test_nonfinite_samples_and_invalid_safety_parameters_are_rejected(self):
        for volume in (np.nan, np.inf, True):
            with self.subTest(volume=volume), self.assertRaises(ValueError):
                OutputSafety(volume_db=volume)
        for ceiling in (0, -1, 1, 1.1, np.nan, np.inf, True):
            with self.subTest(ceiling=ceiling), self.assertRaises(ValueError):
                OutputSafety(ceiling=ceiling)
        safety = OutputSafety()
        for block in (np.array([[np.nan]]), np.array([[np.inf]])):
            with self.subTest(block=block), self.assertRaises(ValueError):
                safety.process(block)


class FakeOutputStream:
    """A blocking output sink that never accesses PortAudio or a device."""

    latency = 0.05

    def __init__(self, **kwargs):
        self.options = kwargs
        self.blocks = []
        self.operations = []
        self.started = False
        self.stopped = False
        self.aborted = False
        self.closed = False
        self.fail_abort = False
        self.fail_close = False
        self.written = threading.Event()

    def _record(self, operation):
        self.operations.append((operation, threading.get_ident()))

    def start(self):
        self._record("start")
        self.started = True

    def write(self, samples):
        self._record("write")
        if not self.started or self.closed:
            raise RuntimeError("write on inactive fake output")
        if samples.ndim != 2:
            raise AssertionError("output stream requires a samples x channels array")
        if samples.dtype != np.float32:
            raise AssertionError("output stream requires float32 samples")
        if not samples.flags.c_contiguous:
            raise AssertionError("output stream requires C-contiguous samples")
        if samples.shape[1] != self.options["channels"]:
            raise AssertionError("output stream channel count does not match device")
        if not np.all(np.isfinite(samples)):
            raise AssertionError("nonfinite samples must never reach an output device")
        self.blocks.append(np.array(samples, copy=True))
        self.written.set()
        # Model device-paced blocking so pause/stop can arrive before EOF.
        time.sleep(len(samples) / self.options["samplerate"])
        return False

    def stop(self):
        self._record("stop")
        self.stopped = True

    def abort(self):
        self._record("abort")
        self.aborted = True
        if self.fail_abort:
            raise OSError("fake abort failure")

    def close(self):
        self._record("close")
        self.closed = True
        if self.fail_close:
            raise OSError("fake close failure")


class FakeStreamFactory:
    def __init__(self, fail_opens=0):
        self.fail_opens = fail_opens
        self.attempts = 0
        self.streams = []

    def __call__(self, **kwargs):
        self.attempts += 1
        if self.attempts <= self.fail_opens:
            raise OSError("fake open failure")
        stream = FakeOutputStream(**kwargs)
        self.streams.append(stream)
        return stream


class AudioPlayerLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.fs = 44100
        self.tmp = tempfile.TemporaryDirectory(prefix="ecc3852-player-test-")
        self.addCleanup(self.tmp.cleanup)

    def make_audio(self, name="synthetic.wav", frames=60000, channels=2):
        path = Path(self.tmp.name) / name
        time_axis = np.arange(frames) / self.fs
        mono = 0.04 * np.sin(2 * np.pi * 1000 * time_axis)
        sf.write(path, np.repeat(mono[:, None], channels, axis=1),
                 self.fs, subtype="PCM_24")
        return path

    def make_player(self, factory=None):
        factory = FakeStreamFactory() if factory is None else factory
        player = AudioPlayer(block_size=512, stream_factory=factory)
        self.addCleanup(player.close)
        return player, factory

    def wait_for(self, player, predicate, message="player state did not arrive"):
        deadline = time.monotonic() + 2.0
        tick = threading.Event()
        while time.monotonic() < deadline:
            view = player.snapshot()
            if predicate(view):
                return view
            tick.wait(0.005)
        self.fail(f"{message}: {player.snapshot()}")

    def load_ready(self, player, path):
        player.load(path)
        return self.wait_for(player, lambda view: view["state"] == "stopped")

    def test_load_reports_metadata_without_opening_an_output_stream(self):
        path = self.make_audio(frames=3211)
        player, factory = self.make_player()
        self.assertEqual(player.snapshot()["state"], "empty")
        view = self.load_ready(player, path)
        self.assertEqual(view["path"], str(path.resolve()))
        self.assertEqual(view["sample_rate_hz"], self.fs)
        self.assertEqual(view["channels"], 2)
        self.assertEqual(view["position_samples"], 0)
        self.assertEqual(view["total_samples"], 3211)
        self.assertEqual(view["source"]["sample_rate_hz"], self.fs)
        self.assertFalse(factory.streams)

    def test_play_pause_resume_stop_use_one_worker_and_preserve_position(self):
        player, factory = self.make_player()
        self.load_ready(player, self.make_audio())
        player.play()
        self.wait_for(player, lambda view: view["position_samples"] >= 512)
        player.pause()
        paused = self.wait_for(player, lambda view: view["state"] == "paused")
        position = paused["position_samples"]
        self.assertGreater(position, 0)
        self.assertTrue(factory.streams[0].stopped)
        self.assertTrue(factory.streams[0].closed)
        threading.Event().wait(0.03)
        self.assertEqual(player.snapshot()["position_samples"], position)
        player.play()
        self.wait_for(player, lambda view: view["position_samples"] > position)
        self.assertEqual(len(factory.streams), 2)
        player.stop()
        stopped = self.wait_for(player, lambda view: view["state"] == "stopped")
        self.assertEqual(stopped["position_samples"], 0)
        self.assertTrue(factory.streams[-1].aborted)
        self.assertTrue(factory.streams[-1].closed)
        operation_threads = {ident for stream in factory.streams
                             for _, ident in stream.operations}
        self.assertEqual(len(operation_threads), 1)
        self.assertNotIn(threading.get_ident(), operation_threads)
        self.assertEqual(factory.streams[0].options["samplerate"], self.fs)
        self.assertEqual(factory.streams[0].options["channels"], 2)
        self.assertEqual(factory.streams[0].blocks[0].dtype, np.float32)

    def test_eof_closes_stream_and_replay_starts_from_identical_samples(self):
        frames = 2003
        player, factory = self.make_player()
        self.load_ready(player, self.make_audio(frames=frames))
        player.play()
        ended = self.wait_for(player, lambda view: view["state"] == "ended")
        self.assertEqual(ended["position_samples"], frames)
        first = np.concatenate(factory.streams[0].blocks)
        self.assertEqual(first.shape, (frames, 2))
        self.assertTrue(factory.streams[0].stopped)
        self.assertTrue(factory.streams[0].closed)
        np.testing.assert_array_equal(first[-1], 0)
        player.play()
        self.wait_for(player, lambda view: len(factory.streams) == 2
                      and view["state"] == "ended")
        second = np.concatenate(factory.streams[1].blocks)
        np.testing.assert_array_equal(second, first)

    def test_output_open_failure_is_visible_and_play_can_retry(self):
        factory = FakeStreamFactory(fail_opens=1)
        player, _ = self.make_player(factory)
        self.load_ready(player, self.make_audio())
        player.play()
        error = self.wait_for(player, lambda view: view["state"] == "error")
        self.assertIn("fake open failure", error["error"])
        self.assertEqual(error["position_samples"], 0)
        player.play()
        playing = self.wait_for(player, lambda view: view["state"] == "playing"
                                and view["position_samples"] >= 512)
        self.assertIsNone(playing["error"])
        self.assertEqual(factory.attempts, 2)
        player.stop()
        self.wait_for(player, lambda view: view["state"] == "stopped")

    def test_missing_input_error_recovers_after_loading_a_valid_file(self):
        player, _ = self.make_player()
        player.load(Path(self.tmp.name) / "does-not-exist.wav")
        error = self.wait_for(player, lambda view: view["state"] == "error")
        self.assertIn("FileNotFoundError", error["error"])
        ready = self.load_ready(player, self.make_audio(frames=1000))
        self.assertIsNone(ready["error"])
        player.play()
        self.wait_for(player, lambda view: view["state"] == "ended")

    def test_loading_another_file_aborts_old_stream_and_replaces_metadata(self):
        player, factory = self.make_player()
        self.load_ready(player, self.make_audio())
        player.play()
        self.wait_for(player, lambda view: view["position_samples"] >= 512)
        path = self.make_audio("synthetic_mono.wav", frames=1501, channels=1)
        ready = self.load_ready(player, path)
        self.assertTrue(factory.streams[0].aborted)
        self.assertTrue(factory.streams[0].closed)
        self.assertEqual(ready["channels"], 1)
        self.assertEqual(ready["total_samples"], 1501)
        self.assertEqual(ready["position_samples"], 0)
        player.play()
        self.wait_for(player, lambda view: view["state"] == "ended")
        self.assertEqual(np.concatenate(factory.streams[1].blocks).shape, (1501, 1))

    def test_live_settings_reach_worker_and_stop_preserves_latest_target(self):
        player, _ = self.make_player()
        self.load_ready(player, self.make_audio())
        player.play()
        self.wait_for(player, lambda view: view["position_samples"] >= 512)
        target = EQSettings(bass_db=5, mid_db=-7, treble_db=8)
        player.set_settings(target)
        applied = self.wait_for(player, lambda view: view["settings"]["mid_db"] == -7
                                and view["position_samples"] >= 3000)
        self.assertEqual(applied["settings"]["bass_db"], 5)
        player.stop()
        stopped = self.wait_for(player, lambda view: view["state"] == "stopped")
        self.assertEqual(stopped["settings"]["treble_db"], 8)
        self.assertEqual(stopped["position_samples"], 0)
        player.set_settings(EQSettings())
        player.stop()
        self.wait_for(player, lambda view: view["settings"]["bass_db"] == 0)

    def test_close_terminates_worker_closes_output_and_rejects_commands(self):
        player, factory = self.make_player()
        self.load_ready(player, self.make_audio())
        player.play()
        self.wait_for(player, lambda view: view["position_samples"] >= 512)
        player.close()
        self.assertEqual(player.snapshot()["state"], "closed")
        self.assertFalse(player._thread.is_alive())
        self.assertTrue(factory.streams[-1].aborted)
        self.assertTrue(factory.streams[-1].closed)
        player.close()
        with self.assertRaises(RuntimeError):
            player.play()
        with self.assertRaises(RuntimeError):
            player.load(self.make_audio("after_close.wav", frames=10))

    def test_close_terminates_worker_even_when_device_shutdown_raises(self):
        for fail_abort, fail_close in ((True, False), (False, True), (True, True)):
            with self.subTest(fail_abort=fail_abort, fail_close=fail_close):
                player, factory = self.make_player()
                self.load_ready(player, self.make_audio())
                player.play()
                self.wait_for(player, lambda view: view["position_samples"] >= 512)
                stream = factory.streams[-1]
                stream.fail_abort = fail_abort
                stream.fail_close = fail_close
                player.close()
                self.assertFalse(player._thread.is_alive())
                self.assertEqual(player.snapshot()["state"], "closed")
                self.assertTrue(stream.aborted)
                # close must still be attempted if abort raised.
                self.assertTrue(stream.closed)


if __name__ == "__main__":
    unittest.main()
