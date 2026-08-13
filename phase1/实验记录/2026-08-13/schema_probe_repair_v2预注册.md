# Schema/probe-first V2：conditional-debug 独立修复门预注册

日期：2026-08-13
状态：**outcome 前冻结；仅为可行性门，不是方法效果实验**

## 1. 为什么允许这一轮

V1 对两个预先冻结任务只通过 1/2 probe，按原门槛正式为 FAIL。失败任务的单次 draft 在写出任何
artifact 前因通用 sklearn API 不兼容退出。V1 的停止规则只允许一次独立修复：新任务、新 seed，draft
失败时最多使用一个固定 debug，首次 externally valid 候选出现后立即停止。禁止修补或重放 V1 代码。

本轮只回答：加入公平、固定的一步 conditional debug 后，prompt-only schema/probe operator 是否能在两种
新任务上稳定产生可 replay 的候选。即使 PASS，也不表示 coverage、最终质量、regret 或搜索收益改善。

## 2. 任务冻结与预检替换记录

最终矩阵在任何候选生成和 API POST 前冻结为：

| index | task | modality | public inputs |
|---:|---|---|---|
| 0 | `spaceship-titanic` | structured tabular classification | `train.csv` 724,849 B；`test.csv` 75,894 B；`sample_submission.csv` 12,204 B |
| 1 | `tweet-sentiment-extraction` | text span extraction | `train.csv` 3,151,814 B；`test.csv` 244,504 B；`sample_submission.csv` 33,009 B |

固定 seed 为 862，issue 为 `schema_probe_repair_v2`。两个任务均不同于 V1，且一表格一文本；选择只依据
modality、AIRA task config 存在、public 数据非空以及冻结 validator 能识别标准 submission，不读取任何
候选结果或任务成绩。

必须保留两次 outcome 前替换：最初候选 `us-patent-phrase-to-phrase-matching` 在 Hydra compose 时因仓库没有
task YAML 被拒绝；随后候选 `random-acts-of-pizza` 因只有大小写不同的 `sampleSubmission.csv`，与冻结
validator 明确要求的 `sample_submission.csv` 不兼容而被拒绝。两次都只发生配置解析/文件名检查，没有
LLM 候选生成、API POST、GPU scientific run 或性能 outcome；不是按结果换题。

## 3. 冻结生成协议

- 底座与四个 operator client：`deepseek-v4-flash`；不微调、不 RL-finetune；
- prompt：与 V1 完全相同的 `CRITICAL ANYTIME ARTIFACT CONTRACT` draft；不加入针对 sklearn 或任务的修补；
- 每任务恰好一个 physical generation，禁止 retry；
- `step_limit=3`：blank root + draft + 至多一个 debug；
- `num_children=1`、`max_debug_depth=1`；禁止同一步创建多个 sibling；
- `stop_after_first_valid=true`：draft externally valid 时停在两节点；draft buggy 时只执行一个 debug，之后停在三节点；
- `execution_timeout=600` 秒/候选，solver `time_limit_secs=1200`；
- 生成 LLM 温度沿用 schema config：draft/debug/improve 0.6，analyze 0.5；记录完整 resolved config、seed、命令和 commit；
- 逻辑 operator 请求上限为每任务 draft+analyze+debug+analyze，共不超过 8 次；transport retry 仍按现有 client 配置记录。

拓扑审计 fail-closed：journal 行数必须等于 state `current_step` 和 export 节点数；节点只能是
`root→valid draft` 或 `root→buggy draft→debug`。拒绝 improve、多 child、错 parent、断号、额外节点和配置漂移。
若有 debug，冻结 debug leaf；即使 generation 标成 buggy 也不换节点，由独立 replay 判定真实 contract。

## 4. 冻结 replay 与完整性契约

只有两个冻结 leaf 都通过静态 contract（Python AST、`candidate_probe.csv`、两个 marker、`os.replace`、
`os.fsync`）才启动 replay。静态 gate 失败直接计总体 FAIL，不改代码。

