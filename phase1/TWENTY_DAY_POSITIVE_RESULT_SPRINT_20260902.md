# 20 天正结果冲刺路线（2026-09-02）

本文件服从 `CURRENT_DIRECTION.md`，不改变任何冻结 cohort、揭盲门或 GPU 审批规则。核心裁决是：停止继续堆叠
同一语料上的微型事后审计，把未来 20 天集中到一条真正能抬高论文上限的确认链——**新配置可追溯语料上的
clean critic scaling + 冻结前瞻确认**；同时把已经足够强的数据集/审计资产写成论文。

## 当前起点与唯一关键阻塞

- 最新语料状态为 296 source archives、559 provisional first-960 runs；Target-522 结构目标已闭合，first-960 还差
  401 runs。
- 按学长所说的理想生产速度 60 runs/day，401 runs 的条件点估计是 6.683333 天；这不是进度保证，上传和
  eligible rate 都可能使其延长。
- `config-v2` canonical sidecar 文件名数仍为 0。学长分支 `dojo-reproduce` 仍停在
  `5baccb170ce287f9c8eed7b23ccf693a0268515a`，最近没有新的 outcome 文档。
- 连续 intake 的第二个 145-poll 周期已正常完成，并由结果前冻结的 v2 契约续接为 PID=`4181149`；首轮
  `rc=0`、独立 verifier PASS。该续接只恢复 CPU outcome-blind 摄取，不改变上述语料计数或任何科学协议。
- v11 历史 generator provenance 的 model-ID 轴已补齐：16,012/16,012 configured model ID、15,905 exact
  version-or-model；但 provider/contract 轴仍只有 9,901/16,012，不能把历史恢复当成新 producer 的 outcome-before
  config-v2 sidecar，也不能据此提前启动 clean scaling。
- 因而眼下最大风险不是模型不够大，而是未来 8 天继续生产的 runs 仍缺少 outcome-before config provenance，导致
  0.6B→8B scaling 再次被 cross-config mixing 否决。

必须尽快由学长 review/apply：
`phase1/upstream_patches/0001-Add-prospective-config-v2-producer-hook-18-tests.patch`，SHA-256=
`56a3e4b61918e1b06830712d418ed27ef5135017eab2b9e833b92c626054c9a5`；生产时显式设置
`DOJO_CONFIG_V2_SIDECAR=1` 和稳定、公开的 `DOJO_GENERATOR_RELEASE`。该补丁默认关闭、不输出环境 dump、凭据、
label 或 outcome，且已对学长当前 commit clean-apply 验证。若第 2 天仍未部署，clean scaling 主交付应立即标为
`SCHEDULE_AT_RISK`，不能事后回填 provenance。

## 20 天的四条并行线

### A. D0–D3：关闭结构门，不再改协议

1. 保持 intake、Target-300、Target-522、WL、receipt 与 config readiness 现有 watcher；只读 PID、锁、LATEST、hash
   和结构 marker。
2. Target-522 已按冻结 selection 闭合；Stage-A / contrast-rank v2 已 exact-commit/A-B/postflight 完成，但 frozen
   支持要求不足，正式为 `LIMITED_SUPPORT`，不得重选 cohort、改阈值或 rescue。
3. 不恢复旧 within/lineage/selective/yield/Probe/HCE/多保真/K≥1 路线，不为“再找一个小正数”改 cohort 或门。
4. 历史 Table 4A 已按 931-row exact-common-support UST formal 填入正文；旧 400-pair judge 报告因 endpoint-run
   聚类错误与证据绑定不足被排除。它关闭写作缺口，但不计作新的 predictor 正结果。

### B. D1–D9：让 first-960 真正可用于 clean confirmation

1. 每日核验新增 runs 是否带 canonical config-v2 sidecar；首个 sidecar 只停在 metadata redaction/review 门，不能因出现
   文件名就自动放行。
2. first-960 必须按预注册时间顺序闭合，并另有 accrual-closure receipt；1,500 structural pairs 仍只是一项支持门。
3. frozen cohort 闭合前不读 label/outcome/prediction values/accuracy/utility，不用周期 test 选 checkpoint。
4. transition、WL 与 prediction receipt 必须保持 append-only 和 exact-prefix；任一 hash 漂移或重复未知即 fail-closed。

### C. D7–D14：只在来源门通过后跑一次 clean scaling

候选矩阵固定为独立 critic（不是 agent 底座更新）：Qwen3 Base `0.6B/4B/8B × seeds 6/7`，共 6 个训练 run；
context、训练步数、optimizer、train/dev/frozen 划分、checkpoint rule 和 scorer 必须单旋钮一致。开始前另报每臂 GPU、
墙钟 hard cap、总 GPU·h 和 checkpoint/resume 方案，由用户明确批准。禁止周期访问 frozen/test；checkpoint 只能由
train-run dev 选择，最终 frozen cohort 一次性评估。

