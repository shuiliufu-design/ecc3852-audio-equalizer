# Audio Equalizer for Music: Analysis and a Three-Band IIR Design

**Working draft, 10 November 2026.** Methods and design describe the existing implementation. All numerical results in §§5 and 7 are **synthetic verification**, not a song experiment. Section 7 incorporates the player conversation's saved device and widget checks; no human listening study, GUI screenshot review or formal music result is claimed. `[TO FILL ...]` denotes missing evidence, never an estimated result. Group members: `[TO FILL — names, student IDs and actual contributions]`.

## 1. Introduction and objectives

This project develops a Python workflow for analysing audio and adjusting its spectral balance with independently controlled bass, mid and treble filters. The objectives are to locate sample peaks, describe time-varying spectral content, implement an inspectable digital equalizer, and compare the original and processed signals using reproducible measurements. The player reuses the same causal filtering core.

The three-control design follows the conventional tone-control structure discussed by Välimäki and Reiss [R5]. More recent work explores multi-shelf graphic equalization [R6] and real-time linear-phase octave equalization [R7]. These provide design context; the present implementation does not reproduce those systems or inherit their reported performance.

`[TO FILL — selected song, reason for selection and the musical objective of the chosen settings.]`

## 2. Input and analysis methodology

### 2.1 Software and source preservation

The saved synthetic run records Python 3.12.14, NumPy 2.5.4, SciPy 1.18.1, Matplotlib 3.11.2 and SoundFile 0.14.0 in `outputs/demo/results.json`. The lock file records the reproducible environment. These are the run's recorded versions; online documentation is cited separately with its access date.

Audio is decoded to a float64 array of shape samples × channels at its actual sample rate. The offline pipeline applies no resampling, waveform downmix, automatic loudness normalization or limiter. The original file is retained and its SHA-256 is checked before and after processing. A requested segment start is rounded down to a sample; duration is rounded to a sample count and limited by the file end. Metadata records the actual start and end-exclusive samples and times.

All reported event times initially refer to the first sample of the selected segment. Original-file time is obtained by adding the saved `source.start_s`. Empty, complex or non-finite audio and invalid settings are rejected. Analysis requires at least two samples. Formal-song provenance, format, source duration and actual segment range remain `[TO FILL — music manifest and results.source]`.

### 2.2 Sample amplitude and time-domain measures

For sample array \(x[n,c]\), the absolute peak is

\[
P=\max_{n,c}|x[n,c]|.
\]

The implementation retains its signed sample value, zero-based sample index, one-based channel and time \(n/F_s\). Ties select the earliest sample and then the lowest channel index. The maximum signed sample is reported separately. Aggregate RMS is

\[
x_{\mathrm{RMS}}=\sqrt{\frac{1}{NC}\sum_{n=0}^{N-1}\sum_{c=1}^{C}x[n,c]^2}.
\]

Per-channel RMS and DC means are also recorded. Amplitude is expressed relative to digital full scale (FS), without acoustic calibration. RMS is not a perceptual loudness measurement.

### 2.3 Time-frequency representation

`analyze_audio` uses `ShortTimeFFT` [R3] with a periodic Hann window and one-sided PSD scaling. With the current/default settings, let \(L=\min(N,\max(2,\operatorname{round}(0.030F_s)))\), hop \(H=\max(1,\operatorname{round}(0.25L))\), and FFT length \(M\) be the next power of two at least \(L\). Window duration and overlap are configurable. Only complete windows inside the selected audio are included; the final incomplete window is omitted. Frame \(m\) is timestamped at \((mH+\lfloor L/2\rfloor)/F_s\).

For each channel, windowed DFT power is normalized by \(F_s\sum_n w[n]^2\), with interior positive-frequency bins doubled. DC and the Nyquist bin are not doubled. The channel powers are then averaged:

\[
\overline{S}[k,m]=\frac{1}{C}\sum_{c=1}^{C} S_c[k,m].
\]

Averaging powers avoids cancellation of opposite-phase stereo waveforms. It produces an aggregate spectrum, not a channel-specific event location. PSD units are FS²/Hz; logarithmic figures use \(10\log_{10}(\overline{S}/(1\,\mathrm{FS}^2/\mathrm{Hz}))\).

