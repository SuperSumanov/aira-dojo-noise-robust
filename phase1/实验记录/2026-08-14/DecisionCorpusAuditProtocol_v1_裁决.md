# Decision-Corpus Audit Protocol v1 裁决

日期：2026-08-14。性质：主线数据/评测资产，不是新的 critic 方法结果，也没有读取论文冻结集之外的
隐含 outcome。代码与结果位于 `phase1/decision_corpus_audit.py`、
`phase1/verify_decision_corpus_audit.py` 和
`phase1/results/decision_corpus_audit_v11_20260814/`。

## 1. 为什么需要这一项

最新直接竞品已经覆盖“大规模 MLE trajectory dataset”“执行前偏好预测”“轨迹诊断”和“replay
intervention”等宽主张。我方仍可防守的贡献不是数据条数本身，而是把真实搜索决策的 sampling unit、
choice set、有效支持、gap 分布和 prospective boundary 做成第三方可执行的 benchmark contract。

因此本轮没有再在同一 OOF 上调一个 critic，而是把以下最容易被审稿人质疑的事实一次性机读化：

1. endpoint 是否来自同一 physical run；
2. train/frozen 是否在 pair、endpoint、parent、run 四层都隔离；
3. parent graph 是否完整、候选是否被复用、有效 parent/run/task 到底有多少；
4. 固定 gap 桶及 `gap_raw < 1e-2` 难区占比；
5. 被裁剪 parent 是否被如实计数，而不是误当作新的 root 或静默丢弃。

## 2. 实现与失败关闭规则

- producer 只读取九个 v11 pair JSONL 与 `card_run_map.json`，不读取 code/observation/stdout/runtime；
- better/worse endpoint 必须都可映射且落在同一 physical run；
- parent 若存在于 run map，必须与 endpoints 同 run；若 parent 被裁剪而不存在，则计入
  `orphan_parent_choice_sets`，不伪造成根节点；
- 同一 pair set 内 reverse/duplicate pair、非有限 gap、错误 budget/split、混合 choice-set context 均失败关闭；
- 对每个共同 budget，train/frozen 的 unordered pair、endpoint、parent、run 任一交集非零，正式状态即失败；
- verifier 不 import producer，独立重读十个输入、核对 SHA-256 并重算所有发布 aggregate；篡改测试会失败。

跨平台复核附录：第一版卡片在 Windows `core.autocrlf=true` 工作树上记录了 raw-byte SHA，Linux
干净检出的 LF 文件因此会在进入统计前正确地 hash fail。统计结果没有变化，但该 hash contract 不可发布。
修正版冻结 `normalized_utf8_lf_v1`：只把 CRLF/CR 规范成 LF，同时保留文件是否有末尾换行；producer、
独立 verifier 与测试均按此规则重算。旧 raw-byte 卡片不再是正式 artifact。

聚焦测试结果为 `8 passed`。

## 3. v11 正式结果

正式状态为 `VERIFIED_DECISION_CORPUS_AUDIT`，独立状态为
`INDEPENDENTLY_VERIFIED_DECISION_CORPUS_AUDIT`；九个 pair sets、十个输入 hash 均通过。

| set | pairs | parents | endpoints | runs | tasks | gap<1e-2 | complete parents |
|---|---:|---:|---:|---:|---:|---:|---:|
| train:b0 | 4,263 | 2,293 | 5,499 | 333 | 23 | 1,849 (0.4337321135350692) | 2,259 |
| frozen:b0 | 1,498 | 845 | 2,022 | 92 | 22 | 751 (0.5013351134846462) | 805 |
| train:b1 | 861 | 597 | 1,325 | 140 | 22 | 470 (0.5458768873403019) | 594 |
| frozen:b1 | 323 | 229 | 507 | 42 | 20 | 214 (0.6625386996904025) | 224 |
| train:b2 | 692 | 466 | 1,044 | 105 | 21 | 408 (0.5895953757225434) | 464 |
| frozen:b2 | 265 | 180 | 404 | 27 | 17 | 183 (0.690566037735849) | 176 |

b0/b1/b2 的 train--frozen overlap 均为：pair=0、endpoint=0、parent=0、physical run=0。
extension 三组也被完整审计并单列在 audit card，不与 frozen headline 合并。

## 4. 正面含义与限制

正面含义有两点。第一，论文现在不仅能说“我们做了 run-clean split”，而能发布一个独立程序让第三方对
任意同类 decision corpus 复核四层隔离与实际 choice-set 支持。第二，冻结 b0 中难区占 50.1335%，明显
不是由任意全局配对得到的轻松样本；这与既有 pair-graph intervention 的 predictor-family 排名反转共同
构成 choice-set fidelity 的正结果链。

但本卡不声称所有 parent graph 完整：frozen b0 只有 805/845 完整，train b0 为 2,259/2,293；也不把
b1/b2 难区比例上升解释为因果效应，因为后续预算层受历史 continuation policy 的删失影响。本卡还没有
重算 regrade noise ceiling、部署 query/init cost 或 prospective activation；这三项继续引用各自独立
attestation，不能合并成一个“全都验证”的模糊主张。

## 5. 裁决

`Decision-Corpus Audit Protocol v1` 进入主线资产。它增强的是 NeurIPS D&B 式数据与评测协议贡献，
不自动解锁新的付费方法实验，也不改变 first-960 prospective confirmation 的冻结规则。下一步只做：

1. 将 label-noise、deployment contract、prospective boundary 作为有独立 hash 的外部 attestations 挂到
   audit-card schema，而不复制或偷换它们的 estimand；
2. 等 E1-Q 完整结束后，把 paired continuation label feasibility 作为可选扩展卡，不冒充主方法收益；
3. first-960 有新 physical runs 时按已冻结机制积累，不按 outcome 停止。

## 6. 后续 attestation 状态（2026-08-14）

label-quality 外部证据已由 `label_repeatability_attestation_v2` 完成，路径为
`phase1/results/label_repeatability_v2_20260814_4e3bebe/`。它不改写本 card 的 scope：
`recomputes_label_noise=false` 仍为真；二者是 hash 分离、estimand 分离的证据。v2 直接报告 repeat agreement，
只有在显式独立/可交换/对称误差模型下才给 inferred single-label quantity，并保留 10→22 task extrapolation。

deployment-cost 与 prospective boundary 仍是独立 attestation；前者尚未并入 release index，后者仍处于
`PROSPECTIVE_COHORT_COLLECTING`。不得因为 label-quality 已完成而把三项都写成“统一 card 已验证”。
