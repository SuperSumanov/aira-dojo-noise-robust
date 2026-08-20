# DecisionCorpusEvidenceIndex v1：五项正资产证据栈

日期：2026-08-20。该工作不新增科学 estimand，而是把当前最可守的五类证据按原始作用域与负边界绑定，防止写作
时把不同问题事后合并：`decision_corpus`、`label_repeatability`、`normalized_clone`、`deployment_cost`、
`prospective_gate`。

最终 index SHA-256=`cfbe749f84114a633d902a358f8ef8243c4c4fe71433961c94e18494ca93769d`，包含 5 个互异
estimands、15 个不重复 artifact paths。独立 verifier 不 import 任何 producer，逐文件核对 SHA，再验证 106 项
JSON 固定断言；本地和 Linux 输出逐字节一致。Linux 故障注入定向测试 `7/7`，phase1 全套 `455/455`。

当前状态有意固定为 `PROVISIONAL_EVIDENCE_STACK_AWAITING_FIRST960`：`estimands_merged=false`、
`prospective_outcomes_read=false`、`prospective_vault_open_allowed=false`、
`frozen_accuracy_computed_by_deployment_cost=false`、`release_complete=false`。因此它形成的是 D&B 投稿可用的
正资产骨架，不是完成的 release，也不会把 223/960 的前缀冒充前瞻效果。

这条叙事的正面价值在于同时回答五个 reviewer 问题：资源是否忠实于真实 sibling 决策、标签是否可重复、语料
是否由跨 run 浅层复制堆出、predictor 查询是否真的比执行便宜、未来确认是否结果盲。每项 `does_not_prove`
仍单独保留，尤其 AST coverage 强门失败、成本不等于准确率、first-960 未完成三项不得隐去。

产物：`phase1/results/decision_corpus_evidence_index_v1_20260820/`。
