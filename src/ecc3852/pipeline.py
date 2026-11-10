"""Reproducible offline experiments shared by demo and later song analysis."""

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import csv
import importlib.metadata
import json
import platform

import numpy as np
import soundfile as sf

from .analysis import AnalysisSettings, analyze_audio
from .audio_io import file_sha256, load_audio, save_audio
from .equalizer import EQSettings, apply_equalizer, design_equalizer
from .plots import plot_original, plot_responses, plot_comparisons


ROOT = Path(__file__).resolve().parents[2]


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def load_config(path=None):
    config_path = Path(path).expanduser().resolve() if path else ROOT / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    return validate_config(config)


def validate_config(config):
    """Validate the public Python API as strictly as the CLI; take a snapshot."""
    if not isinstance(config, dict):
        raise ValueError("config must be a JSON object")
    try:
        config = json.loads(json.dumps(config, allow_nan=False))
        for section in ("analysis", "equalizer", "presets", "export"):
            if not isinstance(config.get(section), dict):
                raise ValueError(f"config.{section} must be an object")
        AnalysisSettings(**config["analysis"])
        EQSettings(**config["equalizer"])
    except (TypeError, OverflowError) as exc:
        raise ValueError(f"invalid config: {exc}") from exc
    if not config.get("presets"):
        raise ValueError("config must define at least one preset")
    reserved = {"comparison_original", "results", "summary", "config_used", "readme"}
    names = set()
    for name in config["presets"]:
        if (not name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in name)
                or name.casefold() in reserved or name.casefold() in names):
            raise ValueError("preset names must be safe identifiers and not reserved output names")
        names.add(name.casefold())
        gains = config["presets"][name]
        if not isinstance(gains, dict) or set(gains) != {"bass_db", "mid_db", "treble_db"}:
            raise ValueError("each preset must define only bass_db, mid_db and treble_db")
        EQSettings(**(config["equalizer"] | gains))
    policy = config["export"]
    if policy.get("gain_policy") != "one_shared_attenuation_for_input_and_all_presets_never_boost":
        raise ValueError("export gain_policy must retain one common attenuation")
    if policy.get("subtype") not in ("PCM_16", "PCM_24", "PCM_32"):
        raise ValueError("export subtype must be PCM_16, PCM_24 or PCM_32")
    ceiling = policy.get("peak_ceiling")
    if (isinstance(ceiling, bool) or not isinstance(ceiling, (int, float))
            or not np.isfinite(ceiling) or not 0 < ceiling < 1):
        raise ValueError("export peak_ceiling must be between 0 and 1")
    return config


