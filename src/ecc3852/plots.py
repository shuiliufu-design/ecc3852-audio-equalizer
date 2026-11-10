"""Headless, comparable figures with explicit units and synthetic labels."""

from pathlib import Path
import os

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[2] / ".cache/matplotlib"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .equalizer import frequency_response


plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.dpi": 130})
COLORS = ["#475569", "#d97706", "#0d9488", "#7c3aed"]


def _save(fig, directory, name):
    fig.savefig(Path(directory) / name, dpi=160, facecolor="white")
    plt.close(fig)


def plot_original(audio, sample_rate, summary, spectrum, directory, label):
    times = np.arange(len(audio)) / sample_rate
    fig, axes = plt.subplots(2, 1, figsize=(11, 6), constrained_layout=True)
    for channel in range(audio.shape[1]):
        axes[0].plot(times[::max(1, len(audio) // 60000)],
                     audio[::max(1, len(audio) // 60000), channel],
                     lw=0.5, alpha=0.8, label=f"Channel {channel + 1}")
    peak = summary["absolute_peak"]
    axes[0].scatter(peak["time_s"], peak["signed_value"], c="#dc2626", s=20, zorder=5)
    axes[0].set(xlabel="Time from selected segment start (s)", ylabel="Amplitude (FS)",
                title=f"{label} | waveform; peak {peak['amplitude']:.5f} at {peak['time_s']:.5f} s")
    axes[0].legend(loc="upper right")
    axes[1].plot(spectrum.welch_frequencies_hz,
                 10 * np.log10(np.maximum(spectrum.welch_psd, 1e-16)), c=COLORS[0])
    axes[1].set(xlabel="Frequency (Hz)", ylabel="PSD (dB re 1 FS²/Hz)",
                xlim=(0, sample_rate / 2), title="Welch PSD | mean of channel powers")
    axes[1].grid(alpha=0.2)
    _save(fig, directory, "01_original_analysis.png")


def plot_responses(settings_by_name, sample_rate, directory, label):
    fig, ax = plt.subplots(figsize=(10, 4.5), constrained_layout=True)
    minimum, maximum = 0.0, 0.0
    for index, (name, settings) in enumerate(settings_by_name.items()):
        freq, db = frequency_response(sample_rate, settings)
        minimum, maximum = min(minimum, float(np.min(db))), max(maximum, float(np.max(db)))
        ax.semilogx(freq[1:], db[1:], label=name.replace("_", " "), c=COLORS[index % len(COLORS)])
    ax.axhline(0, c="#94a3b8", lw=0.5)
    margin = max(1.0, (maximum - minimum) * 0.1)
    ax.set(xlim=(20, sample_rate / 2), ylim=(minimum - margin, maximum + margin), xlabel="Frequency (Hz)",
           ylabel="Gain (dB)", title=f"{label} | three-band IIR frequency responses")
    ax.grid(which="both", alpha=0.2)
    ax.legend()
    _save(fig, directory, "02_equalizer_responses.png")


def plot_comparisons(original_spectrum, spectra_by_name, directory, label):
    fig, ax = plt.subplots(figsize=(10, 4.5), constrained_layout=True)
    ax.semilogx(original_spectrum.welch_frequencies_hz[1:],
                10 * np.log10(np.maximum(original_spectrum.welch_psd[1:], 1e-16)),
                color="#111827", lw=1.5, label="Original")
    for index, (name, spectrum) in enumerate(spectra_by_name.items()):
        if name == "flat":
            continue
        ax.semilogx(spectrum.welch_frequencies_hz[1:],
                    10 * np.log10(np.maximum(spectrum.welch_psd[1:], 1e-16)),
                    color=COLORS[index % len(COLORS)], lw=0.9, label=name.replace("_", " "))
    ax.set(xlim=(20, original_spectrum.frequencies_hz[-1]), xlabel="Frequency (Hz)",
           ylabel="PSD (dB re 1 FS²/Hz)", title=f"{label} | before/after PSD, raw filter outputs")
    ax.grid(which="both", alpha=0.2)
    ax.legend()
    _save(fig, directory, "03_psd_comparison.png")

    # One shared color scale; independent auto-scaling would hide EQ changes.
    all_spectra = [("Original", original_spectrum), *spectra_by_name.items()]
    maximum = max(float(np.max(item.power_psd)) for _, item in all_spectra)
    vmax = 10 * np.log10(max(maximum, 1e-16))
    vmin = vmax - 80
    fig, axes = plt.subplots(len(all_spectra), 1, figsize=(11, 2.3 * len(all_spectra)),
                             sharex=True, sharey=True, constrained_layout=True)
    for ax, (name, spectrum) in zip(axes, all_spectra):
        heat = ax.pcolormesh(spectrum.times_s, spectrum.frequencies_hz / 1000,
                            10 * np.log10(np.maximum(spectrum.power_psd, 1e-16)),
                            vmin=vmin, vmax=vmax, cmap="magma", shading="auto", rasterized=True)
        ax.set(ylabel="Frequency (kHz)", title=name.replace("_", " "))
    axes[-1].set_xlabel("Window center from selected segment start (s)")
    fig.suptitle(f"{label} | STFT PSD, common color scale")
    fig.colorbar(heat, ax=axes, label="PSD (dB re 1 FS²/Hz)", shrink=0.8)
    _save(fig, directory, "04_spectrogram_comparison.png")
