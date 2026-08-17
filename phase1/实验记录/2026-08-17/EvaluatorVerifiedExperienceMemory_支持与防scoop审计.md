# Evaluator-Verified Experience Memory：支持度与防 scoop 审计

日期：2026-08-17。状态：并行 CPU 审计；不改变 `CURRENT_DIRECTION.md` 的唯一 score-channel 主实验，
不授权 GPU/API。前瞻 label vault 与 replay outcome 未读。

## 1. 结论先行

“固定底座权重、让 harness 从历史经验中持续进化”本身已经不是安全的新颖性主张。当前仍值得推进的窄方向是：

> 在真实 MLE-agent 搜索中，把 physical-run-clean 的成功代码、生成但执行失败的 sibling 身份、可信外部
> evaluator 的评分可观测性，以及任务原生 artifact contract 组成一个可审计的经验资源；随后只在全新
> task/seed 上检验该资源是否提高早期 pristine-score coverage，而不损伤完整预算质量。

这条线的独特性若成立，来自 **MLE 的可信 evaluator、选择性评分缺失和 source-opportunity provenance 的组合**，
不是 memory、retrieval、self-evolution 或 fixed-weight harness 这些已有原语。

现有 v11 足以支持一个同任务 memory baseline，但不足以支持未见任务的通用方法主张。下一步应先补齐
outcome-blind artifact contract 和安全失败类别，再决定是否做三臂因果 A/B；不能现在直接跑一个“memory prompt”
并把正数解释成 learned harness。

## 2. 冻结排除与支持度审计

审计实现：`phase1/audit_experience_memory_support.py`；完整机读结果：
`phase1/results/experience_memory_support_v11_20260817/audit.json`。脚本先把三份
`decision_clean_b0/b1/b2.jsonl` 的全部 `intask_split=test` endpoint 映射到 physical run，再排除这些 run
中的所有卡片。它不把只删 endpoint 当成防泄漏。

| 项目 | 精确结果 | 允许的解释 |
|---|---:|---|
| frozen decision rows | 2,087 | 三份文件全部为冻结 test |
| frozen endpoints / runs / tasks | 2,030 / 92 / 22 | 整 run 排除单位已确定 |
| memory overlap | card=0；run=0；非空代码 SHA=0 | 没有三种直接交集 |
| run-clean memory pool | 12,316 cards / 575 runs / 25 tasks | 有规模化成功经验候选 |
| 每 run 最优 finite-`y_norm` episode | 575 | `y_norm` 已按 metric direction 归一化 |
| 含静态 artifact-writer marker | 567/575=0.986087 | 仅静态规则，不冒充执行验证 |
| frozen tasks 有任意同任务 memory | 22/22 | 可做 seen-task baseline |
| frozen tasks 有至少 5 个 episode | 21/22=0.954545 | 大多数任务有重复支持 |
| 训练侧 missing identities 状态恢复 | 699/769=0.908973 | 可发布 coarse failure-status memory |
| 恢复状态中的 execution error | 691/699=0.988555 | 失败是核心数据，而非边角噪声 |
| 非平凡任务描述卡片 | 0 | 不能声称语义检索或 unseen-task transfer |

两次独立进程输出逐字节一致，结果 SHA256=
`769acc3d198dadb5643e3557f57c738967806546e212c258d0de51ad794a53f0`；合成聚焦测试 `1 passed`。
本地全套测试因环境缺 `scikit-learn` 在 collection 阶段中止；远端在精确 base commit
`858785fcdea77f2e4e1e8688970a0900a2917f36` 的一次性 clean worktree、既有实验环境中补入本轮两个文件后，
完整 `phase1/tests` 为 `340 passed in 34.18s`，且 worktree 已验证清理。

## 3. 防 scoop：哪些宽主张已经关闭

