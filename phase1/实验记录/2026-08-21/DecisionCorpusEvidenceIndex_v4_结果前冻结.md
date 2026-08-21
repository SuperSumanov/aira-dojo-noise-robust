# Decision-Corpus evidence index v4：结果前冻结

时间：2026-08-21。该工作只把已经正式通过并发布的 status-certified edge manifest 接入统一证据合同，不产生新效果
estimand，不重算 partial-order headline，也不读取任何新 outcome。

## 固定输入与结构

以 normalized-LF SHA-256=`424f06b161086972fedf55d5e8e06e22d92c21e1558a04b2dd6c55e3cb637b49`
的 v3 index 为不可变来源。v3 七项 entry 的顺序、artifact、assertion、claim 和边界逐项继承且不得修改；在
`decision_observability` 后新增第八项 `status_certified_partial_order`。

新增项固定绑定：

- 2,079-line `edges.jsonl`，normalized SHA-256=
  `dda9f121dc32a1ef309992b0bec61934864e35ec337385bb2f5c0c548b258a3d`；
- formal summary，normalized SHA-256=
  `5dd53823ca6e432e4ab593a1267c9a73bce954be977deceb6de63c4ed90ea84b`；
- independent verifier，normalized SHA-256=
  `ae280675707b38fad4da3042296b90c7a2fd3c744f484ba482703c542d0e5abf`；
- edge/summary hash manifest，normalized SHA-256=
  `e843720791e51501e07e556acaa05cd8624c1334d74879e4a6df8a61e1780323`。

## 固定主张与边界

唯一新增支持主张：发布物含 2,079 条显式 provenance-certified validity edges；只保留 execution-error 的 2,060-edge
子集仍通过原全部材料和支持门。允许报告显式 validity edge 数。

强制保留：validity dominance 不是 numeric-quality total order；unknown/unregistered/finite-finite 未发布关系继续
unresolved；不恢复 complete source choice set，不假定 MAR，不证明 predictor accuracy、search utility、causality、
prospective effect 或算法 novelty。grade-absent 不是材料性结论所必需。禁止 first/only。

## 十三项 preflight

1. 方向：Decision Corpus / D&B 证据发布，不调 predictor/controller。
2. 问题：显式 failure-aware partial order 能否作为第八个不合并 estimand 进入统一 index。
3. 输入：固定 v3 index、三份 JSON 与一份 JSONL，全部 hash 如上。
4. 单位：一个 evidence entry；JSONL 逐行对象、逐字节 hash 与 line count 同时绑定。
5. 输出：八个互异 estimands 的 v4 index 与独立 verification receipt。
6. 主门：source hash、旧 entry 原样继承、四份新输入 hash、2,079 lines、全部 JSON assertions。
7. 推断：无；仅 deterministic packaging，不生成 CI/p 值。
8. 泄漏：不读 code、raw archive、checkpoint、pair orientation、score 或 prospective vault outcome。
9. 对照：claim drift、edge-binding drift、manifest exact-key、source order 与 checked-in output 测试。
10. 复现：builder×2、独立 verifier×2，full commit、输入 hash 和命令写入产物。
11. 失败：旧条目漂移、边界删除、hash/line/assertion 不符、秘密命中或 worktree 漂移即不发布。
12. 资源：single-thread CPU；GPU/API/base-LLM update 均为 0。
13. ETA：完整 phase 回归在内小于 30 分钟。

正式目录必须只读，builder/verifier 两次输出逐字节一致，focused 与全部 phase tests 通过，秘密扫描为 0。任一项失败
只保留失败目录，不更新方向入口、不写正式裁决。
