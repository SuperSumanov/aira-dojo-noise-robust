# Senior 0828 NEXT：防撞、硬约束与安全执行裁决

日期：2026-08-29（Asia/Hong_Kong）

主线：Decision Corpus + Predictor Benchmark + Audit Protocol

学长源提交：`f534114e60658043c07f7a15d6440492caffc8ad`

后续数据/上下文修复：`4b9e9725c7ad867d36ead698de0ebe5ae48b8a4f`、`30b396323f28064040bb0bdf9cccb198d676dd27`

## 1. outcome 中三项建议的裁决

### A. 用便宜强模型复核 reward/decision pair：保留，但先冻结诊断协议

这是当前可执行且与 predictor benchmark 直接相连的一项。它回答的是：在相同完整信息集、相同历史 pair、相同
双方向询问下，强 API evaluator 的可辨识性、顺序稳定性与成本如何；它不是新的 frozen test，也不能替代未来 cohort。

执行前固定：

- 两个 32-pair 历史 panel：`value_hardware_time` 与 verified direct-sibling decision；
- 4 个任务单位 gap 桶，每 panel 每桶 8 对；全局 endpoint-disjoint、每 physical run 最多 1 对、每 task 最多 4 对；
- 两个 endpoint 必须处于完全相同的 task、client、hardware、time limit 与 execution timeout stratum；
- 全 task 描述、真实资源约束与两份完整 code 原样输入，禁止截断；A/B 与 B/A 都问；
- provider 永远看不到 `better/worse`、grade、gap、pair 来源标签或已有 predictor 输出；
- reasoning 原始响应只保存在远端权限 0600 的 append-only 文件；Git 只进聚合回执；
- 请求固定 ZDR 与拒绝数据收集；不设 `max_tokens`；temperature=0、固定 seed；
- smoke 为 8 对 × 4 模型 × 2 方向，共 64 calls，硬停预算 2 USD；通过后完整阶段累计上限 10 USD；
- 本次只冻结和模拟验证，**尚未授权或发出任何付费请求**。真实调用另需一张包含模型、calls、最坏预算和账户
  guardrail 的 launch receipt。

### B. 在 2--3 个简单任务上微调 Qwen 生成器：按原提法拒绝

该提法会更新 agent 底座，直接违反项目一直有效的“不微调 / 不 RL-finetune agent 底座 LLM”硬约束，也会让当前
论文容器从数据集与 predictor benchmark 漂移到通用 self-improving agent。未经用户明确修改项目边界，不实现、不排队、
不借“demo”名义绕开。

允许的窄替代是：**固定 generator，只训练/使用独立 verifier 或轻量选择器，研究在相同执行预算下如何分配昂贵标签**。
这与 Decision Corpus 的真实用途一致：减少必须执行的候选，而不是把 verifier 变成底座更新信号。

### C. 比较 3×8 H200 RL trajectory 与强 API 模型：只接受脱敏导出

outcome 文档中存在带访问凭据的 W&B 链接。该凭据不得点击、复制、写入日志或用于自动访问；学长应撤销/轮换并清理
Git 历史。若要做 trajectory 审计，由学长导出脱敏后的 prompt、final answer、reward/metadata 与 run receipt 到受控目录，
再做结构与错误类型比较。原始私有 reasoning 不进入 Git，也不以隐藏 chain-of-thought 作为论文证据。

## 2. related-work 防撞结论

“generator 与 verifier 迭代产生数据并共同提升”不能作为广义 novelty：ACE、ReVeal、CURE、V-STaR 等已经覆盖
self-evolution、execution/self-verification、coder/tester co-evolution 与迭代 generator-verifier 训练。相关入口：

- ACE: <https://arxiv.org/abs/2605.16299>
- ReVeal: <https://arxiv.org/abs/2506.11442>
- CURE: <https://arxiv.org/abs/2506.03136>
- AlphaEvolve: <https://arxiv.org/abs/2506.13131>

因此本项目不宣称“首次让 generator/verifier 共同进化”。仍有空间的窄问题是：**面对昂贵、延迟且任务异质的真实
MLE execution labels，固定 generator 下 verifier 能否以可审计的方式提高 label efficiency，并在未触碰的外部 cohort 上确认。**
它必须落在完整成本账、run-clean split、pair relation certificate、noise ceiling 与 untouched confirmation 上，才是本项目
相对现有自演化工作的差异。

## 3. 当前可允许的正面主张与杀死条件

当前只允许提出待验证假设：完整 task/resource/code 信息可能让强 evaluator 在 verified pair 上提供比旧截断 judge 更稳定的
信号，并可据此改善固定生成器的标签分配效率。不能先写“API judge 有效”或“能提升搜索”。

杀死条件如下：

1. exact-stratum、direct-sibling、run/task breadth 或每桶 8 对不可同时满足：停止，不放宽选择规则；
2. smoke 出现输入/输出截断、隐私路由不满足、响应不可解析、成本账不闭合：停止，不进入 full；
3. A/B 顺序不一致或拒答严重：只能报可靠性失败，不从 reasoning 猜答案；
4. full 结果若没有 task/run-clustered 支持：不得用 call-level 样本量或挑模型救回；
5. 未经新的 GPU/API 成本批准，不启动 generator 微调、RL 或大规模调用。

## 4. 安全回执

- 用户提供的 OpenRouter 凭据没有写入本地文件、Git、命令、测试或日志；实现只允许从远端进程环境变量读取。
- 学长 outcome 中的 W&B 访问凭据没有使用或复述。
- prospective first-960 / Target-300 / Target-522 的 label、outcome、prediction、accuracy、utility 均未读取。
- 本次资源计数：GPU jobs=0，API calls=0，model fits=0，base-model updates=0。
