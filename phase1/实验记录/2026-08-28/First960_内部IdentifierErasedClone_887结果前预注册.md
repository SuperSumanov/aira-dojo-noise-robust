# First-960 内部 identifier-erased fuzzy clone：887 快照结果前预注册

冻结时间：2026-08-28T04:31:13Z。状态：`RESULT_UNREAD_PREREGISTERED`。

## 问题与动机

当前主线是 Decision Corpus + Predictor Benchmark + Audit Protocol。本实验只回答 benchmark-integrity
问题：在 outcome-blind first-960 当前前缀内部，即使删除非关键字 identifier、数值和字符串差异，
高相似代码是否仍局限于同一 physical run。

现有证据还留有一个明确缺口：366-run 内部 fuzzy-clone 审计保留 identifier；404-run 的
identifier-erased 审计比较的是历史 critic-train 与 future prefix，而不是 future prefix 内不同 runs。
本项填补二者交叉处，不训练模型，不读取结果标签，也不把代码去重算法包装成方法 novelty。

## 固定人口与输入

- snapshot：`887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`；
- intake registry SHA-256：`37e41460c85661fd9afc6f8789a065088a9da88dde027b955ff4bc366d5bbcd8`；
- provisional runs SHA-256：`510d81820d7825fc6baa6db562b2371e50eb7d71d04cb1cc0bd17d095d6cdbca`；
- accumulator summary SHA-256：`2f28b5b53cca5d6ea5ebf16f746a70f9c1de0e3197487a6ed78d41b4cb611302`；
- 已知结构量：435 runs、11,906 endpoints、34 tasks，closure=false。

只允许读取 snapshot-bound `eligible_blind_manifest.jsonl`、intake registry、provisional runs 和
accumulator summary。禁止读取 label/outcome vault、prediction 文件或数值、accuracy/effect/search utility、
raw senior archives；输出不得包含 task/run/card/code identity。

## 固定表示、阈值与关系

表示为 `python_token_identifier_erased_v1`：Python tokenizer 删除 comment/layout；保留关键字与 operator；
其他 NAME→`<IDENT>`、NUMBER→`<NUMBER>`、STRING→`<STRING>`。之后取 token 5-gram set，
BLAKE2b-128，至少 20 个 distinct shingles。

Primary 为 exact Jaccard≥`17/20=0.85`；`19/20=0.95` 只作更严格 sensitivity，不能 rescue primary。
不按 task/run 预过滤。每条边按互斥顺序归为 sibling、parent-child、same-run-other、
cross-run-same-task、cross-run-cross-task。

## 结果前门与解释顺序

公共完整性门固定为：fingerprint coverage≥0.99；cross-run affected endpoint fraction≤0.01；
cross-task fraction≤0.005；无 size≥10 且跨≥3 tasks 的 component；384-document prefix join 与
brute force 完全一致。

解释严格按以下顺序：

1. `STRICT_LINEAGE_LOCAL_PASS`：公共门全部通过，且 primary cross-run pair count 恰为 0；
2. `LOW_CROSS_RUN_ONLY`：公共门通过但 cross-run pair 非 0，只允许说低于容忍阈值；
3. `INTEGRITY_GATE_FAIL`：任一门失败，不支持更强完整性主张。

已知先验必须披露：366-run lexical 内部结果和 404-run historical→future identifier-erased 结果都为零
cross-run link，因此本项并非无方向先验；但在冻结本协议前，没有读取 887 快照的内部 identifier-erased
相似度、candidate、edge、component 或 gate 结果。

## 控制、资源和主张边界

控制包括 alpha-renaming+literal-change 正控、结构无关负控、producer A/B、独立且不 import producer 的
verifier A/B，以及固定 384 documents brute force。所有随机性关闭，整数阈值，CPU-only；每条正式命令
timeout 1,800 秒，虚拟内存上限 32 GiB。GPU/API/model-fit/base-update=`0/0/0/0`。

即使 `STRICT_LINEAGE_LOCAL_PASS`，也只证明固定 syntactic abstraction 下的 observed prefix；不证明 semantic
clone、预训练污染或其他 shortcut 不存在，不提供 predictor effect。identifier erasure 本身可能制造 false positive，
所以非零边也不能直接称数据泄漏。first-960+独立 closure 后必须原协议重跑。

机器协议：`phase1/prospective_identifier_erased_clone_887_protocol_v1.json`。
