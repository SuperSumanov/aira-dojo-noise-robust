# Public Artifact Contract Support v1：预注册与执行前检查

日期：2026-08-17。状态：`NOT RUN`。本文件冻结在读取 sample-submission header、row count、dtype aggregate
之前。此前只做过路径名/文件大小的探索性 inventory，已经看见 25 个目标任务中至少 20 个有 public candidate；
因此 coverage 只能作描述，不能追认为确认性门。

## 1. 目的与 estimand

只回答公开 artifact contract 在任务间是否具有非平凡结构异质性，能否支撑未来 task-held-out retrieval 设计。
不评估方法、不读取成绩、不声称 speedup。

## 2. 十三项执行前检查

1. **方向**：score-channel 仍是唯一主实验；本轮只是 P1 的 CPU 数据资格审计。
2. **代码版本**：使用包含本文件、`audit_public_artifact_contract.py`、task manifest 和单测的精确 Git commit；
   完整 SHA 写入结果报告。
3. **任务宇宙**：`phase1/public_artifact_contract_tasks.tsv` 固定 25 个 run-clean memory tasks 与 task type。
4. **允许路径**：仅 `<data-root>/<task>/prepared/public/` 的顶层 sample-submission candidate 与
   `description.md`。
5. **禁止路径**：任何 `prepared/private`、train/test feature 文件、标签、score、journal、vault、env。
6. **选择规则**：只接受大小写归一后的 `sample_submission.csv` / `sampleSubmission.csv`，或文件名含
   `sample_submission` 的 `.csv.zip`；多候选 fail-closed；ZIP 必须恰有一个安全 CSV member。
7. **输出**：只写 header、观察到的值类型集合、空值计数、行/列数、hash、bytes、description hash；
   永不写任一原始 sample value。
8. **完整性**：header 非空且唯一、每行 width 一致、resolved path 仍在对应 public dir；否则 fail-closed。
9. **结果前冻结门**：至少 8 个唯一 `(header, observed types)` schema signatures；dominant signature
   share <=0.5；宽度桶 `1-2`、`3-10`、`>10` 三类全部出现。
10. **解释**：三门全过只允许 `artifact_contract_is_nontrivial=true`；不允许方法效果、泛化或因果主张。
11. **复现**：输入文件逐个 SHA256；两次独立进程输出必须逐字节相同；另用不含真实数据的单测覆盖
    plain CSV、ZIP 与 private-path negative control。
12. **资源**：CPU-only，预计 <10 分钟；GPU=0、API=0、底座更新=0。
13. **失败/后续**：门失败则关闭结构化 contract retrieval；门通过也只允许设计 task-held-out retrieval
    支持审计，P2 三臂仍需主实验确认、功效分析、确切矩阵与用户预算批准。