replay 使用已验证的 production Singularity interpreter和镜像 SHA256
`801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda`，public data 只读；每个候选只连续
执行一次，host checkpoints 固定为 30/60/120/240/360/600 秒，poll 0.10 秒。候选进程看不到 pristine grader；
退出后才评分 snapshot。保存 source/export/code/manifest hash、host monotonic capture、marker、自报时间、
每次 submission transition、checkpoint、rc、stderr 和容器 provenance。

合法 probe 必须同时满足：

1. host 120 秒内稳定出现；
2. pristine grade finite；
3. 与 sample submission 表头和行数一致，但预测候选特异、非常数且不逐行复制 sample；
4. marker hash 与捕获 hash 一致；
5. 后续 checkpoints 不修改 probe；
6. 代码、source export、manifest 和 workdir solution hash 全部一致；
7. 无共同 fallback 冒充 candidate probe。

合法 full transition 必须在同一进程、probe 之后、host 600 秒内出现，并满足独立 marker/hash/finite grade。

## 5. 唯一裁决规则

- **PASS**：两个任务的合法 probe 都在 host 120 秒内出现，且至少一个任务有合法 full transition；
- **PARTIAL**：两个 probe 都通过，但没有合法 full transition；
- **FAIL**：任一生成 entry、严格拓扑、静态 contract、replay 完整性或 probe 门失败；
- validator 的 failure/abstention/无 artifact 全部进入分母；不做 complete-case 删除。

V2 PASS 只授权设计新任务/新 seed 的小规模因果 A/B。V2 PARTIAL/FAIL 均关闭 prompt-only schema 路线；
后续只能单独提出 runtime-owned probe API，不能再改 prompt 或同任务补跑。

## 6. 资源矩阵与停止预算

- generation：1 个 Slurm allocation，2 个 task steps 并行，各 1×RTX3090；预期实际 candidate execution
  不超过 0.667 GPU·h，外加 LLM/启动开销；
- replay：2 个 array elements，各 1×RTX3090、最多 600 秒，candidate execution 上限合计 0.333 GPU·h；
- 预期实际 candidate execution 上限合计 1.000 GPU·h；scheduler allocation 的保守硬上限单独记录，
  不把排队/空闲 allocation 隐藏为零；
- 并发最多 2 GPU，本轮不与其他用户作业叠加；排除 `projgpu7/8/33`、`gpu36/38`；
- 不启动 150-run 确认或任何训练 sweep。

## 7. 长实验前完整性清单

1. **全部旋钮落盘**：任务、seed、模型、温度、step/child/debug/time、checkpoint、容器和 gate 均在本文及 resolved config；
2. **cheap test**：MCTS first-valid、严格拓扑、builder→extractor fixture、Singularity worker/validator 单测必须全过；
3. **去重**：两任务唯一、与 V1 不重合；每任务一个 task id、一个 source export、一个 code hash；
4. **分布**：一表格一文本；报告每任务，不用二样本均值作统计结论；
5. **评测分层**：coverage、probe validity、full transition 分开；没有 headline accuracy；
6. **模型保存**：本轮不训练模型；保存完整 LLM/容器/config/commit provenance；
7. **泄漏**：不读 `decision_clean_b*.jsonl` frozen test，不训练任何 predictor；候选只见 public task data；
8. **随机性/顺序**：seed 862、index→task 映射和字典序输出固定；不按 outcome retry；
9. **密钥**：只 source 远端 `.env`，不打印、不复制进 repo；提交前文件名和内容双扫描；
10. **walltime**：generation 45 分钟、replay 40 分钟/array 的 scheduler cap；worker 自身 600 秒 fail-closed；
11. **power**：N=2 只能裁决 feasibility，禁止显著性、总体成功率或 venue-level 效果结论；
12. **真实 rc**：entry、wait、worker、validator 的 rc 在写日志前捕获；父 job 与 scientific step 分开报告；
13. **先冻结再扩展**：本文、代码、tests 和 Git commit 在 sbatch 前固定；结果出来后不换任务、阈值或 gate。
