# Historical v11 train ↔ first-960 fuzzy-overlap v1：结果前预注册

冻结时间：2026-08-26T16:04:21+08:00。冻结时只核验历史输入的行数、端点/run/task/parent 计数与文件
SHA-256，并运行 synthetic/exhaustive/adversarial tests；尚未对任何真实 historical↔prospective 文档对计算
candidate、Jaccard、edge、component 或 gate。正式结果只能由随后公开的精确 source commit 在 fresh no-smudge Linux
worktree 中生成。

## 1. 问题、贡献边界与输入人口

前一项审计证明当前 first-960 prefix 内 Jaccard≥0.85/0.95 的高相似代码全部局限于同一 physical run，但这不能排除
“前瞻评测端点与曾用于 critic 训练的历史代码近重复”。本审计只回答一个更直接的时间外 benchmark-integrity 问题：
历史 v11 critic train endpoint 与当前 outcome-blind first-960 prospective endpoint 在固定 lexical 定义下是否发生高相似
重叠。

历史侧固定为三个不可变 `intask_split=train` 文件的并集：

- `decision_train_v11_b0.jsonl`：4,263 rows，normalized-LF SHA-256=
  `bd31b4679c7b4405703b976921df0bc63acba4fc0c4a002f4b8f36d171251fca`；
- `decision_train_v11_b1.jsonl`：861 rows，SHA-256=
  `5053bb3825c5d6a420491cdb056594b306b4850c2b3c179361031becade5d528`；
- `decision_train_v11_b2.jsonl`：692 rows，SHA-256=
  `f0cb83c41b1e45d198384726194b3a2bd013132957d71aa2d81aea318dd7c881`。

三者共 5,816 rows、5,519 unique endpoints、333 physical runs、23 tasks、2,302 parents。代码只从固定
`cards_current_v11.jsonl` 取，文件 SHA-256=
`6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75`。历史文件本身含回顾性 label/
observation 字段；程序会解析 JSON object，但只使用 card ID、physical run、task、parent 与 code，明确记录
`historical_label_or_observation_fields_used=false`。这不是“历史文件字节未打开”的主张。

前瞻侧仍是预注册时间全序 first-960 eligible physical runs；当前只允许使用 immutable snapshot 中的 blind code/
identity manifests 和 accumulator/intake receipts。closure=false 时结果一律 provisional，first-960+closure 后原协议重跑。

代码重复影响 ML-for-code 评测、5-token shingle near-dedup 与 exact prefix filtering 均有既有工作，故不主张算法
novelty、first/only 或 semantic clone detection：

- Allamanis (2018)：https://arxiv.org/abs/1812.06469
- The Stack：https://arxiv.org/abs/2211.15533 ，
  https://huggingface.co/datasets/bigcode/the-stack-dedup
- AllPairs prefix filtering：https://research.google/pubs/scaling-up-all-pairs-similarity-search/

可防守的贡献仅是 outcome-blind MLE-agent 时间外 cohort 的 train→future lexical-overlap 机器审计与可复现证据。

## 2. 结果前冻结的表示、join 与输出

表示逐项复用已正式验证的 first-960 fuzzy-clone 协议，并新增 fail-closed 参数契约：

1. Python tokenizer 去 comment/格式噪声，number/string 归一化，identifier/API/operator 保留；
2. 连续 5-token shingles、distinct set、deterministic BLAKE2b-128；少于 20 个 distinct shingles 或 tokenizer 失败
   不插补，降低各自 side 的 coverage；
3. primary Jaccard 固定为 `17/20=0.85`，strict sensitivity 固定为 `19/20=0.95`；strict 不能 rescue primary；
4. 在 historical+prospective 的联合 document frequency 顺序上做 exact bipartite prefix join，候选再做完整 set
   intersection，以整数交叉乘法判断阈值；
5. 固定报告 candidate/exact pair count、same-task/cross-task pairs、两侧 affected endpoints/fractions、bipartite
   components、最大 component endpoints/tasks 和匿名 canonical edge digest，不输出 code/card/run/task 值；
6. 以 card identity SHA-256 分别固定 256 historical 与 256 prospective documents，对 65,536 个 bipartite pairs
   做 brute-force edge-set 复核。

## 3. 固定成功门与杀死规则

只有以下六项全部通过，才允许
`strong_low_historical_train_future_overlap_support=true`：

