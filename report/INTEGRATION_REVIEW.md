# 主对话集成验收

2026-11-10（Asia/Kuala_Lumpur）。已接收实时播放器和报告专项交接，复核代码、保存日志、设备记录及报告证据快照。

## 已确认的范围

- 实时播放器复用现有DSP，512帧阻塞输出、状态保持、有限历史预热与30 ms交叉淡化、显式固定播放衰减和样本峰值保护，与专项记录一致。未发现默认工作流程中需新增修复的正确性问题。
- 报告正确区分合成/音乐、理论响应/测量、原29项基线/实时后53项测试、设备报告延迟/声学延迟。报告方法和既有数值与证据一致。
- 约246 ms是此前PortAudio报告的输出延迟，约2.29 ms是该次记录的单块DSP与输出准备耗时。主对话本次未重新访问声卡、启动GUI或试听，继续引用历史设备记录。
- 集成修改前，report/evidence_inventory.json的34项核心与12项播放器文件SHA-256全部匹配。旧demo/player输出、旧验证日志、原inventory与verification.json保留。变更前代码与相关文档备份在outputs/integration/baseline_snapshot/，有独立映射清单。

## O1：CSV峰值语义已在生成器修正

历史 `outputs/demo/` 使用schema 1，保留原样：

- CSV `export_peak_fs` = raw_peak × common_gain，属于PCM量化前预计峰值。
- JSON `presets.*.export.decoded_peak` = 实际读取导出WAV后的样本峰值。

新运行生成schema 2：

- CSV `estimated_export_peak_fs`：预计峰值。
- CSV `decoded_export_peak_fs`：解码实测峰值；包括原信号对比副本和全部预设。
- JSON新增 `export.original_comparison_decoded_peak` 和字段解释，既有预设的decoded_peak保持原义。

集成回归测试分别读取实际WAV核对CSV和JSON，并检查预计值仍对应同一个共同增益。DSP、采样、滤波、归一化策略和PCM位深未改变。

## O2：正式音乐状态的决定

当前没有音乐，生成器继续输出 `is_formal_music_experiment=false`。不提供只凭用户音频命令成功就自动改为true的开关，也不修改历史JSON。

已新增空白 `music_review_template.json`，供选曲后建立独立记录。主对话将核对曲名/版本/取得方式、原文件哈希、实际片段、config/results哈希和来源确认日期。来源确认、计算完成、人工听感、截图、较长音乐播放与报告完成分别记录。取得实际音乐后再实现读取该来源记录的正式运行支持；该功能本轮尚未实现。

## 接续事项

1. 用户选择音乐，保留原文件至audio/original/，提供曲名和取得方式。
2. 主对话进行独立音乐实验并保存新输出，结合音乐说明频率/Q/增益和窗长选择。
3. 运行播放器并由用户记录真实试听；完成可见截图和音乐播放验证。
4. 报告对话根据新证据补音乐部分；当前草稿不能作为最终提交版本。

本轮集成的新测试日志和schema-2验证输出位于outputs/integration/，与历史记录分开。

## 本轮实际验证结果

- `.venv/bin/python run.py test`：53项通过，1.423 s。原有用例加强了CSV字段与实际WAV的独立交叉验证，测试数保持53。
- 新schema 2对同一合成信号离线运行成功，保存在`outputs/integration/demo_v2/`；本轮没有重复生成图表。
- 原对比副本和四个预设的WAV与`outputs/demo/`基线逐样本一致。bass_boost预计峰值0.3028744654053621 FS，解码峰值0.30287444591522217 FS，差异为正常PCM量化。
- 新测试日志为`outputs/integration/validation.log`，结构化检查为`outputs/integration/acceptance.json`。这些记录没有取代原报告的数值快照或设备证据。
