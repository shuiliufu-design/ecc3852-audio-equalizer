# 实时播放器与界面交接

当前界面更新：2026-11-10，用户实际反馈原12秒扫频示例掩盖均衡差异。播放器默认与Synthetic demo改为独立60秒固定120/1000/6000 Hz混合试听示例，并提供英文Bypass EQ做A/B对比。原12秒文件及以下历史设备证据保留不变。最新验证和局限见STATUS.md与outputs/audibility/；没有把新示例称为正式音乐或已通过人工听感。

2026-11-10，Asia/Kuala_Lumpur。当前全部输入为 synthetic/demo；正式音乐和人工听感尚未提供。

## 启动与安装

在 `/Users/ma/Documents/ChatGPT/ECC3852 Assignment` 执行：

```sh
.venv/bin/python play.py
```

默认载入 `audio/demo/synthetic_demo.wav`，不自动播放。点击播放后可拖动低、中、高音滑块，范围 -12 至 +12 dB，提交值以 0.5 dB 步长取整。频率和 Q 读取 `config.json` 的 equalizer 部分。重置只改变三个增益，保持正在播放的位置；停止回到开头；暂停保留滤波状态并在音频队列排空后暂停。

新环境：`sh scripts/setup_player.sh`。可选：`--list-devices`、`--device ID`、`--volume-db -24`、位置参数音频路径。设备 ID 随设备变化，以当次列表为准。WAV/FLAC 等解码能力取决于 libsndfile；不支持的文件、采样率或声道会显示错误，不静默转换。

## 文件清单

新增：

- `play.py`：可选播放入口；离线 `run.py` 不变。
- `src/ecc3852/player.py`：`RealtimeEqualizer`、`OutputSafety`、`AudioPlayer` 和输出设备查询。
- `src/ecc3852/gui.py`：Tkinter 控件、40 ms 滑块提交节流、播放状态、保护与设备显示。
- `requirements-player.txt`、`scripts/setup_player.sh`：复用现有锁定依赖，追加 sounddevice 0.5.6。
- `tests/test_player.py`：24 项数值与 fake stream/真实 worker 测试，不要求声卡或 Tk 桌面。
- `scripts/check_audio_output.py`：独立低音量本机输出验证，使用真实设备，不录音。
- `scripts/check_player_gui.py`：原生 Tk 控件/事件和尺寸检查，模拟音频后端，不输出声音。
- `PLAYER_HANDOFF.md`：本交接。

更新文档：`README.md`、`STATUS.md`、`HANDOFF.md`。没有修改 DSP 核心、共享配置、现有离线 CLI、报告或实验结果。验证证据另存在 `outputs/player/`，没有覆盖主对话的日志。

## 接口和设计

`RealtimeEqualizer` 仅调用现有 `EqualizerProcessor`，不重写 IIR 系数，不修改其私有状态。固定参数逐块结果与离线 `apply_equalizer` 逐样本相同。每个声道有独立历史。

变参时先用前面的输入预热新处理器：可用时至少 250 ms，按新 SOS 极点的衰减估算延长，最长 2 秒。该估算不是对任意输入的严格误差界；有限预热不声称等同无限历史。两处理器在相同输入上持续运行，按全局样本数线性交叉淡化 30 ms；完成后保留新实例。淡化途中再收到请求时，完成当前淡化，然后接最新目标。GUI 连续拖动时仍周期性提交，避免等到停手才生效。

音频文件在独立 worker 中一次解码到内存；同一线程拥有传输控制、DSP 和阻塞 `sounddevice.OutputStream.write()`，无 Python 高优先级音频回调。GUI 通过队列发命令，每 100 ms 读取快照。输出为 C 连续 float32、512 帧一块，最后允许短块。进度是已提交源样本数，可能领先真实听到的位置一个设备缓冲；不是声卡 DAC 时间戳。

固定播放增益默认 -18 dB，CLI 可显式设为 [-60, 0] dB。随后硬裁切至 ±0.95 FS 并统计受影响的逐声道样本数、保护前累计峰值。该保护在触发时会失真，应降低增益；不做逐块归一化。播放开始/继续、暂停、文件结尾加约 10 ms 音量渐变；停止立即 abort 并复位，可能有截断。离线处理/导出没有任何改变。

## 实际验证

