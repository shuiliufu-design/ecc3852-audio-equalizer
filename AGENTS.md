# ECC3852 项目工作约定

- Final deliverables must be in English: source code (identifiers, comments and docstrings), application UI, authored runtime messages, figure labels/captions, submission README, final report and presentation/demo materials. Keep original proper names and source metadata accurate. Chinese is permitted for user conversations and internal coordination documents; follow this rule in every specialist chat.
- 技术路线为 Python。当前没有正式音乐；合成信号仅用于验证，不得写成歌曲实验结果。
- 恢复项目或交接任务时，先读 `PROJECT_PLAN.md` 和 `STATUS.md`。日常改动只读与任务有关的文件。
- 原始音乐保存在 `audio/original/`，保留原文件；裁剪、转换和均衡器输出另存，并记录来源、时间范围、采样率及声道。
- 均衡器采用可检查系数和频率响应的因果 IIR 实现。未来实时播放器复用该核心，并在音频块之间保留滤波状态。
- 分析须使用实际采样率、明确声道处理方式和时间原点；拒绝空数据、非有限数值及不合理参数。频段和窗长是可解释的设计选择。
- 图表、数值和报告结论必须来自实际运行。合成输出明确标记为 synthetic/demo；参数、单位、阈值、防削波处理及适用范围均需记录。
- 修改 DSP 逻辑后运行相关测试，记录实际命令和结果；不要用未运行的测试或试听替代验证。
- 报告对照保存的结果与配置；文献使用核实过的原始来源，不编造引用、实验结果、听感或评分规则。
- 作业要求来自先前对原 PDF 的提取；原 PDF 当前缺失，恢复后须再次核对。实时功能原文标为 Challenge，但未明确给出选做、加分或评分规则。
- 已有三个对话：主对话负责 DSP 与整合；报告对话负责 `report/` 与文献整理；界面对话负责播放器与界面。接口或共享配置的变动写入状态文件，避免同时改同一文件。
