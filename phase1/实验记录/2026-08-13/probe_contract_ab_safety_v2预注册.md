# Probe-First Artifact Contract Safety/Discovery V2 预注册

日期：2026-08-13
状态：**冻结预注册；用户已批准预算；在本文件对应 commit 之前未对本矩阵调用 API、未提交 GPU**

## 1. 唯一问题与主张边界

在新的 task×seed blocks 上，只向 draft system prompt 增加冻结的 progressive artifact contract，是否相对
original prompt：

1. 提高 host 在 120 秒内获得 candidate-specific、schema-valid、finite-pristine-score artifact 的覆盖；
2. 不降低 600 秒 full-like candidate 的有效率；
3. 不造成方向修正后的 full-quality 明显损害。

这仍是机制的 safety/discovery A/B，不是 fixed-budget search utility confirmation。它测试主动构造便宜
low-fidelity candidate，而不是已由 SPT pilot 否定的“从同一段现有代码中被动截获早期 prediction”。
N=8 仅用于 safety/discovery；不报告显著性、总体成功率或 venue-level 效应。

## 2. 冻结矩阵、seed 与选择边界

全局 seed 固定为 **887**。每个相邻的两行是一对；同一 task 的两臂并发启动。Arm order alternates，避免固定
命令顺序偏差。生成结束后不得因失败或结果难看而替换任务。

| index | task | arm | metric direction | sample submission source |
|---:|---|---|---:|---|
| 0 | aerial-cactus-identification | original | higher | `sample_submission.csv` |
| 1 | aerial-cactus-identification | contract | higher | `sample_submission.csv` |
| 2 | AI4Code | contract | higher | `sample_submission.csv` |
| 3 | AI4Code | original | higher | `sample_submission.csv` |
| 4 | denoising-dirty-documents | original | lower | `sampleSubmission.csv` |
| 5 | denoising-dirty-documents | contract | lower | `sampleSubmission.csv` |
| 6 | kuzushiji-recognition | contract | higher | `sample_submission.csv` |
| 7 | kuzushiji-recognition | original | higher | `sample_submission.csv` |
| 8 | learning-agency-lab-automated-essay-scoring-2 | original | higher | `sample_submission.csv` |
| 9 | learning-agency-lab-automated-essay-scoring-2 | contract | higher | `sample_submission.csv` |
| 10 | text-normalization-challenge-english-language | contract | higher | zip 内 `en_sample_submission_2.csv` |
| 11 | text-normalization-challenge-english-language | original | higher | zip 内 `en_sample_submission_2.csv` |
| 12 | mlsp-2013-birds | original | higher | `sample_submission.csv` |
| 13 | mlsp-2013-birds | contract | higher | `sample_submission.csv` |
| 14 | whale-categorization-playground | contract | higher | `sample_submission.csv` |
| 15 | whale-categorization-playground | original | higher | `sample_submission.csv` |

任务只按 public-data 可用性、模态覆盖和未进入相关干预 outcome 来选。明确排除：

- schema feasibility V1/V2 的 4 个任务；
- 无效 A/B 10637 的 6 个任务；
- SPT runtime pilot 已看过结果的 `random-acts-of-pizza`、
  `us-patent-phrase-to-phrase-matching`、`petfinder-pawpularity-score`；
- `playground-series-s3e18` 与 `detecting-insults-in-social-commentary` 的远端 `prepared/public` 为空。

旧语料中某任务存在并不构成本实验 outcome；本实验不读取任何旧 pair、node score 或代码来选样。

## 3. 公平契约

- 唯一允许变化的是 draft system prompt 中的四行 artifact-contract block；
- 底座均为 `deepseek-v4-flash`；analyze/debug/draft/improve client、temperature、seed、step budget、debug
  budget、执行超时、容器、GPU 类型、public data、grader 与每对的启动波次固定；
- `step_limit=3`、`num_children=1`、`max_debug_depth=1`、`stop_after_first_valid=true`、
  `execution_timeout=600`、`time_limit_secs=1200`；两臂各至多一次 conditional debug；
- resolved solver 删除 draft prompt、`solver.exp_name`、`solver.checkpoint_path` 后必须逐字段相等；别的差异一律
  `INVALID`；
- candidate 只挂载 `prepared/public`，看不到 pristine grader、private label、held-out 分数或旧 critic 数据；
- `decision_frozen_v11_b*`、`decision_clean_b*` 以及其 node/code 内容完全不进入生成、重放或任务选择；
- 失败、timeout、语法错误、无 submission、不可评分结果全部保留在固定分母，不重试、不补样。

DeepSeek 的远端采样并不保证位级确定性，metadata seed 也不能消除服务端随机性。因此单 seed 结果只作
safety/discovery；若通过，确认实验必须多 seed 并把 arm 顺序作为区组因素。