1. `.venv/bin/python run.py test`：53 项通过，最新 1.442 s。原 29 项加播放器 24 项；日志 `outputs/player/validation.log`。覆盖固定参数与离线一致、声道隔离、EOF/重播、暂停/继续/停止、跨块淡化、快速目标合并、硬峰值保护、C 连续 float32、设备打开失败重试、换文件和设备关闭异常。
2. `.venv/bin/python scripts/check_audio_output.py`：真实 MacBook Air扬声器、44100 Hz、双声道、512 帧、-24 dB。快速变参、暂停/继续、停止/重播、三个合成频段独立调整、12 秒完整 EOF 排空均通过。欠载 0、保护触发 0；保护前累计峰值 0.0338161315 FS。设备报告 `outputs/player/device_check.json`。
3. 同一次设备运行，PortAudio 报告输出延迟 246.2585 ms；最大一次 DSP render 2.2935 ms，512/44100 = 11.61 ms。没有通过麦克风测量声学延迟，也没有人工试听。
4. `.venv/bin/python scripts/check_player_gui.py`：7 组 Tk 控件/事件检查通过，含连续拖动时提交、重置、状态与错误、保护显示、尺寸和关闭。默认 820×720、最小 720×700；当次请求布局 539×650。记录 `outputs/player/gui_check.json`，它使用模拟播放器。

实际设备首轮发现 `data must be C-contiguous`，已通过 `np.ascontiguousarray(..., dtype=float32)` 修复并加 fake stream 回归约束。关闭过程中设备异常也会尝试关闭流并让 worker 退出。原始输入通过现有加载器记录 SHA-256，不写入原文件。

## 未完成和局限

- 人工试听、可见窗口截图视觉检查、正式音乐、较长时间稳定性和其他设备/平台验证。桌面自动化工具无法定位未打包 Python 窗口，Tk 控件检查不能代替截图检查。
- 本机实际输出延迟约 246 ms，滑块不会瞬时可闻；该值由设备/PortAudio 缓冲决定。当前是 Python 尽力实时实现，没有硬实时保证。
- 文件整体载入内存，适合本作业的短音乐片段；超长或多声道文件可能占用较多内存。设备不支持采样率/声道时明确报错。
- 预热最多 2 秒；自定义很低的频率或很高的 Q 可能需要更长历史。若以后变更默认设计，须重新检验切换瞬态和处理耗时。
- 设备断连若导致底层阻塞写长期不返回，worker 无法及时取新命令；关闭等待 5 秒后会报告超时。普通设备打开/关闭异常已有测试，未声称覆盖所有热插拔故障。
- 当前不增加实时录音、拖动定位、循环、实时 WAV 导出等额外功能；离线输出继续使用既有处理入口。

## 可复制回主对话

```text
实时播放器阶段已完成。启动：在 ECC3852 Assignment 目录运行 .venv/bin/python play.py，默认加载现有 synthetic_demo.wav，不自动播放。
已实现加载、播放/暂停/停止、低中高独立滑块、重置、状态和过载显示。复用 EQSettings / EqualizerProcessor；播放器层有限历史预热 + 30 ms 双实例线性交叉淡化，保留跨块状态；固定播放增益默认 -18 dB，末级 ±0.95 FS 硬峰值保护并计数。
未修改共享 DSP 核心、config.json、run.py、原音频或离线结果。新增文件及设计见 PLAYER_HANDOFF.md；可选依赖 requirements-player.txt，安装入口 sh scripts/setup_player.sh。
全量 53 项测试通过。真实 MacBook Air扬声器以 -24 dB、44.1 kHz 双声道完成完整12秒合成输出及三段变参/暂停继续/重播，欠载0、保护触发0；设备延迟约246 ms。Tk控件与连续拖动事件检查通过。
证据：outputs/player/validation.log、device_check.json、gui_check.json。待人工试听、截图视觉检查、正式音乐与长时稳定性验证；没有音乐结论或听感声明。
```

## 查阅的官方接口文档

- [sounddevice streams](https://python-sounddevice.readthedocs.io/en/latest/api/streams.html)：阻塞写、启动、排空停止与 abort 生命周期。
- [sounddevice installation](https://python-sounddevice.readthedocs.io/en/latest/installation.html)：macOS pip 安装包含 PortAudio。
- [Python Tkinter](https://docs.python.org/3/library/tkinter.html)：可选 Tk 模块和事件循环。

这些是接口资料，不替代报告中的研究文献；不要把软件文档日期当成最新 DSP 研究结论。
