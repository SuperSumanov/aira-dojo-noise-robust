# 2026-09-07：构建与入口验收的原始安全回执

三份JSON从远端安全导出，导出manifest SHA：
`138d235e526e2aa31b67a2b9c735b00937b9a49dee079d3144ab5cb7671beb99`。
本地逐文件bytes/SHA再次复核，未从摘要重写回执。

- `r4_terminal_independent.json`：真实12648 COMPLETED/3199秒，6608源码、104wheel payload、1扩展及旧对象核验。
  这是sm120依赖构建完成，**不是**PRO6000实际GPU数值或模型训练完成。
- `ampere_entry_cpu.json`：911886a真实Linux237检查通过、62源码文件，零GPU上下文/真实语料读取；
  是RTX3090独立synthetic入口CPU验收，**不是**实际卡上运行。原bf43062在测试前扫描误报的目录仍保留。
- `historical_grader_metadata.json`：固定84历史run/24归档、双遍168独立解码对照，未发现版本来源字段。
  结果字节曾进入JSON解析器，不用于成绩选样，也没有补造evaluator或建立训练准入。

矩阵、预算与保护评测边界见CURRENT_DIRECTION和相关preflight。实际训练/效果仍需各自独立门，不混合这些证据。
