# 报告证据复核与主对话待确认事项

日期：2026-11-10。本轮未改DSP代码、共享配置、已保存实验输出或顶层状态文件；在`report/`保存了只读诊断的结果。`outputs/validation.log`中的29项测试属于主对话实际运行记录，本轮**没有重跑完整测试**，也没有试听或访问音频设备。

## 已执行的复核

- 阅读分析、读写、均衡器、绘图和流水线实现，以及相关测试；检查demo四张图与保存的题目页面图。
- 对原合成WAV核对SHA-256，重新计算四预设的原始峰值/RMS、flat恒等差、极点模，并读取实际导出WAV峰值及量化误差。诊断只读原文件，不覆盖demo结果。
- 以本项目`.venv/bin/python -B`执行；数值见`verification.json`。`evidence_inventory.json`保留34项核心/配置/数据依据，另记录12项后来完成交接的播放器代码/日志；两个证据范围分开，不用固定核心诊断替代变参或设备检查。

| 检查 | 实际复核结果 |
| --- | --- |
| 合成源哈希 | 与results.source.sha256一致 |
| flat与输入最大绝对差 | 0 |
| 三个非平直预设PCM24最大绝对量化误差 | 均小于2⁻²³ = 1.1920928955×10⁻⁷ FS |
| 最大极点模：bass/mid/treble预设 | 0.9831891914 / 0.9042726147 / 0.6242886509，均<1 |
| 单独+6 dB低/高棚式在200/4000 Hz处 | 均约+3 dB |
| 单独+6 dB峰值段在1000 Hz处 | 约+6 dB |

本轮没有发现会推翻当前合成验证结论的核心数值错误。以下是输出语义与后续证据状态事项，由主对话决定是否调整，报告已按当前实现处理。

界面对话随后完成交接；已只读核对其实现、53项测试保存日志、合成实机与模拟后端Tk记录，见`real_time_evidence.md`。报告未重跑这些检查，也未进行人工试听或截图检查。原29项是DSP基线，最新53项为原29加播放器24项。

## O1：CSV导出峰值列是量化前预计值

位置：`src/ecc3852/pipeline.py`写`summary.csv`的行。

`export_peak_fs`目前等于`raw_peak_fs × common_gain_linear`，并未读取实际导出WAV。实际WAV峰值在`results.json:presets.*.export.decoded_peak`。两者微小差异来自正常PCM量化，不是发现削波，但列名易误读。

在项目根目录复现（只读，已实际执行等价诊断）：

```sh
.venv/bin/python -B - <<'PY'
import csv, json
from pathlib import Path
import numpy as np
import soundfile as sf
r = json.loads(Path('outputs/demo/results.json').read_text())
rows = list(csv.DictReader(Path('outputs/demo/summary.csv').open()))
print(next(v['export_peak_fs'] for v in rows if v['setting'] == 'bass_boost'))
print(r['presets']['bass_boost']['export']['decoded_peak'])
x, _ = sf.read('outputs/demo/bass_boost.wav', always_2d=True)
print(float(np.max(np.abs(x))))
PY
```

输出应与本轮数值一致：

```text
0.3028744654053621
0.30287444591522217
0.30287444591522217
```

建议主对话决定：将CSV列重命名为“预计峰值”，或改存实际解码峰值并相应更新测试。**本轮不修改代码**；草稿§5的“Decoded EQ WAV peak”直接引用JSON的decoded字段，避免误用。

## O2：正式音乐状态当前固定为false

位置：`pipeline.py:run_experiment`构建结果字典时，`is_formal_music_experiment`无条件为`False`，用户音频的note也提示还需审核来源与报告适用性。这是保守的现有证据策略，不妨碍本阶段合成验证。

只读查看：

```sh
rg -n 'is_formal_music_experiment|User audio run' src/ecc3852/pipeline.py
```

关键内容：

```python
"is_formal_music_experiment": False,
"User audio run; music source and report suitability still require review."
```

正式歌曲阶段需主对话约定如何保留来源审核与实验状态；不要仅凭`process`运行成功就说“正式实验完成”，也不要由报告对话擅自编辑原结果JSON来使状态变成true。

## 写作边界与可选补充

- 最高显著频率采用每个信号自身的全局谱峰作−40 dB参照；其时间是最高频率行的最强窗，非首次出现。前后数值变化不能直接称为真实带宽变化。
- 相对频段功率占比不是绝对声能；RMS不是感知响度；0.95 FS是样本峰值策略，不是已验证true-peak限制。
- 固定参数的块/整段一致性不验证滑块切换；静态稳定性也不证明任意动态参数序列安全。
- 初始频率/Q与窗长尚无歌曲依据；现有曲线是理论幅频响应。相位/群延迟、组合预设的分段响应可按讨论需要补充，不属于本轮已经生成的图。
- 合成预设中每次仅一个活动段，现有图02因此同时展示对应活动段与总响应；不要声称已为所有任意组合生成独立段响应图。
- 独立片段由零状态启动，不等价于全曲先滤波再裁剪；当前不追加滤波尾音。报告已解释这点，是否改变处理策略由主对话按实验目的决定。

## 可重现关键诊断

以下命令只读原合成文件和保存配置，打印flat差、量化误差和最大极点模；本轮实际执行了包含这些计算的诊断，结果保存在`verification.json`。

```sh
.venv/bin/python -B - <<'PY'
import json, sys
from pathlib import Path
import numpy as np
import soundfile as sf
sys.path.insert(0, str(Path('src').resolve()))
from ecc3852.equalizer import EQSettings, apply_equalizer, design_equalizer
r = json.loads(Path('outputs/demo/results.json').read_text())
x, fs = sf.read(r['source']['path'], dtype='float64', always_2d=True)
for name, p in r['presets'].items():
    settings = EQSettings(**p['settings'])
    y = apply_equalizer(x, fs, settings)
    wav, _ = sf.read(Path('outputs/demo') / p['export']['file'], always_2d=True)
    error = np.max(np.abs(wav - y * p['export']['common_gain_linear']))
    pole = max(np.max(np.abs(np.roots(row[3:])))
               for row in design_equalizer(fs, settings))
    print(name, 'PCM error=', error, 'max pole=', pole)
    if name == 'flat':
        print('flat difference=', np.max(np.abs(y - x)))
PY
```
