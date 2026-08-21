# Clean Direct-Decision G0：静态预检、可复现运行包与调度阻塞

日期：2026-08-21。状态：`G0_ENGINEERING_READY_BUT_NOT_SUBMITTABLE_BY_CURRENT_ACCOUNT`。
本记录只涉及 dev-only 工程预算校准；GPU jobs=0、API calls=0、held-out test reads=0，尚无模型 accuracy。

## 1. 先发现并修正的协议缺口

第一版上游补丁建立了 train/dev 隔离与 one-shot test 契约，但其 launcher 没有传 `--max_steps`；若直接运行，
会按 1 epoch 而不是预注册的 10 steps 执行。这个错误在任何 GPU 结果前发现，未产生 outcome。第二补丁：

- 文件：`phase1/upstream_patches/0002-Allow-fixed-step-critic-budget-calibration.patch`；
- SHA-256：`89d7af494e436c4d5a7ed5c4a06e43c4d012cb26c3efd3c1e9f52bf00b3bd641`；
- 应用于 senior `baf6bdd...` + 第一补丁的 detached overlay，commit=
  `e740bab3524248f8175ec27dcd7e034515ef5bc5`；
- 明确传递并记录 `max_steps`、cosine scheduler、warmup ratio；非法 0/负值 fail closed；
- bash syntax、diff check、非法值负测与 train/dev/one-shot 聚焦测试 13/13 通过。

随后增加纯 instrumentation 补丁 `0003-Record-critic-wall-clock-receipts.patch`，SHA-256=
`a4146bdc6ef3123e3b88a3b909352dd40db3cff992503919d4207c1756313f67`。它只在 world process zero 输出
`train_begin / optimizer_step_1 / optimizer_step_final / dev_evaluate_complete / train_end` 五个 JSON timing
marker，不读取 metric、不改变 forward/loss/optimizer。最终 source commit=
`51c7f480a844364a91cf1ee4ebd9dac18f6bb832`；四组聚焦测试共 15/15 通过。

复核训练配置时还发现 `head_frac=0.25` 原先只存在于 pinned source 默认值。它会改变实际送入 backbone 的代码，
属于科学旋钮，因此在结果前显式冻结为 0.25；`eval_on_start=false` 也一并冻结，保证只在 step 10 做一次 dev eval。

## 2. 固定输入与模型资产

| 资产 | rows/items | bytes | SHA-256 / revision |
|---|---:|---:|---|
| component train | 4,689 pairs | 3,208,089 | `0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e` |
| component dev | 551 pairs | 376,635 | `3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4` |
| Cards | 31,742 | 604,190,866 | `5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb` |
| Qwen3-1.7B-Base | 10 files | 3,452,692,285 | `ea980cb0a6c2ae4b936e82123acc929f1cec04c1` |

模型 10 文件的仓库相对 manifest SHA-256=
`ceb388235719297e3647478ad2d96486a41d1f84e4c3fd8301c4772d6840e148`。CPU-only 预检重新逐项哈希，且
`AutoConfig`/`AutoTokenizer` 离线加载得到 `qwen3`、hidden size 2048、tokenizer size 151,669。运行环境为
Python 3.12.13、torch 2.5.1+cu121、transformers 5.12.1、accelerate 1.14.0、DeepSpeed 0.19.3。
最终源码上的完整预检 34.23 秒、exit 0、max RSS 737,016 KiB；receipt SHA-256=
`da2774c0dabcd195a86d75d5580317301812629c161402ea49073cdd57f2ff7b`，并绑定 verifier SHA-256=
`f6cba4eb78c7bc3d9f344605c7450cd87dd57d8e133c52043ab4bc0592adc960`。

当前模型 cache 权限属于 `yzyang4`，不能假定学长可读。交接时不放宽整个 cache 权限；学长应在自己的账号按
同一公开 revision 下载，并用同一 10-file manifest 验证，或使用管理员明确配置的共享只读目录。

## 3. 运行包及 fail-closed 验收

- worker：`phase1/scripts/critic_component_g0_worker_20260821.sh`；
- 授权账号模板：`phase1/scripts/critic_component_g0_pro6000_20260821.sbatch`；
- 独立验收：`phase1/verify_critic_component_g0.py`；
- control 单测：6/6；上游 timing/数据契约测试：15/15；远端最终 source/input/model 预检：PASS。

worker 不接受 test-pair 参数，也没有 `sbatch` 调用。它要求干净且精确 pin 的 source/control checkout，逐项验证
train/dev/Cards/model SHA，把 HF/Transformers 强制为 offline，并把 Triton 与 Torch extension cache 放入 node-local
scratch，避免已观察到的 NFS autotune-cache 退出风险。运行期固定：

`Qwen3-1.7B Base, seed=6, 2×Pro6000, bf16, ZeRO-3, max_len=16384, head_frac=0.25,
task_cond=true, budget_cond=false, lr=1e-5, cosine, warmup=0.03, per-device train/eval batch=8/8,
grad_accum=8, effective pair batch=128, max_steps=10, eval_steps=10`。

postflight 必须看到唯一 `checkpoint-10`、`global_step=10`、唯一 step-10 `eval_pair_accuracy`、五个顺序和 step
都精确的单调 timing marker、全部有限 dev 指标、metadata 中完全一致的数据/代码哈希、两张不同 PRO 6000
UUID、5 秒 GPU telemetry 和 GNU time exit 0；
任何一项失败都不会生成 `COMPLETE`。

## 4. 当前唯一执行阻塞

2026-08-21T01:28:59Z 的只读调度审计显示：`yzyang4` association 为 account=`gpu`、QOS/defaultQOS=
`gpu/gpu`；`projgpu39` 确有 `zliang_gpu` partition 与 `gpu:pro6000:2`。但对同一 2-GPU/2-hour job，显式
`--qos=zliang_gpu` 和省略 QoS 的 `sbatch --test-only` 都以 rc=1 返回
`allocation failure: Invalid qos specification`。队列行数为 0，未提交真实 job。

解除阻塞需要两件事同时满足：用户明确批准 G0 的精确上限（1 run、2 GPUs、2h，最多 4 GPU·h），以及学长用
有权限账号提交或管理员给当前账号授予该 QoS。不能改用别的 GPU、缩 context、换数据或改 batch 绕过。
即使 G0 完成，它也只测工程吞吐与可运行性；G1 的 8 runs 必须据实测 epoch 时间另报总 GPU·时并重新批准。
