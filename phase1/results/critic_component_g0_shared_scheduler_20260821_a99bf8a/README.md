# Clean Direct-Decision G0 shared scheduler qualification

正式状态：`G0_SHARED_SCHEDULER_TEST_ONLY_PASS`。

- control commit：`a99bf8a78ee25fc0257dce5aabdc947ef0725839`；
- 远端正式目录：
  `/research/d7/spc/yzyang4/critic-component-g0/scheduler-audits/a99bf8a-v1`；
- focused tests：`11 passed in 0.13s`；
- 全部 phase tests：`616 passed, 25 warnings in 58.69s`；
- test-only 回执：虚拟 job `11321`，预测在 `2026-08-22T18:22:07` 于 `projgpu39` 启动；
- 虚拟 job 随后查询返回 `Invalid job id`，当前用户 queue before/after/diff 都是 0 bytes；
- real jobs / GPU jobs / API / test-pair reads / scientific outcomes：全为 0；
- 正式目录递归可写文件为 0，文件名与内容凭据扫描均为 0；
- `SHA256SUMS` SHA-256：
  `226f48c6f67acb72467a24ef7e23180cdd38924dd57d1e22ca429f191c68693f`。

`gpu_24h` 明确允许 `gpu` QoS，当前账号 association 为 `gpu|gpu|yzyang4||gpu|gpu`；共享模板固定
12 CPU、`mem=0`、2×PRO 6000、`projgpu39`、2 小时。前两个资源项只适配该节点的 Slurm 配置，不改变
Qwen、数据、seed、context、batch、optimizer step 或 dev-only estimand。实际 G0 仍未获精确预算授权，模板和
审计脚本都不会自提交。

同名目录中的文件是正式只读目录的逐字节副本；按 basename 改写绝对前缀后，20 个 manifest 项全部通过
SHA-256 校验。
