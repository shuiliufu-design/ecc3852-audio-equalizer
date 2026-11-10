"""Exercise real output at low gain; never records audio or claims listening QA."""

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
import sys
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ecc3852.equalizer import EQSettings
from ecc3852.player import AudioPlayer, output_devices


def wait_for(player, predicate, description, timeout=6):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        view = player.snapshot()
        if view["error"]:
            raise RuntimeError(view["error"])
        if predicate(view):
            return view
        time.sleep(0.02)
    raise TimeoutError(f"Timed out: {description}; {player.snapshot()}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", type=int)
    parser.add_argument("--report", type=Path, default=ROOT / "outputs/player/device_check.json")
    args = parser.parse_args()
    source = ROOT / "audio/demo/synthetic_demo.wav"
    settings = EQSettings(**json.loads((ROOT / "config.json").read_text())["equalizer"])
    report = dict(timestamp=datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).isoformat(),
                  signal_kind="synthetic_demo", source=str(source),
                  volume_db=-24, block_size=512, crossfade_ms=30, stages=[],
                  human_listening="not_performed", microphone_recording=False, result="failed")
    player = None
    try:
        report["available_outputs"] = output_devices()
        player = AudioPlayer(settings, device=args.device, volume_db=-24)
        def stage(name, view):
            report["stages"].append(dict(stage=name, **view))
            print(name, view["state"], view["position_samples"], flush=True)
        player.load(source)
        view = wait_for(player, lambda v: v["state"] == "stopped", "load")
        stage("loaded", view)
        fs = view["sample_rate_hz"]
        player.play()
        stage("playing", wait_for(player, lambda v: v["position_samples"] >= fs // 2, "play"))
        for index in range(16):
            player.set_settings(replace(settings, bass_db=12 if index % 2 else -12,
                                        mid_db=-12 if index % 2 else 12,
                                        treble_db=12 if index % 2 else -12))
            time.sleep(0.04)
        view = player.snapshot()
        stage("rapid_slider_changes", view)
        player.pause()
        view = wait_for(player, lambda v: v["state"] == "paused", "pause")
        stage("paused", view)
        paused_position = view["position_samples"]
        time.sleep(0.2)
        if player.snapshot()["position_samples"] != paused_position:
            raise AssertionError("source position changed while paused")
        player.play()
        stage("resumed", wait_for(player, lambda v: v["position_samples"] > paused_position + fs // 3, "resume"))
        player.set_settings(settings)
        view = wait_for(player, lambda v: v["settings"] == settings.__dict__ and not v["transitioning"], "flat reset")
        stage("flat_reset", view)
        player.stop()
        stage("stopped_at_zero", wait_for(player, lambda v: v["state"] == "stopped" and v["position_samples"] == 0, "stop"))
        player.play()
        stage("restarted", wait_for(player, lambda v: v["position_samples"] >= fs // 3, "restart"))
        # Exercise each known demo section (bass / mid / treble), then EOF.
        for name, start, target in (
            ("bass_section", 1, replace(settings, bass_db=6)),
            ("mid_section", 4.5, replace(settings, mid_db=-6)),
            ("treble_section", 8.5, replace(settings, treble_db=6)),
        ):
            wait_for(player, lambda v, s=start: v["position_samples"] >= int(s * fs), name, timeout=6)
            player.set_settings(target)
            stage(name, wait_for(player, lambda v, t=target: v["settings"] == t.__dict__ and not v["transitioning"], name + " transition"))
        stage("eof_drained", wait_for(player, lambda v: v["state"] == "ended", "EOF", timeout=6))
        player.stop()
        stage("final_stop", wait_for(player, lambda v: v["state"] == "stopped", "final stop"))
        if any(v["underflows"] for v in report["stages"]):
            raise RuntimeError("Output stream reported an underflow; inspect device report")
        report["result"] = "passed"
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        print(report["error"], file=sys.stderr)
    finally:
        if player is not None:
            try:
                player.close()
            except Exception as exc:
                report["close_error"] = f"{type(exc).__name__}: {exc}"
                report["result"] = "failed"
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"Report: {args.report}")
    return 0 if report["result"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
