# Frozen 0.5B @ 8192 run-OOF critic（outcome 前预注册）

日期：2026-08-14；协议：`frozen_embed_v11_discovery_v1`；seed：887。本文和对应源码在任何新
frozen-embedding 预测结果产生前冻结。它属于当前的 **run-clean MLE-agent 搜索树数据集 / sibling
decision benchmark** 主线，不是早期 HCE、多保真或 probe 方向。

## GCCV

**Goal**：检验一个不微调底座、可在执行前调用的冻结代码表示，能否在真实 sibling decision 上跨
physical run 排序，并达到足以只看一次论文冻结集的训练期发现门。

**Context**：v11 有 16,012 cards / 667 physical runs / 25 tasks。发现阶段只使用
`v11_decision/decision_train_v11_b0.jsonl`：4,263 pairs / 333 runs / 23 tasks / 2,293 parents /
5,499 endpoints；无 oriented duplicate 或 reverse pair；最大任务 900/4,263。论文冻结集不作为
脚本参数、不建 manifest、不抽 embedding，也不用于阈值、超参或任务选择。

**Constraints / fairness contract**：

- backbone 固定为本地 `Qwen2.5-0.5B-Instruct`，只做 `eval + inference_mode`，绝不更新其权重；
- 输入固定为 `# MLE-bench task: {task}\n{whole child code}`，没有 grade、gap、parent outcome、runtime、
  stdout、自报分或执行反馈；task 是部署时已知上下文；
- tokenizer 使用模型原生 tokenizer，不加 chat template；每端点最多 8,192 tokens；超过时固定保留前
  25% 和后 75%，不足时不 padding 到定长；
- 端点表示固定为最后层 `concat(masked mean pooling, last non-pad token)`，两个 896 维半向量分别做
  L2 normalization，得到 1,792 维；落盘 float16，训练转 float32；
- 唯一主模型为无截距 L2 logistic ranker：镜像差向量 `[e_b-e_w, e_w-e_b]`，`C=0.05`，
  `liblinear`，`tol=1e-6`，`max_iter=2000`；每个 parent 的总训练权重相同；
- 5-fold `GroupKFold` 按 physical run；每个端点只接收其所在 run 的 OOF 模型分数；不调 C、不比较
  pooling、不选择 layer、不看 outcome 后改 context；
- `gap_raw` 只用于 outcome 后的预注册 utility 计算，不进入表示或训练权重；任何 regret-weighted head
  只能在本协议结束后作为显式新实验，不能替换本门控；
- b1/b2 不参与本发现门，因为是否有后续执行是搜索策略诱导的 censoring；
- manifest 的 shard 只由 `crc32("887:" + card_id) % 4` 决定，与标签、任务和长度无关；
- 所有输入、源码、模型权重、chunk 和输出均记录 SHA-256；输出目录 append-only。

## 主指标与控制

1. OOF pair accuracy（headline）；
2. physical-run macro 与 task macro，分别对 cluster means 做 10,000 次 bootstrap CI；
3. complete-parent top-1：只对 pair graph 恰为 `n(n-1)/2` 的 parent 计分，预测并列按 precision 计；
4. parent-equal gap utility：先在每个 parent 内计算
   `sum(gap_raw * hit) / sum(gap_raw)`，再对 parent 等权平均，避免大 pair-set 或大 gap parent 垄断；
5. task consistency：仅统计至少 20 pairs 的任务；
6. orientation oracle 必须为 1.0；固定 CRC32 random endpoint score 的 pair accuracy 必须在
   `[0.47, 0.53]`。预检时其确定值为 2,147/4,263 = 0.5036359371；这不是模型 outcome。

## Discovery unlock（必须全部满足）

完整性：pairs=4,263、runs>=300、tasks=23、dominant-task<=0.25、端点 feature 覆盖严格相等、每个
fold 的 physical-run 交集为 0、complete-parent share>=0.95、模型收敛、无 NaN/inf、在 900 秒 CPU
head wall cap 内、oracle/random controls 通过。

效果：

1. OOF pair accuracy >= 0.54；
2. run-macro bootstrap 95% CI 下界 > 0.50；
3. task-macro bootstrap 95% CI 下界 > 0.50；
4. complete-parent top-1 >= 0.50；
5. parent-equal gap utility >= 0.55；
6. 至少 15 个 supported tasks，且其中 accuracy>=0.50 的比例 >=0.60。

任一失败即 `DISCOVERY_NO_UNLOCK`：不得让本方法读取或抽取
`decision_frozen_v11_b*.jsonl` 的端点。全部通过只得到 `DISCOVERY_UNLOCK_RECOMMENDED`，随后另写
一次性的 frozen 评分协议；不能回头改本协议阈值或挑另一个训练配置。

## 资源矩阵与 ETA

- GPU smoke：1 个 RTX3090、16 endpoints、最多 15 分钟，验证模型加载、8192 路径、pooling、float16
  chunk、metadata 与重入行为；
- full extraction：4 个 deterministic shards，各 1×RTX3090 / 6 CPU / batch=2 / chunk=32；并发上限
  4 jobs，预估合计 2--4 GPU·h、墙钟 30--120 分钟，单 shard 硬上限 4 小时；
- OOF head + verifier：登录节点单进程 CPU，预计 2--8 分钟，硬 cap 15 分钟；
- API 调用 0；底座训练 0；checkpoint 是每 32 endpoints 一个不可覆盖 NPZ chunk。smoke 实测速率若
  外推超过单 shard 3.5 小时，full 不提交，先报告 `ENGINEERING_CAP_ABORT`。

## 允许的结论

- 通过 discovery 和后续一次 frozen：可称“冻结小模型表示 + 轻量 run-clean rank head 是 critic 的
  正向基线”，不能称模型规模无关，也不能称改善 agent 搜索，后者仍需 prospective fixed-budget A/B；
- discovery 失败：只关闭这一个固定表示/头配置，不推出 frozen representations 普遍无效；
- 不论结果如何，仍服务于 benchmark 主张：给出训练量、run-clean 协议、真实 sibling top-1、utility
  与任务异质性，而不是只报 pooled pair accuracy。
