# 报告准备

当前没有正式音乐结果，本目录只记录结构与证据需求。合成信号验证须明确标为 synthetic verification，不得写成对实际歌曲的发现。

## 本阶段文件（2026-11-10）

| 文件 | 用途 |
| --- | --- |
| [draft.md](draft.md) | 英文报告草稿：已有实现的方法、IIR 设计、合成验证；歌曲结果与听感标为待填 |
| [requirements_matrix.md](requirements_matrix.md) | 作业原条款、报告章节、现有证据和缺项 |
| [music_experiment_plan.md](music_experiment_plan.md) | 正式音乐数据、图表、讨论和提交材料清单 |
| [listening_log.csv](listening_log.csv) | 仅列字段的实际试听记录表，当前没有试听记录 |
| [evidence_inventory.json](evidence_inventory.json) | 本轮依据的代码、配置、结果、图表与哈希快照 |
| [verification.json](verification.json) | 本轮只读重算的flat差、极点、量化误差与实际导出峰值 |
| [real_time_evidence.md](real_time_evidence.md) | 新交接的53项测试、合成实机输出与模拟后端Tk检查的证据边界 |
| [technical_review.md](technical_review.md) | 只读复核结果、输出字段注意事项与主对话复现命令 |
| [HANDOFF_REPORT.md](HANDOFF_REPORT.md) | 可交回主对话的进度、边界与后续动作 |

文献核实表见 [verified_sources.md](../references/verified_sources.md)，可导入的书目信息见 [references.bib](../references/references.bib)。草稿暂用稳定编号 `[R1]`–`[R7]`；这是项目写作约定，题目未指定引用格式。

正文暂用英文，项目交接与待补说明用中文。当前交付为可版本管理的 Markdown 草稿，尚未制作最终排版 PDF/Word。不要将本阶段文件作为已经完成音乐实验的最终报告提交。

## 建议结构

1. **Introduction and Objectives**：作业目标、歌曲选择和均衡器用途。
2. **Input Audio and Methodology**：音乐来源、格式、采样率、声道、时间范围；分析与缩放方法。
3. **Original Audio Analysis**：最大绝对幅度、带符号样本值、时间和声道；波形、频谱、spectrogram；最强时频能量位置；按明确阈值定义的最高显著频率；补充分析。
4. **Equalizer Design**：IIR 选择依据、三个 biquad、参数与系数、独立增益控制、各段及整体频率响应、稳定性。
5. **Validation and Music Results**：合成验证与正式音乐实验分别展示；处理前后对比、参数、指标、导出音频及实际听感。
6. **Real-time Challenge**：若实现，说明处理流程、块长、状态和参数更新、设备、延迟的计算或测量方式及运行表现；未实现时如实说明，评分依据以老师说明为准。
7. **Discussion and Conclusion**：结果解释、设计取舍、限制及结论。
8. **References**：核实且相关的技术资料与研究文献。
9. **Appendix and Submission Checklist**：代码入口、依赖版本、复现命令、小组分工及提交清单。

## 写作时必须取得的证据

- 每项图表与数值对应一个实际结果文件及配置；图注明时间、频率、幅度／功率单位与使用声道。
- 窗长、重叠和 FFT 点数必须说明；比较 spectrogram 使用一致色标。
- 明确区分最高显著频率、最强时频功率点以及奈奎斯特上限。
- 均衡前后比较记录增益和防削波处理；人工听感、运行延迟和实时稳定性只记录实际观察。
- 文献记录作者／机构、标题、年份、链接和所支持的具体方法；官方工具文档不能自动替代最新研究文献的检索。
- 提交须包含原曲、处理后音频、源代码、相关图表及解释。截止日期依课程第 14 周安排确认，并保留要求的提交记录。
