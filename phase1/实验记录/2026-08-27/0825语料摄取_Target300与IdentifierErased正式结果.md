# 0825 语料摄取、Target-300 进度与 identifier-erased overlap 正式结果

## 1. 结果盲摄取

0825 的 12/12 个 source archives 已由 append-only intake 正式提交；transaction registry 从 86 增至 98。
最终 settle poll 为 `archives=246 ready=0 transactions=98 outcomes_read=false`，对应 immutable snapshot：

`ad0b624d636cb5e89f94d8887a7abe99f7b9ef6ce77bbde7da704b0275dedb0e`

provisional first-960 从 366 runs / 10,683 endpoints / 2,755 sibling pairs / 30 tasks 增至
404 / 11,310 / 2,884 / 31，逐项净增 `+38 / +627 / +129 / +1`。当前进度为
`404/960=0.42083333333333334`，尚差 556 runs，closure=false。

dominant structural-pair task share 从 `0.308529945553539` 降至 `0.2947295423023578`，变化
`-0.013800403251181204`（`-1.3800403251181204` percentage points）。这是结构平衡改善，但仍高于
预注册的 25% cap，故 balance gate 仍失败。

该批没有 `*.config_v2.jsonl` sidecar，不能据此确认 producer/config exact-stratum scaling，也不授权 GPU
重训。所有数字都是 outcome-blind 结构统计，不是 predictor accuracy、effect 或 search utility。

## 2. Target-300 identity cohort 进度

在同一 `LATEST` 连续 5 次、每次间隔 300 秒稳定后，固定 science commit
`ab59a011d945e4a96daf7dbbbc927a59027da077` 的 runner 正式完成。target-300 cohort 从
64 runs / 21 archives 增至 129 runs / 41 archives / 21 tasks；exact previous prefix survived=true，
remaining=171，boundary archive 尚不存在，closure=false。

独立 verifier 状态为 `PASS_COLLECTING_TRUTH_UNREAD`。label/outcome/score/raw archive payload 未打开，
`truth_support_computed=false`，replay 未授权。该 cohort 与 first-960 estimand 不同，不得混池；达到 300 也不会
自动授权 effect/replay。

公开结果包：`phase1/results/score_channel_target300_progress_ad0b_20260827_ab59a01/`。

## 3. Historical train ↔ future identifier-erased overlap

从公开 source commit `065d0b56fdc366d05faf723ef03938e7f7a913f2` 在同一 immutable snapshot 正式运行
结果前冻结的 identifier/literal-erased audit：历史侧 5,519 endpoints / 333 runs，前瞻侧
11,310 endpoints / 404 runs；两侧 fingerprint coverage 分别为 1.0 与 `0.999027409372237`。

固定表示为 Python tokenizer、删除 comments/layout、保留 hard keyword/operator、其他 NAME→`<IDENT>`、
number/string→固定 token，再作 token 5-shingle、BLAKE2b-128、minimum 20 distinct shingles。primary
Jaccard≥0.85 下完成 `5,923,921` 次 exact candidate checks，near-duplicate pairs=`0`；same-task/cross-task
=`0/0`，两侧 affected endpoints=`0/0`，components=`0`。strict Jaccard≥0.95 亦为 0。256×256 的
65,536-pair brute-force control 与 prefix join 完全一致，六个预注册 gate 全部通过。

producer/verifier A/B 均逐字节一致；focused/full=`29/1212 passed`，full 有 47 warnings；禁读路径/凭据命中
=`0/0`。另一个不修改 formal root 的独立 recheck 验证 24 个 manifest payload 和全部固定计数。

允许结论仅为：在结果前固定的 identifier/literal-erased syntactic 定义下，历史 v11 critic-train endpoints 与
404-run provisional future cohort 没有高相似链接。这加强了 benchmark 的时间外 syntactic-independence 证据。
它不证明 semantic clone 或预训练污染不存在，不提供 predictor effect；first-960 + independent closure 后必须原协议重跑。

公开结果包：
`phase1/results/historical_train_future_identifier_erased_overlap_ad0b_20260827_065d0b5/`。

## 4. 失败与修正记录

- formal-v1 因运行中 `LATEST` 从 8579 漂移到 ad0b 而 fail-closed；该目录没有 `COMPLETE`，不产生科学结果。
- 成功 formal 后一次人工 `sha256sum -c` 在错误工作目录运行，因清单使用相对路径而报告文件不存在；没有修改
  formal root。随后由独立 recheck 在正确根目录验证 24 个 payload，成功结果不依赖该错误诊断。
- 不能把 0-links 当作 critic 方法正结果；当前最强方法正信号仍是学长的 exploratory 0.6B→8B scaling，必须等待
  exact-stratum sidecar、train-run dev checkpoint 和全新 frozen cohort 才能确认。
