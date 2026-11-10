"""Exercise real WAV files and the reproducible offline experiment boundary."""

import csv
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import soundfile as sf

from ecc3852.audio_io import common_export_gain, file_sha256, load_audio, save_audio
from ecc3852.equalizer import EQSettings, apply_equalizer
from ecc3852.pipeline import ROOT, load_config, run_experiment


PCM24_STEP = 2.0 ** -23


class AudioIOTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def test_pcm24_roundtrip_preserves_rate_shape_and_samples_within_one_step(self):
        rng = np.random.default_rng(3852)
        source = rng.uniform(-0.75, 0.75, (1234, 2))
        path = self.directory / "roundtrip.wav"
        save_audio(path, source, 48000)
        decoded, sample_rate, metadata = load_audio(path)
        self.assertEqual(sample_rate, 48000)
        self.assertEqual(decoded.shape, source.shape)
        self.assertEqual(metadata["subtype"], "PCM_24")
        np.testing.assert_allclose(decoded, source, rtol=0, atol=PCM24_STEP)

    def test_selected_clip_has_sample_aligned_times_and_retains_source_hash(self):
        fs = 16000
        samples = np.column_stack((np.linspace(-0.4, 0.4, 8000), np.linspace(0.3, -0.3, 8000)))
        path = self.directory / "source.wav"
        save_audio(path, samples, fs)
        before = file_sha256(path)
        full, _, _ = load_audio(path)
        requested_start, requested_duration = 0.1234567, 0.2
        clip, actual_fs, metadata = load_audio(path, requested_start, requested_duration)
        first = int(np.floor(requested_start * fs))
        length = round(requested_duration * fs)
        np.testing.assert_array_equal(clip, full[first:first + length])
        self.assertEqual(actual_fs, fs)
        self.assertEqual(metadata["start_sample"], first)
        self.assertEqual(metadata["end_sample_exclusive"], first + length)
        self.assertEqual(metadata["start_s"], first / fs)
        self.assertEqual(metadata["end_s_exclusive"], (first + length) / fs)
        self.assertEqual(metadata["sha256"], before)
        self.assertEqual(file_sha256(path), before)
        tail, _, tail_metadata = load_audio(path, start_s=0.4, duration_s=100)
        self.assertEqual(len(tail), 1600)
        self.assertEqual(tail_metadata["end_sample_exclusive"], len(full))

    def test_invalid_clip_ranges_and_nonfinite_audio_are_rejected(self):
        path = self.directory / "source.wav"
        save_audio(path, np.zeros((1600, 1)), 16000)
        for start in (-0.1, np.nan, np.inf, 0.1, 2.0):
            with self.subTest(start=start), self.assertRaises(ValueError):
                load_audio(path, start_s=start)
        for duration in (0.0, -1.0, np.nan, np.inf, 1e-12):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                load_audio(path, duration_s=duration)
        nonfinite = self.directory / "nonfinite.wav"
        sf.write(nonfinite, np.array([0.0, np.nan, np.inf]), 16000, subtype="FLOAT")
        with self.assertRaises(ValueError):
            load_audio(nonfinite)
        for invalid in ([np.nan], [np.inf], [], [1.0], [-1.0]):
            with self.subTest(samples=invalid), self.assertRaises(ValueError):
                save_audio(self.directory / "invalid.wav", invalid, 16000)

    def test_common_gain_preserves_relative_amplitudes_and_never_boosts(self):
        quiet = np.array([0.1, -0.2])
        loud = np.array([0.4, -2.0])
        gain = common_export_gain([quiet, loud], ceiling=0.95)
        self.assertAlmostEqual(gain, 0.475)
        self.assertEqual(np.max(np.abs(loud * gain)), 0.95)
        self.assertEqual(common_export_gain([quiet]), 1.0)
        self.assertEqual(common_export_gain([np.zeros(10)]), 1.0)
        for ceiling in (0, 1, -0.1, np.nan, np.inf):
            with self.subTest(ceiling=ceiling), self.assertRaises(ValueError):
                common_export_gain([quiet], ceiling=ceiling)
        with self.assertRaises(ValueError):
            common_export_gain([])


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.source_path = self.directory / "original" / "loud_source.wav"
        self.output_path = self.directory / "results"
        self.sample_rate = 48000
        time = np.arange(12000) / self.sample_rate
        # Bass boost must exceed full scale before the common export attenuation.
        samples = np.column_stack((0.8 * np.sin(2 * np.pi * 50 * time),
                                   0.4 * np.sin(2 * np.pi * 1000 * time)))
        save_audio(self.source_path, samples, self.sample_rate)
        self.source_hash = file_sha256(self.source_path)
        self.config = load_config()

    def test_pipeline_exports_all_comparisons_with_one_gain_and_safe_pcm_peak(self):
        result = run_experiment(self.source_path, self.output_path, config=self.config, make_plots=False)
        gain = result["export"]["common_gain_linear"]
        self.assertGreater(gain, 0)
        self.assertLess(gain, 1)
        original, _, _ = load_audio(self.source_path)
        comparison, _, _ = load_audio(self.output_path / "comparison_original.wav")
        np.testing.assert_allclose(comparison, original * gain, rtol=0, atol=PCM24_STEP)
        ceiling = self.config["export"]["peak_ceiling"]
        # PCM's least significant bit permits at most one quantization step at a ceiling.
        self.assertLessEqual(np.max(np.abs(comparison)), ceiling + PCM24_STEP)
        for name, preset in result["presets"].items():
            with self.subTest(preset=name):
                decoded, fs, _ = load_audio(self.output_path / preset["export"]["file"])
                expected = apply_equalizer(original, self.sample_rate, EQSettings(**preset["settings"])) * gain
                np.testing.assert_allclose(decoded, expected, rtol=0, atol=PCM24_STEP)
                self.assertEqual(preset["export"]["common_gain_linear"], gain)
                self.assertEqual(preset["export"]["sample_rate_hz"], self.sample_rate)
                self.assertEqual(preset["export"]["channels"], 2)
                self.assertEqual(fs, self.sample_rate)
                self.assertLessEqual(preset["export"]["decoded_peak"], ceiling + PCM24_STEP)
                self.assertEqual(preset["export"]["sha256"], file_sha256(self.output_path / f"{name}.wav"))
        flat, _, _ = load_audio(self.output_path / "flat.wav")
        np.testing.assert_array_equal(flat, comparison)
        self.assertGreater(result["presets"]["bass_boost"]["export"]["raw_samples_at_or_above_full_scale"], 0)
        self.assertEqual(file_sha256(self.source_path), self.source_hash)

    def test_result_json_csv_config_and_clip_provenance_are_consistent(self):
        result = run_experiment(self.source_path, self.output_path, config=self.config,
                                start_s=0.025, duration_s=0.15,
                                signal_kind="synthetic_demo", make_plots=False)
        def reject_nonfinite(value):
            raise AssertionError(f"Nonfinite JSON number: {value}")
        saved = json.loads((self.output_path / "results.json").read_text(), parse_constant=reject_nonfinite)
        saved_config = json.loads((self.output_path / "config_used.json").read_text())
        self.assertEqual(saved, result)
        self.assertEqual(saved_config, self.config)
        self.assertEqual(saved["source"]["sha256"], self.source_hash)
        self.assertEqual(saved["source"]["start_sample"], 1200)
        self.assertEqual(saved["source"]["end_sample_exclusive"], 8400)
        self.assertEqual(saved["original_analysis"]["samples"], 7200)
        self.assertEqual(saved["signal_kind"], "synthetic_demo")
        self.assertEqual(saved["schema_version"], 2)
        self.assertFalse(saved["is_formal_music_experiment"])
        self.assertIn("Synthetic", saved["note"])
        with (self.output_path / "summary.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual({row["setting"] for row in rows}, {"original", *self.config["presets"]})
        for row in rows:
            summary = (result["original_analysis"] if row["setting"] == "original"
                       else result["presets"][row["setting"]]["raw_analysis"])
            self.assertAlmostEqual(float(row["raw_peak_fs"]), summary["absolute_peak"]["amplitude"])
            self.assertAlmostEqual(float(row["raw_rms_fs"]), summary["rms"])
            self.assertAlmostEqual(float(row["export_gain_db"]), result["export"]["common_gain_db"])
            self.assertNotIn("export_peak_fs", row)
            self.assertEqual(float(row["estimated_export_peak_fs"]),
                             summary["absolute_peak"]["amplitude"] * result["export"]["common_gain_linear"])
            name = row["setting"]
            filename = "comparison_original.wav" if name == "original" else result["presets"][name]["export"]["file"]
            decoded, _, _ = load_audio(self.output_path / filename)
            actual_peak = float(np.max(np.abs(decoded)))
            self.assertEqual(float(row["decoded_export_peak_fs"]), actual_peak)
            if name == "original":
                self.assertEqual(result["export"]["original_comparison_decoded_peak"], actual_peak)
            else:
                self.assertEqual(result["presets"][name]["export"]["decoded_peak"], actual_peak)
            for field in ("raw_peak_fs", "raw_rms_fs", "export_gain_db",
                          "estimated_export_peak_fs", "decoded_export_peak_fs"):
                self.assertTrue(np.isfinite(float(row[field])))

    def test_output_cannot_contain_or_overwrite_original_source(self):
        for output in (self.source_path.parent, self.directory, self.source_path):
            with self.subTest(output=output), self.assertRaises(ValueError):
                run_experiment(self.source_path, output, config=self.config, make_plots=False)
        self.assertEqual(file_sha256(self.source_path), self.source_hash)
        self.assertFalse((self.directory / "comparison_original.wav").exists())

    def test_direct_api_rejects_unsafe_config_before_writing(self):
        cases = []
        traversal = deepcopy(self.config)
        traversal["presets"] = {"../escaped": self.config["presets"]["flat"]}
        cases.append(("relative path traversal", traversal))
        duplicate = deepcopy(self.config)
        duplicate["presets"]["FLAT"] = deepcopy(duplicate["presets"]["flat"])
        cases.append(("case-insensitive duplicate preset", duplicate))
        for field, value in (("peak_ceiling", 1.0), ("subtype", "FLOAT"),
                             ("gain_policy", "independent_normalization")):
            invalid = deepcopy(self.config)
            invalid["export"][field] = value
            cases.append((f"invalid {field}", invalid))
        for description, config in cases:
            with self.subTest(case=description):
                with self.assertRaises(ValueError):
                    run_experiment(self.source_path, self.output_path, config=config, make_plots=False)
                self.assertFalse(self.output_path.exists(), "validation must precede output writes")
                self.assertFalse((self.directory / "escaped.wav").exists())
                self.assertEqual(file_sha256(self.source_path), self.source_hash)

    def test_missing_input_cli_returns_clear_error_without_traceback(self):
        command = [sys.executable, str(ROOT / "run.py"), "process",
                   str(self.directory / "missing.wav"), "--output", str(self.output_path)]
        completed = subprocess.run(command, cwd=self.directory, capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("Audio file not found", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)
        self.assertFalse(self.output_path.exists())


if __name__ == "__main__":
    unittest.main()