## 4. 观测与端点

生成阶段固定每臂最后一个拓扑合法 leaf，并保存完整 config、status、export、manifest、snapshot 及哈希。随后每个
leaf 在同一容器中独立连续重放一次；host 每 0.10 秒观察原子写入，保存
30/60/120/240/360/600 秒 checkpoint，candidate 停止后才调用 pristine grader。

一个 artifact 仅在下列条件全部满足时算 scoreable：

- CSV header、行数和逐行 ID 与任务冻结 sample submission 一致；
- 至少一个预测列非恒定，且预测值不等于 sample submission；
- pristine grader `rc=0` 且 score 为 finite；
- snapshot 的 size/SHA 与 watcher 记录一致。

contract probe 还必须在 120 秒内捕获、不可被后续修改、恰有一个 hash 一致的
`CANDIDATE_PROBE_READY` marker，且是第一个 submission event。contract full-like 必须在 600 秒内有恰一个
hash 匹配的 `FULL_CANDIDATE_READY` 后续 event；original full-like 使用最后一个 scoreable endpoint。

## 5. 冻结裁决门

- **K0 compliance**：contract 合法 probe 至少 **6/8**；
- **K1 coverage**：contract coverage@120 至少 **6/8**，并且逐 task 配对的净 coverage gain 至少
  **+3 blocks**；
- **K2 full validity**：contract full-valid 数最多比 original 少 **1 block**；
- **K3 quality safety**：至少 **4** 个 task 有 paired full scores；按公开 metric direction 修正后，
  relative delta 的 median ≥ **−0.05**；relative delta `< −0.10` 的 catastrophic harm 最多 **1 task**。

裁决顺序固定：四门全过为 `PROMISING`；quality pairs 不足为 `INCONCLUSIVE`；K2/K3 失败为
`QUALITY_KILL`；否则 K0/K1 失败为 `NO_COVERAGE_GAIN`。任何 provenance、配置、manifest、replay 或双验证器
失败均为 `INVALID`，不能解释为方法负结果。full quality 只对可用 pair 做描述性汇总，但 missing pair 仍通过
K2 和“至少 4 pair”门进入惩罚，不把 complete-case 冒充总体。

## 6. 双验证与结果报告

主 validator 与一个不导入 project builder/extractor/validator/helper 的独立 verifier 在结果出现前同时冻结。
独立 verifier 从原始 config/export/journal/state/status/snapshot 重建拓扑，逐个 unique artifact 再调用 pristine
grader，并独立重算 K0–K3。两者 verdict、gates 和所有 summary scalar 必须一致。

报告必须给出 8 个逐 task pair、两个 arm 的覆盖、有效率、首个 scoreable 时间、方向修正质量差、LLM token/
latency 使用及所有失败，不只报告均值。

## 7. 预算、停止与 ETA

- generation：16 entries × candidate execution cap 600 秒，candidate 上限 **2.67 GPU·h**；
- replay：16 entries × 600 秒，candidate 上限 **2.67 GPU·h**；
- candidate 总上限 **5.33 GPU·h**；
- Slurm：generation `4×RTX3090 × 100 min = 6.67 GPU·h`；replay array
  `16 × 1×RTX3090 × 20 min = 5.33 GPU·h`；scheduler hard cap 精确为 **12.00 GPU·h**；
- 并发不超过 4 jobs/4 GPUs，排除 `projgpu7/8/33`、`gpu36/38`；
- 最多 64 条 logical API usage records，无自动 retry 或替换；余额低于 ¥25 时 fail-closed；
- 预计排队外 3–5 小时；detached monitor 最长 7 小时。任一 cheap/Hydra/data/secret/budget gate 失败则不提交。

## 8. 13 项 preflight 对应关系

1. 16 份 resolved Hydra config 从产物侧验证唯一旋钮；
2. V2/V1 fixture、worker、主/独立 validator cheap self-test；
3. 不读取冻结 test pair/node/code；
4. 固定 8 个 task blocks，结果逐 task 展开；
5. 配对 arm、固定分母与 missingness 门替代不适用的训练 eval-stratify；
6. 本实验不训练模型，但保留全部生成与重放产物；
7. pair/node/逐字节 code 三层泄漏均因无旧语料输入而为零；
8. seed、矩阵和 arm order 在 API POST 前冻结；
9. push 与 prereg bundle 均扫描秘密；
10. candidate 与 scheduler 两套墙钟核算；
11. 明确 N=8 的 discovery power 边界；
12. 链脚本先保存每一步 `$?` 再记录，并在失败时退出；
13. 矩阵 append-only；outcome 后禁止补样或换任务。

只有 `PROMISING` 且双验证一致，才进入多 seed、与 ArchPilot-style proxy/critic/full execution 的 fixed-budget
search utility 对照；其他裁决按本文件停止，不事后改门。
