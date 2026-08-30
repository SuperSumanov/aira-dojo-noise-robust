# VCCD Target-522 Stage-A 自动执行链冻结（2026-08-30）

## 裁决

当前状态是 **`STAGE_A_EXECUTION_CHAIN_FROZEN_BEFORE_TARGET522_CANDIDATE`**。这不是 VCCD 有效的正结果；它只把未来
Target-522 到达后的结构选择变成自动、唯一、可复验的动作，消除人工选择 snapshot、临时换预算和只跑一次 producer 的自由度。

科学协议 `vertex_cost_contrast_target522_effect_v1.json` 已在 commit
`63a5b38bcdb6f057c6ea86309cd4ae7ca82dcce7` 公开。fresh detached post-push 根为
`/research/d7/spc/yzyang4/vccd-target522-protocol-postpush-20260830-r1`，结果为：

- changed blobs=`7`，credential pattern hits=`0`；
- protocol bindings=`15`，协议 SHA-256=`b3df170ebb4ae097549cb0225142e94aebfa481aea6c79815f1be2af687d9e1d`；
- focused=`25 passed in 2.61s`；full phase1=`1705 passed, 48 warnings in 97.70s`；
- worktree clean，prospective values 未读，GPU/付费 API/model fit/base update=`0/0/0/0`。

机器回执为 `vertex_cost_contrast_target522_protocol_postpush_receipt_20260830.json`。

## 新冻结执行合同

执行合同 `vertex_cost_contrast_target522_execution_v1.json` 的最终 SHA-256 为
`66937a1f82ff4d427b382f5bb2ce15481f40d2a3fd7777c84d6596a2cef15856`，绑定：

- Stage-A producer=`freeze_vertex_cost_contrast_target522_selection.py`；
- 独立 verifier=`verify_vertex_cost_contrast_target522_selection.py`，不导入 producer；
- formal runner=`scripts/run_vertex_cost_contrast_target522_selection_formal_20260830.sh`；
- six-hour resumable monitor=`scripts/monitor_vertex_cost_contrast_target522_selection_formal_20260830.sh`；
- runner contract tests、上一科学协议的 fresh post-push 回执与 related-work addendum。

候选前的追加查重发现最接近工作为 ICML 2025 *Comparing Few to Rank Many*：它已经从任意 K-subset 购买一次人类完整排序，
并以 Plackett-Luce D-optimal design 选择子集。NeurIPS 2024 *Active preference learning for ordering items in- and out-of-sample*
进一步覆盖 contextual logistic preference、主动 pair 采样与新 item 泛化；NeurIPS 2021 也已给出 multi-wise full-ranking feedback 的
主动排序样本复杂度。因此执行合同追加绑定 `vertex_cost_contrast_target522_related_work_addendum_v1.json`（SHA-256=
`4176772f5287d4bd77957a151973578489acaa4bdfbeb3171ca43ab3c222a816`）。我们的差异只能是：每执行一个 MLE endpoint
才获得一个标量 grade，偏好仅在既有 parent clique 内确定性派生；可行集跨任务/run 且受搜索树约束；目标是在不重叠 physical
runs 上泛化 critic，并完整核算依赖 clique rank、task/run cluster、noise/leakage/query cost。不得再声称 D-opt、K-way active
ranking、contextual active preference 或 feature-based preference design 首创，也不得在反馈 oracle 不匹配时声称优于这些方法。

本地 focused（工程核心 + Stage-A producer/verifier + runner contract）为 `33 passed in 1.34s`。远端部署前仍必须对最终
exact patch 跑完整 `phase1/tests`；只有公开 commit 的 fresh post-push 也通过，monitor 才能启动。

## 唯一激活路径

1. monitor 部署时必须证明固定 selection 根中 `candidate.tsv/READY/COMPLETE/FAILED_RC/CONTINUITY_GAP/TIMEOUT_RC`
   全部不存在；在 `COMPLETE` 前只检查 marker，不读 candidate/profile/code/value。
2. `COMPLETE` 出现后，重验固定 selection 的 `SHA256SUMS`，不能传入候选路径或 snapshot 参数。
3. 在公开 exact commit 的 fresh detached worktree 中先跑 focused 和 full tests。
4. producer A/B 独立写 public 与 mode-0600 private selection；有 private 时必须逐字节相同，无 private 时两次都必须不存在。
5. verifier A/B 从同一 frozen inputs 独立重构 run split、uniform/VCCD order 与 yield witness constraints，输出逐字节一致。
6. 对 producer/verifier 做 file+network trace；禁止 external senior data、label/outcome vault、prediction、raw archive、`.env`
   和 network 访问。末尾再次重验 selection manifest，才写不可变 `COMPLETE`。

## 13 项预检与资源矩阵

方向、问题、唯一 selection、source hashes、complete-run population、Stage-A estimand、三臂六 checkpoint、endpoint cost、A/B
复现、focused/full tests、run/public/private integrity、trace security、resources/failure 均已写入 runner；monitor 另有 13 项等待与
激活预检。资源固定为：

| 组件 | 次数 | 资源 | 上限 |
|---|---:|---|---:|
| 六小时 marker monitor | 721 polls | 单 CPU metadata only | 30 秒间隔 |
| Stage-A producer | 2 | 单 CPU | 每次 yield solver 至多 900 秒 |
| 独立 verifier | 2 | 单 CPU | 每次 timeout 1800 秒 |
| critic/model fit | 0 | — | first-960 closure 前禁止 |
| GPU / 付费 API / base update | 0 / 0 / 0 | — | 禁止 |

预期 Stage A 总墙钟 `10--70` 分钟，90 分钟 fail-closed。该矩阵不包含未来效果阶段；后者仍固定为至多 7 个 CPU fits，且
first-960 + accrual-closure 不存在时绝不执行。

## 冻结时结构状态

`2026-08-30T03:03:57Z` 的安全只读状态：LATEST=`98f2cba9ca4b3ac6404305da2528a4e8c391ba795f74438a5e4cca1a162765fa`，
snapshot dirs=`117`，structural physical runs=`468`；Target-522 candidate/READY/COMPLETE/FAILED 均不存在，config-v2 filename
count=`0`，prospective values 未读。Target-300 的旧支持 cohort 已结构性结束，但不改变 VCCD 的 first-960 closure 效果门。

## 解释边界

- Stage-A `READY` 只表示支持、run split 和三臂 endpoint selections 可复验冻结，不表示准确率、calibration 或 search utility 改善。
- 若 support gate 失败，按预注册输出 limited-support 并停止；不得减门或换 split。
- 若 yield solver 未给出 witness，只保留协议允许的 uniform+VCCD 结构包；不得放宽 yield floors。
- 任一异常都保留证据并停止，不用 OpenRouter、历史 single-fold、旧 HCE/多保真/Probe/score-channel/K≥1 路线救回。
