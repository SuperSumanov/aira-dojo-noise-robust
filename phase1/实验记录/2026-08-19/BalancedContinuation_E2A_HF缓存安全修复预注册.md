# BalancedContinuation E2-A HF 缓存安全修复预注册（2026-08-19）

状态：**第二次 warm 工程失败后的结果前修复协议；新的 warm/formal 尚未启动**。本修复不读取任何科学
outcome，不改变 E2-A 的 estimand、任务或实验预算。

## 1. 观察边界与失败分类

- source commit：`81e05352b0d6d77eec289f59a38243a92ded92fe`；
- warm root：`/research/d7/spc/yzyang4/balanced-e2a-warm-smoke-81e0535-a1`；
- chunk 0 job `11220`，slots 0--3；chunk 1 job `11228`，slots 4--5；
- spaceship、TPS-May、spooky、US-patent、Nomad 五项 capability/producer/verifier/safety rc 全零；
- TPS-May candidate wall=`1119.5009202449583` 秒，在统一 1200 秒上限内生成合法 submission；
- Essay candidate wall=`11.917737385025248` 秒，producer rc=3，错误发生在任何训练前：Transformers
  `4.57.6` 检测到镜像 PyTorch `2.5.1+cu124`，依据 CVE-2025-32434 安全门拒绝加载旧
  `pytorch_model.bin`；
- collection status=`E2A_WARM_CHUNK_FAILED`，formal_not_launched=true；所有 summary 均为
  `dsearch_rows_read=dval_rows_read=dtest_rows_read=0`、`labels_opened=false`、`outcomes_read=false`。

因此该结果只证明执行环境对一个冻结候选不兼容，不构成方法负结果。既有 5 个成功 task 也只是工程
capability，不得解释为科学正结果。该 warm 永久保留且不与修复 run 拼接。

## 2. 权重等价性独立审计

共享 cache 中存在以下两个 regular blobs：

- 原 PyTorch：SHA=`691d48a2800b926a19e3051def466fc2cca4f59a15e42ce4a0cf7f1b380b5e33`，
  size=`371146213` bytes；
- safetensors：SHA=`57cbd0cad054ba5be8d4c6965b836e132f029edbbe3ed9c5bc9ef4fe1c40c34e`，
  size=`371101258` bytes。

审计器拒绝 PyTorch <2.6，只允许 `torch.load(..., weights_only=True, mmap=True)`；实际在 PyTorch
`2.11.0+cu128` 运行。结果为 210 tensors、185,537,893 elements、371,075,786 tensor bytes；key set、
shape、dtype 与每个 tensor 的 `torch.equal` 全部通过，210 tensors 均为 float16。receipt：

- path：`/research/d7/spc/yzyang4/scratch/deberta_v3_base_tensor_equivalence_20260819.json`；
- repository copy：`phase1/results/balanced_continuation_e2a_hf_cache_20260819/tensor_equivalence.json`；
- SHA256：`2156d53785303a4f203682e7c0eba7c9123ae63fe6f397d5473eee4444d25c01`；
- status：`VERIFIED_EXACT_TENSOR_EQUIVALENCE`。

没有以旧 Transformers 绕过安全门，也没有在 PyTorch 2.5 下执行有漏洞的 `weights_only` 反序列化。

## 3. 唯一允许的环境修复

1. 从共享 cache 逐文件复制到一个新的、实验专用且路径固定的 cache；不得原地修改共享 cache。
2. 只在 `microsoft/deberta-v3-base` main snapshot 中移除 `pytorch_model.bin` link 和对应
   `.no_exist/model.safetensors` marker，加入指向上述已验证 safetensors blob 的相对 symlink。
3. 不新增、删除或替换其他模型 payload；每个 regular file 记录 size+SHA，每个 symlink 记录相对 target，
   目录也进入 canonical manifest。
4. 全 cache 文件设 0444、目录设 0555；manifest 本身不可写。preparation、warm launcher、formal launcher
   都核验 manifest/payload SHA，worker 与独立 verifier 核验 cache path 和双 SHA。
5. real worker contract 从兼容保留的 v1 升为 E2-A v2；历史 v1 artifacts 仍可验证，不能被新字段破坏。

这等价于安全封装同一模型权重，不是 task-specific 代码修补；候选 `solution.py` 保持逐字节不变。

## 4. 冻结矩阵与资源

- 修复验证：0 GPU / 0 API；
- warm：原六个固定 assignment 全部从零运行，6 candidate executions / 0 API，4+2 顺序 chunks，最多
  4 submitted tasks，单 candidate 1200 秒，hard cap=2.0 GPU·h；
- formal（仅 warm 6/6 后）：60 rollouts / 120 candidate executions / 60 Qwen calls，15 个顺序 chunks，
  expected=`13.581222464241607 GPU·h`，candidate hard cap=`40.0 GPU·h`；
- 排除 `projgpu7/8/33,gpu36/38`，0 retry、0 replacement、0 adaptive allocation。

任务、24 parents/24 physical runs/48 siblings、6 calibration parents、seed、代码、split、metric 双实现、
Qwen operator、H=1、fresh workspace、1200 秒 timeout、Slurm wall 与所有科学裁决门均保持不变。

## 5. 解锁门

新的不可变 source commit 必须先通过：focused tests、远端完整 Linux tests、bash syntax、全 cache 重哈希、
DeBERTa offline load probe、13/13 preflight、assignment 重建、secret filename/content scan=0。新的 warm 必须
六任务全部 capability/producer/verifier/safety rc=0、artifact shape 合法、0 API、0 private mount、0
score/label/outcome read。任一失败立即停止；不得只补失败 task，也不得自动继续 formal。

## 6. pre-submit 失败记录

首次新 launcher root `balanced-e2a-warm-smoke-5b78119-a1` 在任何 Slurm submission 前失败：独立 cache
verifier 在 `cd source_root` 之前以 `python -m` 启动，因而无法 import `phase1`。该 root 只有 launcher
静态文件和错误日志，0 GPU / 0 API / 0 candidate execution，不允许复用。唯一修复是把已有的
`cd "$source_root"` 移到 cache verifier 之前；cache、contract、assignment、timeout、矩阵和全部科学门不变。
