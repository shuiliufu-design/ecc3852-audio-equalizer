# Contributing

This repository is the shared ECC3852 Digital Signal Processing assignment project. Read `AGENTS.md`, `PROJECT_PLAN.md` and `STATUS.md` when joining or resuming work. See [Team setup](docs/TEAM_SETUP.md) for installation and first-run commands.

## Agree on ownership

| Area | Primary responsibility |
| --- | --- |
| `analysis.py`, `equalizer.py`, `audio_io.py`, `pipeline.py`, `plots.py`, `cli.py`, shared configuration | DSP implementation and integration |
| `player.py`, `gui.py`, `play.py`, player-specific checks | Real-time playback and interface |
| `report/`, literature and bibliography | Report and references |

Before editing a shared file, tell the team which files you will change. Coordinate changes to public APIs, `config.json`, dependencies and measurement definitions with the integration owner. The player should reuse the shared DSP rather than introduce a second filter implementation.

## Use a branch and pull request

Start from an up-to-date `main`, then create a short, task-specific branch:

```sh
git switch main
git pull --ff-only
git switch -c feature/describe-your-change
```

Make one focused change, run the relevant checks, and commit only the intended files:

```sh
git add PATHS_TO_CHANGED_FILES
git commit -m "Describe the resulting behavior"
git push -u origin feature/describe-your-change
```

Replace the example branch and file paths with your actual names. Open a pull request on GitHub. Describe the change, how to run it, the checks actually performed, and remaining limitations. Ask the integration owner to review and merge. This is a team convention; repository protection settings may be configured separately.

## Validate changes

From the repository root on macOS/Linux:

```sh
.venv/bin/python run.py test
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe run.py test
```

The numerical suite does not require an audio device. Player or UI changes also need the relevant checks described in the setup guide. A simulated stream or Tk widget test does not prove speaker output, human audibility, screenshot appearance or long-duration stability. Record the exact command and result; do not report checks that were not run.

## Preserve reproducibility

- Use a separate output directory for each experiment. Avoid having multiple people or processes write to the same generated directory.
- Keep original music unchanged and outside Git. Share agreed source metadata and hashes so each teammate can obtain or copy the same local input.
- Follow `.gitignore`; do not force-add virtual environments, caches, temporary files or generated audio. Agree with the team before adding selected experimental evidence.
- Treat saved evidence as a dated snapshot. If code, configuration or results change, create a new record instead of rewriting historical hashes to imply they are the same run.
- In schema 2, `estimated_export_peak_fs` is the pre-quantization prediction; `decoded_export_peak_fs` is measured from the saved WAV. Use the appropriate value in the report.
- Keep synthetic verification separate from formal music evidence. A successful processing command does not by itself establish reviewed song provenance or assignment completion.

## Language and reporting

Final source code, comments, docstrings, UI text, figures, captions, submission documentation, report and presentation materials must be in English. Chinese may be used for internal coordination. Preserve proper names and source metadata accurately.

Report conclusions must follow the saved measurements and genuine listening observations. Verify original references and publication information; do not invent citations, music results, subjective findings or grading rules.
