# Global value → local decision：趋势复核与负控修正

日期：2026-08-23。状态：`POST_HOC_POSITIVE_HYPOTHESIS_REVISED_PROTOCOL_EFFECT_BLOCKED`。本记录只复核学长已经公开的
0820 outcome 表并审计 0DU 候选四臂；没有读取新 frozen/prospective outcome、没有训练模型、没有提交 GPU/API。
来源绑定 `dojo-reproduce@ac008af8b907d319b694f26b0ba9cf4053b3bf69`，outcome 文档 Git blob 为
`b41ab437395df034104624afbb678a1c0f987343`。

## 1. 不能再写“global scaling 完全不迁移”

对固定模型顺序 0.6B/1.7B/4B/8B/14B 做事后 Spearman 与全部 5! 排列的单侧 order audit：

| 曲线 | rho | 至少同样有序 / 全排列 | 0.6B→14B | 每 log10(B) OLS 斜率 |
| --- | ---: | ---: | ---: | ---: |
| value seed 6 Final | 0.9 | 5/120 | +7.69 pp | +6.3195 pp |
| value seed 7 Final | 0.9746794344808964 | 2/120 | +6.55 pp | +4.2593 pp |
| value 两-seed mean Final | 1.0 | 1/120 | +7.12 pp | +5.2913 pp |
| value checkpoint→filtered local，seed 7 | 0.9746794344808964 | 2/120 | +4.38 pp | +3.4339 pp |

上述 rho 与排列命中数另由远端 SciPy `spearmanr` 独立重算，逐项得到
`0.9/5`、`0.9746794344808964/2`、`1.0/1`、`0.9746794344808964/2`，状态
`INDEPENDENT_SCIPY_SCALING_SHAPE_PASS`。

相反，直接 local decision 训练的 0.6B/1.7B/4B/8B Best 与 Final rho 均为 0，至少同样有序为 13/24；
端点分别是 -0.73/-1.04 pp。故当前最积极且与表一致的假设不是“global 完全不能迁移”，而是：

> global value supervision 形成了随容量改善、且能部分 zero-shot 迁移到 local decision 的表示；naive local-only
> optimization 在小而依赖严重的 sibling 数据上过拟合，可能擦除该 scaling。短而受控的 local calibration 才是
> 应确认的部署桥。

这些排列分数只是五点曲线有序度描述，不是 pair-iid 或 confirmatory p-value。value 只有两个 seed、local transfer
只有 seed 7，outer test 被周期性查看，checkpoint 也 test-touched，且 pair 共享 endpoint；所以本节不能进入摘要为
“已确认 scaling/transfer”。

## 2. 0DU 四臂存在的假正风险

原候选把 staged 的一次 global+一次 local 序列化 token 总量作为共同预算，local-only 则循环 local rows 填满预算。
旧日志已经显示 local-only 到第二 epoch 时 eval loss 升至 0.76--0.89；新 split 的 local rows 又明显少于 global rows。
因此若 staged 胜 local-repeat，至少有两种解释：

1. true global quality labels 提供了可迁移表示；
2. 用更多 unique code/pairs 替代重复 local updates，只是避免 local overtraining。

原 interleaved arm 只能判断顺序，不能区分这两项。由于通用 staged/multitask 方法 novelty 已被 0DU 关闭，花预算争
schedule-specific H2 的价值低于排除这个假正。

## 3. 修订候选五臂（仍未授权）

在 exact new split、producer provenance、Cards LFS、G0 与预算通过后，候选改为：

1. `L1`：local-only 恰一遍，达到最后一条 local row 即停；它是过拟合诊断，不作 compute-matched headline。
2. `Lbudget`：local-only deterministic cycle 到共同 optimizer-token budget；对应原 A。
3. `Gbudget`：global-only deterministic cycle 到共同 budget；对应原 B。
4. `G→L`：每个真实 global row 一次，再每个 local row 一次；共同 budget 由它定义，对应原 C。
5. `Ghash→L`：与 `G→L` 使用逐字节相同 endpoint、row order、token、step 和 local 阶段；但 global orientation
   改为每个 endpoint 的 `sha256(20260823|card_id)` 标量全序。它保持 shared-endpoint comparison 的传递一致性，却与
   quality label 无关，用来区分“真实 global labels”与“更多 unique code/optimizer steps”。

原 interleaved arm 从首轮删除；若未来仍要研究 schedule，必须在主机制过门后用独立 frozen cohort 和新预算，不得
在同一 test 上结果后追加。

## 4. 分层裁决建议

Primary 仍是一次性 local frozen sibling accuracy，task-cluster CI 为主，parent/run 为敏感性；全部 checkpoint hash
先锁定，随后 evaluator 只开一次 frozen test。

1. **部署收益**：`G→L − Lbudget >= 0.02`、task-CI 下界>0、三个 seed 符号全正；同时 `G→L − Gbudget`
   task-CI 下界>0，且 `G→L` 超过同池 TF-IDF、task-CI 下界>0。
2. **真实 label 信息**：`G→L − Ghash→L` task-CI 下界>0；否则不得写 global quality supervision 可迁移，只能写
   unique-data/optimization regularization。
