# 文献入口

核查日期：2026-11-10（Asia/Kuala_Lumpur）。本次仅整理与当前音频分析、三段 IIR 和后续实时实现有关的来源，不声称已穷尽最新研究。

- [逐项核实、支持范围及使用限制](verified_sources.md)：包含原始链接、出版信息、已读取层级和草稿对应章节。
- [可导入书目信息](references.bib)：BibTeX，键与下表一致。
- [报告工作草稿](../report/draft.md)：使用稳定编号 `[R1]`–`[R7]`；编号是项目写作约定，不是题目指定格式。
- [作业原文来源状态](source_status.md)：作业要求与研究文献分开管理；保留的页面图不是恢复的原 PDF。

| 编号 | 资料 | 类型 | 年份与用途 | BibTeX 键 |
| --- | --- | --- | --- | --- |
| R1 | W3C, *Audio EQ Cookbook* | 基础技术说明 | 2021-06-08，biquad 公式、增益及 Q | `w3c2021cookbook` |
| R2 | SciPy, `sosfilt` | 官方软件文档 | 无独立出版年；2026-11-10访问，SOS及状态接口 | `scipy_sosfilt` |
| R3 | SciPy, `ShortTimeFFT` | 官方软件文档 | 无独立出版年；2026-11-10访问，STFT及标度 | `scipy_shorttimefft` |
| R4 | SciPy, `welch` | 官方软件文档 | 无独立出版年；2026-11-10访问，分段平均PSD | `scipy_welch` |
| R5 | Välimäki & Reiss, *All About Audio Equalization: Solutions and Frontiers* | 基础综述 | 2016，EQ结构及音调控制背景 | `valimaki2016allabout` |
| R6 | Schlecht, Sinjanakhom & Välimäki, *Multi-shelf graphic equalizer* | 近期研究 | 2025卷期；2024在线，多shelf及图示均衡设计 | `schlecht2025multishelf` |
| R7 | Bruschi et al., *Real-Time Implementation of a Linear-Phase Octave Graphic Equalizer* | 近期研究 | 2024，实时IFIR方案与评价 | `bruschi2024realtime` |

软件网页访问日期不等同于研究出版年；SciPy线上页面本次显示 v1.18.0，本机合成实验记录为1.18.1。基础资料与近期研究分别保留真实年份。R6、R7提供相关工作与设计讨论，不能把其系统、延迟、动态范围或听感结果当成本项目结果。所有项目数值仍须追溯实际配置和输出。
