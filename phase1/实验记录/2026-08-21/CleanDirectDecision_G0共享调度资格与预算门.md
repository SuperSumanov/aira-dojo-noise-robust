# Clean Direct-Decision G0：共享调度资格与预算门

日期：2026-08-21。正式状态：`SHARED_SCHEDULER_ELIGIBLE_CAPACITY_AND_BUDGET_PENDING`。本轮只有
`sbatch --test-only`；real/GPU jobs、API calls、test-pair reads、scientific outcomes 均为 0。

## 1. 阻塞原因被精确拆开

原模板使用专属 `zliang_gpu` partition/QoS、16 CPU 和 128G Slurm memory；当前账号确实没有该 QoS。但
`projgpu39` 同时属于共享 `gpu_24h`，partition 明确允许 `gpu` QoS，当前账号 association 也是
`gpu|gpu|yzyang4||gpu|gpu`。节点的 Slurm `CfgTRES` 把 memory 记为 `1M`，现有合法 2-GPU 作业实际使用
12 CPU、`MinMemoryNode=0`。因此此前的 `Requested node configuration is not available` 同时混入了资源描述
错误，不能只解释为无权限。

新增共享模板只改变调度资源声明：`gpu_24h/gpu`、12 CPU、`mem=0`。科学配置保持：Qwen3-1.7B Base、
seed 6、2×PRO 6000、bf16/ZeRO-3、16,384 context、head fraction 0.25、task conditioning 开、budget
conditioning 关、LR 1e-5/cosine/warmup 0.03、有效 pair batch 128、10 optimizer steps、一次完整 dev eval。
train/dev/Cards、模型 revision、source commit 和全部哈希不变，held-out test 路径仍不被 worker 接受。

## 2. fail-closed 加固

`phase1/verify_critic_component_g0.py` 现在只接受两个白名单组合：

- 专属路线：`zliang_gpu/zliang_gpu`、16 CPU、128G；
- 共享路线：`gpu_24h/gpu`、12 CPU、`MinMemoryNode=0`。

两者都强制 2 小时、`projgpu39`、两张不同且显存至少 90,000 MiB 的 PRO 6000。preflight 从真实
`scontrol` 行复核 job ID、partition、QoS、CPU、memory、time、node 与 2-GPU TRES；任一漂移即拒绝。
共享模板和 worker 都没有自提交命令。

## 3. 正式资格结果

commit `a99bf8a78ee25fc0257dce5aabdc947ef0725839` 的隔离 worktree 完成：

- focused=`11 passed in 0.13s`；
- 全部 phase tests=`616 passed, 25 warnings in 58.69s`；
- shared template/worker/audit script bash syntax 与 verifier compile 全过；
- `sbatch --test-only` rc=0，返回虚拟 job `11321`，预测
  `2026-08-22T18:22:07` 在 `projgpu39` 启动；
- 随后查询该 ID 返回 rc=1 / `Invalid job id`；当前用户 queue before/after/diff 均为 0 bytes；
- 正式目录只读，manifest 20/20，凭据扫描 0；`SHA256SUMS` SHA-256=
  `226f48c6f67acb72467a24ef7e23180cdd38924dd57d1e22ca429f191c68693f`。

动态容量复核显示另一用户 job `11320` 已于 `2026-08-21T18:22:07` 占用两张卡至
`2026-08-22T18:22:07`，所以当前阻塞是容量等待，而非 association/QoS。这个结束时间只作调度快照，不是
执行承诺。

## 4. 失败链完整保留

前三个正式 attempt 都在 scheduler test 前停止：

1. `4ee8b06-v1`：训练 venv 没有 pytest；
2. `ca020f9-v1`：隔离 worktree 从登录目录启动，模块根未进入 import path；
3. `cd7ad45-v1`：完整测试无断言错误但 BLAS 展开到约 30 CPU 线程，主动 TERM，未等结果。

最终脚本固定 test venv、`cd` 到 control root，并把 OMP/OpenBLAS/MKL/NumExpr/BLIS/vecLib 线程都限制为 1；
正式运行 CPU 约 66%，不再扩散。失败目录不覆盖、不追认为成功。

## 5. 仍未获得的授权

调度资格通过不等于预算获批。实际 G0 仍是精确 1 run、2 GPUs、2 小时 hard cap，最多 4 GPU·h；它只做
dev-only 工程校准，不产生论文 accuracy。必须在用户明确批准这一矩阵后，等待共享节点可用才允许提交；G1 的
8-run 科学矩阵仍须按 G0 实测 wall time 重新报价并再次批准。

直接证据：`phase1/results/critic_component_g0_shared_scheduler_20260821_a99bf8a/README.md`。
