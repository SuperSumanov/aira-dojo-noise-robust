# OpenRouter Full-Context v2：结构可行性与独立复验正式裁决

日期：2026-08-29

正式分类：`METRIC_INDEPENDENT_EXACT_PANEL_FEASIBLE`

边界：这是历史 evaluator 诊断的结构可执行性正结果，不是模型准确率、predictor scaling 或 search utility 结果。

## 1. 冻结链

- parent protocol SHA-256：`56a33c2409fd1cd317df948577bacb769f6bf61c08dd748f38b2e7c62e727a29`
- metric-omission amendment SHA-256：`63e8acc446417ee8fab51dabcdc296a8d3b38412900a7eb6152f96d5f592cae3`
- builder/judge freeze commit：`727ed927b5308c2b7a2fa896bdc236c00a12b4f9`
- independent verifier commit：`932ef387439c1f3a27ec0ec358bc986226f81bae`

v1 因 40,950 Cards 全无结构化 metric name 而按预注册规则 KILL。v2 在看到 metric-independent eligibility
前只删除不可获得的单独 metric-name 行；完整 task description、higher/lower direction、client、hardware、两个时限和
完整代码均保留。两个 panel、四个 gap 桶、每桶 8 对、direct-sibling、same-run exact-resource、run/endpoint/task cap、
模型、双方向、隐私和预算合同均未改变。

## 2. 结构 readout

八个固定 strata 的 eligible counts 为：

| Panel | g1_2 | g2_4 | g4_8 | g8_inf |
|---|---:|---:|---:|---:|
| decision direct sibling | 86 | 72 | 58 | 102 |
| value hardware-time | 103 | 118 | 80 | 279 |

第一可行 deterministic seed 为 0。最终恰好选择 64 pairs（每个 stratum 8）、64 physical runs、29 tasks、128
endpoints；每 run 最多 1 对、每 task 最多 4 对、endpoint duplicate excess=0。smoke subset 恰好 8 对。完整代码总计
2,239,954 UTF-8 bytes，单 endpoint minimum/median-nearest-rank/p90/max=`5,650/15,594/29,141/58,940`。

私有 panel SHA-256=`a9d9f1df5a7a9aef2ba14682eb0514849ec8aba9abcc9dda69101babb7ff6be1`；公开 aggregate
receipt SHA-256=`8736be6a685e207eb39c25f1e7f7fa60f44adc0a908975fc1f7eb6e625343968`。私有行、身份、方向、gap
和代码均未进入 Git。

## 3. 独立复验

`verify_openrouter_full_context_panel_v2.py` 不 import builder 或 judge；它从五个 immutable historical inputs 独立重建
eligibility、first-feasible seed、全部 64 个私有行和整份 aggregate receipt，并要求逐字段精确相等。fresh detached formal
中两次 verifier 输出逐字节相同，结果 SHA-256=`4ab25eaacdc17758c282541871ccf36d125f6c2424c68c5d1044ecd5cc7933a5`。

- focused/full tests：`14/1551 passed`（full 另有 47 warnings）
- network calls / forbidden prospective opens / private values emitted：`0/0/0`
- GPU/API/model fits/base LLM updates：`0/0/0/0`
- r1 因 direct-file module path 在 import 阶段失败，无 `COMPLETE`；r2 改为 package module 入口后才是唯一正式结果。

## 4. 允许与禁止的表述

允许：缺少全库 metric name 时，预先冻结的最小表示修正仍能得到一个 gap-balanced、run-disjoint、endpoint-disjoint、
full-context 的 evaluator 诊断 panel，并可由第二实现精确重建。

禁止：目前没有任何 API evaluator 的准确率、排序优势、模型间差异或 label-efficiency 正结论。`live_calls_authorized=false`
保持不变；用户给出的 API credential 未写入文件、日志或 Git。任何 smoke 调用仍须单独冻结 launch receipt 和成本批准。

## 5. 下一步

先在不调用 API 的条件下冻结 evaluator-to-label-allocation 的 estimand、基线、预算单位、功效门和 untouched confirmation
边界。若之后获得明确成本授权，只先跑预注册 8-pair smoke；过 parse/privacy/truncation/cost gates 后才允许 64-pair full，
不得根据中间准确率选模型、任务或 gap 桶。
