"""Check the listening stimulus has steady, independently adjustable bands."""

import unittest

import numpy as np

from ecc3852.demo import listening_demo
from ecc3852.equalizer import EQSettings, apply_equalizer


class ListeningDemoTests(unittest.TestCase):
    def test_all_three_fixed_tones_are_present_in_each_interior_second(self):
        audio, fs, manifest = listening_demo(duration_s=5)
        self.assertFalse(manifest["is_music"])
        self.assertEqual(audio.shape, (5 * fs, 2))
        self.assertLess(float(np.max(np.abs(audio))), 1)
        self.assertEqual(float(np.max(np.abs(audio[[0, -1]]))), 0)
        frequencies = np.fft.rfftfreq(fs, 1 / fs)
        for second in (1, 2, 3):
            spectrum = 2 * np.abs(np.fft.rfft(audio[second * fs:(second + 1) * fs, 0])) / fs
            for component in manifest["components"]:
                frequency = component["frequency_hz"]
                index = np.argmin(np.abs(frequencies - frequency))
                self.assertAlmostEqual(float(spectrum[index]), component["left_amplitude"], places=10)
            expected = np.array([120, 1000, 6000])
            actual = np.sort(frequencies[np.argsort(spectrum)[-3:]])
            np.testing.assert_array_equal(actual, expected)

    def test_mid_boost_and_cut_have_24_db_contrast_in_mixed_demo(self):
        audio, fs, _ = listening_demo(duration_s=3)
        amplitudes = []
        for mid_db in (-12, 12):
            output = apply_equalizer(audio, fs, EQSettings(mid_db=mid_db))
            segment = output[fs:2 * fs, 0]
            spectrum = 2 * np.abs(np.fft.rfft(segment)) / fs
            amplitudes.append(float(spectrum[1000]))
        contrast = 20 * np.log10(amplitudes[1] / amplitudes[0])
        self.assertAlmostEqual(contrast, 24, places=8)


if __name__ == "__main__":
    unittest.main()
