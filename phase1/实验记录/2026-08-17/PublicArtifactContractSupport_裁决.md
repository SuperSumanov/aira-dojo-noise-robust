# Public Artifact Contract Support v1：裁决

日期：2026-08-17。裁决：`VERIFIED_NONTRIVIAL_PUBLIC_ARTIFACT_CONTRACT`。本轮不改变 score-channel
唯一主实验，不授权 GPU/API 或方法效果主张。

## 1. 执行完整性

- 结果前 source commit：`1dac61cf71c58e89dd084380165e48b4f1438a43`；
- 首次 wrapper 因没有把 cwd 切到 clean worktree，在任何 contract 读取前以 51 个 `phase1` import
  collection errors fail-closed；无结果产物。只修 wrapper cwd，不改 repo 代码、任务、输入规则或门；
- 同一 commit 重跑的完整 `phase1/tests` 为 `342 passed in 46.47s`；
- 两次独立进程输出逐字节相同，SHA256=
  `166eaa6770b4abd6118f0168abc2b6e8afb5633847af48628f3f637ad9b56bdb`；
- private/train/test feature/official label/score/journal/前瞻 outcome/env 读取均为 0；GPU=0，API=0。

## 2. 预注册门结果

25 个固定 run-clean memory tasks 中找到 20 个 public sample-submission contracts 和 20 个 public
descriptions。按任务类型为 image 7/12、NLP 9/9、tabular 4/4。20/25 coverage 在 header 审计前已经由
路径 inventory 看见，只作探索性描述。

尚未看的 header/type 异质性门全部通过：

| 门 | 冻结阈值 | 结果 | 裁决 |
|---|---:|---:|---|
| unique `(header, observed types)` signatures | >=8 | 19 | PASS |
| dominant signature share | <=0.5 | 0.10 | PASS |
| width buckets | 3/3 | `1-2`、`3-10`、`>10` | PASS |

因此允许写：公开 artifact contract 在现有 MLE 任务中是非平凡、任务特异的执行前结构信号；“统一要求写
`submission.csv`”不是完整 contract。

## 3. 结果后压力检查与收缩

为排除 header 名称制造虚假唯一性，结果后另算了不含列名、只保留列数与观察类型的描述性 signature：仍有
17 个；唯一共享原 signature 的是英/俄 text-normalization。不过 16/20 contracts 都是两列，宽结构差异只由
4 个任务贡献。因此主张收缩为 **列语义/placeholder 类型高度任务特异，并存在少量宽结构任务**，不写成
“所有任务的输出结构都完全不同”。

缺失的 5 个任务为 aptos、dog-breed、dogs-vs-cats、histopathologic、ranzcr，均因本机没有对应 public dir；
它们全是 image 任务。禁止从 `prepared/private` 补齐或把 20-task 结果无条件外推到 25 tasks。

## 4. 对正面路线的影响

这关闭了 senior 所担心的纯手写统一 heuristic 的一部分批评：未来 harness 可以消费任务原生、公开且可机器
验证的 contract，而不是硬编码一个相同 probe。但它仍未证明 agent 能学习、检索或利用该信号。

下一资格门只允许 CPU/support 工作：

1. 构造不含 outcome 的 contract fingerprint；
2. leave-one-task-out 检查 retrieval 是否仍有同类型、非 task-ID 的邻居，并对 unsupported image tasks abstain；
3. 固定 train-only failure taxonomy，验证 691 个 execution errors 中有多少与 artifact/schema 可修复失败有关；
4. 只有 score-channel 主实验确认且上述门通过，才对 `S/C/M` 三臂做功效分析与预算申请。

不得现在把 `artifact_contract_is_nontrivial=true` 改写成 coverage 提升、搜索加速或 learned harness 方法收益。
