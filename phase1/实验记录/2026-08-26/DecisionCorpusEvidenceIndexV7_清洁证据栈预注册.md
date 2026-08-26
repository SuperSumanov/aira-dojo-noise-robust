# Decision Corpus Evidence Index v7：清洁证据栈预注册

冻结时间：2026-08-26T14:42:45+08:00。本文写在任何 v7 formal artifact 生成或提升之前；实现与合成/本地 smoke
可以先行，但正式件只能从随后公开的精确 source commit 在 fresh Linux worktree 中产生。

## 1. 为什么必须重建而不是修补 v6

旧 Decision Corpus Evidence Index v6 直接把已撤回的 prediction coverage matrix 作为第十项证据；该 matrix 实际打开
pair-prediction files、解析 prediction-derived fields 并聚合 tie/activation/eligibility，同时错误声明
`prediction_values_aggregated=false`。ABC crosswalk v1 又绑定 v6、该 matrix 和从 matrix 读取逐任务 counts 的 task-balance
guard v1。因此 v6 与 crosswalk v1 的受影响指针只能 historical-withdrawn，不能靠修改旧文件或复算相同数字恢复。

v7 必须从最后一个未受该事故影响的 v5 精确重建，且 formal file trace 中不得打开 v6、两套 withdrawn coverage matrix、
task-balance v1/forward v1 或 crosswalk v1。旧文件一律保留，不删除、不覆盖。

## 2. 冻结输入与五个 replacement entries

唯一基底为 `decision_corpus_evidence_index_v5_20260821/index.json`，normalized-LF SHA-256=
`4bff2b9fa48f2b530de886ab6b799011e8c4aa48ed378cdee0959c8b087a1627`。新增五项：

1. `evidence_provenance_repair`：绑定 immutable taint registry，明确哪些旧链撤回及“不追溯修复”；
2. `prediction_receipt_common_support`：只绑定 promoted-state/independent-verifier receipt，认证当前 2,755-pair support；
3. `structural_weighting_shift`：绑定 atlas 与 trajectory 的独立复核，保留 TV=0.337082500713674 的结构正资产及
   single-drop robustness 失败；
4. `opportunity_yield_aggregation_audit`：绑定 closure-time 两级聚合审计契约，不冒充已观察 effect；
5. `task_balance_structural_only_v2`：绑定 2,635→2,755、debt 657→645 的纯结构复算，同时保留 cap 与
   immediate-action adherence 失败。

这些数字均已为操作者所知；v7 是 evidence-provenance repair 与机器 claim-boundary 资产，不是 blind numerical discovery。

## 3. 允许与禁止的主张

允许：receipt-certified common support、结构 task-weight shift、opportunity-yield interpretation contract、
“task-balance debt improved but remains uncleared”、历史撤回链完整可审计。

禁止：orientation/tie/margin/activation 分布、predictor accuracy/effect/search utility、first-960 closure、robust magnitude、
producer compliance、causal acquisition effect、alternate weighting 挽救 primary、v1 provenance 已被追溯修复。

v7 formal 不得读取 prospective label/grade/outcome、prediction pair/value、raw archive payload；GPU/API/model-fit/
base-LLM update=`0/0/0/0`。

## 4. 正式矩阵与杀死条件

- builder A/B 独立进程，输出必须逐字节一致；
- non-importing verifier A/B 独立重建 v7，输出必须逐字节一致；
- entry/artifact/bound-file 数固定为 14/37/3，JSON assertions 固定为 434；
- v5 source、taint registry 与 11 个 replacement JSON 均做 normalized-LF SHA-256 和逐字段断言；
- source v6 或任一 forbidden artifact path 出现在 file trace、index evidence path 或 verifier receipt，立即失败；
- focused tests、完整 `phase1/tests`、13 项预检、clean worktree、credential scan、A/B comparison、manifest 任一失败，
  均不得写 `COMPLETE` 或提升结果；
- independent verifier 不得 import builder；历史文件不修改。

本地 smoke 在冻结前只确认实现可运行：`10 passed, 1 skipped`；该数字不是 formal evidence。正式结果无论通过或失败均须
记录，且不能据此新增 predictor/effect 主张。
