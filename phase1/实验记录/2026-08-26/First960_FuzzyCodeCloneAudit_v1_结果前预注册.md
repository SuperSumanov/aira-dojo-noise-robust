# First-960 fuzzy code-clone audit v1：结果前预注册

冻结时间：2026-08-26T15:24:35+08:00。冻结时尚未在真实 prospective code 上计算候选 pair、Jaccard、edge、
component 或任何 gate；仅运行 synthetic/adversarial tests。正式结果只能从随后公开的精确 source commit 在 fresh
no-smudge Linux worktree 生成。

## 1. 为什么做、什么不算贡献

现有审计只证明 raw exact、token-literal exact 和 AST-literal exact fingerprint 下的浅层 clone 较少，并明确保留
“未排除 fuzzy/语义近重复”的限制。代码重复影响 ML-for-code 评测并不是本项目的新发现：Allamanis (2018)
系统展示了 duplication 对指标的夸大并给出数据收集建议；The Stack 使用 5-token shingles、MinHash/LSH 和 exact
Jaccard 复核做 near-dedup。exact set-similarity join 与 prefix filtering 也已有 AllPairs 系列工作。

- Allamanis, *The Adverse Effects of Code Duplication in Machine Learning Models of Code*：
  https://arxiv.org/abs/1812.06469
- Kocetkov et al., *The Stack* 及其 dataset card：https://arxiv.org/abs/2211.15533 ，
  https://huggingface.co/datasets/bigcode/the-stack-dedup
- Bayardo, Ma, Srikant, *Scaling Up All Pairs Similarity Search*：
  https://research.google/pubs/scaling-up-all-pairs-similarity-search/

因此不主张 near-dedup 算法 novelty，也不写 first/only。可防守的新增资产仅是：在 outcome-blind、按物理 run 与
时序固定的 MLE-agent first-960 cohort 中，分开 sibling、parent-child、same-run、cross-run same-task 与 cross-task
关系，量化搜索过程的 lexical near-duplicate 结构，并把它接入可复现的数据质量协议。

## 2. 结果前固定表示与阈值

1. Python tokenizer 删除 comment、NL/NEWLINE、INDENT/DEDENT 和格式噪声；number/string 分别归一化，保留
   identifier、keyword、import/API 与 operator。
2. 顺序 token 构成连续 5-gram；每个 shingle 用 deterministic BLAKE2b-128 表示，文档视为 distinct-shingle set。
3. tokenization 失败、token 少于 5 或 distinct shingles 少于 20 的端点不插补、不删除，统一降低 coverage。
4. primary cutoff 固定为 Jaccard≥`17/20=0.85`；strict sensitivity 固定为 `19/20=0.95`。strict 只能并列报告，
   不得在 primary 失败时救结论。
5. 候选检索使用全局 document-frequency ordering 的 exact prefix filter，并对候选做完整 set intersection；阈值
   用整数交叉乘法判定，不使用 float rounding。它是 128-bit shingle hash space 上的 exact threshold join，不是
   semantic equivalence proof。

## 3. 固定输出与主门

两档阈值都报告：candidate/exact pairs、relation pair counts、各 relation affected endpoints、跨 run/cross-task
affected fraction、跨 run connected components、最大 component endpoints/tasks，以及不暴露身份的 canonical edge
digest。same-run sibling/parent-child 重用是搜索动力学描述，不进入跨-run数据独立性的正门。

只有以下五门全部通过，才允许 `strong_low_fuzzy_clone_support=true`：

- fingerprint coverage≥0.99；
- Jaccard≥0.85 的 cross-run affected endpoint fraction≤0.01；
- cross-task affected endpoint fraction≤0.005；
- size≥10 且跨≥3 tasks 的 cross-run component 数为 0；
- 以 card identity SHA-256 固定选出的 384 documents 上，prefix join 与全 pair brute force edge set 完全一致。

门值沿用此前 exact-clone 审计的 1%/0.5%质量尺度，并在真实 similarity 前冻结。失败不得改 tokenizer、shingle
size、threshold、最短长度、cohort、分母或 component 定义；strict/某任务子集/删主导 run 均不能 rescue primary。

## 4. 独立性、安全与解释边界

- producer 与 verifier 各双跑逐字节一致；verifier 不 import producer，并以独立 postings 枚举重算全部 edge
  aggregates/digest；
- synthetic exhaustive/random/adversarial sets 必须先证明 prefix join 与 brute force 一致；真实 384-doc subset
  再做一次 deterministic exact check；
- 允许输入仅为固定 snapshot 的 `eligible_blind_manifest.jsonl`、`provisional_runs.jsonl`、`intake_registry.jsonl`
  与对应 `summary.json`；SHA、schema、run/task/accounting 全部核验；
- file trace 对 label/grade/outcome/scorer prediction/raw archive/env/secret 路径命中必须为 0；输出不得含 code、
  task、card、run 值；credential shape 命中必须为 0；
- CPU-only，GPU/API/model-fit/base-LLM update=`0/0/0/0`；完整测试、13项预检、clean worktree 和 manifest 任一失败
  即无 `COMPLETE`。

通过只能写成“当前 provisional prefix 在固定 lexical token-shingle/Jaccard 定义下跨-run近重复较低”。它不能证明
语义等价程序不存在、变量重命名 clone 不存在、公开 Kaggle task 未进入底座预训练、predictor 无泄漏或方法有效。
当前 cohort 仍是 366/960 且 closure=false；即使 provisional 全门通过，也必须在 first-960+closure 后原协议重跑，
不得提前揭盲或启动效果分析。

## 5. 冻结时实现状态

- schema：`phase1/prospective_fuzzy_clone_schema.py`；
- producer：`phase1/audit_prospective_fuzzy_code_clones.py`；
- non-importing verifier：`phase1/verify_prospective_fuzzy_code_clones.py`；
- synthetic/adversarial focused tests：`13 passed in 0.20s`；
- 真实 candidate count、similarity、edge、component 与 gate：未读取、未计算。