| Parameter | Existing synthetic run |
| --- | ---: |
| Sample rate | 44,100 Hz |
| Hann window | 1,323 samples = 30 ms |
| Hop / actual overlap | 331 samples / 74.9811% |
| FFT length / bin spacing | 2,048 / 21.533203125 Hz |
| Frame spacing | 7.505668934 ms |
| Complete frames | 1,595 |

A 30 ms window is an initial compromise between time localization and spectral detail. The 7.51 ms frame spacing is not event-time accuracy. Zero padding gives a denser frequency grid without improving the resolving power of the 30 ms observation. `[TO FILL — justify the window against the selected music and, if useful, compare another window length.]`

### 2.4 Two distinct frequency/time descriptors

Because the assignment's maximum-frequency/energy wording is ambiguous, two operational measures are retained. They are project definitions, subject to clarification by the lecturer.

1. **Strongest time-frequency PSD bin:** \((k_*,m_*)=\arg\max_{k,m}\overline{S}[k,m]\). Report its frequency, window-center time and PSD. This is not integrated total energy.
2. **Highest significant frequency bin:** find the highest \(k\) for which at least one frame satisfies \(\overline{S}[k,m]\geq S_{\max}10^{T/10}\), with initial threshold \(T=-40\) dB. At that frequency, report the time of the maximum PSD frame, not its first threshold crossing.

The threshold is relative to **each analysed signal's own** global spectrogram peak. Noise, leakage, window choice and EQ-induced changes of that peak can alter the estimate. It is neither a guaranteed physical bandwidth nor simply \(F_s/2\). Silence returns null spectral events rather than invented frequencies. `[TO FILL — song estimates and threshold sensitivity.]`

### 2.5 Recording-wide PSD and band power proportions

Welch PSD [R4] uses Hann segments of \(\min(N,8192)\) samples, half-segment overlap, `detrend=False` and density scaling. Per-channel estimates are averaged. The recording-wide dominant frequency is the maximum Welch bin, distinct from the strongest short-time bin.

The low/mid/high analysis intervals are [0,200), [200,4000) and [4000,\(F_s/2\)] Hz. Each reported proportion is the sum of Welch PSD bins in an interval divided by the sum over all bins. The constant bin width cancels in this ratio. These are relative power proportions, not absolute acoustic energies or ideal filterbank outputs. A proportion may increase merely because another band is attenuated.

## 3. Original music analysis — pending

`[TO FILL — music provenance and source hash; maximum absolute and signed peaks; per-channel RMS/DC; waveforms and Welch PSD; spectrogram and parameters; strongest PSD bin; highest significant frequency and threshold; interpretation supported by the selected music.]`

Both segment and original-file timestamps must be given where event locations are discussed. Do not identify an instrument or voice solely from a synthetic frequency or an unlabeled PSD peak. The planned evidence is listed in `music_experiment_plan.md`.

## 4. Equalizer design and implementation

### 4.1 Topology and initial parameters

Three second-order sections are cascaded: low shelf → peaking mid band → high shelf. The design uses the RBJ biquad equations documented in the W3C *Audio EQ Cookbook* [R1]. The tone-control discussion in [R5, §6.1] provides context for this simple structure; final music-specific parameters still require justification.

| Control | Structure | Frequency interpretation | Initial value | Gain range |
| --- | --- | --- | ---: | ---: |
| Bass | Low shelf, slope S=1 | Midpoint between shelf levels in dB | 200 Hz | −12 to +12 dB |
| Mid | Peaking, Q=1 | Peak/cut center | 1,000 Hz | −12 to +12 dB |
| Treble | High shelf, slope S=1 | Midpoint between shelf levels in dB | 4,000 Hz | −12 to +12 dB |

The frequencies are not brick-wall crossover boundaries. For an isolated +6 dB shelf its control frequency has +3 dB gain; full shelf gain occurs toward the appropriate spectral end. The isolated mid filter has its requested gain at 1 kHz. Each gain changes only its own section, while section responses overlap in frequency. The combined response is therefore evaluated explicitly.

