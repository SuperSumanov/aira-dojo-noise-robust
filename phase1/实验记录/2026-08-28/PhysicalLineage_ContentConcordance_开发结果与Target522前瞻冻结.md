# Physical lineage × content concordance：开发结果、防撞边界与 Target-522 前瞻冻结

日期：2026-08-28；协议冻结：`2026-08-28T14:30:00Z`

## 裁决

值得推进的正方向不是“代码相似图可以替代真实搜索树”，而是更精确的两段式结论：

1. 平面代码相似图与 physical parent graph 是不同测量对象；
2. 一旦给出真实的 physical run 与 tree depth，内容相似度可以对 recorded parent 做很强的、可独立复验的交叉认证。

这使 tree-native release 多出一项正资产：不仅保存 parent pointer，还能在不读 outcome 的条件下，用代码内容与结构元数据
互相校验，并对同层错误 parent substitution 做穷举负控。它是数据质量/谱系证书，不是 predictor effect 或新搜索算法。

## 887 development population：已见结果必须完整披露

固定 outcome-blind snapshot `887491a...` 有 11,906 endpoints；11,894 个可在
`python_token_identifier_erased_v1` 下 fingerprint。首轮 runner 因远端主工作树没有检出依赖模块而在 import 前
fail closed，未产生任何科学量；`explore-v2` 改用 commit `be91107...` 的 detached worktree，科学规则不变。

### 平面 pair graph

- within-run fingerprinted pairs：524,810；fingerprint-eligible physical parent edges：10,876；
- Jaccard≥`17/20`：precision=`5713/11421=0.5002189`，recall=`5713/10876=0.5252850`，
  F1=`11426/22297=0.5124456`；
- 即便在同一 population 上用真实 parent label 选择最优阈值，oracle max F1 也只有
  `11446/22315=0.5129285`，阈值为 `1301/1531≈0.8497714`。

这不否定 similarity landscape；它只说明 flat near-neighbor edge 不能被当成 physical parent edge。

### run + exact preceding depth 的 parent retrieval

10,876 条 fingerprint-eligible parent edges 全部满足 `parent.depth = child.depth - 1`。排除只有一个候选的 trivial case 后，
有 9,739 条 ambiguous edges：

- recorded parent 是 unique maximum-Jaccard candidate：`9196/9739=0.9442448`；
- 同一候选集 uniform random 期望约 `0.2996201`，unique-top lift 约 `+0.6446247`；
- 穷举 99,039 个非 parent 同层候选，只有 543 个会被误收为 unique top，false-acceptance=
  `543/99039=0.00548269`；
- 若每个 child 均匀替换一个错误 parent，期望误收约 `0.0104840`；
- task breadth：33 个 conditionable tasks 中 `33/33` 达到 0.85，`31/33` 达到 0.90；
- run breadth：394 个 conditionable runs 中 `377/394` 达到 0.85，`367/394` 达到 0.90；最大 task/run
  contribution share 分别约 0.2830/0.0717。

### 结构 ablation

- same run + any shallower depth：unique-top=`9137/10866=0.8408798`；
- same run、完全移除 depth：unique-top=`2633/5438=0.4841854`；其 33 个 conditionable tasks 中没有一个达到
  0.85，run median 约 0.5294；
- 因此高恢复率不是“同 run 的代码都很像”这一点单独造成的；明确 tree depth 对 parent disambiguation 有实质信息。

两个阶段都由不导入 producer 的独立实现逐字段复算：首份 aggregate/verification SHA-256 为
`36bf9db4...e6c5e1` / `b2ce6193...cd9f9`；扩展为 `893772da...96f42` /
`b83e03a1...eedd1`。两次均未读 label/outcome/prediction/raw senior archives；GPU/API/model-fit/base-update=
`0/0/0/0`。

## 直接相关工作边界

