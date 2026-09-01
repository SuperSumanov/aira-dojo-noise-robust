# 发布合规清单(2026-08-08 首版,实证支撑)

> **2026-09-02 状态覆盖：历史初版，不是 v11 最终 release clearance。** 本文件的污染扫描只覆盖 v6 的
> 9,433 cards，且当时清单的 22 个赛事规则只精读 4 个；v11 已有 16,012 cards / 25 tasks。
> 2026-09-02 的 25/25 官方规则页初筛见 `KAGGLE_RULES_TRIAGE_V11_20260902.md`，仍不是法律放行。Qwen 输出条款与最终数据许可兼容性、
> 逐赛事规则、全量 credential/PII/competition-data scan、`licenses.json` 和机构/法律 review 均未闭合。
> 本文件末尾“没有直接竞品”的 novelty 结论也已被 ML-Agent、OpenMLE 与 mle-traj supersede，不得引用。
> 当前数据卡入口：`phase1/DATACARD_DECISION_CORPUS_DRAFT_20260902.md`。

两份独立 license 调研 + 集群实测。**历史判断“可发布”已由上方 2026-09-02 状态覆盖；当前结论是尚未完成
v11 release clearance。**

## 已完成(实测,非判断)

### 1. Competition Data 逐字污染:已量化并脱敏

Kaggle Standard Rules §7.B 禁止转发 Competition Data。我们每张卡存 800 字符执行输出,
理论上可能夹带真实数据行。**对全部 9,433 张卡 × 20 个任务的原始 prepared 数据做逐字比对:**

| | 结果 |
|---|---|
| 含逐字竞赛数据的卡 | **19 张(0.20%)**,共 34 个跨度 |
| chaii-hindi-and-tamil-qa | 18 张 / 31 跨度 / 最长 80 字符(印地语维基段落片段 + gold answer) |
| google-quest-challenge | 1 张 / 3 跨度 / 最长 103 字符(一条完整问题原文) |
| 其余 18 个已扫任务 | **0** |
| 未扫(集群无 prepared 数据) | dog-breed(146 张)、histopathologic(99 张)—— 均为图像任务,发布前需补扫 |

**方法学要点(第一版扫描的教训,必须写进数据集卡片)**:朴素子串匹配被假阳性主导——
49 个空格、40 个等号都能"命中源数据"。`scrub_stdout.py` 因此加了熵过滤(跨度需
≥12 种不同字符、去空白后长度 ≥60% 阈值、含字母数字)。加过滤后污染率从抽样的 0.7%
降到全量的 0.20%,证明大部分"命中"是格式而非数据。

**脱敏产物**:`phase1/cards_v6_scrubbed.jsonl`。逐项验证:9,433→9,433 张、id 顺序一致、
**仅 19 张的 stdout_tail 改变、其余字段逐字节未动**、19 张全部含 `[REDACTED:competition-data]`
标记。周围的指标行/traceback 完整保留(那是这个字段的科学价值所在)。

### 2. insults 任务:语料中不存在,无需剔除

`detecting-insults-in-social-commentary` 是 2012 招聘赛,规则明文禁止公开分享代码
(连论坛都不行)。**实测确认它不在语料里**(学长早前报的"永久规则封"意味着它从未成功采集),
所以这条风险自动消解,不需要做剔除动作。

## 待办(按优先级)

1. **补扫 dog-breed / histopathologic**(245 张卡):需要先把这两个任务的 prepared 数据
   拉到集群。在此之前发布说明里必须标注"2 个图像任务未做逐字比对",不能声称全量已验。
2. **Qwen 批次定性 —— 已拍板(2026-08-08,用户决定)**:Qwen 批次保留、进公开发布,
   发布声明限定学术研究用途(non-commercial academic research only 附加条款,针对
   qwen3-coder-flash 生成的卡片;DashScope Article 4.48(d)(v) 竞品训练限制随卡片
   provenance 传递给下游使用者)。DeepSeek 卡片不受此限(§4.2(3) 明文授权)。
3. **逐赛事规则复核**:22 个赛事只精读了 4 个,其余按 API license 字段和模板年代推断。
   2012-2013 年的老赛事(mlsp-2013-birds、whale-2013、random-acts-of-pizza)最可能非标准,
   发布前必须逐个读规则页。
4. **Kaggle 论坛发帖**:2019 年后模板的赛事,§8.B 要求代码分享须发在该赛事的论坛/kernels。
   发个指向数据集的说明帖即可,顺便是 outreach。

## 许可方案(已定)

| 产物 | 许可 | 依据 |
|---|---|---|
| 数据集(生成代码 + 分数 + 树结构) | **apache-2.0** 或 cc-by-4.0 | Kaggle §8.B 要求 OSI 认可且**不限制商用** → **不能用 NC** |
| 我们改过的 aira-dojo fork | **CC BY-NC 4.0** + Meta 署名 + 注明修改 | 上游即 CC BY-NC 4.0,是 Adapted Material |
| Kaggle 竞赛数据 | **零字节**,附 `prepare.py` 走 Kaggle API | MLE-bench / MLE-Dojo 标准做法 |

**必须照抄的两句**:MLE-bench 的许可切割句("This license applies to the code in this
repository, but not the external datasets and files...");jupyter-agent-dataset 的
上游 ToS 免责段。另附 `licenses.json`(赛事 slug → 规则 URL),抄 MLE-Dojo。

数据集卡片必须声明:不含 Kaggle 竞赛数据;用户须遵守 Kaggle ToS 及各赛事规则;
代码由 DeepSeek(及 Qwen)生成、使用者应遵守其条款;署名 aira-dojo(CC BY-NC 4.0, Meta)
与 MLE-bench(MIT, OpenAI);AI 生成内容披露(DeepSeek §8.1)。NeurIPS 还需
Croissant + Responsible AI 元数据。

## 新颖性（历史段，已被直接竞品 supersede，不得引用）

MLE-bench 排行榜**没有任何一个团队公开过 agent 生成的解代码——一个都没有**。
AIDE 的内部表示本就是一棵解树、AIRA-dojo 同理,全都只放框架。HuggingFace 上不存在
MLE/Kaggle 的 agent 轨迹数据集(只有 SWE 领域的)。唯一先例是 `q-hwang/MLAgentBench_logs`
——**无 LICENSE 文件、1 star**。即这个领域一直有这个东西、从没人正经发布过。
