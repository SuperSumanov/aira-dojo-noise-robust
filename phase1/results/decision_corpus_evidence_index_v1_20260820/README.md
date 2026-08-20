# Decision-Corpus evidence index v1

这是一个**临时、未完成**的五项证据索引，用哈希和机器可核断言把当前 D&B 数据资产证据绑在一起，同时禁止
把不同 estimand 合成一个夸大的总分。状态固定为 `PROVISIONAL_EVIDENCE_STACK_AWAITING_FIRST960`；前瞻
first-960 与独立 accrual closure 未完成前，`release_complete=false` 且不得打开结果保险库。

| 条目 | 当前正证据 | 必须同时披露的边界 |
|---|---|---|
| decision_corpus | 真实 sibling choice set、physical-run 结构与同预算 train/frozen 隔离经独立复核 | 不证明准确率、成本或前瞻泛化 |
| label_repeatability | 10 tasks 上 original vs first repeat ordering agreement=`0.9658601259529334` | transported ceiling 依赖明确模型假设，不是经验 predictor accuracy |
| normalized_clone | token 5,638/5,643、AST 5,488/5,643 覆盖内跨 run/跨任务重复端点均为 0 | AST coverage 强门失败；不排除 fuzzy/语义/训练污染 |
| deployment_cost | 18 fits、4,608 queries 的 A/B 正门与跨运行稳定性全部通过 | 不计算 frozen accuracy，不证明搜索收益或方法 novelty |
| prospective_gate | 当前 223/960 runs、1,473 pairs、25 tasks 的 outcome-blind 收据 | cohort 与 closure 未完成，前瞻效果仍未知 |

验证器不 import 各 producer，会从仓库根解析每个相对路径，逐文件核对 SHA-256，再验证 JSON 中的固定状态、
计数、通过门和负边界：

```bash
python phase1/verify_decision_corpus_evidence_index.py \
  --repo-root . \
  --index phase1/results/decision_corpus_evidence_index_v1_20260820/index.json \
  --out phase1/results/decision_corpus_evidence_index_v1_20260820/independent_verification.json
```

该索引的作用是形成一条可审计的正资产叙事：资源结构可信、标签次序高度可重复、浅层跨 run clone 未见、在线
查询相对执行足够便宜，并且未来前瞻裁决仍保持封存。它不替代各原始报告，也不能绕过 first-960 + closure 门。

真实索引含 5 个互异 estimands、15 份无重复路径的哈希绑定 artifacts；index SHA-256=
`cfbe749f84114a633d902a358f8ef8243c4c4fe71433961c94e18494ca93769d`。本地与 Linux 独立输出逐字节一致；
Linux 定向测试 `7 passed in 0.12s`，phase1 全套 `455 passed in 63.49s`。远端测试输出与 hash receipt 保存在
本目录的 `remote_*` 文件中。