def run_experiment(input_path, output_dir, config=None, start_s=0.0, duration_s=None,
                   signal_kind="user_audio", make_plots=True):
    """Measure raw filter effects, then export all files at one common gain.

    No input resampling, downmix, loudness normalization, hidden limiter, or
    zero-phase filtering is applied. The exported original is a separate file.
    """
    source = Path(input_path).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    if source.is_relative_to(output_dir):
        raise ValueError("output directory must not contain the original source file")
    config = validate_config(config) if config is not None else load_config()
    settings = AnalysisSettings(**config["analysis"])
    preset_settings = {name: EQSettings(**(config["equalizer"] | gains))
                       for name, gains in config["presets"].items()}
    audio, sample_rate, source_meta = load_audio(source, start_s, duration_s)
    settings.validate(sample_rate)
    coefficients = {name: design_equalizer(sample_rate, preset).tolist()
                    for name, preset in preset_settings.items()}
    # Two passes avoid retaining a full-length audio buffer per preset.
    peaks = [float(np.max(np.abs(audio)))]
    for preset in preset_settings.values():
        peaks.append(float(np.max(np.abs(apply_equalizer(audio, sample_rate, preset)))))
    export_gain = min(1.0, config["export"]["peak_ceiling"] / max(peaks)) if max(peaks) else 1.0
    original, original_spectrum = analyze_audio(audio, sample_rate, settings)
    output_dir.mkdir(parents=True, exist_ok=True)
    subtype = config["export"]["subtype"]
    original_export = output_dir / "comparison_original.wav"
    save_audio(original_export, audio * export_gain, sample_rate, subtype)
    original_decoded, _ = sf.read(original_export, dtype="float64", always_2d=True)
    original_decoded_peak = float(np.max(np.abs(original_decoded)))
    del original_decoded
    preset_results, preset_spectra = {}, {}
    for name, preset in preset_settings.items():
        filtered = apply_equalizer(audio, sample_rate, preset)
        summary, spectrum = analyze_audio(filtered, sample_rate, settings)
        export_path = output_dir / f"{name}.wav"
        save_audio(export_path, filtered * export_gain, sample_rate, subtype)
        decoded, decoded_rate = sf.read(export_path, dtype="float64", always_2d=True)
        preset_results[name] = {
            "settings": asdict(preset), "sos": coefficients[name], "raw_analysis": summary,
            "export": {"file": export_path.name, "sha256": file_sha256(export_path),
                       "sample_rate_hz": decoded_rate, "samples": len(decoded),
                       "channels": decoded.shape[1], "decoded_peak": float(np.max(np.abs(decoded))),
                       "raw_samples_at_or_above_full_scale": int(np.count_nonzero(np.abs(filtered) >= 1)),
                       "common_gain_linear": export_gain},
        }
        preset_spectra[name] = spectrum
    result = {
        "schema_version": 2, "signal_kind": signal_kind,
        "is_formal_music_experiment": False,
        "note": ("Synthetic implementation check; not song evidence." if signal_kind == "synthetic_demo"
                 else "User audio run; music source and report suitability still require review."),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": source_meta, "analysis_time_origin": "selected segment start; add source.start_s for original-file time",
        "original_analysis": original, "presets": preset_results,
        "export": {"policy": config["export"]["gain_policy"], "common_gain_linear": export_gain,
                   "common_gain_db": float(20 * np.log10(export_gain)), "subtype": subtype,
                   "peak_ceiling": config["export"]["peak_ceiling"],
                   "original_comparison_file": original_export.name,
                   "original_comparison_decoded_peak": original_decoded_peak,
                   "plot_and_raw_analysis_reference": "before common export attenuation"},
        "summary_columns": {
            "estimated_export_peak_fs": "Raw sample peak times common export gain, before PCM quantization",
            "decoded_export_peak_fs": "Measured absolute sample peak of the exported WAV after decoding",
        },
        "environment": {"python": platform.python_version(), **{
            name: importlib.metadata.version(name) for name in ("numpy", "scipy", "matplotlib", "soundfile")}},
    }
    if file_sha256(source) != source_meta["sha256"]:
        raise RuntimeError("source changed during analysis; results are not reproducible")
    write_json(output_dir / "results.json", result)
    write_json(output_dir / "config_used.json", config)
    with (output_dir / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["setting", "raw_peak_fs", "raw_rms_fs", "export_gain_db",
                         "estimated_export_peak_fs", "decoded_export_peak_fs"])
        for name, summary in [("original", original), *[(n, v["raw_analysis"]) for n, v in preset_results.items()]]:
            decoded_peak = (original_decoded_peak if name == "original"
                            else preset_results[name]["export"]["decoded_peak"])
            writer.writerow([name, summary["absolute_peak"]["amplitude"], summary["rms"],
                             result["export"]["common_gain_db"],
                             summary["absolute_peak"]["amplitude"] * export_gain, decoded_peak])
    label = "SYNTHETIC DEMO" if signal_kind == "synthetic_demo" else "USER AUDIO - review source before report"
    if make_plots:
        plot_original(audio, sample_rate, original, original_spectrum, output_dir, label)
        plot_responses(preset_settings, sample_rate, output_dir, label)
        plot_comparisons(original_spectrum, preset_spectra, output_dir, label)
    (output_dir / "README.md").write_text(
        f"# {label}\n\n"
        "This directory was generated by the experiment pipeline. Synthetic demonstrations verify "
        "the implementation and do not constitute music-experiment evidence.\n\n"
        "`results.json` records source hashes, actual sample ranges, analysis definitions, "
        "filter coefficients and measurements. `config_used.json` records the run configuration. "
        "Figures and raw_analysis refer to signals before the shared export attenuation.\n\n"
        "Schema version 2: CSV estimated_export_peak_fs is the peak predicted before PCM quantization; "
        "decoded_export_peak_fs is measured from the saved WAV. Small differences arise from quantization.\n\n"
        f"Every WAV uses the same gain: {export_gain:.9f} ({result['export']['common_gain_db']:.4f} dB). "
        "Presets are not normalized individually. comparison_original.wav is a separate reference copy; "
        "the source file is preserved.\n\n"
        "Timestamps are relative to the selected segment start; add source.start_s for source-file time. "
        "The highest significant frequency is estimated using an explicit relative threshold. "
        "It depends on noise, window leakage and threshold choice, and is not an exact bandwidth boundary.\n",
        encoding="utf-8")
    return result
