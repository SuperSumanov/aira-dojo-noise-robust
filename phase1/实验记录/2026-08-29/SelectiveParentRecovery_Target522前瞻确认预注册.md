# Selective parent recovery：Target-522 不重叠前瞻确认预注册

本地日期：2026-08-29。冻结时间：`2026-08-28T16:10:51Z`。

## 1. 动机与唯一问题

snapshot 887 的正式时间切分已得到开发正结果：较早 290 个 runs 选出的 exact-Jaccard margin 阈值
`1006/16929`，在较晚 145 个不重叠 runs 上达到 `2684/2691` precision 与 `2691/2907` coverage，并通过全部冻结门。
但它仍是同一已披露 snapshot 内的 development split，不能称真正 prospective confirmation。

本协议只问一个更强的问题：**完全不再训练或选阈值，固定复用 `1006/16929`，能否在自动捕获的首次 Target-522
crossing 相对 887 新增的至少 87 个完整 physical runs 上继续达到高精度、有用覆盖、错误下降和跨 task/run 广度？**

## 2. 结果前冻结状态

在协议最终定稿前的结构巡检中：

- `LATEST=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`；
- Target-522 `READY/COMPLETE/FAILED_RC/candidate.tsv` 均不存在；
- 固定 selection PID `4047654` 存活；
- candidate identity、increment profile、任何 prospective label/outcome/prediction 均未读。

candidate 只能来自既有 hash-bound selection root
`/research/d7/spc/yzyang4/tree-within-stratum-forward-target522/latch-42f1044-after-887-v2` 的首次 observed crossing；
不接受调用者另选 snapshot，不允许读取 profile 后选择 overshoot。

## 3. 固定 population、规则与门

Primary population 只含 candidate 中 run_id 不在 887 的完整新增 physical runs；887 行不进入 estimand，也不能用累计人口
rescue。eligible child 必须满足：recorded parent 同在 increment、两端 fingerprint-valid、parent depth 恰为 child depth-1，
且完整 same-run exact-depth candidate set 至少有两个候选。recorded parent 不参与排名；top tie 一律拒绝。

规则完全固定：identifier-erased Python token 5-shingle、exact set Jaccard、unique top，且
`top_score-second_score >= 1006/16929`。未来数据不得重选阈值、重平衡/过滤任务、改变表示或调门。

硬支持要求：

- candidate total runs≥522、disjoint increment runs≥87、baseline 逐字节 append-only；
- fingerprint coverage≥99%、所有 fingerprint-eligible parent edge depth-consistent；
- ambiguous edges≥1,000、accepted edges≥500、wrong alternatives≥5,000；
- 可条件化 tasks≥8（每 task accepted≥20），runs≥60（每 run accepted≥5）。

最强分类要求：precision≥`49/50`、coverage≥`1/2`、selective error≤无 reject unique-top error 的一半；至少 3/4
可条件化 tasks 达 0.95 precision、3/4 runs 达 0.90，同时最大 accepted contribution share 不超过 task 2/5、run 1/5。
三个 wrong-parent 分母继续分别报告，禁止互换。

## 4. 解释边界

若全部通过，只允许称：固定 development threshold 在首次自动锁定的 disjoint future increment 上实现所报 precision、
coverage、error reduction 与 breadth，支持可选 `suggested_parent + confidence + provenance` 自审计层。

recorded parent 不是外部语义/因果真值；orphan 不在 primary；不申一般 selective classification、lineage inference 或
parentage verification novelty；不计算 predictor accuracy、effect 或 search utility，也不完成 first-960/closure。

## 5. 实现与复验合同

protocol / producer / 独立 verifier / test / runner / watcher SHA-256：

- `f3adc77b61a305f834f84df0e5668095f511de15d1c68d2d90ff0ef956c3228f`；
- `0704edfa2e8511c32ded328098f3617608f362552ac176b780691a11501130b7`；
- `0eaafbec14ff3058514d2d4236472f033c84c2a5476751657bf5dadca4d813c2`；
- `a74a5c2c37a60cecbe9123bf84dc7649bd9939bf07965ed4d3c87a44c28b4a13`；
- `bcedd747aec081627996cd5dfc43e21e84a5c0b7dbc13dd84e6bbb98752568e2`；
- `00bc65830edeb55d474777b025dbfeb5013f73972b2356db62088c92295b4986`。

producer A/B 与不导入新 producer 的 verifier A/B 各自必须逐字节一致；两边分别使用 producer/independent snapshot、
fingerprint 与 candidate/margin 重算。正式 runner 还要求 fresh detached worktree、focused/full tests、file/network trace、
凭据扫描与 immutable manifest。当前本地相关测试=`51 passed`；本机全套收集因缺少 scipy/sklearn 依赖而不能作为完整
回执，必须以远端固定 venv 的 fresh post-push 全套结果为准。GPU/API/model-fit/base-update=`0/0/0/0`。

## 6. Post-push 与 watcher 部署回执

公开 source commit 为 `349b9ca9ef84defd70e950d873564cbd8973c180`。fresh detached Linux 逐项复核 source hashes、
protocol dependencies、887 development package manifest 与 runner/watcher syntax；focused/full=`51/1456 passed`，
full 有 47 warnings，凭据文件名/内容命中=`0/0`，post-push manifest SHA-256=
`d9f094a562b0bad9b51dd80fbcc35c3d6eee06c562020d30b8b1fc9724c190b0`。

watcher 已上线到固定 root
`/research/d7/spc/yzyang4/tree-content-selective-parent-forward-target522/formal-monitor-349b9ca-target522-v1`。
`2026-08-28T16:18:01Z` 独立 postflight 确认 PID=`4119941` 存活、exclusive lock held、13/13 preflight PASS；
selection `READY/COMPLETE/candidate.tsv` 仍不存在，LATEST 仍为 887。deployment receipt manifest SHA-256=
`e067089795da56e2179320be1bbf310c4e6ecacb6667717614ddb429656fb844`。

因此协议与执行链已结果前就绪，但尚不存在 Target-522 scientific result；prospective values/raw archives 未读，
GPU/API/model-fit/base-update=`0/0/0/0`。
