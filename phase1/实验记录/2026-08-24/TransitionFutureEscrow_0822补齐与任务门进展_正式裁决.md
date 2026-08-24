# Transition Future Escrow：0822 预测托管补齐与任务门进展

日期：2026-08-24
状态：`TRANSITION_ESCROW_INSUFFICIENT_FUTURE_SUPPORT`

## 1. 为什么需要本次动作

主 first-960 transaction 没有缺固定 scorer 预测。snapshot
`f109ac928ed076f83b651af3c4a98bccd11cf592a3c81da541f34f0d2b11d708` 的 score-registry validator 已覆盖：

- 74 accepted transactions / source archives；
- 9,992 eligible endpoints；
- 328 scoreable runs；
- 29 tasks；
- fixed scorer SHA-256=`c4b9713d5a994c90ac8e24674154ae78d39f7c7961473078c1c7d61ce1c15d23`；
- `labels_read=false`、`label_vault_opened=false`、outcome files 打开列表为空。

缺口发生在独立的 parent-relative transition future escrow。它的 monitor 已在
`2026-08-23T03:58:28Z` 按计划正常完成 145 polls，最后状态是 snapshot
`79701f90db165be0ee886a10cdb96737df90266b2923cbc9a279198f6362029c`。之后 0822 的六个 accepted archives
进入主 intake，但这条单列 prediction escrow 没有仍在运行的进程。由于协议是 append-only current-snapshot
重建，预测没有丢失且无需逐个补中间 snapshot；只要精确 prior rows 全部存活，即可从最后合法 artifact 直接续到
当前不可变 snapshot。

这项动作属于已激活的 0CP transition extension，不恢复旧 HCE、probe、多保真或 score-channel replay，也不改变
Decision Corpus + Predictor Benchmark 主线。

## 2. 结果前 preflight 与固定输入

本轮在任何新 prediction fit 前写入 13 项 preflight：

- science commit：`7458f0969b92a258ea0e495bbbee282aa12b748e`；
- monitor control commit：`ca8e000edb3138ec2a949b9d899ca9f255fb0ace`；
- monitor script SHA-256：`52df665581b31986bb9db0cb79458e69194d1e7398cbabcd409b6670c5ded154`，
  与此前 append receipts 中记录的脚本逐字节相同；
- activation：`2026-08-21T07:05:03.916471Z`；
- fixed model summary SHA-256：`7b32ddc85217245d65c767445439072e4dd08f4da88523ce5c52fc3156122bf3`；
- prior artifact：`20260822T212930Z_79701f90db16/artifact`；
- prior summary SHA-256：`55c295c511ef79e786eb8d33834c1d2fdda1254fff9a3d0174e417fac07c77b4`；
- current snapshot：`f109ac928ed076f83b651af3c4a98bccd11cf592a3c81da541f34f0d2b11d708`；
- 训练 reference 固定为既有 5,240 retrospective train+dev pairs；不新增训练数据或调参；
- 每个新 snapshot 只做 producer + independent verifier 共六次固定 HGB fit，单线程 CPU；
- GPU=0、API=0、base-LLM update=0；
- prospective vault/score/grade/outcome 路径禁止传入，strace 与 credential scan 必须为零；
- 任一 source/hash/prior-survival/refit/trace/credential 门失败即停止，不自动 retry。

本轮初始 append 预计 4--6 分钟，实际从 `2026-08-24T11:10:32Z` 到 `11:14:32Z` 完成。monitor 随后继续
145×300 秒轮询；只有 LATEST 改变时才重复固定 append，未改变时不 fit。

## 3. 正式输出与独立复核

只读产物：

`/research/d7/spc/yzyang4/transition-future-escrow/7458f09-append/20260824T111032Z_f109ac928ed0`

正式完整性结果：

