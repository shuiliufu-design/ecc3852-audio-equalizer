#!/usr/bin/env python3
"""Separate optional playback entry point; leaves offline run.py unchanged."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))


def main(argv=None):
    parser = argparse.ArgumentParser(description="ECC3852 real-time three-band equalizer")
    parser.add_argument("file", type=Path, nargs="?",
                        help="Audio file; defaults to a steady 60-second synthetic listening demo")
    parser.add_argument("--device", type=int, help="Output device ID from --list-devices")
    parser.add_argument("--volume-db", type=float, default=-18, help="Fixed playback gain, -60 to 0 dB (default -18)")
    parser.add_argument("--list-devices", action="store_true", help="List output devices without opening the GUI")
    args = parser.parse_args(argv)
    try:
        from ecc3852.player import OutputSafety, output_devices
        OutputSafety(args.volume_db)
        if args.list_devices:
            print(json.dumps(output_devices(), ensure_ascii=False, indent=2))
            return 0
        from ecc3852.equalizer import EQSettings
        from ecc3852.gui import launch
        from ecc3852.demo import ensure_listening_demo
        config = json.loads((ROOT / "config.json").read_text())
        settings = EQSettings(**config["equalizer"])
        initial_path = args.file if args.file is not None else ensure_listening_demo()
        launch(settings, initial_path, args.device, args.volume_db)
        return 0
    except (ValueError, OSError, RuntimeError, ImportError) as exc:
        print(f"Player error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
