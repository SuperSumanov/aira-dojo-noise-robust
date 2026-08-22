# Score-channel future identifiability cohort：结果前冻结

日期：2026-08-23；UTC freeze=`2026-08-22T18:03:44Z`。状态：
`FROZEN_OUTCOME_UNREAD_WAITING_COHORT`。本协议只冻结 CPU truth-support 资格门，不授权任何 replay/GPU。
机器打印 protocol SHA-256=`54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d`。

## 1. 冻结时点

0821 的 12 个 archive 已被 inventory monitor 看见，但仍在 6 小时稳定门内：最近一轮为 archives=204、baseline=128、
ready=0、rejected=7、transactions=57、outcomes_read=false；scientific snapshot 未变。远端 `intakes/0821-*` 为空。
本轮只读取 path/size/mtime inventory，没有列 tar header，更没有打开 payload、journal、label、grade、code、stdout 或
submission。12 个初始 archive 的三元组已逐项写进机器协议。

## 2. 为什么不是再跑一次 120 秒

旧 cohort 的辨识漏斗为 158 structural → 10 truth-informative → external comparative 0 / stdout comparative 1 → paired
0。重复同一 cap 既没有功效，也会浪费 GPU。新 cohort 的第一问题只问：在完全新 temporal runs 中，是否存在足够多且
跨任务的 non-tied sibling decisions，值得设计 evaluator replay？没有先过这个 CPU 门，就不讨论模型或 cap。

## 3. 结果前固定 cohort

- 起点：archive mtime 严格晚于最后一个 0820 archive (`1787326374000000000` ns)，包含已绑定的全部 0821 初始包；
- 后续 archive 只按 `(mtime_ns, relative_path UTF-8 bytes)` 追加；
- 累计 accepted unique physical runs 首次达到 300 时，纳入使其越线的**完整 archive**后关闭；
- structural rejection 不计 run target，整包拒绝，不允许 filename 推断 task 或部分 salvage；
- 关闭条件不读 label/score，旧 archive/run 分配不得因扩语料重排。

每个 run 对 finite-graded structural parent 做固定 SHA lottery，最多 2 parent，seed=20260813；lottery 不读 score
magnitude。truth-informative 主定义固定为 sibling `y_norm` range>`1e-12`；同时完整报告固定 edges
`[0,1e-4,3e-4,1e-3,3e-3,1e-2,3e-2,1e-1,3e-1,∞)`，不在看结果后换阈值。

## 4. 资格门

只有以下四项同时满足，才允许准备另一个 GPU 申请：

1. non-tied selected parents≥80；
2. 至少 8 tasks 含 non-tied parent；
3. non-tied parent 的 dominant task share≤0.25；
4. selected physical runs≥60。

PASS 也不授权执行，只允许根据支持量做 effective channel coverage 功效分析、列精确 candidates×cap×shards×GPU·h，
再交用户批准。相同 120s 不自动恢复；若需要 pilot 选 cap，pilot 和 confirmation 必须 physical-run disjoint。

## 5. 13 项预飞映射

1. 旋钮从产物侧：cohort inventory、run count、parent lottery 与 gap bins 都必须写 receipt。
2. 新路径先便宜验证：只做 CPU producer×2/verifier×2；GPU=0。
3. 查重：run/card/parent identity 唯一，旧 assignment survival fail-closed。
4. 分布：逐 task/run 与完整 gap bins，禁止只报总 non-tie share。
5. 配平：≥8 tasks、dominant≤0.25；无模型 eval sampler。
6. 模型保存：无训练，N/A。
7. 泄漏：cohort closure/lottery 不用 label magnitude；raw label 不输出。
8. RNG：唯一 seed=20260813，SHA ordering；append 不重排旧项。
9. 密钥：每次 intake 仍先 credential scan；push 前两类 staged scan。
10. 墙钟：本阶段 GPU/API/model fit 均为 0。
11. 功效：80 个 non-tied 只是进入 replay 设计的最低支持，真正申请前还要按 channel comparative rate 重算。
12. 链 rc：intake/audit 任一步非零即停止，不能让坏产物进入下游。
13. 扩语料冻结抽签：按 archive 顺序整包追加，旧 run/parent assignment 不重排。

Selective labels/positivity 是已有统计学问题；本协议只构建 MLE-domain D&B integrity measurement，不申方法 novelty。

## 6. 推送后独立复验

commit `74e492027b95cd1e44f205f7705c00736d9740b5` 推送后，集群从 GitHub 精确 commit 建立 fresh
no-smudge worktree，未复用本地工作树。机器重新得到 protocol SHA-256=
`54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d`；focused test 为
`1 passed in 0.03s`，完整 phase1 suite 为 `748 passed, 33 warnings in 58.59s`。测试前后 worktree 均 clean，
回执文件名与高置信内容密钥扫描都为 0。只读回执已收入
`phase1/results/score_channel_future_identifiability_freeze_20260823/remote_verification_74e4920/`；其中
`SHA256SUMS` 文件自身 SHA-256=
`b05583c1f85f6e8fade8612365f37ce1763c046e3b6a21c2783519a694a9f86a`。
