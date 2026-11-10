"""Command-line entry points; no audio-device access is required."""

import argparse
from pathlib import Path
import sys
import unittest

from .audio_io import save_audio
from .demo import synthetic_demo
from .pipeline import ROOT, load_config, run_experiment, write_json


def main(argv=None):
    parser = argparse.ArgumentParser(description="ECC3852 audio analysis and three-band IIR EQ")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Generate and analyze clearly labelled synthetic audio")
    demo.add_argument("--config", type=Path)
    demo.add_argument("--output", type=Path, default=ROOT / "outputs/demo")
    process = commands.add_parser("process", help="Analyze a selected real audio file")
    process.add_argument("input", type=Path)
    process.add_argument("--config", type=Path)
    process.add_argument("--output", type=Path, default=ROOT / "outputs/music")
    process.add_argument("--start", type=float, default=0, help="Segment start in seconds")
    process.add_argument("--duration", type=float, help="Segment duration in seconds; default is remainder")
    commands.add_parser("test", help="Run meaningful DSP, analysis and I/O checks")
    args = parser.parse_args(argv)
    if args.command == "test":
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    try:
        config = load_config(args.config)
        if args.command == "demo":
            audio, sample_rate, manifest = synthetic_demo()
            demo_dir = ROOT / "audio/demo"
            demo_dir.mkdir(parents=True, exist_ok=True)
            source = demo_dir / "synthetic_demo.wav"
            save_audio(source, audio, sample_rate)
            write_json(demo_dir / "signal_manifest.json", manifest)
            result = run_experiment(source, args.output, config, signal_kind="synthetic_demo")
        else:
            result = run_experiment(args.input, args.output, config, args.start, args.duration)
        peak = result["original_analysis"]["absolute_peak"]
        print(f"Completed: {Path(args.output).resolve()}")
        print(f"Signal kind: {result['signal_kind']}")
        print(f"Peak: {peak['amplitude']:.6f} FS at {peak['time_s']:.6f} s, channel {peak['channel']}")
        print(f"Common export gain: {result['export']['common_gain_db']:.3f} dB")
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
