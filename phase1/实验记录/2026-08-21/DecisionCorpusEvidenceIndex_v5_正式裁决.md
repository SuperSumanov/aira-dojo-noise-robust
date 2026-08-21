# Decision-Corpus Evidence Index v5：正式裁决

日期：2026-08-21。控制 commit：`fff9e9fb937390142b059818dde3c593ece144a8`。正式状态：
`INDEPENDENTLY_VERIFIED_SOURCE_ANSWERABILITY_EVIDENCE_INDEX`。

## 裁决

v4 的八个 estimands 以固定 index hash 逐项继承；第九项 `source_decision_answerability` 已作为独立 release
contract 接入。新 entry 直接绑定 3,252-row parent CSV、23-row task CSV、summary、独立 verification 与 producer
manifest。CSV 同时核验 normalized hash、精确 header、line/data-row count 与每行宽度，不只信任 manifest 中的
手工数字。

正式 index 包含 9 entries、26 JSON artifacts、3 bound files 与 305 assertions；normalized SHA-256=
`4bff2b9fa48f2b530de886ab6b799011e8c4aa48ed378cdee0959c8b087a1627`。builder×2、独立 verifier×2
逐字节一致，独立 receipt SHA-256=`6a1a09cd3ca8d6b8e0ac6c729e8231adea2392db35825c1c11fb08d321a8bce1`。

## 允许与禁止

机器可核验的新正资产是：published orientation 对全部 source parents 的 unique-winner answerability 为
2,344/3,252；status-aware partial order 为 3,001/3,252，新增 657，最终 rate=
`0.9228167281672817`。该 entry 与 `status_certified_partial_order` 分开保留，不能合并成一个“证据总分”。

schema 显式禁止 predictor accuracy、search utility、complete numeric total order、MAR、prospective effect 与
first/only 语言；传递推断不是 logged comparison，source identity unavailable 也没有被插补。v5 仍是
`AWAITING_FIRST960`，不改变 strict-future 或 GPU 批准门。

## 完整性

- 正式 focused=`7 passed, 1 skipped`，完整 phase tests=`678 passed, 1 skipped, 25 warnings`；
- 回传正式 index 后，本地 checked-output gate=`8 passed`；
- worktree drift、secret filename/content hits、正式可写文件均为 0；
- GPU=0、API=0、base LLM update=0、prospective outcomes read=false；
- 本地产物：`phase1/results/decision_corpus_evidence_index_v5_20260821/`；
- 远端只读证据：`/research/d7/spc/yzyang4/decision-corpus-evidence-index-v5/fff9e9f-v1`。
