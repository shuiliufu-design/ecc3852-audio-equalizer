# 已核实文献及证据边界

核查日期：**2026-11-10（Asia/Kuala_Lumpur）**。本文是本次报告准备的检索与核实记录，不是系统综述，也不声称穷尽最新文献。只收录实际打开过的一手来源；本轮不收录仅核实摘要的2026年候选论文。

稳定编号与 [报告草稿](../report/draft.md) 的 `[R1]`–`[R7]` 对应，机器可读条目见 [references.bib](references.bib)。以下出版信息和方法背景不能替代项目自己的配置、代码、运行结果与试听证据。

## 核实口径

- **基础技术资料**：R1；**软件文档**：R2–R4；**基础综述**：R5；**近期研究**：R6–R7。
- “已读全文”表示本次已打开原始全文并核对所引用的相关部分，不表示复现论文或逐项审计所有实验。
- SciPy本次在线页面标题显示 **v1.18.0 Manual**；项目合成运行记录为 **SciPy 1.18.1**。正文应分开记录，不能声称在线文档是本机锁定版本的完整快照。
- 软件网页未提供独立发表日期时不虚构年份；`urldate=2026-11-10`仅为访问日期。网页版权年、抓取时间和HTML更新时间均不替代研究出版年份。
- 论文中的结构、数据集与性能结论只适用于论文研究对象。本项目仍是手动三控制、因果IIR实现，当前只有合成验证。

## [R1] Audio EQ Cookbook

**引用信息**：W3C, *Audio EQ Cookbook*, Working Group Note, 8 June 2021. Editor: Raymond Toy. Adapted from *Audio-EQ-Cookbook.txt* by Robert Bristow-Johnson, with permission.

