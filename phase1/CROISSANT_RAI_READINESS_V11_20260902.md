# Croissant 1.1 + Responsible AI 1.0 readiness (v11)

日期：2026-09-02。裁决：`ENGINEERING_READY_PUBLICATION_FIELDS_BLOCKED`。

## 结论

Croissant/RAI 不再是“从零开始”的发布工程：v11 的 10 个 JSONL resources、24,119 行、路径、字节数、
SHA-256 和 schema field paths 已由 producer + 独立 verifier 固化。严格构建器可从这份 value-free schema
inventory 生成 Croissant 1.1 `distribution` / `recordSet` / field source，以及 RAI 1.0 文档字段。

但现在**没有生成最终 Croissant JSON-LD**，也不能把本结果写成 release clearance。构建器在以下五个最终
publication fields 任一缺失、使用占位符或 URL 非 HTTP(S) 时都会失败：

1. `license`：机构/法律裁决后的最终数据集许可 URL；
2. `url`：最终 dataset landing page；
3. `creator`：确认过的个人/机构署名；
4. `datePublished`：真实发布日期；
5. `contentBaseUrl`：能够逐文件下载 immutable resources 的公开基址。

这五项之外，competition rules、provider-output terms、全量 credential/PII/path/competition-content 扫描及
最终 `LICENSE` / `NOTICE` / `licenses.json` 仍是独立门，不能被 Croissant receipt 替代。

## 实现与复验

- producer：`phase1/build_croissant_rai_metadata.py`
- independent verifier：`phase1/verify_croissant_rai_metadata.py`
- fail-closed config template：`phase1/croissant_release_config_v11.template.json`
- machine receipt：`phase1/results/croissant_rai_readiness_v11_20260902/`
- focused tests：9/9 passed，包括五类占位/非法值拒绝、缺字段拒绝、array field 映射、hash-bound
  distributions 与 prospective scope violation 拒绝。

正式构建命令只应在所有发布门关闭后执行；不能把 template 里的 null 改成猜测值。构建后还必须用独立 verifier
验证 required dataset fields、10/10 distributions、10/10 record sets、resource digest/size、RAI 字段和占位符零命中。

## 规范依据与边界

- MLCommons Croissant 1.1 要求 dataset-level `@context`、`@type`、`dct:conformsTo`、`description`、
  `license`、`name`、`url`、`creator`、`datePublished`，并要求 `distribution` 由 `FileObject` / `FileSet`
  构成：<https://docs.mlcommons.org/croissant/docs/croissant-spec-1.1.html>。
- Croissant RAI 1.0 使用独立 versioned conformance IRI 和 `rai:` vocabulary：
  <https://docs.mlcommons.org/croissant/docs/croissant-rai-spec.html>。

当前 RAI 文本明确保留公开任务偏差、generator/operator/hardware/yield selection、历史 source retention、
不完整 opportunity sets、post-execution 信号和未闭合发布门；不会把数据卡中的限制洗白成结构化元数据后的“已安全”。

## 科学解释

本工作关闭的是 NeurIPS D&B 发布可用性工程风险，不新增模型效果证据，
`counts_as_distinct_claim_evidence=false`。它的正面价值是：一旦内容和许可门关闭，最终机器可读 metadata
可以在分钟级、可复验地产出，而不会在投稿最后阶段临时手填或引入不可追溯字段。
