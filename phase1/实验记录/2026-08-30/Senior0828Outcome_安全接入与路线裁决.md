# 学长 0828 outcome：安全接入与路线裁决

## 安全接入

GitHub `dojo-reproduce` 在检查时仍为 `5baccb170ce287f9c8eed7b23ccf693a0268515a`，最新 outcome 路径是：

```text
src/mle_critic/docs/outcomes/0828/MIXED_PAIRWISE_REWARD_AND_RL_EXPERIMENTS.md
```

该 blob 未直接打开。远端流式扫描发现 credential-shaped hit=`1`，随后生成 mode-0600 的脱敏副本：

- raw blob SHA-256=`17317a2d239cb862ec16d57aa0a2fa168f2c1a6cd841117950d8ee8127129ad6`；
- sanitized SHA-256=`15f04f806175c87e81043b00b8f06cdfe9b20e8d460f269078c2182f8c76c3f5`；
- sanitized credential hits=`0`；
- raw blob printed=`false`。

原 credential 没有回显、使用或写入本地/Git。报告中的 W&B access token 也不得用于访问；需要学长提供 public report 或
不含 credential 的安全 export。

## 报告中实际完成的实验

1. 旧 value/decision test 按 external-grade gap 分四档；曲线并不单调，不能简单写成“gap 越大越容易”。
2. 0819 mixed train=`14,715`、decision validation=`1,160`；混合目标是 value/decision/hardware-time 的 8:1:1 抽样，
   但输出没有保留 `source_dataset`，无法恢复去重后的真实来源比例。
3. Qwen3 Base 的 seed-7 出现 1.7B→14B proxy scaling，14B best=`62.76%`；seed-6 没有复现，0.6B seed-6 缺失。
4. 同一 test 的 TF-IDF/static-LR/static-GBM=`56.64/54.66/55.52%`。seed-7 14B 超过轻量基线，但不能跨 seed 稳健外推。
5. RL 在 mixed decision test 不稳定；experiment value test 的 14B RL 最高约 0.59，低于不严格 matched 的 8B BT 0.6411。
6. RL system prompt 把每 task 第一条 journal 的 constraints 当 task-level 条件，和其他 experiment 的 hardware/time limit/
   execution timeout 可能错配。

## 对 scaling 的严谨裁决

这批结果是值得保留的探索性容量信号，但不能升级为 clean scaling confirmation：

- seed interaction 明显，唯一漂亮的 14B 数字只在 seed-7；
- 表中是 validation best/final，不是 train-run dev 选 checkpoint 后一次性 frozen outer test；
- mixed train 没有 provenance，无法做 source-stratified coverage/ablation；
- 1,160 decision pairs 共享 Card endpoint，且 draft/improve 混合；
- 0820 与 0828 test population 不同，百分点不能直接相减；
- 资源条件错配污染 RL prompt。

因此继续沿现有裁决：只有 future exact-stratum producer、train-run dev checkpoint selection、新 frozen physical-run cohort 和
完整 cluster-aware inference 才能确认 scaling。

## 学长提出的三项工作与裁决

### 1. OpenRouter full-context judge panel

合理，但应复用已存在的 `openrouter_full_context_live_v2` 预注册 panel，不能另挑漂亮 pair。必须：

- 历史 development panel 与 prospective frozen cohort 分离；
- 不截断输入，超 context 显式记 coverage/missingness；
- 两个方向、固定模型目录/价格、逐 call 成本、失败与推理轨迹全保存；
- task/run/endpoint-cluster 统计，不能把共享 endpoint rows 当独立样本；
- 先给确切 model×pair×orientation calls、最大 token、USD stop 与余额门，再取得付费执行批准。

聊天或报告中的 key 不存、不使用。目前不发 live call。

### 2. generator + verifier + 稀缺昂贵 label 的 self-improvement demo

一般框架已有高度重叠的一手工作：

- ReST：generator 采样、reward 过滤、离线再训练；
- Self-Rewarding LM / SPIN：模型自评或 self-play 迭代训练；
- ReST-MCTS*：process-reward tree search 同时改进 policy/reward model；
- VDS-TTT：verifier 选择生成样本并 test-time LoRA；
- Sol-Ver：code solver/test verifier 共同 self-play；
- RAFT/RRTF/CodeRL：reward/test feedback 排序、选择或训练 code generator。

因此“generator+verifier 反复训练”本身不能成为 novelty。学长指出的 MLE 特殊性仍有价值：真实 label 昂贵且在生产中逐步
到达。可防守问题应改为：在**同一真实 execution-label budget** 下，joint adaptation 是否比 generator-only、critic-only、
memory-only 与 uniform 提高 held-out MLE end-to-end utility。

但本项目硬约束禁止微调/RL-finetune agent 底座，故不执行 Qwen3 0.6B/0.8B generator fine-tuning。以后若另批，可先做
不更新底座参数的 experience retrieval/in-context memory harness：把已执行经验经 outcome-blind schema 写入可审计 memory，
generator 只在 context 中读取；critic 仍是独立模块。这样既响应学长“agent 能根据过去经验自然发展能力”的要求，也不越过底座
更新边界。它仍需 related-work 与等预算 end-to-end 设计，不从 demo 小任务直接外推。

### 3. 三个 8×H200 RL trajectories

科学上值得做 training-time/trajectory qualitative audit，但报告只给含 token 的 W&B URL，且完整配置/奖励曲线尚未入仓。不得用
该 token。等待学长提供 public artifact 或安全脱敏 export 后，再固定：run IDs、checkpoint steps、pair panel、轨迹抽样 seed、
blind coding rubric、强模型对照与 inter-rater agreement。当前不凭网页截图下结论。

## 当前正向落点

该 outcome 最直接支持的不是立刻训 generator，而是我们当前论文容器：它亲自暴露了 mixed provenance、endpoint dependence、
跨 seed/checkpoint/test-population 比较和 resource-prompt integrity 的缺口。Decision Corpus + Predictor Benchmark + Audit Protocol
正是把这些缺口变成可复验资产；最新 FOREAGENT incidence-rank 外部审计进一步证明这些报告标准不只适用于我方语料。

一手 related work：

- https://arxiv.org/abs/2308.08998
- https://arxiv.org/abs/2401.10020
- https://arxiv.org/abs/2401.01335
- https://arxiv.org/abs/2406.03816
- https://arxiv.org/abs/2505.19475
- https://arxiv.org/abs/2502.14948
- https://arxiv.org/abs/2307.14936