IIR sections provide a compact causal structure for the intended streaming reuse. No comparative FIR benchmark or measured CPU/latency advantage of this IIR design has been established here. The device-reported output latency in §7 is a separate observation. The choice accepts a non-linear phase response; linear-phase alternatives have their own implementation and latency considerations [R7].

### 4.2 Coefficients and transfer function

For gain \(G\) dB and control frequency \(f_0\), define \(A=10^{G/40}\), \(\omega_0=2\pi f_0/F_s\), and \(c=\cos\omega_0\). For the peaking section, \(\alpha=\sin\omega_0/(2Q)\):

\[
\mathbf b=[1+\alpha A,\;-2c,\;1-\alpha A],\qquad
\mathbf a=[1+\alpha/A,\;-2c,\;1-\alpha/A].
\]

For shelves with S=1, \(\alpha=\sin\omega_0/\sqrt{2}\), \(\beta=2\sqrt{A}\alpha\), \(u=A+1\), \(v=A-1\). The low-shelf coefficients are

\[
\begin{aligned}
\mathbf b_L&=A[u-vc+\beta,\;2(v-uc),\;u-vc-\beta],\\
\mathbf a_L&=[u+vc+\beta,\;-2(v+uc),\;u+vc-\beta].
\end{aligned}
\]

The high-shelf coefficients are

\[
\begin{aligned}
\mathbf b_H&=A[u+vc+\beta,\;-2(v+uc),\;u+vc-\beta],\\
\mathbf a_H&=[u-vc+\beta,\;2(v-uc),\;u-vc-\beta].
\end{aligned}
\]

Every section is divided by its own \(a_0\) and stored as \([b_0,b_1,b_2,1,a_1,a_2]\). Its transfer function and the total response are

\[
H_i(z)=\frac{b_{0i}+b_{1i}z^{-1}+b_{2i}z^{-2}}{1+a_{1i}z^{-1}+a_{2i}z^{-2}},\qquad
H(z)=H_L(z)H_M(z)H_H(z).
\]

Zero-gain sections are explicitly replaced with `[1,0,0,1,0,0]`, ensuring exact flat filtering rather than relying on numerical pole-zero cancellation. With all sections active the cascade has up to sixth-order numerator and denominator; the single-band demonstration presets have two identity sections.

The following active rows are copied from the saved **synthetic** run at 44.1 kHz; rounded values are for exposition. Full precision and all three rows per preset remain in `results.json:presets.*.sos`.

| Preset / active section | b0 | b1 | b2 | a1 | a2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| bass_boost / low shelf +6 dB | 1.007017440 | −1.965814454 | 0.959924831 | −1.966095739 | 0.966660986 |
| mid_cut / peaking −6 dB | 0.954535451 | −1.799290976 | 0.863173510 | −1.799290976 | 0.817708962 |
| treble_boost / high shelf +6 dB | 1.742695375 | −2.322910674 | 0.880675015 | −1.089276603 | 0.389736320 |

### 4.3 Causal processing and stability

`apply_equalizer` uses a single causal `sosfilt` pass [R2] along the sample axis with zero initial state. It does not use forward/backward filtering. Design checks reject non-finite coefficients and any denominator root with magnitude at least one. The response utility evaluates the total SOS response on 4,096 points including DC and Nyquist; displayed curves are magnitude in dB, not measured acoustic responses.

`EqualizerProcessor` retains two delay states per section per channel, with state shape `(3,2,channels)`. Reusing the instance across blocks preserves filter history. `reset()` clears it for a new stream or seek. This core processor has fixed settings; the separate player layer handles gain transitions using multiple core instances, as described in §7.

When a segment is filtered independently, zero initial state does not reproduce filtering the full song before cropping. Startup transients and causal phase shifts must be considered in interpreting peaks and segment boundaries. The current output has the input length and does not append the filter's decay tail.

### 4.4 Shared export attenuation

Let \(P_{\max}\) be the largest absolute sample across the unprocessed segment and all raw preset outputs. The common export gain is

\[
g=\begin{cases}\min(1,0.95/P_{\max}),&P_{\max}>0,\\1,&P_{\max}=0.\end{cases}
\]

