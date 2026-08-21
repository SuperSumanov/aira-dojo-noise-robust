# Source Choice Benchmark S1：执行前冻结

日期：2026-08-21。状态：`NOT RUN`。S0 已按结果前门授权 S1；本轮只构造 benchmark inputs 与 sealed label
vault，不训练 predictor、不评分模型、不提交 GPU/API。

## 固定对象与输出

以 0DG 的 status-certified winner 为标签，只纳入 0DI 已证明 candidate-code reference complete 的 3,000 个
source parents。candidate 顺序固定为 raw candidate ID 的 SHA-256 升序，与 winner/outcome 无关。每组输出 task、
run/parent hash、parent code、source size，以及每个 candidate 的匿名 ID hash、完整 code、code hash、生成时已知的
operator/step/depth 与 `card`/`journal_recovered` provenance。

- train 输出带 winner candidate hash；
- frozen/extension 公开 inputs 不含 winner；winner 单独写入不进入 Git 的只读 vault，公开 summary 只保留 vault
  SHA 与行数；
- frozen evaluator 只能读取 group-complete predictions 与 vault，输出聚合指标，不输出逐组 truth。

输入 SHA、上游 answerability module/protocol、3,252-parent census、identity、5,897 published orientations、2,079
status edges、996-row missing-status registry、721-row construction census、cards v11，以及 0DG/0DI summary 均在
协议内固定。pair JSON 虽承载 gap 字段，本轮只访问 better/worse orientation，禁止访问或输出 gap。

## journal 与代码安全

complete/retained candidate code 来自 hash-pinned cards。missing candidate 只接受 status registry 中
`UNIQUE_NODE_RECOVERED` 且绑定 expected parent 与 source-journal SHA 的节点。扫描 allowlisted roots 时先读取 bytes
做 credential 检测；命中时绝不 JSON parse。只有 SHA 在 needed set 中的 credential-safe journal 才解析，且只访问
competition ID、node/parent ID、code、operator、step/depth，不访问 metric score、stdout 或 runtime。公开与 vault
产物再次全量 secret scan。

## 无结果后调整的精确门

- groups=3,000、candidate slots=8,027、tasks=23、variable-arity groups=1,521；
- train/frozen/extension groups=2,109/778/113，candidate slots=5,739/2,041/247；
- 每组 source size≥2、candidate 唯一、code 非空且 hash 重算一致、winner 恰在 candidate set；
- parent card、task、run、lineage parent 与完整 children set 全闭合；
- incomplete group 必须对应 frozen eligible construction row；missing node 的 journal SHA/parent/context 全闭合；
- train/frozen parent 与 physical-run hash overlap=0；公开 frozen/extension 行中 winner 字段命中=0；
- producer×2 与不 import 本 producer 的 verifier×2 逐字节一致；任一失败整体关闭，不删组、不补码、不换 root。

## 十三项 pre-flight

1. 方向：0DI 的发布材料后续，不恢复 HCE/TD/probe/多保真。
2. 问题：把可回答且 code-reference complete 的 source groups 实际物化。
3. 单位：source parent；固定 all-parent 与 certified-winner 上游分母。
4. 标签：status-aware partial-order unique winner；不把传递关系叫 logged comparison。
5. 输入：十项 SHA-pinned 文件/模块与三个 pair normalized hashes。
6. 隔离：train 带标签；frozen/extension inputs 无标签，vault 独立只读。
7. 排序：candidate-ID hash 升序，禁止按 label、score、status 或生成顺序重排。
8. 代码：完整 UTF-8 bytes 与 SHA；不截断、不规范化、不去重吞并 candidate。
9. provenance：card 与 journal_recovered 分列；journal SHA/parent 必须绑定。
10. 安全：所有普通输入 parse 前 scan；journal credential-first；输出再次 scan。
11. 复现：固定 commit、producer×2、独立 verifier×2、逐字节 diff、全 manifest。
12. 资源：CPU-only，GPU=0、API=0、底座更新=0；预计 30--60 分钟。
13. 停止：任何精确计数、hash、schema、identity、code、vault 隔离或回归失败均 fail-closed，无 rescue。

通过只意味着 benchmark artifact 与 sealed evaluator 可用；不等于 predictor accuracy、listwise 方法收益、search
utility、prospective effect、complete-v11 主张或算法 novelty。
