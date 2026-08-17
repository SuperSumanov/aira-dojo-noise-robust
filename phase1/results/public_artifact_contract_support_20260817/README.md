# Public artifact-contract support v1

日期：2026-08-17。裁决：`VERIFIED_NONTRIVIAL_PUBLIC_ARTIFACT_CONTRACT`。

本轮只读取 25 个固定任务各自 `prepared/public` 顶层的 sample-submission candidate，并只输出 header、
观察值类型集合、空值计数、行/列数和 hash；没有读取 private、train/test feature、label、score、journal、
前瞻 outcome 或 env。GPU=0，API=0，底座更新=0，方法效果主张仍不允许。

## 冻结与执行

- source commit：`1dac61cf71c58e89dd084380165e48b4f1438a43`；
- task manifest：`phase1/public_artifact_contract_tasks.tsv`，25 个任务；
- 结果前冻结异质性门：unique schema signatures >=8；dominant signature share <=0.5；
  输出宽度桶 `1-2`、`3-10`、`>10` 全部出现；
- 首次 wrapper 在任何 contract 读取前，因未切到 worktree 导致 `phase1` import collection 失败；
  无结果产物。只修正 wrapper cwd 后使用同一 source commit 和门重跑；
- 第二次完整 `phase1/tests`：`342 passed in 46.47s`；
- 两次独立进程的 `audit.json` 逐字节相同，SHA256=
  `166eaa6770b4abd6118f0168abc2b6e8afb5633847af48628f3f637ad9b56bdb`。

## 结果

| 项目 | 精确结果 |
|---|---:|
| 固定任务 | 25 |
| public contracts | 20 |
| public descriptions | 20 |
| image / NLP / tabular contract coverage | 7/12；9/9；4/4 |
| 唯一 schema signatures | 19 |
| 去掉列名、只保留列数与观察类型后的 signatures | 17 |
| dominant signature share | 0.10 |
| 输出宽度桶 | `1-2`、`3-10`、`>10` |
| 两列 contract | 16/20 |
| 冻结异质性门 | PASS |

20/25 coverage 在 header 审计前的路径 inventory 中已经看见，因此只作描述，不能追认为确认性结果；
19-signature、dominant share 与 width buckets 在结果前未读且按冻结门裁决。

结果后的描述性压力检查显示，唯一完全共享原 signature 的是英/俄 text-normalization；去掉列名后仍有
17 个 signatures。不过 16/20 contract 都是两列，说明异质性主要来自列语义/placeholder 类型，宽结构差异
只由 4 个任务贡献。未来 retrieval 必须 task-held-out，并证明不是 task ID 或列名 lookup。

## 解释边界

允许：声称 public artifact contract 在现有 MLE 任务中是非平凡、任务特异的结构信号；继续构造
outcome-blind schema fingerprints 和 task-held-out retrieval 支持审计。

不允许：声称 memory/contract 已提高 coverage、质量或搜索速度；启动三臂付费实验；把缺失的 5 个 image
任务从 `prepared/private` 补齐。