The same gain is applied to `comparison_original.wav` and every preset before PCM24 export. No preset is normalized separately and quiet audio is not boosted. The plots and `raw_analysis` describe signals **before** this shared attenuation. Decoded WAV peaks are separately saved as `presets.*.export.decoded_peak`. In the preserved schema-1 evidence under `outputs/demo/`, CSV `export_peak_fs` is the pre-quantization prediction. New schema-2 runs use explicit CSV columns `estimated_export_peak_fs` and `decoded_export_peak_fs`; the latter is measured from the saved WAV. Original comparison WAV decoding is recorded as `export.original_comparison_decoded_peak`. This field clarification does not change the filter or the baseline measurements in §5; see `INTEGRATION_REVIEW.md`.

This is a sample-peak export policy, not a true-peak or perceptual loudness guarantee. PCM quantization and playback reconstruction are separate considerations. The common gain preserves relative preset levels but does not loudness-match a listening comparison.

## 5. Synthetic verification — existing evidence only

### 5.1 Known signal and figures

The 12 s stereo PCM24 input has 529,200 samples at 44.1 kHz. It contains 100 Hz during 0–4 s, 1 kHz during 4–8 s and 8 kHz during 8–12 s, with 50 ms fades and a quiet 250–10,000 Hz linear chirp. Right-channel tones have 0.8 times left amplitude and a 0.4 rad phase offset. These are generated components, not music or identified instruments.

Existing figure evidence (all explicitly labelled SYNTHETIC DEMO):

- **S1** `outputs/demo/01_original_analysis.png`: per-channel waveform, marked sample peak and channel-mean Welch PSD.
- **S2** `outputs/demo/02_equalizer_responses.png`: theoretical total magnitude responses. Each non-flat preset has one active section, so it also illustrates that section's isolated response.
- **S3** `outputs/demo/03_psd_comparison.png`: original/processed Welch PSD before shared attenuation, on common axes.
- **S4** `outputs/demo/04_spectrogram_comparison.png`: original and four presets using the same PSD color scale. The 80 dB displayed color span and numerical display floor do not define measured noise levels.

### 5.2 Saved measurements

The input absolute peak is **0.164999008 FS**, with signed value **−0.164999008**, at sample **146,302**, channel **1**, time **3.317505669 s**. Aggregate RMS is **0.073667331 FS**. The strongest short-time PSD bin is **107.666016 Hz at 0.135079365 s**; the highest significant bin at −40 dB is **10,012.939453 Hz at 11.971519274 s**. The latter is a finite-window threshold estimate; it does not establish a physical component above the chirp endpoint. The recording-wide Welch maximum is **102.282715 Hz**, reflecting a different estimator and grid from the spectrogram.

| Setting | Bass/mid/treble (dB) | Raw peak (FS) | Raw RMS (FS) | Decoded EQ WAV peak (FS) |
| --- | --- | ---: | ---: | ---: |
| Original | — | 0.164999008 | 0.073667331 | — |
| Flat | 0 / 0 / 0 | 0.164999008 | 0.073667331 | 0.164999008 |
| Bass boost | +6 / 0 / 0 | 0.302874465 | 0.115992617 | 0.302874446 |
| Mid cut | 0 / −6 / 0 | 0.162942535 | 0.064294353 | 0.162942529 |
| Treble boost | 0 / 0 / +6 | 0.169118925 | 0.086126219 | 0.169118881 |

All comparisons use common export gain **1.0 (0 dB)** for this run. None of the raw preset samples reaches full scale. The changes are consistent with processing known synthetic components; they establish no song-specific or perceptual benefit. The dash in the original's decoded column means no decoded-peak field for the original is supplied in the result schema, rather than a zero value.

### 5.3 Automated validation and its scope

`outputs/validation.log` records the main conversation's actual command `.venv/bin/python run.py test`, **29 tests passed**, on 10 November 2026. The report preparation reviewed that log and the test definitions; it did not rerun the complete test suite. Independent read-only checks are recorded in `technical_review.md`.