3. **排除 local-repeat 假正**：若 `L1 > Lbudget`，则必须再要求 `G→L − L1` task-CI 下界>0，才能写 global
   supervision 在避免过拟合之外仍有增益。若 `G→L≈L1>Lbudget`，正结论降为“预算分配避免 local overtraining”。
4. Draft/Improve、task macro、LOTO、seed dispersion、单 task 贡献≤35% 和 leave-one-task-out 不翻转仍保留。

上述 arm 数、hash seed、比较层级和降级措辞必须在任何新 checkpoint 训练前机器冻结。具体模型规模、总 token 与
GPU·时仍由 G0 后另报，当前仍为 0 production runs / 0 GPU·h；本记录不授权提交。

五臂语义已写入 `phase1/global_local_calibration_candidate_protocol_v2.json`，SHA-256 为
`3e0785a13f9d9fc3638a222e78fd74010757b1201249ebd0ad7a5597c224a2e9`；5 个合同测试通过。该 JSON 将具体
checkpoint、optimizer-token budget 与 GPU·时保持为 null，状态为
`ARMS_FROZEN_IDENTITY_G0_BUDGET_EFFECT_BLOCKED`，因此仍不能执行 effect stage。

## 5. hash control 可实现性烟测

学长 `ac008af...` 的两个历史 pair LFS 对象先做高置信 credential-shape scan，命中 0；schema 只打印字段名、类型、
行数与 split count，不打印 row value。global 文件共 16,204 rows（train/test=14,206/1,998），39 tasks；decision
文件共 7,644 rows（6,484/1,160）。两者都有字符串 `better/worse` endpoint，故 endpoint 全序 control 不依赖
Cards/code 或 grade magnitude 即可构造。

对历史 global train 单独物化时，producer×2 与非导入式 verifier×2 逐字节一致：train SHA-256=
`d9163bbcde70d8fe1f6f2ead9db266eca7ced932682cdaed9d3a9ece6fa43010`，14,206 rows / 39 tasks，overlay
v2 SHA-256=`55ced63f9ea41adcd57c2067cb70fcfa3d430ba7171d89ae6f697e79396a2849`。overlay 中
`gap_raw/agrees_with_quality/steps_to_best/subtree_sizes` 命中 0，grade-derived commitment 也是 0；15 个
protocol/overlay 聚焦测试通过。交换全部真实 orientation、改 gap 或新增 outcome 注释时，v2 overlay 逐字节不变。

最终加固版未提交源码覆盖包（SHA-256=`6583c993ca2ebc99a2e834f2596c18c7194ea0fbf12f1280e5bedb21e5b5f152`）
覆到 `74ffb87...` 的远端隔离克隆后，联合 truth-gate 聚焦测试 25/25，完整 `phase1/tests` 783/783；33 个 warning
均为既有 sklearn 弃用警告。此前两个 wrapper 分别在“基线对象未 fetch”与“系统 Python 无 pytest”处、测试启动前
失败，已写入回执，不能藏掉或误计作 code failure。

提交前人工审计还捕获一次必须记录的修正：首版 overlay 写 `source_row_sha256`，虽不暴露源值且没有进入任何训练，
但该承诺会随 better/worse、gap 等 outcome 元数据变化，不能叫严格 grade-independent。首版 overlay SHA
`3f80cd031e8532cf955ab90d42c9723461b8ee07fcf8b3f3a5527ea68e786cf0` 已在提交前撤回。v2 仅承诺
`row_number/task/train/unordered_endpoints`，将 task 纳入 unordered-pair hash，并对 endpoint 跨 task 复用 fail closed。

这仍只是旧 test-touched schema smoke：它不解除 exact identity、新 split、Cards、G0 或预算阻断，也没有模型 accuracy。
正式 effect 只能在未来 train-only 文件上重新物化并绑定新 SHA，不能复用本 smoke overlay。

## 6. Related-work 边界：不能主张 staged transfer 方法 novelty

检索到的原始工作已经覆盖三类邻近主张：White et al. 的 NeurIPS 2021 predictor suite 系统比较初始化/查询成本并
研究 predictor 组合（https://arxiv.org/abs/2104.01177）；Wistuba & Pedapati 的 ICML 2020 工作把跨数据集信息用于
pairwise learning-curve ranking（https://proceedings.mlr.press/v119/wistuba20a.html）；可迁移通用 NAS predictor 与
expressive-space surrogate 也分别已有明确工作（https://arxiv.org/abs/2302.10835，
https://arxiv.org/abs/2504.12971）。因此“global 预训练后 local 校准”本身不是可守的方法贡献。

本五臂实验若通过，允许的贡献边界只有 D&B 机制证据：在同一 MLE-agent 数据资产上，容量 scaling 何时出现、为何在
physical sibling 决策上消失，以及增益来自真实 quality label、更多 unique code，还是避免 local-repeat 过拟合。
若未同时越过 `Ghash→L` 与 `L1` 负控，则连“quality supervision transfer”也不能写。论文容器仍必须依靠 corpus、
run-clean contract、cost/noise/leakage audit 与真实搜索决策协议，而不是把标准 transfer recipe 改名为新算法。
