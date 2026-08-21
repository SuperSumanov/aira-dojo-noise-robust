# Source Choice Materialization S0：执行前冻结

日期：2026-08-21。状态：`NOT RUN`。目标不是再训练 hurdle/listwise 模型，而是回答一个发布工程资格问题：
0DG 中 3,001 个 status-certified source winners，有多少同时具备全 source-set candidate code 的既有、已审计
可用性，足以物化成 run-clean 的 failure-aware source-choice benchmark？

## 两个冻结输入

1. 0DG `per_parent.csv`，SHA-256=
   `b2488d059ce4fafacc321e98fb4f4e82b5f0b4d4abc86a413d9e6f80da0cb4d4`。只读 role/task、
   run/parent hash、source/finite size、identity availability 和 winner-identified boolean；不含 raw ID 或 code。
2. 2026-08-15 hurdle 的纯结构 `construction_per_parent.csv`，SHA-256=
   `846da509373ee0d6bbb072f7fcc9f21dbcbda0ad5ced0355dabffa5e61975f67`。它在旧正式流程中已对 journal
   先整文件 credential scan，再核对缺失节点 code presence、retained-code hash、parent/status/journal provenance；
   本轮只读 role/task/run/parent/source-size/eligible/reason，不读旧模型结果、candidate score、utility 或 code。

完整 source parent（source size=finite size）按 v11 endpoint/card closure 记 code-complete；identity-available 的
incomplete parent 只有在固定 hurdle construction row 为 eligible 时才记 code-complete。其余一律 false。两表以
SHA-256(parent/run raw ID) 连接；context 或计数不闭合立即失败。

## 结果前材料门

- materializable certified winners≥2,800，且占全部 3,252 parents≥0.85；
- 占 3,001 certified winners 的 code-complete share≥0.90；
- train/frozen materializable winners≥1,900/700，且各自 certified-winner code coverage≥0.90；
- 有 materializable winner 的 tasks≥20，其中至少 15 个 task 各有≥20 groups；
- source size≥3 的 variable-arity groups share≥0.50；
- dominant-task share≤0.25；train/frozen parent-hash 与 run-hash overlap 均为 0。

任一门失败，禁止物化 source-choice benchmark，不降低阈值、不筛 task、不把 identity-unavailable 或 code-incomplete
parent 当完整输入。通过也只授权下一步生成 **answerability-conditioned** train inputs 与 sealed frozen evaluator；
不得恢复“整个 v11 是完整 choice-set dataset”，不得声称 listwise loss/metric novelty 或 predictor/search utility。

## 十三项 pre-flight

1. 方向：直接延伸 failure-aware Decision Corpus，不恢复旧 HCE/TD/probe/多保真。
2. 问题：已认证 source winner 是否可实际物化为全候选代码齐备的 benchmark group。
3. 输入：两份不可变 CSV 与协议 SHA；不读 raw tar/journal、cards/code、score 或 outcome。
4. 单位：parent group；headline 保持全部 3,252 与全部 3,001 certified winners 两个分母。
5. 已知：answerability 与旧 incomplete construction 各自计数已知；二者的 parent-level join/覆盖未计算。
6. 身份：只用 SHA-256 parent/run join，raw identity 不输出。
7. 标签：winner boolean 只作物化资格；不读取 winner candidate ID。
8. 支持：role/task/arity/concentration 与 split overlap 均预固定。
9. 推断：完整冻结语料的精确 census，不伪报 iid CI。
10. 复现：producer×2、独立 verifier×2、固定 commit、逐字节 diff 与输入/输出 manifest。
11. 安全：输入 parse 前 credential scan；禁止路径 syscall audit；输出无 code/raw ID。
12. 资源：single-thread CPU，GPU=0、API=0、底座更新=0，预计含全回归小于 30 分钟。
13. 停止：任何 hash/schema/join/上游固定计数/材料门失败都原样关闭；不得结果后 rescue。
