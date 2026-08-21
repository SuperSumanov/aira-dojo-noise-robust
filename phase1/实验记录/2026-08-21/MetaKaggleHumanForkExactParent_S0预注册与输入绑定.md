# Meta Kaggle Human Fork Exact Parent：S0 预注册与输入绑定

日期：2026-08-21。状态：`S0A_CRLF_ENGINEERING_RETRY_FROZEN_NOT_RUN`。本路线是 0CP AIRA strict-future 主线之外的
cross-domain extension，不恢复 HCE/TD/多保真，也不改变 first-960/closure 或 transition escrow。

工程纠错记录：commit `d5d93bc...` 的第一次 acquisition attempt 在任何新表下载前 fail closed。Kaggle CLI 的
`--csv` 输出使用 CRLF；逐字节 `grep -Fx` 因尾部 `\r` 拒绝第一条固定 metadata 行。该 attempt 只写了公开 dataset
listing/metadata receipt，没有打开任何 CSV data row。重试只把 raw listing 原样保留后复制一份去除 `\r` 的
normalized listing，用它做固定行检查和 before/after diff；输入文件、snapshot 时间、身份定义、支持门和停机规则
均不变。正式 receipt 改写到新目录 `receipts/s0a-crlf-v2`，旧 attempt 不删除、不晋升。

## 1. 假设与 novelty 边界

正面候选是假设：同一公开 Kaggle notebook version 被不同人 fork 后，fork 起点的 parent-relative code change
可能包含可迁移的“未来潜力”信号；若成立，可用大量 human fork 作为轻量 critic 的外部弱监督，再在严格未来 AIRA
sibling 上一次性验证。它不会微调底座 LLM。

不能主张首个人类 notebook trajectory/fork 数据集。TraceML 已公开 human trajectories、fork graph 与 score；
KGTorrent 已系统收集 Kaggle notebooks；Code Code Evolution 已研究 notebook revisions 的行为变化。当前检索没有找到
“用官方 exact fork siblings 的隐藏 leaderboard outcome 训练/验证 MLE-agent future-potential critic”的直接工作，
但这只是 narrow gap，不把未检出当成 novelty 证明。相关入口：

- [Meta Kaggle](https://www.kaggle.com/datasets/kaggle/meta-kaggle)；
- [Meta Kaggle Code](https://www.kaggle.com/datasets/kaggle/meta-kaggle-code)；
- [TraceML](https://huggingface.co/datasets/TraceML-HF/TraceML)；
- [KGTorrent](https://arxiv.org/abs/2103.10558)；
- [Code Code Evolution](https://arxiv.org/abs/2209.02851)。

## 2. 最关键的身份纠正

`KernelVersionKernelSources.SourceKernelVersionId` 表示 notebook 引用的另一个 notebook output/source，不能据此称
fork。正式 fork parent 只认 `Kernels.ForkParentKernelVersionId`；child 的 `FirstKernelVersionId` 必须唯一连接到
`KernelVersions.Id`，并要求该 first-version row 的 `ParentScriptVersionId` 与 explicit fork parent 一致。两列不一致
或 parent/child 缺失即身份失败，不按标题、作者、时间或代码相似度猜。

同一 exact parent 至少有两个不同 child Kernel 才形成 sibling group。每个 parent 只取一对：先按
SHA256(`parent_version_id|child_kernel_id`) 排 child，取前两个；pair orientation 使用独立 hash domain。parent 与两个
child first versions 必须各自只有一个且相同的 `SourceCompetitionId`，competition 必须已结束且 final leaderboard
verified。这样不会因大 fork group 产生组合爆炸，也不在 outcome 后选 pair。

## 3. S0a：输入 acquisition，只读 header

固定 official daily snapshot 的 file metadata：

| 文件 | Kaggle 列表大小 | update time |
|---|---:|---|
| Competitions.csv | 152MB | 2026-08-21 05:23:20 |
| KernelVersionCompetitionSources.csv | 163MB | 2026-08-21 05:27:29 |
| KernelVersionKernelSources.csv | 51MB | 2026-08-21 05:27:26 |
| Kernels.csv | 293MB | 2026-08-21 05:27:34 |
| KernelVersions.csv | 5GB | 2026-08-21 05:28:49 |
| Submissions.csv | 2GB | 2026-08-21 05:28:12 |

前三个既有输入已 SHA 绑定；本轮新增约 7.3GB。下载前后完整 file listing 必须逐字节相同；每个文件只做 SHA、bytes
和第一条 CSV header。`Submissions.csv` 的任何 data row、public/private score 与 notebook code 都禁止打开。
若 snapshot 在下载间变化、header/schema 缺失或文件不完整，S0a 直接关闭。

## 4. S0b：结果盲 identity/support 门

S0a 通过后才允许流式读取 `Kernels`、`KernelVersions`、competition source link 和 `Competitions` 的身份/时间/状态；
仍不打开 `Submissions.csv` data rows。全部门为：

1. Kernel Id 与 KernelVersion Id 唯一，required columns 完整；
2. selected child first-version 与 parent-version join 均完整，child/parent scripts 不同，时间严格有序，图无环；
3. `ForkParentKernelVersionId` 与 child first row 的 `ParentScriptVersionId` 全部 selected edges 一致，且全体 explicit
   fork 的一致率≥0.95；
4. fixed one-pair-per-parent 后 canonical pairs≥500、distinct parents≥100；
5. completed/verified competitions≥20，dominant competition pair share≤0.20；
6. selected pair 的 parent/children singleton competition identity 100% 完整。

任一失败即关闭，不读 score/code、不改 population/阈值追救。全部通过也只允许另立 S1 score-support/effect
预注册；S1 必须在打开 `Submissions.csv` 第一条 data row 前冻结 hidden-private primary、固定时间/版本预算、non-tie、
task/parent clustered inference、code availability、AIRA overlap 与 stop rule。

已知风险是 Meta Kaggle 明确是过滤后的非完整数据库，且已有用户报告大量
`Submissions.SourceKernelVersionId -> KernelVersions.Id` 缺失；所以 score join 必须是 S1 的独立 kill gate，不能把
缺失当随机样本。参考：
[Meta Kaggle join warning](https://www.kaggle.com/questions-and-answers/575094)。

## 5. 十三项执行前检查

1. 方向：仅外部 cross-domain extension，主线仍为 strict-future AIRA escrow。
2. 代码：单用途 acquisition；S0b producer/verifier 在 S0a 后另写、先测后跑。
3. 输入：dataset id、daily file metadata、既有 SHA 与下载前后 listing 固定。
4. 单位：exact parent version、child Kernel/branch、competition；parent 是 cluster。
5. 已见结果：披露 TraceML join 失败和 Meta Kaggle score join warning，不据此调门。
6. 特征：S0 不建模；S0b 只用 identity/time/status，不读 code/score。
7. 泄漏：Submissions data rows 与 notebook code 在 S0 全封；后续 task/parent closure 另冻。
8. 安全：Kaggle 凭据只在远端 env；不打印、不复制；raw code 后续须 credential/PII quarantine。
9. 统计：S0 仅精确 count/share/identity rate，无 predictor effect 或显著性。
10. 复现：完整 file listing、SHA、headers、固定 hash domain；S0b 必须 producer×2/verifier×2。
11. 资源：新增约 7.3GB；预计 10--40 分钟；CPU/network-only、GPU/API=0。
12. 失败：snapshot/schema/join/identity/support 任一不符即 fail closed。
13. 停止：S0 一次性；过门后也先冻结 S1，再读任何 score row。
