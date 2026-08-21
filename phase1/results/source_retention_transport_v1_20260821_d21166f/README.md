# Source-retention transport v1：紧凑证据

- 正式状态：`VERIFIED_TASK_CONDITIONED_SOURCE_RETENTION_TRANSPORT`
- 正式 commit：`d21166fb344c0645ed1e31ea6bc7e7487e441e6f`
- 输入：3,252 parents；SHA-256=
  `75c02200d1f9b8d87614762a9f2b71ba3c678d598ff28bc237c8a46a4bc36d03`
- 资格：15 common tasks；train/frozen parents 每任务至少 30/15
- headline：Spearman rho=`0.8151043256715026`
- permutation：100,000 次，双侧 `p=0.0005999940000599994`
- paired-task bootstrap：20,000 次，95% CI=`[0.5368038356525456,0.9594112875401973]`
- LOTO：15/15 正，minimum=`0.779067271041392`
- parent-present sensitivity：rho=`0.8295238095238096`
- train-defined frozen top-minus-bottom tertile retention=`+0.21714885427161656`
- producer×2、independent verifier×2 byte-identical；reconstruction difference=0
- focused=`6 passed`；full phase1=`627 passed, 25 warnings`
- forbidden path / credential filename / credential content hits 均为 0；GPU/API/model update=0

本目录只保留 reviewer-facing 紧凑回执。完整只读 artifact 位于：
`/research/d7/spc/yzyang4/source-retention-transport/d21166f-v1`。

允许主张 task-conditioned source-retention profile 跨 disjoint-run train/frozen roles 复现。禁止 MAR、因果
task effect、完整 choice set、missing numeric outcome、predictor/search utility 与 first/only。