- [TraceGraph](https://arxiv.org/abs/2605.31308) 用 observable action-observation signature 与 mutual-kNN
  构建 shared decision landscape，并明确把 core/trap 定位为 outcome-informed descriptive overlays，而不是 blind
  predictor。它没有声称 similarity edge 是 physical lineage；本结果应写成二者互补，不能写成推翻 TraceGraph。
- [mle-traj-v3](https://huggingface.co/datasets/jerryyan/mle-traj-v3) 已同时发布 within-version、fork 与
  token-Jaccard code-sim edges，并按 `version > fork > code_sim` 选 canonical parent。因此不能申“首次联合 parent
  与 similarity graph”。可守差异是：我方针对自动 MLE search 的真实 physical parent，在结果盲、时间前瞻、完整
  candidate set 上做 exact corruption-control certificate，而不是用 similarity edge 构造 canonical lineage。
- [Graph of Trace](https://aclanthology.org/2026.acl-demo.29/) 已把 scientific-agent execution events 组织成实时
  directed graph；不能申“首次图结构记录 agent workflow”。
- [Tracing the Roots](https://arxiv.org/abs/2604.10480) 重建的是 post-training dataset 之间的文档级继承关系，
  不是单次 search run 内的 node parent pointer；仍关闭泛化的“data lineage 首创”措辞。
- Tree Training/TreePO/TreeAdv 等已覆盖 shared-prefix reuse 与 tree-aware credit；本线不申 tree learning 或
  weighting novelty。

## Target-522 不重叠前瞻确认

在 `2026-08-28T14:29:52Z` 立即复查：selection PID=`4047654`、锁有效、LATEST 仍为 887、435/522、
candidate=`none`。因此此时可以在任何 candidate identity 或 increment profile 出现前冻结新协议：
`phase1/tree_content_lineage_forward_target522_v1.json`。

Primary population 复用已经独立锁定的 Target-522 selection package，但只使用不在 887 中的完整 physical runs（至少 87）。
强 content-concordance 门固定为：exact-depth unique-top≥0.90、相对 uniform random lift≥0.50、穷举错误 parent
false-acceptance≤0.02；task/run 中至少 3/4 的 conditionable groups 达到 0.85，且贡献 share≤0.40/0.20。

最强 classification 还要求 hierarchy complementarity：no-depth unique-top≤0.70、exact-depth 比 no-depth 至少高 0.30、
flat pair oracle F1≤0.70。hard support 包含 fingerprint coverage≥0.99、eligible parent edges≥1,500、ambiguous
exact-depth edges≥1,000、wrong alternatives≥10,000、conditionable tasks/runs≥8/60，以及所有 eligible edge depth
一致。所有判定只用 exact fractions；decimal 只展示。

有序结果必须保留四档：最强 hierarchy-content certificate、只有 content concordance、低于强门、完整性失败。887
development 数值、shallower-depth sensitivity、累计 candidate 或替代阈值均不得 rescue future gate。

## 允许的论文措辞

若最强门在不重叠未来 increment 通过，只允许说：在固定 identifier-erased 表示下，真实 MLE search 的 recorded parent
与内容变化在 run/depth 条件下广泛一致，且同层错误 parent 很少被固定审计误收；去掉 hierarchy 后恢复显著下降，所以
physical tree 与 flat similarity landscape 是互补而非可互换的 release views。

不允许说：parent 是外部语义/因果真值、所有 learned/embedding reconstructor 都失败、首次提出 similarity graph、首次保存
agent tree、证明 predictor 更准、证明 search utility 提升，或结果已泛化到 first-960 closure 之外。

## 实现、推送与前瞻 watcher 回执

协议、producer、不导入 producer 的独立 verifier、攻击测试、formal runner 与 watcher 已由 exact commit
`bee9e97e839fb4ffa9867f00e026b052a0570662` 推送。fresh detached Linux 复验：focused=`34 passed in 1.63s`，完整
`phase1/tests=1438 passed, 47 warnings in 77.88s`；post-push manifest SHA-256=
`08e384b343fbca1da2ee6d9e17efa62bee1ffe591882ef94336669afdbb01109`。changed filename 与 boundary-aware
changed-blob credential hits=`0/0`；prospective label/grade/outcome/prediction、raw senior archive 均未读，
GPU/API/model-fit/base-update=`0/0/0/0`。

watcher root：
`/research/d7/spc/yzyang4/tree-content-lineage-forward-target522/formal-monitor-bee9e97-target522-v1`。独立部署
postflight 于 `2026-08-28T14:52:33Z` 验证 PID=`4087901` 存活、exclusive lock held、无
`FAILED_RC/READY/COMPLETE/TIMEOUT_RC/INTERRUPTED_RC`，且只观察 selection `COMPLETE` 的存在性，没有读取
candidate 或 profile。postflight manifest SHA-256=
`f1141aa784bf8873adf1a71edd1469280b25706d7a745618184eb50ad00070d4`。

首次外层 launcher 在 watcher 已启动后，把 Git fetch 写入 stderr 的两行正常进度提示当作非空错误，因此没有走完
launcher 自身的最终 postcheck。该事实与 stderr hash 已保留；它不是科学运行失败：watcher 源码与 runner 均重新绑定
exact git object、PID/lock/markers 已由独立 postflight 复验。为避免重复实例与选择时序扰动，没有重启 watcher。
截至本回执 selection 尚未闭合，因此仍没有真实 Target-522 classification。
