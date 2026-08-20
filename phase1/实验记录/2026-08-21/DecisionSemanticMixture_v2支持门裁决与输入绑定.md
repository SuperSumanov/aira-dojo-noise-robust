# Decision Semantic Mixture v2：exact-config 支持门裁决与输入绑定

日期：2026-08-21。状态：`V2_EXACT_CONFIG_SUPPORT_ELIGIBLE` / `V2_MODEL_INPUTS_BOUND_NOT_RUN`。

## 1. 资格门裁决

固定 support source commit 为 `21a4d4e4e81e780259fbf300112b561ae0fc1116`，学长数据 commit 为
`baf6bddefe62b769b2fab699ff5805dd627dc69f`。过滤器只比较 pair 两端的
`(task, client, hardware, time_limit, execution_timeout)`，不使用 `gap_raw` 数值、better/worse 方向、code、
label、model prediction、checkpoint 或 prospective vault。

| 子集 | raw train | eligible train | raw test | eligible test |
|---|---:|---:|---:|---:|
| merged | 5,596 | **5,240** | 960 | **931** |
| Draft | 3,552 | **3,196** | 343 | **314** |
| Improve | 2,044 | **2,044** | 617 | **617** |

共剔除 385/6,556=`0.0587248322147651`。385 对全部来自 Draft，且唯一失配字段/联合 pattern 都是
`hardware`；Improve 没有被过滤。eligible test 覆盖 28 tasks，其中 23 tasks 至少 10 pairs；最大任务 100/931=
`0.10741138560687433`。merged eligible 共 6,171 pairs / 6,067 endpoints / 651 physical runs / 2,181
`(task,parent)` keys / 160 exact-config strata；test 为 931 pairs / 1,346 endpoints / 140 runs / 550 parent keys。

事前固定的 10 个布尔门全部通过：merged、Draft、Improve 六个 train/test 数量门，20-task、15-supported-task、
dominant-share 与完整性门均为 true。filtered merged 是 Draft+Improve 的逐行 exact disjoint union；每对 exact config
且 task 一致；train/test endpoint overlap=0、physical-run overlap=0。

producer 双跑逐字节相同；不 import producer 的 verifier 双跑逐字节相同，所有独立检查通过；聚焦测试 11/11。
artifact filename/content credential scan 都为 0，GPU/API/model fit/checkpoint/base-LLM update/prospective outcome read
均为 0。

## 2. 绑定给 v2 模型的唯一输入

| role | SHA-256 | bytes | rows |
|---|---|---:|---:|
| cards | `5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb` | 604,190,866 | 31,742 cards |
| merged | `bd6551dfce85d83f9f59716a31a9d7ab88605d6a21f51b41eb28177a952f47d0` | 2,552,829 | 6,171 |
| Draft | `3ca77a18e224cacbb7f52121d6e8c2b66f17298c68dd06fbc42a14a238ad05b9` | 1,465,008 | 3,510 |
| Improve | `7aca481afda5317fe78a0ad52fc7488fceff7fde6531c74ebb718df9e3b6926e` | 1,087,821 | 2,661 |

同时绑定 support `summary.json` SHA=`fa838d852d0be10caeb5f64905e43ac170aa317d4727e66a03680fa5ee472b0a`
与 verifier SHA=`98dd01681b4fac444b14ff76fd835e4897a2da20897e817bdf6d83830e2c278a`。正式远端 bundle：

- `/research/d7/spc/yzyang4/decision-semantic-exact-config-support/21a4d4e-baf6bdd-v2.tar.gz`
- bytes=`965897`
- SHA-256=`ff5e2448a1222c4a59480ab8db638908b98d1d644ae9d6bf97f69cdddb11d986`

## 3. v2 模型协议保持不变

资格门通过只授权把上述三个 filtered pair 文件写入常量。表示、三个 heads、`0.5` mix、20k task/parent
bootstrap、六个 discovery 效果门、tie 规则和 retrospective 证据级别逐字沿用 v1 预注册；不重新选 C、词表、
截断、权重、任务或子集。正式矩阵仍为 producer×2 + 独立 full-refit verifier×2，共 12 个 LR fits，顺序单进程
CPU；GPU·时=0、API=0、底座更新=0。

通过只可能得到 `DISCOVERY_UNLOCK_FUTURE_CONFIRMATION`，不能成为确认性论文结果。相关工作边界已在读取 support
结果前冻结于 `DecisionSemanticRouting_防Scoop边界.md`：semantic/domain routing 与 MoE reward modeling 已有直接
先例，故即使为正也只作 MLE-agent benchmark diagnostic/baseline 与未来 cohort 候选，不申方法首创。

## 4. 工程失败链（不隐藏）

1. 第一次 launcher 手工抄错 source commit 全哈希，在 worktree 创建和数据读取前 fail-closed；无结果目录。
2. commit `8e229c7` 双跑开始后，在未读取数字时发现实现漏写预注册要求的 parent 支持描述；该 bundle 不追认为正式
   结果，补齐独立 pair/endpoint/run/task/parent/config-stratum 清单后另立 commit。
3. commit `21a4d4e` 的双 producer 与双 verifier 完成后，原 launcher 的 zero-match `grep` 在 `pipefail` 下被当成
   非零失败，发生在安全回执与总 manifest 阶段。独立 postflight 只重做 byte comparison、credential scan 与
   SHA manifest，不重跑或修改任何 scientific artifact；原因和范围写入 bundle 的 `launcher_failure_receipt.txt`。

这些失败不能改写成科学结果，也不改变事前阈值。