The tests cover known-signal amplitude/time/channel location, independent FFT comparison, PSD normalization, opposite-phase channel power, threshold behaviour, silence and invalid inputs. Equalizer checks cover exact zero-gain identity, coefficient control independence, no channel crosstalk, steady-tone gain agreement, state reset and exact fixed-setting block/offline agreement. Stability tests cover the default frequencies/Q at 44.1 and 48 kHz for the −12/0/+12 dB gain combinations, not every possible frequency/Q combination. Pipeline checks cover source preservation, crop metadata, PCM24 quantization, config rejection and a loud synthetic case requiring common attenuation.

These baseline tests validate implemented numerical behaviour. They do not establish musical quality, all time-varying filter transitions, real device performance or end-to-end latency. The subsequently handed-over player tests and limited device checks are described separately in §7. No human listening results are available.

## 6. Formal music results and listening — pending

| Result category | Status / required evidence |
| --- | --- |
| Original song and selected range | `[TO FILL — manifest and actual sample range]` |
| Input analysis and event locations | `[TO FILL — music results.json and figures M1/M4]` |
| Preset design and comparisons | `[TO FILL — settings, SOS, raw metrics, figures M2/M3/M4]` |
| Export headroom and output files | `[TO FILL — common gain, decoded peaks and output hashes]` |
| Actual listening observations | `[TO FILL — dates, listeners, devices, playback settings and observations]` |

The pipeline currently marks every run `is_formal_music_experiment=false`; a successful `process` run alone establishes computation, not reviewed music provenance or completion of this assignment. The main conversation will record the selected song, source hash, actual segment, configuration/result hashes and source-review state using `music_review_template.json`. Music-source confirmation, analysis, listening, GUI screenshots and long-run playback are separate states. The current generator has no switch to produce a formally reviewed music run; support for that step will be added with the actual song, rather than by manually changing historical JSON. No placeholder in this section should be replaced without corresponding music evidence.

## 7. Real-time Challenge — synthetic device and widget verification

### 7.1 Player design

During report preparation, the player conversation completed `PLAYER_HANDOFF.md` and saved its evidence separately under `outputs/player/`. The report subsequently reviewed that handoff, relevant player/GUI implementation and the saved logs; it did not rerun playback.

One worker loads the file, owns DSP/transport state and writes C-contiguous float32 blocks through blocking `sounddevice.OutputStream.write()`. There is no Python audio callback. Blocks normally contain 512 frames, with a shorter final block allowed. The Tk interface provides loading, play/pause/stop, three independent gain sliders and reset; updates are submitted about every 40 ms in 0.5 dB steps. Pause preserves filter state; stop aborts the stream and resets position/state.

For a new setting, a second core processor is warmed with available input history: at least 250 ms when available, extended using pole-decay estimates up to a 2 s cap. Both processors then run on the same input during a 30 ms sample-counted linear crossfade. Further changes are coalesced to the latest target after the active fade. Finite warm-up is not exact infinite-history equivalence or a strict transient-error guarantee.

Playback uses a fixed gain, default −18 dB; the device check used −24 dB. Transport operations apply approximately 10 ms amplitude ramps, and the final safety stage hard-clips samples to ±0.95 FS while counting affected channel-samples. This can distort when triggered; it is separate from the offline common-attenuation export policy. The implementation does not normalize individual blocks.

### 7.2 Saved verification and scope

| Evidence | Recorded outcome |
| --- | --- |
| `outputs/player/validation.log` | 53 tests passed: original 29 plus 24 player tests; saved run 1.442 s |
| `device_check.json` | Synthetic input; MacBook Air speakers, 44.1 kHz, stereo, 512-frame blocks, −24 dB playback gain; parameter changes, pause/resume, stop/replay and full 12 s EOF drain passed |
| Underflows / safety activations | 0 / 0 during that recorded synthetic check |
| Largest recorded pre-clipping peak | 0.033816132 FS, after fixed playback gain and transport ramps; counters reset on stop |
| PortAudio-reported output latency | 246.258503 ms |
| Largest recorded block DSP/output-preparation time | 2.293500 ms; includes render, ramps, safety and float32 preparation, excluding blocking write |
| `gui_check.json` | Seven Tk widget/event checks passed using a simulated audio backend; screenshot review unavailable |

