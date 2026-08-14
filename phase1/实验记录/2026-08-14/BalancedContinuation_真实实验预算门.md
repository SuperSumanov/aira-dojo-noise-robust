# Balanced continuation：真实实验配置矩阵与预算门

日期：2026-08-14。以下矩阵在任何真实 GPU/API run 前给出。当前只批准并执行 0-GPU synthetic 工程测试；
真实矩阵尚未启动。

执行更新（同日）：完整 synthetic worker E0 已在 commit `f7b75a5b7d353116a0ecb0ca94ed3e7ca9870585`
通过 22 项聚焦测试、143 项全量 phase1 测试、13/13 preflight、24 rollout/72 candidate attempts/
48 operator calls/24 unique fresh workspaces；retry/replacement/GPU/API 均为 0。该更新只关闭 E0 工程门，
不改变下表的真实 E1/E2 预算、批准状态或科学结论门。

历史执行中位数按 561 秒/候选执行做 planning point estimate，并额外加 30% 作为 workspace、grading、LLM 和调度
开销。实际每行都必须保存逐 job wall/GPU/API cost，最终不能用估算替代实测。

| 阶段 | tasks | anchors/task | siblings B | replicates K | horizon H | rollout jobs | 候选执行数 | 预计 GPU·时（含 30%） | 目的 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| E0 synthetic | 2 synthetic | 2 | 3 | 2 | 2 | 24 | 72 synthetic | 0 | assignment/verifier/失败门 |
| E1 real smoke | 2 fast tasks | 1 | 2 | 2 | 1 | 8 | 16 | 3.24 | fresh workspace、warm start、外部 evaluator 端到端 |
| E2 pilot | 4 tasks | 3 | 2 | 3 | 2 | 72 | 216 | 43.76 | 只估 reliability/effect size，不发显著性主张 |
| E3 confirm 候选 | 8 tasks | 8 | 2 | 3 | 1 | 384 | 768 | 155.58 | task-clustered label/utility 确认；仅 E2 过门后 |

计算式：`jobs = tasks × anchors/task × B × K`；每 job 固定 `1 + H` 次候选执行；
`GPUh = executions × 561 / 3600 × 1.30`。E1+E2 总计 80 jobs、232 次候选执行、47.00 预计 GPU·时；
E3 不预授权，需根据 E2 实测方差重新做 power analysis，不能机械照表开跑。

## 公平契约

- 唯一变化是 continuation allocator/critic；底座、operator prompt/config、task data、D_search/D_val pristine
  evaluator、B/K/H、每次 timeout、hardware class、candidate pool 和 total executions 固定。
- 每个 rollout 新 output dir 和 fresh workspace；不在同一目录清文件后伪装 fresh，不允许读取 held-out/test 路径。
- warm start 恰好执行一次；随后恰好 H 个 operator transitions。timeout/invalid 是观测结果，不补跑。
- blocked order 在 outcome 前冻结；provider 若不保证 seed determinism，仍记录 request seed/ID，并把这种随机性计入 K。
- 一行一个 rollout 写 CSV/JSONL，包含 commit、config hash、seed、task、anchor/sibling、开始/结束时间、GPU、
  execution/API cost、停止原因；代码/label vault 与分析表分离。
- 先报告 task/run cluster uncertainty 和逐任务方向，不只报 pooled mean。

## 13 项长实验预检（E1 前必须逐项实际 PASS）

1. 方向与 estimand：`V_H^π`、三个 primary gates、撤回边界写入 frozen prereg。
2. cheap tests：producer、independent verifier、worker、workspace/evaluator 安全测试全过。
3. 输入分布：task/anchor/sibling 支持和 exact-code duplicate 在 outcome 前打印。
4. 资源矩阵：jobs、candidate executions、GPU·时、API calls 与 QOS slot 重新由实际 config 打印。
5. 训练/验证：discovery/fresh-confirm physical runs 零交集；first-960/frozen test 不读。
6. checkpoint/resume：每个 rollout 原子状态机；只按 rollout ID resume，不能重复计费/计样本。
7. 公平契约：除研究 allocator 外所有 hashes 相等；不相等即 INVALID。
8. RNG/数值：assignment/LLM/framework seed 全记录；NaN/Inf 和 direction 由 synthetic test 覆盖。
9. 密钥：远端 `.env` only；raw tar redact-before-read；push filename/content scan 均为 0。
10. wall-clock smoke：E1 每 task 至少一整个 block 完成；超时不事后增加 cap。
11. 推断/停止：E1/E2/E3 角色、kill gates 与禁止追参规则固定。
12. 退出码：launcher、每个 job、collector、verifier 的 rc 立即记录，`tee` 不覆盖。
13. append-only/hashes：input/assignment/config/result/receipt 全部新目录、SHA manifest 与独立重算。