- producer rc=0，输出 2,589 pairs；
- verifier rc=0，`producer_imported=false`；
- maximum training-reference difference=0.0；
- maximum future-margin difference=0.0；
- prior 2,426 rows `survival_exact=true`；
- prospective forbidden-path hits=0；
- credential-shape artifact-file hits=0；
- effect metrics=`[]`，prospective outcomes read=false；
- 递归 writable files=0；exact science worktree 前后 clean；
- `output_manifest.sha256` 中全部条目独立 `sha256sum -c` 为 `OK`；
- artifact summary SHA-256=`da62681ed53835de40a9a3dda583e589e05aef7c5bd1d602cc556b78c851d5cf`；
- `output_manifest.sha256` 文件 SHA-256=
  `dc37d5a2b11f1726ae1b5e08cd14fc87d6407dfe2eb23fb9625e8bc3302d46ae`。

monitor 只有在 producer、independent verifier、append survival、trace、credential 和 manifest 全部通过后，才把
state 原子前移到 `f109ac...`。当前 monitor PID 1885182 在首次 append 后继续存活。

本机 precommit 的六组 intake/cohort tests 为 39 passed。加入 transition producer tests 的联合命令在 test
collection 阶段因本机 Python 3.13 环境没有 `scikit-learn` 而退出，未执行；把不依赖它的 support/WL tests 分开后
为 9 passed，另 1 项在进入 fit 时因本机缺 `scipy` 失败。这两条都按环境失败保留，不计作代码反例或通过数，也不以
skip/安装临时依赖追认。push 前必须在集群冻结 venv 的 fresh exact-commit worktree 上重跑完整相关 tests 与全量
`phase1/tests`。

## 4. 支持门的精确变化

| 结果盲结构量 | 旧 `79701f...` | 新 `f109ac...` | 当前门 |
|---|---:|---:|---|
| strict post-activation pairs | 254 | 417 | 描述性 |
| eligible pairs | 222 | 363 | ≥1,500：FAIL |
| eligible physical runs | 28 | 45 | ≥150：FAIL |
| eligible tasks | 11 | 16 | ≥15：**PASS** |
| strict parent-source coverage | 0.8779527559055118 | 0.8776978417266187 | ≥0.80：PASS |
| strict training endpoint overlap | 0 | 0 | =0：PASS |
| strict training run overlap | 0 | 0 | =0：PASS |
| eligible training code overlap | 0 | 0 | =0：PASS |
| dominant eligible-pair task share | 0.481981981981982 | 0.29476584022038566 | ≤0.25：FAIL |

旧 2,172 support-only pairs 保持不变；新 snapshot 的 strict run stratum 为 53 runs，其中完整满足 parent/source/
finite/non-tie 的 eligible runs 为 45。这里的 53 与独立 target-300 identity cohort 的 53 不得因为数字相同而混称：
两者激活边界、单位、筛选和 estimand 不同。

任务数门从 FAIL 变为 PASS 是一项真实的正向**结构支持**进展：新语料确实扩大了严格未来任务覆盖，而不是只增加
同一任务的重复 pair。它仍不是模型效果，因为 accuracy、label、outcome、CI 与 search utility 全部未计算。

## 5. 科学裁决与下一步

正式状态必须保持 `TRANSITION_ESCROW_INSUFFICIENT_FUTURE_SUPPORT`。原因不是任务数，而是另外三道预注册门仍失败：

1. eligible pairs 363 < 1,500；
2. eligible runs 45 < 150；
3. dominant eligible-pair task share=`0.29476584022038566`，仍 >0.25。

结果后、仅结构的双实现审计进一步确认：旧→新新增 141 个 eligible pairs 时，旧主导任务计数保持 107 不变，
所以其占比从 `0.481981981981982` 下降到 `0.29476584022038566`；在主导计数不再增长的条件下，算术上还需至少
65 个非主导 eligible pairs 才到 0.25。该 65 不是 ETA、生产预测或功效保证，完整失败记录与边界见
`TransitionFutureEscrow_任务集中度趋势_结构审计.md`。

不能因为 15-task 门已过而提前读取 outcome，也不能修改 dominant threshold、过滤主导任务、按当前 task 分布改变
生产策略后仍称原始自然时间外估计。合法动作只有继续 outcome-blind 自然摄取与 append-only prediction escrow；
所有门同时过后，才允许按 0CP 已冻结统计一次性揭盲。即使未来为正，也只能称 parent-relative transition candidate
在严格时间外 MLE sibling population 上通过，不能自动授权 replay/GPU 或取代 first-960 primary。