For \(B=512\) at 44.1 kHz, \(B/F_s=11.609977\) ms is the block duration. It is neither acoustic end-to-end latency nor a hard real-time guarantee. The device latency above is host-reported, not microphone-measured. Successful scripted device output and separate simulated-backend widget checks do not constitute a human evaluation of GUI/speaker interaction or audibility of transitions.

### 7.3 Remaining real-time evidence

`[TO FILL — formal music playback, actual human listening, visible GUI screenshot review, longer sessions and any additional devices/platforms tested.]` The evidence details and JSON field locations are in `report/real_time_evidence.md`. [R7] concerns a different linear-phase IFIR system; its performance or listening outcomes are not transferred here. The assignment calls this functionality “Challenge” without specifying optional status, bonus marks or a scoring allocation.

## 8. Discussion and provisional conclusion

The current evidence supports an inspectable causal three-band equalizer and a reproducible analysis/export path on synthetic inputs. Explicit identity sections, pole checks, preserved channel states and shared export attenuation make the numerical behaviour reviewable. Spectral aggregation, threshold definitions and timestamp origins are explicitly documented.

The principal remaining limitations are the absence of a selected song, music-specific parameter justification, actual listening observations, GUI screenshot review and longer real-time sessions. The available device evidence is a short, low-volume synthetic check on one device. Shelf/peak overlap, initial-state transients, non-linear phase, window resolution and relative thresholds must be considered in the final discussion. Recent multi-shelf designs [R6] suggest possible future extensions, but no optimized graphic-EQ matching is implemented here.

`[TO FILL — conclusion based on the formal music results; explain which design objectives were met and which remain unsupported. Do not claim improved clarity, stronger vocals, listener preference or real-time stability without evidence.]`

## References

Stable project keys are used during drafting; the final required citation style has not been specified. Bibliographic metadata, verification scope and source links are maintained in `references/verified_sources.md` and `references/references.bib`.

- **[R1]** W3C, *Audio EQ Cookbook*, Working Group Note, 8 June 2021. R. Toy, ed.; adapted from R. Bristow-Johnson. [Fixed version](https://www.w3.org/TR/2021/NOTE-audio-eq-cookbook-20210608/).
- **[R2]** The SciPy community, “scipy.signal.sosfilt,” *SciPy Manual*. [Official documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.sosfilt.html). Accessed 10 Nov. 2026.
- **[R3]** The SciPy community, “scipy.signal.ShortTimeFFT,” *SciPy Manual*. [Official documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.ShortTimeFFT.html). Accessed 10 Nov. 2026.
- **[R4]** The SciPy community, “scipy.signal.welch,” *SciPy Manual*. [Official documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html). Accessed 10 Nov. 2026.
- **[R5]** V. Välimäki and J. D. Reiss, “All About Audio Equalization: Solutions and Frontiers,” *Applied Sciences*, vol. 6, no. 5, art. 129, 2016. [doi:10.3390/app6050129](https://doi.org/10.3390/app6050129).
- **[R6]** S. J. Schlecht, T. Sinjanakhom and V. Välimäki, “Multi-shelf graphic equalizer,” *Signal Processing*, vol. 226, art. 109630, Jan. 2025. [doi:10.1016/j.sigpro.2024.109630](https://doi.org/10.1016/j.sigpro.2024.109630).
- **[R7]** V. Bruschi, S. Cecchi, A. Nicolini and V. Välimäki, “Real-Time Implementation of a Linear-Phase Octave Graphic Equalizer,” in *Proc. 27th Int. Conf. Digital Audio Effects (DAFx24)*, Guildford, UK, 2024, pp. 459–466. [Conference paper](https://www.dafx.de/paper-archive/2024/papers/DAFx24_paper_69.pdf).

## Appendix: reproducibility and submission — pending completion

Current evidence: source modules under `src/ecc3852/`, tests under `tests/`, `config.json`, `requirements-lock.txt`, saved demo outputs and validation log. Evidence identities are frozen in `report/evidence_inventory.json`; a later change requires reviewing affected prose and regenerating relevant results.

`[TO FILL — final code/version snapshot, actual music commands, final validation log, group contribution statement, original song, equalized audio, final figures/report and course-specific submission/signature confirmation.]`
