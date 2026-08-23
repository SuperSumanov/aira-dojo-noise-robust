# Score-channel future 双 truth runner：闭合交付链

日期：2026-08-23。正式状态：`RUNNER_EXACT_COMMIT_VERIFIED_PRODUCTION_TRUTH_UNREAD`。

## 1. 为什么需要这一层

future identity cohort、原 `y_norm` truth-support gate 和 official-five-decimal raw-grade extension 已分别冻结并测试，
但此前没有一个生产 wrapper 把三者按唯一合法顺序绑定。若在 300-run 闭合时靠手工拼命令，可能漏跑 raw extension、
误用 collecting cohort、让 raw 结果覆盖 base status，或把 PASS 误当 replay 授权。

新增 `phase1/scripts/run_score_channel_future_dual_truth_20260823.sh`，只解决该交付风险，不改变 cohort、parent lottery、
truth 定义、阈值或科学主张。

## 2. 固定执行顺序与输入

runner 接受且仅接受 control commit、closed cohort directory、expected cohort-summary SHA。它在任何 production truth
模块前检查：

1. cohort 位于不可变 identity-cohort root，目录和三项科学文件均不是 symlink；
2. summary SHA 精确一致，状态为 `FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD`；
3. target=300、remaining=0、完整 boundary archive 已纳入、selected runs≥300；
4. label/score/truth/replay 四项 blindness 均为 false/false/false/false；
5. MLE-bench commit、`grade_helpers.py` 与六个 frozen protocol/implementation SHA 全部一致。

随后固定执行 base producer A/B、base independent verifier A/B、raw producer A/B、raw independent verifier A/B。
所有 replica 必须逐字节一致。raw producer/verifier重新构造 closed cohort、sibling clique 与 SHA lottery，同时要求 base
`selected_parents.jsonl` 字节级复用；它不能按 raw grade、`y_norm`、task 或结果重选 parent。

最终 `combined_decision.json` 只并列两个 estimand 的 aggregate status/counts/gates，写死：

- `base_status_overwritten_or_reversed=false`；
- `effect_claim_authorized=false`；
- `replay_submission_authorized=false`；
- `gpu_jobs_authorized=0`。

runner 不被 continuous intake monitor 引用，也不包含调度器/API 调用。

## 3. 13 项预飞

1. 当前方向仍是 future score-channel，未恢复旧 HCE/TD/probe；
2. 只回答 closed cohort 的双 truth support，不检验 channel effect；
3. sampling unit 是 base 固定选择的 physical sibling parent；
4. cohort/protocol/producer/verifier/grader 全部 SHA 绑定；
5. 两个 estimand 同 parent 集、各自门槛独立报告；
6. raw grade 只认证官方五位小数，不恢复 unrounded truth；
7. identity closure 必须先于 label open；
8. producer×2、verifier×2、字节 diff 和独立重建均须通过；
9. 输出 aggregate-only，不落 card-level grade/`y_norm`/gap/winner/code/stdout/submission；
10. file trace 明确禁止 tar payload、blind code、score directory 与 replay outcome；
11. 文件名和高置信内容凭据扫描均须为零；
12. single-thread CPU，GPU/API/model fit/base-LLM update=0/0/0/0；
13. 任一失败保留只读失败目录并停止，绝不自动 launch replay。

## 4. 验证与诚实失败记录

控制 commit：`b108fb8d4d9c04d52ccae1d71d6e3d8d867820b6`。runner/test SHA-256：

- `16cdcc4ac9957b0ef7143c0d0bbfc62244c3882bebb53c334a57568d11bcc29d`；
- `43b25106ede87c83f916ddfaf90f83a8055992e045ba0fd47ab7fe2234a37e53`。

fresh no-smudge Linux exact-commit 验证：

- shell syntax PASS；
- focused 23/23；
- full `phase1/tests` 880/880，33 warnings；
- 当前 33-run collecting receipt 负控 rc=1；
- `label_vault` file-open count=0；
- commit 文件名/高置信内容凭据扫描=0/0；
- worktree before/after clean；
- 远端 `SHA256SUMS` 自身 SHA-256=
  `5bf3b4dbd414e88d3696acb1a25ebb09924536a610ccbb1b236a05f2b0198b31`。

第一次 overlay 验收在科学 focused/full 已通过且 collecting guard 已拒绝后，外层 `label_open_count` 使用逐文件
`grep -c`，得到多行零并在整数比较处失败。失败目录保留；没有 production truth open。v2 只把包装统计改成先合并
命中再 `wc -l`，重新从新 worktree/新 output root 完整验证通过；正式证据只取 v2 与 exact-commit receipt。

## 5. 裁决

该交付链已经可以在 cohort 闭合后安全地运行双 truth CPU gate，但当前 cohort 仍 collecting，production truth 未打开。
它是完整性/可辨识性资产，不是方法正结果。达到 300 runs 后，先 formal closed identity receipt，再人工调用本 runner；
任何 PASS 只允许准备另名 replay 设计和预算申请，仍须用户批准后才能提交 GPU。
