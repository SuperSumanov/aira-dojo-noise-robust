# Source Retention：run-cluster robustness v1 正式裁决

日期：2026-08-21。正式代码 commit：`fa5d65507bd6bab76b7bfaeda04584fae21b78c9`。
状态：`INSUFFICIENT_RUN_CLUSTER_TASK_SUPPORT`。

## 裁决先行

这项结果后压力测试没有通过预注册支持门。固定的 v1 15-task universe 中，只有 9 个任务同时具有
train≥5、frozen≥3 个 distinct physical runs，低于预先要求的至少 10 个任务。因此不能把原有
parent-equal source-retention transport 提升为“run-cluster robust”。不会降低门槛、替换任务集、改变
run weighting 或将九任务数字包装成确认性正结果。

失败是**支持不足**而非观察到方向反转：9 个合格任务的 run-equal train→frozen Spearman rho=`0.7`；按
train run-equal profile 预定的 top/bottom tertiles，在 frozen 上 high-minus-low=
`0.1973544973544974`。这两个值只作为描述性方向证据。冻结程序规定支持门失败后不运行置换、task×run
hierarchical bootstrap 或 LOTO，因此 p、区间与 LOTO 均未产生，不能据此宣称显著或稳健。

## 支持结构

通过 run 门的 9 个任务是：

- `chaii-hindi-and-tamil-question-answering`；
- `denoising-dirty-documents`；
- `dog-breed-identification`；
- `leaf-classification`；
- `mlsp-2013-birds`；
- `nomad2018-predict-transparent-conductors`；
- `petfinder-pawpularity-score`；
- `spooky-author-identification`；
- `tabular-playground-series-may-2022`。

未通过的 6 个任务及 train/frozen run 数分别是：Aptos=`2/1`、Histopathologic=`8/2`、Russian text
normalization=`8/2`、Tweet sentiment=`3/3`、US patent=`10/2`、Whale=`12/2`。主要瓶颈是 frozen role
每任务只有 1–2 个 physical runs，而不是 parent 行数不足。

## 对论文主张的影响

原 v1 的 15-task parent-equal transport（rho=`0.8151043256715026`，paired-task bootstrap 95% CI=
`[0.5368038356525456,0.9594112875401973]`）仍是按其结果前协议成立的描述性正结果；本轮没有发现反向
证据。但 reviewer 的“同一 run 内多个 parents 形成伪重复”质疑尚未被当前 release 充分排除。正文必须写成：

1. source retention 存在跨 disjoint-run roles 的 task-conditioned parent-weighted profile；
2. run-equal 九任务点估计方向一致，但预注册的 run-cluster 支持门差 1 个任务，故稳健性仍未确认；
3. 后续只能由**自然新增且 outcome-blind 的 frozen-role physical runs**补足支持后，在新 temporal escrow 中
   独立确认；不得复用本轮结果调整门或主动选择任务追救。

该裁决不改变 strict-future transition escrow、first-960/closure 或 clean Qwen G0/G1 的既定门，也不产生
predictor/search utility、MAR、因果 task effect、完整 choice set 或方法 novelty 主张。

## 完整性

- 输入仍为 3,252-parent 表，SHA-256=
  `75c02200d1f9b8d87614762a9f2b71ba3c678d598ff28bc237c8a46a4bc36d03`；
- producer×2 与不 import producer 的 verifier×2 分别逐字节一致；
- verifier 独立重建最大差=0，状态=`INDEPENDENT_RUN_CLUSTER_ROBUSTNESS_VERIFIED`；
- focused tests=`5 passed in 1.06s`；完整 phase tests=`632 passed, 25 warnings in 58.45s`；
- forbidden scientific path hits=0；文件名/内容秘密扫描均为 0；正式产物可写文件=0；
- producer summary SHA-256=
  `3a25ced1a63e97ae3e10b22dcc808c299a1c175ac30e04e55fd724ee5a4cfb25`；
- producer manifest SHA-256=
  `5c1db479a39312390911fea594f47411eae6c632b40e32f5cc383e3ab487dc58`；
- per-task run table SHA-256=
  `206d3f5a08d0f75557c4ff345dff6263899ccc78f995765339e7ee23be1abb23`；
- 全量 `SHA256SUMS` 文件 SHA-256=
  `e7ae5c4508904d9656ece5b553e94a168441b569d5c5497496a3de4474efdf75`；
- 完整只读产物：
  `/research/d7/spc/yzyang4/source-retention-run-cluster/fa5d655-v1`。

GPU=0、API=0、底座更新=0，且没有读取 code、numeric outcome、pair orientation、prediction 或
prospective outcome。
