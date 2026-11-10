"""Numerical DSP checks using known signals, not subjective music quality claims."""

import itertools
import unittest

import numpy as np
from scipy.signal import sosfreqz

from ecc3852.equalizer import (
    EQSettings,
    EqualizerProcessor,
    apply_equalizer,
    design_equalizer,
    frequency_response,
)


class EqualizerTests(unittest.TestCase):
    def test_zero_gain_is_identity_for_mono_and_stereo(self):
        rng = np.random.default_rng(3852)
        for shape in ((4096,), (4096, 1), (4096, 2)):
            samples = rng.normal(0.0, 0.1, shape)
            np.testing.assert_array_equal(apply_equalizer(samples, 44100, EQSettings()), samples)

    def test_stable_at_gain_corners_and_standard_sample_rates(self):
        for fs, gains in itertools.product((44100, 48000), itertools.product((-12.0, 0.0, 12.0), repeat=3)):
            with self.subTest(sample_rate=fs, gains=gains):
                sos = design_equalizer(fs, EQSettings(*gains))
                self.assertEqual(sos.shape, (3, 6))
                np.testing.assert_array_equal(sos[:, 3], 1.0)
                for row in sos:
                    self.assertTrue(np.all(np.abs(np.roots(row[3:])) < 1.0))

    def test_shelf_endpoints_and_mid_center_match_requested_gain(self):
        for gain in (-12.0, -6.0, 6.0, 12.0):
            for setting, frequency in ((EQSettings(bass_db=gain), 0.0),
                                       (EQSettings(mid_db=gain), 1000.0),
                                       (EQSettings(treble_db=gain), 22050.0)):
                with self.subTest(gain=gain, setting=setting):
                    _, response = sosfreqz(design_equalizer(44100, setting), worN=[frequency], fs=44100)
                    self.assertAlmostEqual(20 * np.log10(abs(response[0])), gain, places=8)

    def test_controls_change_only_the_corresponding_biquad(self):
        baseline = design_equalizer(48000, EQSettings())
        for index, setting in enumerate((EQSettings(bass_db=6), EQSettings(mid_db=6), EQSettings(treble_db=6))):
            changed = design_equalizer(48000, setting)
            self.assertFalse(np.array_equal(changed[index], baseline[index]))
            for other in range(3):
                if other != index:
                    np.testing.assert_array_equal(changed[other], baseline[other])

    def test_measured_steady_state_tone_gain_matches_transfer_function(self):
        fs = 48000
        setting = EQSettings(bass_db=8, mid_db=-6, treble_db=5)
        time = np.arange(fs * 2) / fs
        # Integer-period tones permit an RMS gain check after the first second.
        for frequency in (50, 200, 1000, 4000, 12000):
            with self.subTest(frequency=frequency):
                signal = 0.05 * np.sin(2 * np.pi * frequency * time)
                filtered = apply_equalizer(signal, fs, setting)
                measured = 20 * np.log10(np.linalg.norm(filtered[fs:]) / np.linalg.norm(signal[fs:]))
                _, response = sosfreqz(design_equalizer(fs, setting), worN=[frequency], fs=fs)
                expected = 20 * np.log10(abs(response[0]))
                self.assertAlmostEqual(measured, expected, places=7)

    def test_streaming_equals_offline_with_irregular_chunks_and_reset(self):
        setting = EQSettings(bass_db=6, mid_db=-5, treble_db=3)
        rng = np.random.default_rng(123)
        for channels in (1, 2):
            samples = rng.normal(0, 0.05, (3333, channels))
            if channels == 1:
                samples = samples[:, 0]
            processor = EqualizerProcessor(44100, setting, channels)
            chunks = [samples[:1], samples[1:258], samples[258:1025], samples[1025:]]
            actual = np.concatenate([processor.process(chunk) for chunk in chunks])
            expected = apply_equalizer(samples, 44100, setting)
            np.testing.assert_allclose(actual, expected, rtol=0, atol=0)
            processor.reset()
            np.testing.assert_allclose(processor.process(samples), expected, rtol=0, atol=0)

    def test_no_crosstalk_between_stereo_channels(self):
        samples = np.zeros((4096, 2))
        samples[0, 0] = 0.1
        setting = EQSettings(bass_db=12, mid_db=-12, treble_db=12)
        filtered = EqualizerProcessor(48000, setting, 2).process(samples)
        np.testing.assert_array_equal(filtered[:, 1], 0)
        self.assertTrue(np.any(filtered[:, 0] != 0))

    def test_frequency_response_shape_endpoints_and_flatness(self):
        frequencies, magnitude = frequency_response(44100, EQSettings(), points=4097)
        self.assertEqual(frequencies.shape, (4097,))
        self.assertEqual(magnitude.shape, (4097,))
        self.assertEqual(frequencies[0], 0)
        self.assertEqual(frequencies[-1], 22050)
        np.testing.assert_array_equal(magnitude, 0)

    def test_invalid_settings(self):
        for kwargs in ({"bass_db": 12.1}, {"mid_db": -13}, {"treble_db": np.nan},
                       {"bass_hz": 0}, {"mid_hz": 5000}, {"mid_q": 0},
                       {"mid_q": np.inf}, {"bass_db": True}, {"bass_db": "6"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                EQSettings(**kwargs)

    def test_invalid_sample_rates_and_response_size(self):
        for fs in (0, -1, np.nan, np.inf, 8000, True):
            with self.subTest(sample_rate=fs), self.assertRaises(ValueError):
                design_equalizer(fs, EQSettings())
        for points in (0, 1, 1.5, True):
            with self.subTest(points=points), self.assertRaises(ValueError):
                frequency_response(44100, EQSettings(), points)

    def test_invalid_audio_and_channel_counts(self):
        invalid = ([], np.zeros((0, 2)), np.zeros((4, 0)), np.zeros((4, 2, 1)),
                   [np.nan], [np.inf], [1 + 2j], ["sample"])
        for samples in invalid:
            with self.subTest(samples=samples), self.assertRaises(ValueError):
                apply_equalizer(samples, 44100, EQSettings())
        for channels in (0, -1, True, 1.5):
            with self.subTest(channels=channels), self.assertRaises(ValueError):
                EqualizerProcessor(44100, EQSettings(), channels)
        with self.assertRaises(ValueError):
            EqualizerProcessor(44100, EQSettings(), 2).process(np.ones(20))


if __name__ == "__main__":
    unittest.main()
