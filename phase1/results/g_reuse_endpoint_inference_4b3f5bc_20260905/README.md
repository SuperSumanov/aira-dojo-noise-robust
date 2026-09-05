# 无标签推理适配器已接通；不是新的 critic 正效果

2026-09-05。代码 commit：`4b3f5bc3f493d25c63d237fd79b3e459c1f2f8f9`。

## 实际补齐了什么

现成评估入口依赖 better/worse 并计算 accuracy，不能作为无标签 prediction escrow。
新增 `phase1/g_reuse_endpoint_inference.py` 将无标签代码/任务名编码、每个 endpoint 一次模型前向、
完整 score matrix 的拼接接入已有 margin 物化器。不改训练数据、损失、模型头、冻结成功门或 queued G0。

三个可调用接口：

- `encode_endpoints(cards, tokenizer, max_len=...)`：只接受 endpoint_id/code/task_name，严格拒绝额外列。
- `score_endpoints(model, encoded, pad_id=..., batch_size=..., device=...)`：要求模型已处于 eval，
  只做 inference；右 padding，保留真正的 padding mask，重复 endpoint 和不完整/非有限输出拒绝。
- `assemble_score_matrix(expected_endpoints, by_model)`：要求五臂×三 seed 和 TF-IDF 全部齐全、支持集完全相同；
  输出可交给现有 `materialize_g_reuse_blinded_margins.py`，再由独立 verifier 复核。

**限制**：接口接收已获准的内存输入，不加载真实数据/checkpoint，不授权使用 GPU，也不认证调用者的 checkpoint、
seed、来源和操作系统读取隔离。合成测试中复制 scalar 填齐矩阵仅测试 schema，绝非已有 15 个 checkpoint。
仍需完整受控训练/推理 caller；不能据此宣布正式 escrow 已完成。

## 已验证的结果

|检查|实际结果|
|---|---|
|Linux 单元测试与已有 margin 接口测试|A：59 passed in 9.65s；B：59 passed in 3.76s|
|编码与精确训练源 CardEncoder 对照|10 组 tokenizer/context 组合，逐 token 一致；每组 5 个合成 endpoint|
|真实 tiny Qwen3 前向对照|18 cases：seeds 6/7/8 × batch 1/2/4 × 正/逆输入顺序，全通过|
|与原 pair_collate + 原 reward-model forward 比较|最大 margin 绝对差 `1.4901161193847656e-08`，低于事前 atol=1e-6/rtol=1e-5|
|参数/梯度|所有 case 参数逐项未变，无 backward，无新梯度|
|A/B 复验|summary.json 与 cases.csv 各自逐字节相同|
|stderr|tests A/B 与 reference A/B 四项均 0 bytes|

tiny 模型为随机初始化、1 layer、hidden=16、intermediate=32、2 attention heads/1 KV head、head_dim=8、
vocab=257、float32/eager、CPU 单线程；并非真实 1.7B/8B checkpoint，也不证明 GPU/bfloat16/FlashAttention 数值一致性。
真实 Qwen tokenizer 只用于合成代码编码对照；最长 fixture 会触发 16K 的 head/tail 截断。
这不是速度 benchmark；测试耗时不能作为 query cost。前向差值是数值等价误差，不是预测准确率。

单元测试环境为 exp：Python 3.11.15、Torch 2.11.0+cu128、pytest 7.4.3；原模型前向对照使用未修改的
G0 selective runtime：Torch 2.11.0+cu128、Transformers 5.12.1。所有阶段 CUDA_VISIBLE_DEVICES 为空，
reference 起止 CUDA context 均未初始化。GPU/API/model fit/protected input=0。

## 来源与复现

reference source=`5f3bc362db922c8edee2ef134656dfdb9a2b74fb`，只执行 hash-bound AST 中的
CardEncoder、pair_collate、BradleyTerryRewardModel 定义，不运行 train main 或数据 reader；模型构造改用随机 tiny backbone，
forward 保持原源码。源码 credential-shape 扫描无命中。

远端根：`/research/d7/spc/yzyang4/g-reuse-endpoint-inference/formal-4b3f5bc-v2`。
source archive SHA：`148135c4cba3c2d86c28b2fe01e0e9dfb251a8a86fadd5629265ea0ad4b5b24a`。
下载的结果 tar SHA：`16339e60d070247ae901afcaebc12810e4c4fee06de6bc0dae02b3b08c35c423`，本地/远端一致。
adapter SHA：`43b38c0e0c377cd7e78e4c91c50b5ff1a4e3790b3162dcd20f6ee132fb2188ae`。
tokenizer 的五个文件在 postflight 与既有 manifest 一致；没有把事后校验声称为这次运行的前后双哈希测量。
详见 `postflight.json`、`reference_a/summary.json`、`reference_a/cases.csv` 和 `SHA256SUMS`。
SHA256SUMS 中源码项相对于远端根；可从上述 exact commit 重建。结果文件在 Git blob 中保持 LF 原始字节。

在上述 exact checkout/root，设置 `CUDA_VISIBLE_DEVICES=''`、`HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`、
`TOKENIZERS_PARALLELISM=false`、`OMP_NUM_THREADS=1`、`MKL_NUM_THREADS=1`、`OPENBLAS_NUM_THREADS=1`、
`PYTHONDONTWRITEBYTECODE=1`、`PYTHONPATH=$PWD`，分别执行：

```bash
/research/d7/spc/yzyang4/venvs/exp/bin/python -m pytest -q -p no:cacheprovider \
  phase1/tests/test_g_reuse_endpoint_inference.py phase1/tests/test_g_reuse_blinded_margins.py

/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260903-selective/bin/python \
  -m phase1.scripts.validate_g_reuse_endpoint_inference_cpu_20260905 \
  --source-root /research/d7/spc/yzyang4/worktrees/critic-g0-final-only-20260903-b \
  --tokenizer /research/d7/spc/yzyang4/cache/huggingface/hub/models--Qwen--Qwen3-1.7B-Base/snapshots/ea980cb0a6c2ae4b936e82123acc929f1cec04c1 \
  --output NEW_OUTPUT_DIRECTORY
```

每项设置 240 秒硬超时；A/B 各运行一次，对照输出必须使用不同的新目录。重新验证也不得覆盖既有证据。

## 失败、未解决项和下一步

首轮 v1 在测试启动前报 G0 精简环境没有 pytest，退出码 1；没有执行测试、训练或修改依赖。
v1 目录保留；v2 改用现有 exp 环境执行测试，参考模型仍在 G0 原环境中执行。没有修订模型输出或放宽容差。

12:25 香港现场复核，G0 12486 仍 PENDING/Resources、0 秒，control=`adbfa801...` 与 CORRECTED_READY
SHA=`0868a211...` 不变。学长分支再次 fetch 仍为 `b8d0951...`。
G0 工程门、同源可开发范围/run→experiment/真实生产评分出处、正式预算和 15 个 final checkpoint 仍待完成；
不得把这次软件进展写成 G-reuse 胜出、scaling 确认或真实搜索收益。