该矩阵已经由 `phase1/critic_scaling_confirmation_contract_v2.json` 锁定（SHA-256=
`c64ab02a20066a9d282de8b3d5a803838e3637e33dd39b53600b52b1dd277642`，实现 commit=
`977e06aae6812c4fb30555184ccd9fcebadb33fb`）。历史 v1 的 0.6B/1.7B/4B/8B 八-run 契约只保留兼容，不再用于新训练。
fresh exact-checkout 已通过 focused/full=`31/2,074` tests、0 failures；这不授权 GPU 或 frozen access。

来源 lock 必须在结果前同时给出 100% canonical config-v2 sidecar coverage、sidecar-manifest SHA-256、稳定 public
generator release、exact generator/config stratum、outcome-before attestation 和 `historical_backfill_used=false`；
producer 与独立 verifier 任一不满足即 fail-closed。

预先固定最小可写结论：

- primary：三点两-seed task-macro 均值单调不降，平均 `8B−0.6B≥0.02`，每个 seed 的差都为正，task-bootstrap
  95% CI 下界为正，所有 high-low LOTO 差为正，且删除按 primary pair 数预先定义的主导任务后仍为正。
- secondary：完整 size curve、TF-IDF/static baselines、初始化成本与单次 query 成本同表；accuracy 与部署收益分开。
- robustness：主导任务按 pair 数最大、task ID 字典序破平，另报 task-macro 与 pair-micro、固定 gap buckets、
  coverage/tie/missingness；这些 secondary view 不得 rescue primary。
- 若 primary 不过，不加 seed、不换切分、不删任务救结果；论文仍按数据集与 benchmark-audit 主线推进。

### D. D0–D20：立即转入论文生产

1. D0–D4：锁定贡献表、数据卡、审计撤回表和 related-work matrix；Evidence Index v10 是唯一 claim ledger。
2. D4–D10：完成方法/语料构建/评测协议初稿与主表占位，Target-522/first-960 只填冻结槽位，不提前揭盲。
3. D10–D16：若 clean scaling 获批并完成，加入 capacity confirmation；否则明确降为 future work，不拖延论文容器。
4. D16–D20：完成完整初稿、可复现说明、limitations、伦理/许可/data statement 与学长内部审稿版。

从现在起，新的 CPU-only audit 只有在它能关闭以下任一 blocker 时才做：数据可发布性、split/label 完整性、claim
去重、前瞻 cohort closure 或 clean scaling provenance。仅重新组合已发布 aggregate 的分析必须标
`counts_as_distinct_claim_evidence=false`。

## 防 scoop 后的准确定位

不能再宣称“首次从树训练 critic”“首次 sibling/parent pairwise RM”或“首次用 critic 引导代码树搜索”：

- [AgentRM](https://arxiv.org/abs/2502.18407) 已从 MCTS 树训练 reward model，并用 Best-of-N/beam search 引导 agent；
- [Step-Level Q-Value Models](https://arxiv.org/abs/2409.09345) 已用 MCTS preference 与 step-level DPO 训练 Q 模型；
- NeurIPS 2025 [ReLoc](https://arxiv.org/abs/2508.07434) 更直接从 code revision tree 的 parent/sibling 局部对训练
  Bradley–Terry reward model，并用 revision distance 引导搜索；
- [SELA](https://arxiv.org/abs/2410.17238) 已把 MCTS tree search 用于自动机器学习 agent；
- [NAS-Bench-360](https://arxiv.org/abs/2110.05668) 说明多任务、预计算 benchmark 本身可以成为主要贡献。

我们当前可守住的差异是：**真实 MLE-agent 完整程序搜索轨迹的 audit-grade benchmark**，包含 physical-run-clean 与
temporal split、source observability、status-certified partial order、label repeatability/noise ceiling、clone/leakage
审计、query/init/execution 成本、append-only prospective cohort，以及同池 predictor suite。clean scaling 若确认，是这套
benchmark 上的强实证发现，不应包装成发明了 reward model。

## 20 天成功判据

- 最低成功：可发布 corpus/data card + audit protocol + 完整 predictor benchmark + 一份内部完整论文初稿。
- 目标成功：Target-522 冻结链完成，first-960 closure 完成，clean 0.6B→8B 两 seed primary 通过。
- 更高成功：在不改主协议的前提下，预先批准的 one-shot deployment/replay 证明 critic 提升固定预算下的真实搜索结果；
  此项必须另做功效与 GPU·时审批，不是本文件自动授权。