| 一手工作 | 已覆盖 | 对我方的直接约束 |
|---|---|---|
| [Argus, arXiv:2608.05144](https://arxiv.org/abs/2608.05144) | 固定权重、自进化 runtime、持久 memory/skills/procedures/verifiers/routing/rejected routes，并用 task-native verification 审核经验 | 不得声称“首个 fixed-weight self-evolving harness”或把 durable verified memory 当新原语 |
| [Reasoning as Gradient / Gome, arXiv:2603.01692](https://arxiv.org/abs/2603.01692) | MLE-agent 中以 success memory 作 momentum、以结构化诊断替代纯 tree search | 不得声称“首次把 MLE 成功经验反馈给后续搜索” |
| [Retrieval-Augmented LLM Agents, arXiv:2603.18272](https://arxiv.org/abs/2603.18272) | 系统研究 trajectory storage/query/selection 与经验检索；也指出 training-free retrieval 可能弱于监督基线 | 不能把简单 few-shot retrieval 的正数直接解释成稳健泛化 |
| [Router-Mem, arXiv:2608.01285](https://arxiv.org/abs/2608.01285) | evidence-conditioned memory sufficiency router 与渐进执行/延迟节省 | “根据经验决定是否继续执行”也不是独占原语 |

截至本次一手检索，未发现一篇同时公开覆盖以下组合：真实 MLE sibling source opportunity、physical-run
隔离、生成但失败节点、pristine evaluator 的 score missingness、以及机制冻结后的 prospective replication。
这是一条可防守的组合边界，不写成绝对“无人做过”。

## 4. 最可能产生正结果的同步路线

### P0：Score-Channel Audit Card（立即、0 GPU/API）

把当前 `C(tau)` 覆盖、`V(tau)` 条件评分价值、`U(tau)` 部署效用、failure-censor status、choice-set
完整性、physical provenance、noise ceiling 和 query/init cost 固定成 machine-readable release card。
这是 D&B 论文的稳贡献，即使后续方法收益一般也成立；它不与前瞻确认争夺 alpha。

### P1：Verified Success/Failure Memory 数据资产（立即、CPU-only，先不过 raw outcome）

分成三层，禁止混成一个模糊 memory blob：

1. `SUCCESS_EPISODE`：只收 official finite `y_norm`、整 run 排除后的 episode；保留 task/run/lineage/hash，
   不把 frozen endpoint 放入 memory。
2. `FAILURE_STATUS`：先只发布既有 `EXECUTION_ERROR` / `OFFICIAL_GRADE_ABSENT` / `UNKNOWN`；若扩展错误类别，
   必须在看分布前冻结 taxonomy，先做凭据扫描，永不输出原始 exception/stdout/code/path。
3. `ARTIFACT_CONTRACT`：只从公开任务说明和 public `sample_submission` 元数据提取列名、dtype、行数、ID
   对齐规则与 metric direction；禁止读私有标签或把 competition test label 当 orchestrator 可见信息。

这三层可以成为“有成功也有失败”的搜索树发布资产，比只发布 12,309 个有限分数卡片更完整；但资产构建本身
仍不证明方法有效。

2026-08-17 的 public artifact-contract 资格审计已经补上第三层的可用性证据：25 个任务中 20 个有 public
contract/description；结果前冻结的 header/type 异质性门以 19 个 signatures、dominant share=0.10 和三类
width buckets 全部出现而通过。结果后去列名压力检查仍有 17 个 signatures，但 16/20 为两列，因此只允许
“列语义/类型非平凡”的窄主张。直接证据见
`phase1/results/public_artifact_contract_support_20260817/README.md`。

### P2：三臂因果 A/B（只在资格门全过后，暂不提交）

未来候选矩阵应为：

- `S`：标准 agent prompt；
- `C`：固定 artifact contract，其他全部相同；
- `M`：同一 contract + 预先冻结的 evaluator-verified memory retrieval。

`S→C` 只识别 contract；`C→M` 只识别 memory。三臂必须固定底座、operator、任务、seed、每任务 wall-clock、
API budget 和 pristine grader；底座不微调、不做 RL。主要指标是 120 秒 finite pristine-score coverage，
安全指标是 execution failure 不升、完整预算 grade 无方向性损害；按 task 与 physical run 聚类，不只报均值。

在以下资格门之前不冻结 run 数和 GPU·时，也不请求用户批准启动：

1. 当前 150-run score-channel 主实验通过资格门且其正向机制得到确认；
2. public artifact-contract manifest 通过 label/path/credential audit；
3. retrieval 在 task-held-out support audit 中不是退化为 task ID lookup；
4. 根据 pilot-free historical base rate 做功效分析，并给出确切矩阵、总 run 数和 GPU·时；
5. 全新 task/seed 与 memory/frozen eval 无 physical-run、card、代码哈希交集。

## 5. 当前裁决

1. 继续 outcome-blind monitor，150 前不读取 vault、不 replay；
2. 立即允许 P0 与 P1 的 CPU 数据契约/单测/预注册工作；
3. 不启动 P2，不花 DeepSeek/Qwen 余额，不提交 GPU；
4. 广义 learned harness novelty 正式放弃，论文主张收窄为 MLE evaluator-verified、failure-censored 的经验资源
   与评分通道机制；
5. 如果 P1 无法形成非平凡 task contract 或安全失败 taxonomy，就停在数据资产贡献，不用事后调 prompt 找正数。
