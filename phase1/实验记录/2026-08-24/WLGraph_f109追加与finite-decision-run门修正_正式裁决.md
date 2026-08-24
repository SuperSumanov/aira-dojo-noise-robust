# WLGraph f109 追加与 finite-decision-run 门修正：正式裁决

日期：2026-08-24

状态：`PREDICTION_ESCROW_COMPLETE / FINITE_DECISION_RUN_GATE_CORRECTED / NO_EFFECT_UNLOCK`

## 1. 结论

固定四臂 WL/graph predictor 已从 0819 的不可变 snapshot `83ab1d...` 结果盲追加到当前 first-960
snapshot `f109ac...`。总托管量从 6,471 endpoints / 249 runs / 1,665 canonical sibling pairs 增至
9,992 endpoints / 328 runs / 2,589 pairs；旧 endpoint 与 pair rows 均逐字段完全保留。新增量为
3,521 endpoints / 79 endpoint-bearing runs / 924 pairs，且全部属于自动 activation receipt 之后按
`generation_started_at_utc` 定义的 strict stratum。

这使 WL extension 首次从 `strict=0` 进入真实未来支持，但**没有解锁效果分析**。修正后的严格支持为：

- 3,521 endpoints，覆盖 79 个 endpoint-bearing runs、17 个 endpoint tasks；
- 924 finite sibling pairs，实际来自 76 个 finite-decision runs、17 个 pair-contributing tasks；
- 主导任务 `osic-pulmonary-fibrosis-progression` 为 545/924，share=
  `0.5898268398268398`。

预注册资格门因此为：pairs `924<1500`（FAIL）、finite-decision runs `76<150`（FAIL）、tasks
`17>=15`（PASS）、dominant share `0.5898268398268398>0.25`（FAIL）。在主导计数固定为 545 的纯条件算术下，
还需 1,256 个非主导 pairs 才能使总数达到 2,180、share 恰为 0.25；pair/run 最低门本身分别还差 576/74。
这些只是确定性缺口，不是生产配额、功效保证或改变学长数据生成分布的授权。

first-960 当前仍为 328/960 且 accrual closure 未提供，所以即便上述四门以后全部通过，也不得自动打开 outcome。
target-300 identity cohort 是另一 estimand，不能与本 strict WL cohort 混池。

## 2. 发现并修正的 gate 口径 bug

初始 append receipt 把 `strict_post_activation_inventory.runs` 从 strict endpoint rows 取唯一 run，得到 79。
但 2026-08-20/21 的预注册文字明确要求 150 个 **finite-decision runs**；有 endpoint 而没有任何 canonical
sibling pair 的 run 不应增加效果资格。独立 stdlib parser 找到 3 个这种 run，因此实际 pair-contributing runs=76。

科学预测产物没有错误，四臂分数也没有改变；错误只在结果盲 gate bookkeeping。修复 commit
`c29bcde1a6a3c402e6f7be1b33144348a98d8c03` 做了唯一语义改动：

- `runs/tasks` 改由 strict pair rows 统计；
- 新增 `endpoint_runs/endpoint_tasks` 保留覆盖描述；
- 新增攻击测试：一个 strict endpoint-only run 可以增加 endpoint coverage，但不能增加 finite-decision run/task gate。

旧只读 receipt 继续保留原始 79，不回写；其 gate 本来已经因 pairs/runs/dominance 失败，所以裁决没有从 PASS 变
FAIL，但其中 run 数字段由本修正 receipt 正式 supersede。后续所有 WL gate 必须使用修正后的 pair-contributing 口径。

发现链也原样保留：第一次 postflight 独立脚本先假设 pair-contributing runs 应等于 receipt 的 79，随后在 assertion
处 fail closed；失败 root
`/research/d7/spc/yzyang4/wl-graph-escrow-postflight/5826ef7-f109ac928ed0-v1` 未写 COMPLETE、未读 outcome。
正是该失败促使我们拆分 endpoint coverage 与 finite-decision support；没有删除或覆盖失败证据。

## 3. 固定 scorer 与执行证据

科学 scorer 未重拟合、未换 arm：

- scorer commit：`031edb34400781ca026bc9833ac7f850312ffb1c`；
- 四臂：`step_only_lr`、`wl_graph_lr`、`wl_graph_static_lr`、
  `wl_graph_static_tfidf_lr`；
- bundle SHA-256：`df02cd1f5ba74be6b171ee9c377eeb58cf209a310a470b2ade671f2db03ee19e`；
- activation receipt SHA-256：
  `0139670acc49c961e38e6851d0416d1e5bfa1c318024b50330c15d51823112fb`。

正式 producer 用时 17:43.80，独立 verifier 用时 16:38.10；两者均 CPU 单线程，GPU/API/base-LLM update=
0/0/0。四臂逐 endpoint 独立复算最大绝对差全部为 0.0。graph view 对 9,992 endpoints 全覆盖：9,790
`python_ast`、195 `python_token_sequence_graph`、7 `raw_line_sequence_graph`，其中 177 达到 8,192-node cap；
这些是覆盖诊断，不是效果。

安全与复现：

- 初始 WL 聚焦测试 19/19；gate 修复后 Linux 聚焦 20/20、完整 phase1
  `964 passed, 47 warnings in 68.05s`；
- producer/verifier 共 18,328 条 syscall trace，forbidden-path hits=0；显式 network syscall count=0；
- 11 个敏感输出共 11,316,324 bytes 的 high-confidence credential scan matches=0；
- 初始 artifact `SHA256SUMS` 自身 SHA-256=
  `1125d48a4a787b2732d5142fff649c41615f8e82c485b14bf84ec84e9f96ca53`；
- artifact summary SHA-256=
  `1370533dfc808ea8f2f6891d544c2ccfd460a503c5f535e4b6fe078eb9ba94ff`；
- 修正 receipt SHA-256=
  `4c239726c58c2160433cc45131fa9341f62c9979e62ec7ffa6983efa4a84c315`；
- 修正 prepush receipt `SHA256SUMS` 自身 SHA-256=
  `5a1a86c6171b346683d65f3d908c1f0f08d09f2a09d61239a743cdd7385145ce`。

正式只读产物：

- prediction escrow：
  `/research/d7/spc/yzyang4/wl-graph-escrow-current/5826ef7-f109ac928ed0-v1`；
- corrected gate prepush：
  `/research/d7/spc/yzyang4/prepush-wl-finite-decision-run-gate/c29bcde-v1`。

## 4. 允许的下一步

1. 继续 append-only、outcome-blind 摄取；新 snapshot 到来时只续写固定四臂 prediction escrow。
2. WL 效果只有在 first-960+closure 与修正后的四项 strict gate 同时满足后，才可另做一次揭盲授权审查。
3. 不针对当前 0.5898 dominance 事后删 OSIC、重加权 gate、改 activation 或换 arm；任务分布只能靠自然未来
   accrual 改善，并同时保留未经筛选的完整前缀。
4. 本结果只支持“可复现的未来 prediction 资产与审计协议”，不支持 WL 优于 TF-IDF、accuracy、regret、search
   utility 或方法首创。
