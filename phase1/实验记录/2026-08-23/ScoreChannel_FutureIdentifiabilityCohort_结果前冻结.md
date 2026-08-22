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

## 7. Outcome-blind 闭合状态机

commit `53ce46f0be18f725987e6d0ce4d72df54ca8c0a9` 实现并 formal 验证了 archive→cohort 状态机。它从
content-addressed `LATEST/SHA256SUMS/transactions.jsonl`、`observations.json` 和已验收 intake 的
`summary.json/archive_manifest.tsv/source_provenance.json` 重建 cohort；不打开 tar payload、blind code、label vault、
score 目录或 outcome。顺序固定为 `(mtime_ns, relative_path UTF-8 bytes)`；只消费首个 unresolved archive 之前的
settled prefix，structural rejection 整包计 0 runs，累计首次≥300 时纳入完整 boundary archive。每次可选地绑定上一版
输出，旧 archives/runs 必须逐行 exact-prefix survival；上一版一旦 closed，后续运行必须逐行完全相同。

producer 与 verifier 没有互相 import；10 个新单元测试覆盖 collecting、完整 boundary、rejection、unresolved ordering
gap、跨包重复 physical run、append-only survival、产物篡改与真实 file-open trace。连同 protocol 测试，formal focused
为 `11 passed in 0.56s`；fresh no-smudge 完整 phase1 为 `758 passed, 33 warnings in 55.55s`。producer×2 与 verifier×2
逐字节一致，strace 中 raw tar / label vault / blind-code sidecar / score directory 的 forbidden open=0，文件名与内容密钥
扫描均为 0。

## 8. 首次 formal collecting 状态

UTC `2026-08-22T18:33:41Z` 的 hash-bound 状态为：

- source commit=`53ce46f0be18f725987e6d0ce4d72df54ca8c0a9`；
- production `LATEST`=`1151aef9524ac0730fb247256cc80fd7f5407d7c399f341e9524eebe784f7680`；
- observations SHA-256=`5efabfb25364afa0b18015b80fdfa8cf120005906932340d26bb4978f6e0823f`；
- observed future archives=12，future transactions=0，settled prefix=0；
- selected archives=0，selected physical runs=0/300，remaining=300；
- pending head=`0821/ranzcr-clip-catheter-line-classification-8seeds.tar.gz`；
- status=`FUTURE_COHORT_COLLECTING` / independent verifier=`PASS_COLLECTING_TRUTH_UNREAD`。

这里的 0 是 6 小时稳定门尚未到时的过程状态，不是 effect 的零值，不支持任何机制正/负结论。formal receipt 位于
`phase1/results/score_channel_future_identifiability_freeze_20260823/formal_identity_cohort_53ce46f/`；其
`SHA256SUMS` 文件自身 SHA-256=
`fefb6a767ebe77ce9232c1423212d8fe062340b6753ad4493f97301d62e3febe`。

诚实失败记录：前两次 wrapper 尝试均在科学 producer/verifier 成功后 fail-closed。`641bdd7` 因尾部要求外部可变
observation ledger 在验证结束后仍不变化而误杀（`LATEST` 未变；仅稳定观测计数更新）；`5b28dda` 因多份 strace 的
per-file `grep -c` 返回多行零，shell 无法作单整数比较。失败回执保留在远端只读目录
`.641bdd7-1151aef9524a-e6edcf2da374.tmp.1573050` 和
`.5b28dda-1151aef9524a-f3b1a47d7802.tmp.1574274`。修复只涉及回执绑定时点与计数汇总，没有改变 protocol、cohort
membership、阈值或禁读正则。

## 9. 首批 0821 append-only formal 更新

最早 archive 精确跨过 6 小时稳定门后，连续 monitor 原子提交 ranzcr；随后 tgs 也按既有时序自然提交。固定 commit
`74ffb87cb39e90062db6a4ace4e13cf1a12041f2` 的成功 formal run 在启动前绑定：

- production `LATEST`=`1ba24a32f72bd5447a03854c4ab33d141ac98f221e377fa19de8a1b9ca521935`；
- observations SHA-256=`cbded93bb9c740b8a11f07b348a25d83e5aea6ff13b6413b08b00f8c1591f9d8`；
- selected archives=2、unique physical runs=8/300、tasks=2、remaining=292；
- per-task runs：ranzcr=4、tgs=4；pending head=plant-pathology；
- status=`FUTURE_COHORT_COLLECTING`，独立 verifier=`PASS_COLLECTING_TRUTH_UNREAD`。

旧 0-run cohort 的 archive/run 前缀精确存活。producer×2、verifier×2 diff 均为空；focused=11/11、完整 phase1=
766/766；forbidden-open、文件名凭据、内容凭据均为 0，验证前后 production SHA 不变。summary SHA-256=
`a90b40236d67c41b4378f6ba6ada27defe1622c0f49534576fc2d492840976f9`，成功包 `SHA256SUMS` 文件 SHA-256=
`355d7964858a815e0d46661307e971c8193e2d414dc694eebd668e06962aebd8`。

第一次 formal wrapper 以 rc=2 失败：它把前一 formal 包装目录而非 `producer_a/` 科学产物目录传给
`--previous-dir`。11 个 focused 与 766 个 full tests 已通过，但 producer 在寻找前一 `summary.json` 时立即停止，
没有产物或 truth 读取。该次绑定一笔事务 `76b4d4...`；失败后 tgs 被生产 monitor 正常追加，所以 retry 输入自然前进为
两笔 `1ba24a...`。retry 重新绑定两笔状态，只改 previous-dir 层级与 worktree 名；commit、协议、排序、门槛不变。
失败暂存目录原样保留，不能误写成 scientific failure，也不能声称两次 transaction SHA 相同。

本地安全回执：
`phase1/results/score_channel_future_identifiability_freeze_20260823/formal_identity_cohort_74ffb87_first_0821/`。
