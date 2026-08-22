# Score-channel future truth-support gate：实现与验证

日期：2026-08-23。状态：`IMPLEMENTATION_VERIFIED_PRODUCTION_TRUTH_UNREAD`。

## 目的与边界

旧 120 秒 replay 在运行后才发现 158 个 selected parents 中 148 个真值全并列，primary common support 更是
0 个 non-tied parent。0DY 因此先冻结一个全新 temporal identity cohort，再决定是否值得申请 replay。本文只实现
cohort 闭合后的 CPU truth-support 资格门；没有读取生产 label/outcome、没有提交 GPU/API、没有训练模型，也没有
产生新的方法效果数字。

## 固定执行语义

1. 命令必须显式给出 frozen protocol SHA 和 closed-cohort summary SHA；cohort 不是
   `FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD` 时，在打开 label vault 前拒绝。
2. intake summary、安全字段、structural-pair SHA、label-vault SHA、run/task/drop 身份全部重新核对；structural
   siblings 必须构成完整 clique，每个 child 只能属于一个 parent。
3. parent eligibility 只要求至少两个 finite `graded` siblings。每 run 以
   `sha256(20260813|run_id|parent_id)` 排序，最多取两个；分数大小、`y_norm` 和 gap 均不参与选择。
4. 选择固定后才计算 `max(y_norm)-min(y_norm)`。任一 candidate 的 `y_norm` 缺失则整个 parent 记
   truth-unavailable，但仍保留原选择，不从该 run 补选第三个 parent。
5. 落盘 `selected_parents.jsonl` 只含身份、候选 ID 与 SHA；不写 `graded/y_norm/gap/winner`。summary 只写固定
   gap-bin、task counts 和四门聚合。
6. 四门仍是 frozen 的 non-tied parents≥80、含 non-tied 的 tasks≥8、dominant non-tied task share≤0.25、
   selected physical runs≥60。全过也只允许准备新的预算申请，`replay_submission_authorized=false`。

## 双实现与测试

`score_channel_future_truth_support.py` 是 producer；`verify_score_channel_future_truth_support.py` 不导入 producer，
独立重读 cohort/intake/pairs/vault，重建 SHA lottery、selected rows、gap bins、task balance 和最终状态。

8 个聚焦测试覆盖：四门精确边界 PASS；79 个 non-tied 时 KILL；missing `y_norm` 不重选；每 run 三 parent 时按
SHA 只取二；collecting cohort 在 vault 缺失情况下仍先因身份未闭合失败；双跑字节一致且不写 raw labels；篡改
selection 被独立 verifier 拒绝；verifier source 不依赖 producer module。

本地最终聚焦结果为 `8 passed in 0.69s`。GitHub 精确 commit
`9a4df02cd1f76cd6c62657d457ea5c4274ff1c38` 在远端 fresh no-smudge checkout 的结果为：

- 聚焦：`8 passed in 0.37s`；
- 全量 `phase1/tests/`：`766 passed, 33 warnings in 75.37s`；
- commit 精确一致、worktree clean、远端敏感文件名计数 0。

## 包装层纠错

三次非科学失败均保留：先是 nounset 与集群环境初始化顺序错误；随后 pytest 范围误写成整个 `phase1/`，收集了
两个需要命令行输入的历史分析脚本；再后遗漏正式 runner 的 BLAS/OpenMP 单线程限制，导致共享 CPU 过度并行，
故主动停止。最终只恢复既有正式环境约束与正确测试目录，没有更改 protocol、producer、verifier、fixture、门槛或
scientific input。它们不能被隐藏，也不能被计作 effect 失败或成功。

## 当前裁决

这项工作消除了“先花 GPU 再发现 truth support 为零”的流程风险，但本身不是正方法结论。production cohort 仍在
collecting；只有身份闭合后才能一次性运行本门。PASS 仍需另做 channel comparative-support 功效分析和精确 GPU
预算申请；KILL 则直接停止 score-channel replay，不换阈值、任务、parent 或 cap 追救。
