"""Known-signal checks of amplitude, frequency, time, and stereo analysis."""

import json
import unittest

import numpy as np

from ecc3852.analysis import AnalysisSettings, analyze_audio


class AnalysisTests(unittest.TestCase):
    fs = 16000

    def test_peak_time_channel_and_signed_peak(self):
        x = np.zeros((16000, 2))
        x[3200, 1] = -0.9
        x[8000, 0] = 0.7
        metrics, _ = analyze_audio(x, self.fs)
        peak = metrics["absolute_peak"]
        self.assertEqual(peak["channel"], 2)
        self.assertEqual(peak["sample_index"], 3200)
        self.assertEqual(peak["time_s"], 0.2)
        self.assertEqual(peak["amplitude"], 0.9)
        self.assertEqual(peak["signed_value"], -0.9)
        self.assertEqual(metrics["signed_maximum"]["signed_value"], 0.7)

    def test_tone_frequency_and_psd_power(self):
        t = np.arange(self.fs) / self.fs
        x = 0.4 * np.sin(2 * np.pi * 1000 * t)
        metrics, spectral = analyze_audio(x, self.fs)
        self.assertAlmostEqual(metrics["rms"], 0.4 / np.sqrt(2), places=10)
        self.assertLessEqual(abs(metrics["dominant_frequency_hz"] - 1000), self.fs / 8192)
        self.assertLessEqual(abs(metrics["strongest_time_frequency_bin"]["frequency_hz"] - 1000), 31.25)
        df = spectral.frequencies_hz[1] - spectral.frequencies_hz[0]
        np.testing.assert_allclose(np.sum(spectral.power_psd, axis=0) * df, 0.4 ** 2 / 2, rtol=0.001)
        self.assertGreater(metrics["band_power_fraction"]["mid"], 0.999)
        self.assertAlmostEqual(sum(metrics["band_power_fraction"].values()), 1.0)

    def test_antiphase_stereo_power_does_not_cancel(self):
        t = np.arange(self.fs) / self.fs
        mono = 0.3 * np.sin(2 * np.pi * 1000 * t)
        metrics, stereo = analyze_audio(np.column_stack([mono, -mono]), self.fs)
        _, single = analyze_audio(mono, self.fs)
        np.testing.assert_allclose(stereo.power_psd, single.power_psd)
        np.testing.assert_allclose(stereo.welch_psd, single.welch_psd, atol=1e-25)
        self.assertGreater(metrics["rms"], 0.2)

    def test_transient_time_is_window_center(self):
        # A Gaussian-envelope sinusoid has a known maximum near 0.65 seconds.
        t = np.arange(self.fs) / self.fs
        x = np.exp(-0.5 * ((t - 0.65) / 0.02) ** 2) * np.sin(2 * np.pi * 2000 * t)
        metrics, _ = analyze_audio(x, self.fs)
        strongest = metrics["strongest_time_frequency_bin"]
        self.assertLess(abs(strongest["time_s"] - 0.65), 0.008)
        self.assertLess(abs(strongest["frequency_hz"] - 2000), 32)

    def test_full_windows_match_an_independent_fft_and_times(self):
        # Compare a short odd-length example to direct non-padded windows.
        x = np.arange(37, dtype=float) / 100
        config = AnalysisSettings(window_ms=9 / self.fs * 1000, overlap_fraction=0.5)
        metrics, data = analyze_audio(x, self.fs, config)
        n = metrics["spectral_settings"]["window_samples"]
        hop = metrics["spectral_settings"]["hop_samples"]
        np.testing.assert_allclose(data.times_s * self.fs, np.arange(len(data.times_s)) * hop + n // 2)
        self.assertGreaterEqual(data.times_s[0] * self.fs - n // 2, 0)
        self.assertLessEqual(data.times_s[-1] * self.fs - n // 2 + n, len(x))
        window = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n) / n)
        expected = np.abs(np.fft.rfft(x[:n] * window, n=metrics["spectral_settings"]["nfft"])) ** 2 / (self.fs * np.sum(window ** 2))
        expected[1:-1] *= 2
        np.testing.assert_allclose(data.power_psd[:, 0], expected, rtol=1e-12, atol=1e-20)

    def test_highest_significant_frequency_uses_explicit_threshold(self):
        t = np.arange(self.fs) / self.fs
        x = np.sin(2 * np.pi * 1000 * t) + 0.05 * np.sin(2 * np.pi * 6000 * t)
        strict, _ = analyze_audio(x, self.fs, AnalysisSettings(significance_threshold_db=-20))
        loose, _ = analyze_audio(x, self.fs, AnalysisSettings(significance_threshold_db=-40))
        self.assertLess(strict["highest_significant_frequency"]["frequency_hz"], 2000)
        self.assertGreater(loose["highest_significant_frequency"]["frequency_hz"], 5900)
        self.assertLess(loose["highest_significant_frequency"]["frequency_hz"], self.fs / 2)

    def test_silence_has_null_spectral_events_and_valid_json(self):
        metrics, data = analyze_audio(np.zeros((1000, 2)), self.fs)
        self.assertIsNone(metrics["strongest_time_frequency_bin"])
        self.assertIsNone(metrics["highest_significant_frequency"])
        self.assertIsNone(metrics["dominant_frequency_hz"])
        self.assertTrue(all(value is None for value in metrics["band_power_fraction"].values()))
        self.assertEqual(metrics["rms"], 0)
        self.assertTrue(np.all(data.power_psd == 0))
        json.dumps(metrics, allow_nan=False)

    def test_short_audio_uses_full_available_window(self):
        for count in (2, 3, 7, 31):
            with self.subTest(count=count):
                metrics, data = analyze_audio(np.linspace(-0.2, 0.2, count), self.fs)
                self.assertEqual(metrics["spectral_settings"]["window_samples"], count)
                self.assertEqual(data.power_psd.shape[1], 1)
                json.dumps(metrics, allow_nan=False)

    def test_invalid_inputs_and_settings(self):
        for audio in ([], [1], [[1], [np.nan]], np.zeros((10, 0)), np.ones((3, 2, 2)), [1j, 2j]):
            with self.subTest(audio=str(audio)):
                with self.assertRaises(ValueError):
                    analyze_audio(audio, self.fs)
        for config in (
            AnalysisSettings(window_ms=0), AnalysisSettings(window_ms=np.nan),
            AnalysisSettings(overlap_fraction=1), AnalysisSettings(overlap_fraction=-0.1),
            AnalysisSettings(significance_threshold_db=1), AnalysisSettings(band_edges_hz=(4000, 200)),
            AnalysisSettings(band_edges_hz=(200, 8000)),
        ):
            with self.subTest(config=config):
                with self.assertRaises(ValueError):
                    analyze_audio(np.zeros(1000), self.fs, config)
        for rate in (0, -1, np.nan, np.inf, True):
            with self.subTest(rate=rate):
                with self.assertRaises(ValueError):
                    analyze_audio(np.zeros(1000), rate)


if __name__ == "__main__":
    unittest.main()
