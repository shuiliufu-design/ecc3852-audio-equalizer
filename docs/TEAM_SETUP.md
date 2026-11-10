# Team setup

Use Python 3.12, Git, and your GitHub account. If the repository is private, accept the repository invitation before cloning. Copy the repository URL from GitHub's **Code** menu, clone it, and open a terminal in the cloned folder. Each teammate creates their own local environment; the original author's `.venv` is not shared.

## macOS or Linux

Install Python 3.12 with venv support, then run:

```sh
sh scripts/setup.sh
.venv/bin/python run.py test
```

For the optional desktop player:

```sh
sh scripts/setup_player.sh
.venv/bin/python play.py
```

The player needs a graphical desktop, Tkinter and an output audio device. Tk is supplied by the Python installation or operating system, not by a pip package. On Linux, PortAudio/libsndfile and Tk may require operating-system packages. The existing real-device verification was performed on the original Mac; other platforms require their own checks.

## Windows PowerShell

Install Python 3.12 with Tcl/Tk support. These commands use the environment's Python directly, so activating the environment is unnecessary:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe run.py test
```

For the optional player:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-player.txt
.\.venv\Scripts\python.exe -c "import tkinter, sounddevice; print('Player dependencies available')"
.\.venv\Scripts\python.exe play.py
```

If the `py` launcher is unavailable, use the installed Python 3.12 executable for the first command. The lock file records the verified versions; this guide does not claim that every platform and audio device has already been validated.

## First run

1. Run `run.py test` with the appropriate environment Python above. The suite is independent of actual speakers and GUI access.
2. Generate the original 12-second synthetic fixture and offline results:

   ```sh
   .venv/bin/python run.py demo --output outputs/team_demo
   ```

   On Windows, replace `.venv/bin/python` with `.\.venv\Scripts\python.exe`. This creates `audio/demo/synthetic_demo.wav` if it was not included in the clone, along with four preset outputs and analysis figures. Use a different output directory for a later run.
3. Start `play.py`. Its default is a separate 60-second steady synthetic listening aid, generated automatically if missing. It does not start playback automatically.
4. Click **Play / Resume**, keep Bass and Treble at 0 dB, and compare Mid at -12 and +12 dB. **Bypass EQ (original sound)** compares the flat signal with the current slider settings while preserving the slider positions. EQ changes band levels rather than shifting the source frequencies.

Both fixtures are synthetic. They do not replace the song required for the assignment.

## Optional device and GUI checks

Generate the original 12-second fixture with `run.py demo` before running the original device-output check. The following command produces sound on the selected output device:

```sh
.venv/bin/python scripts/check_audio_output.py
```

The GUI check uses a simulated audio backend and does not produce sound. Write its result to your own output directory:

```sh
.venv/bin/python scripts/check_player_gui.py --output outputs/team_checks/gui_check.json
```

Use the Windows environment executable where applicable. Keep device records distinct from numerical tests, Tk widget checks, screenshots and human listening observations. Device-reported latency is not a measured acoustic end-to-end latency.

## Working with the selected song

The formal song has not yet been selected. Keep local source audio under `audio/original/`; do not commit the audio file. Before a music experiment, agree on a metadata record containing:

- Song title, artist/author, version and source URL or acquisition method.
- Original filename, SHA-256, sample rate, channels and duration.
- Actual selected start/end samples and the reason for choosing the range.
- Configuration/result hashes and the exact processing command.

Use `report/music_review_template.json` as the starting structure. Share the metadata and arrange access to the same input separately. Do not replace the full original with an EQ output or a cropped reference copy. A run of `process` currently retains `is_formal_music_experiment=false`; formal-source review is handled by the integration owner when the actual song is available.

For branch workflow, file ownership and evidence rules, read [Contributing](../CONTRIBUTING.md).