| 项目 | 核实记录 |
| --- | --- |
| 原始来源 | [固定2021版本](https://www.w3.org/TR/2021/NOTE-audio-eq-cookbook-20210608/)、[W3C当前入口](https://www.w3.org/TR/audio-eq-cookbook/) |
| Bib键 | `w3c2021cookbook` |
| 访问日期／层级 | 2026-11-10；已打开W3C全文，核对抬头、编辑、改编说明及§2公式 |
| 文献属性 | **Working Group Note**，不是W3C Recommendation；原作者贡献与网页编辑分开记录 |
| 支持内容 | 二阶传递函数、a₀归一化、peaking与low/high-shelf系数；增益、Q和shelf slope的定义 |
| 不能支持 | 本项目代码正确性、已测稳定性、已实现实时滑块或特定歌曲的最优参数 |
| 草稿对应 | §4.1拓扑、§4.2系数；需同时对照项目 `equalizer.py` 与保存的SOS |

## [R2] scipy.signal.sosfilt

**引用信息**：The SciPy community, “scipy.signal.sosfilt,” *SciPy Manual*, online documentation, accessed 10 November 2026. 本次页面显示v1.18.0。

| 项目 | 核实记录 |
| --- | --- |
| 原始来源 | [SciPy官方API文档](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.sosfilt.html) |
| Bib键 | `scipy_sosfilt` |
| 访问日期／层级 | 2026-11-10；已打开API全文，核对参数、返回值和实现说明 |
| 支持内容 | 级联SOS、每行6系数、处理轴、零初态与`zi/zf`状态接口；direct-form II transposed实现说明 |
| 不能支持 | 本项目分块一致性、极点位置、参数切换无爆音、音频设备延迟或实际播放稳定性 |
| 草稿对应 | §4.3因果处理与状态保持；项目实测与测试结果另引`outputs/validation.log`等证据 |

## [R3] scipy.signal.ShortTimeFFT

**引用信息**：The SciPy community, “scipy.signal.ShortTimeFFT,” *SciPy Manual*, online documentation, accessed 10 November 2026. 本次页面显示v1.18.0。

| 项目 | 核实记录 |
| --- | --- |
| 原始来源 | [SciPy官方API文档](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.ShortTimeFFT.html) |
| Bib键 | `scipy_shorttimefft` |
| 访问日期／层级 | 2026-11-10；已打开API全文，核对窗、hop、窗中心时间、FFT长度及标度 |
| 支持内容 | 滑窗STFT、步长与帧时间、频率网格间隔`fs/mfft`、PSD缩放和补零FFT设置 |
| 不能支持 | 本项目30ms窗、约75%重叠、声道功率平均或−40dB阈值的普遍最优性；具体完整窗选取和时间原点必须对照项目代码 |
| 草稿对应 | §2.3时频表示；§2.4的两个事件定义属于项目定义，不能归为API规定 |

## [R4] scipy.signal.welch

**引用信息**：The SciPy community, “scipy.signal.welch,” *SciPy Manual*, online documentation, accessed 10 November 2026. 本次页面显示v1.18.0。

| 项目 | 核实记录 |
| --- | --- |
| 原始来源 | [SciPy官方API文档](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html) |
| Bib键 | `scipy_welch` |
| 访问日期／层级 | 2026-11-10；已打开API全文，核对分段平均、窗、重叠、去趋势和单位 |
| 支持内容 | 重叠段的修正周期图平均PSD；`noverlap=None`默认半段；`detrend=False`不去趋势；`density`对应输入单位平方/Hz |
| 不能支持 | `nperseg=8192`、本项目频段边界或对某歌曲的最佳参数；功率比例不是声学能量或知觉响度 |
| 草稿对应 | §2.5全段PSD和频段功率比例；输入为FS时PSD单位相应为FS²/Hz |

## [R5] All About Audio Equalization: Solutions and Frontiers

**引用信息**：V. Välimäki and J. D. Reiss, “All About Audio Equalization: Solutions and Frontiers,” *Applied Sciences*, vol. 6, no. 5, article 129, 2016. DOI: **10.3390/app6050129**。出版社发布日期：2016-05-06。

| 项目 | 核实记录 |
| --- | --- |
| 原始来源 | [出版社公开全文](https://www.mdpi.com/2076-3417/6/5/129)、[DOI](https://doi.org/10.3390/app6050129) |
| Bib键 | `valimaki2016allabout` |
| 访问日期／层级 | 2026-11-10；已打开全文，核对作者、出版信息及§6.1 Tone Control |
| 支持内容 | 传统低高频shelf与mid peaking/notch音调控制；§6.1给出典型±12dB范围、低频100–300Hz和高频3–10kHz控制频率背景 |
| 不能支持 | 它是**2016基础综述**，不能包装为2026最新研究；不能证明200/1000/4000Hz适合尚未选择的歌曲 |
| 草稿对应 | §1设计背景；§4.1初始参数的背景依据，最终音乐参数须结合本项目分析解释 |

## [R6] Multi-shelf graphic equalizer

**引用信息**：S. J. Schlecht, T. Sinjanakhom, and V. Välimäki, “Multi-shelf graphic equalizer,” *Signal Processing*, vol. 226, article 109630, January **2025**. DOI: **10.1016/j.sigpro.2024.109630**。

| 项目 | 核实记录 |
| --- | --- |
| 原始来源 | [作者机构元数据](https://research.aalto.fi/en/publications/multi-shelf-graphic-equalizer/)、[作者机构公开正式全文](https://acris.aalto.fi/ws/portalfiles/portal/154638738/1-s2.0-S0165168424002494-main.pdf)、[DOI](https://doi.org/10.1016/j.sigpro.2024.109630) |
| Bib键 | `schlecht2025multishelf` |
| 访问日期／层级 | 2026-11-10；已打开机构元数据及正式全文，核对作者、卷期、文章号和相关设计讨论 |
| 年份说明 | 正式卷期为**2025年1月**；全文注明首次在线**2024-07-26**。DOI含2024不改变正式卷期年份 |
| 支持内容 | 近期多shelf级联图示均衡方案；可讨论目标增益与实际总响应、shelf结构的设计扩展 |
| 不能支持 | 本项目未实现该论文的全shelf优化或阶数切换；论文的动态范围、逼近精度不能成为本项目性能数据 |
| 草稿对应 | §1近期相关工作、§8限制与未来方向；当前三段shelf–peak–shelf设计仍引用R1与自身实现 |

补充访问说明：ScienceDirect直接打开返回403，本次以作者机构提供的正式公开版本核实全文，没有把搜索摘要当作全文。

## [R7] Real-Time Implementation of a Linear-Phase Octave Graphic Equalizer

**引用信息**：V. Bruschi, S. Cecchi, A. Nicolini, and V. Välimäki, “Real-Time Implementation of a Linear-Phase Octave Graphic Equalizer,” in *Proceedings of the 27th International Conference on Digital Audio Effects (DAFx24)*, Guildford, UK: University of Surrey, 2024, pp. **459–466**, paper 69. Editors: E. De Sena and J. Mannall。机构元数据出版日期：2024-09-03；会议时间：2024-09-03至09-07。

| 项目 | 核实记录 |
| --- | --- |
| 原始来源 | [会议公开全文](https://www.dafx.de/paper-archive/2024/papers/DAFx24_paper_69.pdf)、[作者机构元数据](https://research.aalto.fi/en/publications/real-time-implementation-of-a-linear-phase-octave-graphic-equaliz/) |
| Bib键 | `bruschi2024realtime` |
| 访问日期／层级 | 2026-11-10；已打开会议全文和机构元数据，核对首页作者顺序、会议与页码、§3实时实现及评价概况 |
| DOI状态 | 本次未核实到DOI，使用会议稳定URL，不能编造DOI |
| 支持内容 | 实时线性相位IFIR图示均衡的相关研究；讨论相位、实现和延迟取舍，以及独立进行实际运行与主观评价的必要性 |
| 不能支持 | 本项目是三段因果IIR，不是该论文IFIR十频段方案；不能借用论文的延迟、CPU、误差、试听偏好或实时成功结论 |
| 草稿对应 | §1相关工作、§4.1结构取舍、§7实时Challenge；项目设备及试听结果仍为待补 |

## 本次检索记录与后续使用

2026-11-10使用的检索关键词包括 `audio equalization parametric IIR equalizer 2024 paper real-time`、`audio equalizer IIR filter 2023 2025 differentiable parametric equalization paper`、`Multi-shelf graphic equalizer Aalto 2025`、`Real-time implementation of a linear-phase octave graphic equalizer DOI pages`。优先查看W3C、SciPy、出版社、DAFx会议与作者机构页面。

本轮近期研究选择2024、2025两项直接相关工作，未根据网页抓取时间判断“新旧”。后续若正式音乐实验需要知觉评价、实时参数平滑或特定设计改进的文献，应按实际采用的方法继续定向检索；添加前仍核实原文，并注明核实层级。引用格式待课程规定确认，现有编号及BibTeX仅用于一致交接。
