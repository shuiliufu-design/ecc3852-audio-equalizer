# ECC3852 Digital Signal Processing

Audio analysis and a three-band IIR music equalizer implemented in Python. The project includes an offline analysis pipeline, a real-time player, and reproducible synthetic verification. A song has not yet been selected. The user has confirmed an audible difference in the revised synthetic comparison. Formal music experiments and listening observations, the updated GUI screenshot review, and the final report remain pending.

## Quick start

Open a terminal in the project directory and run:

```sh
.venv/bin/python run.py demo --output outputs/demo_v2
.venv/bin/python run.py test
```

The demo generates a 12-second stereo test signal and four presets: flat, bass +6 dB, mid -6 dB, and treble +6 dB. It saves audio and figures without starting playback. Synthetic results verify the implementation; they do not replace the assignment's song experiment.

The existing `outputs/demo/` directory is the schema-1 baseline cited by the report. The command above writes a new schema-2 run to `outputs/demo_v2/`. Use a separate output directory for each experiment to preserve earlier evidence.

## Installation

For a fresh clone and platform-specific commands, start with [Team setup](docs/TEAM_SETUP.md). Use the branch and pull-request workflow in [Contributing](CONTRIBUTING.md) when working with teammates.

The shared repository is [shuiliufu-design/ecc3852-audio-equalizer](https://github.com/shuiliufu-design/ecc3852-audio-equalizer). Repository access is required before cloning:

```sh
git clone https://github.com/shuiliufu-design/ecc3852-audio-equalizer.git
cd ecc3852-audio-equalizer
```

The verified environment uses Python 3.12.14, NumPy 2.5.4, SciPy 1.18.1, Matplotlib 3.11.2, and SoundFile 0.14.0. Exact offline dependency versions are recorded in `requirements-lock.txt`; `.venv/` is the project-local environment.

On another Mac, install Python 3.12 or later, then run:

```sh
sh scripts/setup.sh
.venv/bin/python run.py test
```

Alternatively, create a virtual environment and install `requirements-lock.txt` with pip or uv. `requirements.txt` gives the allowed dependency ranges; the lock file records the versions used for the current results.

Real-time playback has optional dependencies in `requirements-player.txt`, including sounddevice 0.5.6. Tkinter is supplied by a Python installation with Tk support, rather than by a pip package. Install the player dependencies on a new environment with:

```sh
sh scripts/setup_player.sh
```

The original environment was created with the Python runtime bundled with Codex. It does not alter macOS system Python or accept the system Xcode license.

## Real-time player

Start the player from the project directory:

```sh
.venv/bin/python play.py
```

The player defaults to a separate 60-second listening demo with simultaneous, steady 120 Hz, 1 kHz and 6 kHz components. It is generated if missing and waits for the user to start playback. The pitch stays fixed: EQ changes the levels of existing frequency components. The earlier 12-second segmented/chirp fixture remains unchanged for reproducible numerical experiments.

The player supports audio loading, play/resume, pause, stop, independent bass/mid/treble sliders from -12 to +12 dB, and a reset to 0 dB. Slider values are submitted approximately every 40 ms during continuous dragging. Stop returns to the beginning; pause preserves position and filter state.

For an initial audible comparison, keep Bass and Treble at 0 dB, start playback, set Mid to -12 dB for a few seconds, then +12 dB. Use **Bypass EQ (original sound)** to compare the flat signal against the current slider settings while playback continues. Bypass preserves the slider positions; switching it off restores those settings. Compare at a comfortable system volume. This remains a synthetic implementation check, not a music listening result.

Useful commands:

```sh
.venv/bin/python play.py --list-devices
.venv/bin/python play.py audio/demo/synthetic_demo.wav --volume-db -24
.venv/bin/python scripts/check_audio_output.py
.venv/bin/python scripts/check_player_gui.py
```

Use `--device ID` to select an output from the current device list. The output device must support the file's sample rate and channel count. The player reports unsupported inputs rather than silently resampling or downmixing. If Tkinter is unavailable, use a Python distribution with Tk support.

Playback applies a fixed -18 dB gain by default. `--volume-db` accepts an explicit value from -60 to 0 dB. A final hard sample-peak guard clips to +/-0.95 FS and displays its activation count. Guard activation can cause distortion; reduce playback gain if it occurs. There is no per-block normalization. Approximately 10 ms volume ramps are applied at playback start, resume, pause, and the file ending. These playback controls do not alter offline exports.

The saved device check used a -24 dB synthetic signal on the local speakers. The GUI control check used a simulated audio backend. The device check produces sound; the GUI control check does not. Run device checks in a local terminal if the execution sandbox cannot enumerate output devices. Saved evidence is under `outputs/player/`. Subsequent user feedback confirmed an audible synthetic comparison; formal music listening and screenshot review of the updated bypass interface remain pending. Full player design and historical evidence details are in `PLAYER_HANDOFF.md`.

## Process a song

Preserve the original file in `audio/original/`. WAV or FLAC is preferred; support for other formats depends on the installed libsndfile decoder. Replace the example filename below with the selected song:

```sh
.venv/bin/python run.py process audio/original/your_song.wav --start 30 --duration 45 --output outputs/music/song01
```

Omit `--start` and `--duration` to process the whole file. Use a distinct output directory for every experiment. Timestamps begin at the first sample of the selected segment. `results.json` records the actual source sample range and times; add `source.start_s` to a segment-relative timestamp to obtain its original-file time.

The input is not resampled or downmixed. The original file remains unchanged and its SHA-256 is checked before and after processing. An output directory containing the source file is rejected to protect the original.

A successful `process` command establishes that an audio run completed. The current generator keeps `is_formal_music_experiment=false`; reviewed song provenance and completion of the assignment require separate evidence. The planned source and experiment record is `report/music_review_template.json`.

## Results and output fields

Each full demo or song run generates:

| File | Contents |
| --- | --- |
| `01_original_analysis.png` | Original waveform and Welch power spectral density |
| `02_equalizer_responses.png` | Theoretical equalizer magnitude responses |
| `03_psd_comparison.png` | Before/after PSD using common axes |
| `04_spectrogram_comparison.png` | Before/after spectrograms using a common color scale |
| `comparison_original.wav` | A separate original-signal copy using the shared export gain |
| `flat.wav`, `bass_boost.wav`, `mid_cut.wav`, `treble_boost.wav` | Equalizer outputs for the default presets |
| `results.json` | Source identity, actual sample range, definitions, coefficients, measurements, and export information |
| `summary.csv` | Compact comparison metrics |
| `config_used.json` | Configuration snapshot for the run |

The synthetic signal's known components are recorded in `audio/demo/signal_manifest.json`.

Schema 2 distinguishes `estimated_export_peak_fs`, the peak predicted before PCM quantization, from `decoded_export_peak_fs`, the sample peak measured by decoding the saved WAV. In the preserved schema-1 baseline, CSV `export_peak_fs` is the predicted value. Each preset's JSON `export.decoded_peak` has always represented the measured decoded value. Integration details are recorded in `report/INTEGRATION_REVIEW.md`.

## DSP design and measurement definitions

- Three biquads are cascaded: a 200 Hz low shelf, a 1,000 Hz peaking section with Q=1, and a 4,000 Hz high shelf. Each gain ranges from -12 to +12 dB. These initial design choices can be changed in `config.json`; the frequencies are not nonoverlapping brick-wall crossover boundaries.
- Explicit RBJ Audio EQ Cookbook coefficients are processed with SciPy second-order sections in one causal pass. All controls at 0 dB produce identity filtering. The filter applies no hidden normalization, limiter, or forward/backward filtering.
- `EqualizerProcessor` retains independent filter state per channel across blocks and uses fixed settings. The player switches settings with two instances, finite-history warm-up, and a 30 ms linear crossfade, while reusing the same coefficient implementation.
- The default spectrogram uses a 30 ms Hann window and approximately 75% overlap. Only complete windows inside the signal are included, and timestamps refer to window centers. The FFT length and actual hop size are saved. FFT bin spacing is not the window's resolving power.
- Stereo power spectra are calculated separately and then averaged, preventing cancellation from an initial waveform downmix. The absolute sample peak includes its signed value, sample index, time, and channel. The signed maximum is recorded separately.
- The strongest time-frequency bin and highest significant frequency are distinct measurements. The latter uses an explicit threshold of -40 dB relative to the global spectrogram power peak and is sensitive to noise, leakage, and the chosen threshold. The Nyquist frequency is an analysis limit.
- Band-power fractions are derived from Welch PSD over [0,200), [200,4000), and [4000,Fs/2] Hz by default. Undefined spectral events and fractions for silence are saved as `null`.
- The original comparison and all preset WAVs use one shared gain, attenuating only when needed to keep the predicted sample peak at or below 0.95 FS. Presets are not individually normalized. Raw measurements and figures describe the signals before this common attenuation; the export gain is recorded separately. PCM quantization can produce differences within one quantization step.
- The default frequencies require a sample rate above 8,000 Hz. Lower-rate inputs require explicit changes to the EQ frequencies and analysis bands; parameters are not silently adjusted.

## Verification and remaining work

The latest suite passed all 55 tests, including filter gain and stability, channel isolation, block/offline equivalence, PCM export, CSV/JSON measurement consistency, parameter transitions, peak protection, simulated stream lifecycle, and the steady listening stimulus. The latest log is `outputs/audibility/validation.log`; earlier integration, baseline and player-stage logs remain separate.

The player has a short synthetic device-output record and Tk control checks. Initial user feedback found the original short chirp stimulus unsuitable for hearing the slider effect. After the new steady stimulus and bypass comparison were introduced, the user confirmed hearing a difference. Exact gain settings, timing, device and volume were not re-reported for that confirmation; it is a basic synthetic observation rather than a controlled listening study. A paced simulated stream independently measured Mid gains of +12 and -12 dB on a 1 kHz tone. Numerical evidence is saved under `outputs/audibility/`, and user observations are recorded in `report/listening_log.csv`.

These checks do not establish music quality, long-duration music stability, or acoustic end-to-end latency. Saved PortAudio latency is a device-reported value. Formal song results and the final report must be completed from actual music evidence.

Project coordination and current status are recorded in `AGENTS.md`, `PROJECT_PLAN.md`, `STATUS.md`, `HANDOFF.md`, and `PLAYER_HANDOFF.md`. The original assignment PDF is currently unavailable at its former location. A previously saved page rendering and source-status notes are preserved under `references/`; the recovered original must be checked before submission, including the actual deadline and Challenge grading arrangements.
