# Archive disposition longitudinal replication：competition mapping 修订回执

- 第二次正式运行：focused `12 passed`；全量 `1844 passed, 48 warnings`；producer 因 legacy/baseline path 假设失败，
  result 与 verifier 文件均未产生。
- 安全路径 census：275/275 为两段 `.tar.gz`；accepted=`126`、rejected=`21`、baseline=`128`。
- accepted mapping：固定 snapshot 中 126 transactions 与 126 accepted observations 逐 archive SHA/path 闭合；126/126
  hash-bound `source_provenance.json` 均为 single-task；共 520 provenance rows。
- provenance schema：25 条含可选 `competition_id_source`，495 条不含；其余 12 个必需字段一致，正式校验显式接受且冻结
  这两种版本，不接受其他字段漂移。
- accepted filename cross-check：124 个 `-Nseeds` filename 可解析且与 task 规范化后 0 mismatch；另 2 个使用 hash-bound
  task metadata，不猜文件名。
- rejected mapping：21/21 均满足既有 `competition-Nseeds.tar.gz` 结构。
- 结果前边界：没有计算或输出 accepted/rejected competition intersection、mixed fraction、reason distribution 或任何 identity；
  没有读取标签、outcome、prediction、accuracy、utility，也没有 GPU/API/model fit。
- 不变项：Strong/Partial/Kill 门、历史 218-archive 锚点、extension 定义和 claim boundary 均未改变。

修订后的 producer 与独立 verifier 必须分别重建上述映射，并将这些已知结构计数作为 fail-closed gate，而非把异常名称静默丢弃。