- historical fingerprint coverage≥0.99；
- prospective fingerprint coverage≥0.99；
- Jaccard≥0.85 的 prospective affected endpoint fraction≤0.01；
- 其中 cross-task prospective affected endpoint fraction≤0.005；
- size≥10 且跨≥3 tasks 的 bipartite component 数为 0；
- 256×256 deterministic subset 上 prefix join 与 brute force edge set/digest 完全一致。

任一门失败都不得修改 tokenizer、normalization、shingle size/hash、最低长度、threshold、cohort、分母、component 定义
或历史 train 集；不得删主导 task/run、改报 strict 0.95、改成 exact-only 或用子集挽救 primary。失败只能如实写成存在
train→future lexical overlap，并在后续 benchmark protocol 中做 train-exclusion/cluster sensitivity；不能把失败解释为方法失败。

## 4. 双实现、安全与解释边界

- producer 与 verifier 各双跑逐字节一致；verifier 不 import 新 producer，使用此前 non-importing tokenizer/shingler 与
  自己的 bipartite postings 枚举，独立重算 aggregate、component、digest 和 gates；
- 正式 fresh worktree 必须先 LFS 拉取历史 cards，并逐字节核验上述 SHA；source/schema/tokenizer/verifier blob 全绑定
  公开 commit；14 项 synthetic/exhaustive/adversarial tests 与全套 tests、13 项预检、file trace、credential scan 全过；
- historical 与 prospective physical-run ID 集必须不交；前瞻 label vault、outcome、prediction values、accuracy、search
  utility 与 senior raw archives 均不得打开；GPU/API/model-fit/base-LLM update=`0/0/0/0`；
- 通过最多支持“在固定 lexical token-shingle/Jaccard 定义下，历史 v11 train 与 provisional future cohort 高相似重叠低”。
  它不证明 semantic equivalence absence、identifier-renamed clone absence、Kaggle/public-code pretraining contamination
  absence、最终 first-960 无 overlap、predictor 无其他泄漏或 predictor 有效。

## 5. 冻结时实现状态

- schema：`phase1/historical_train_future_overlap_schema.py`；
- producer：`phase1/audit_historical_train_future_fuzzy_overlap.py`；
- independent verifier：`phase1/verify_historical_train_future_fuzzy_overlap.py`；
- focused synthetic tests：`14 passed in 0.22s`；与既有 fuzzy audit 合并：`27 passed in 0.27s`；
- 真实 candidate/similarity/edge/component/gate：未读取、未计算。

## 6. 正式执行结果（预注册后追加）

正式 source commit=`f9c6de27afd933d9ceee04e67acbd51d25947798`，prospective snapshot=
`8579d7cd32091a11089b935217f7189e321b1d623dbaa69233182ba2fedd9248`。fresh no-smudge Linux worktree 先核验
305,750,663-byte historical cards 与三份 normalized-LF pair SHA，再完成 producer A/B、non-importing verifier A/B、
file trace、安全扫描和 manifest 封口。

结果为：historical 5,519/5,519 endpoints 可 fingerprint；prospective 10,674/10,683 可 fingerprint，coverage=
`0.9991575400168492`。0.85 primary 的 exact candidate checks=`2,880`，near-duplicate pairs=`0`，same-task/
cross-task=`0/0`，两侧 affected endpoints=`0/0`，components=`0`；0.95 strict 同样为 0。固定 256×256 的
65,536 对 brute-force 控制一致，六个预注册门全部通过。

producer/verifier A/B 各自逐字节一致，独立 verifier 不 import producer 且 aggregate matches=true；focused/full=
`14/1182 passed`（47 warnings），forbidden-path/credential hits=`0/0`，GPU/API/model-fit/base-update=`0/0/0/0`。
另一个不修改 formal root 的独立 recheck 对 21 个 manifest payload 与全部固定计数再次通过。formal / recheck manifest
SHA-256 分别为 `8b4dc3aef2ada8f848362f049517511bd2658d847f5911f32435206c48c55730` /
`91e368c6e81e2dd3eb19791f1ed509697bcc29d67fb7c389ee0c34416d6c3713`。

裁决为 `FORMAL_PROVISIONAL_HISTORICAL_TRAIN_FUTURE_OVERLAP_COMPLETE` 且
`strong_low_historical_train_future_overlap_support=true`。允许结论仅是固定 lexical 定义下的 provisional
train→future 高相似链接为零；不外推 semantic/pretraining contamination absence 或 predictor effect。当前 366/960、
closure=false，最终 first-960+closure 后必须原协议重跑。公开结果包：
`phase1/results/historical_train_future_fuzzy_overlap_8579_20260826_f9c6de2/`。
