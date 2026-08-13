# Task-conditioned + top-centered parent ranker：正式裁决

时间：2026-08-14。预注册协议：`task_topcenter_v11_discovery_v1`。代码截面：
`c84d6c6c5f1a937d51755564ba9af2f9dde3ed73`。

## 一句话裁决

独立 verifier 裁决为 **`VERIFIED_DISCOVERY_NO_UNLOCK`**；`frozen_read=false`。task residual 与
top-centered objective 都没有把 0.5B frozen representation 变成稳健的真实 sibling selector，关闭本实现，
不读 `decision_frozen_v11_b*`。

## 预注册执行

- exact train-only pool：4,263 pairs / 333 physical runs / 23 tasks / 2,293 parents / 5,499 endpoints；
- 5-fold outer physical-run OOF，outer 内再按 physical run 做 3-fold 选正则；
- global、task-conditioned 两类头 × all-pair、winner-vs-rest parent-equal top-centered 两类目标；
- 所有配置、正则网格、lexicographic selection、bootstrap seed 和 unlock gate 均在 outcome 前固定；
- 13 项长实验预检全部通过，engineering smoke 不计算 accuracy；
- producer 完成后由不导入 producer 的 verifier 重开输入、features、weights 和 inner OOF score matrices，
  独立重建模型选择与全部指标。

## 结果

主模型 `nested_task_topcenter`：pair=`0.5066854327938072`，complete-parent
top-1=`0.45108455068614434`，parent-equal gap utility=`0.5125829562017966`。

相对 fixed global head：

- top-1 delta=`0.00398406374501992`；run-CI
  `[-0.01717246054159702, 0.02644857206952395]`；task-CI
  `[-0.010422655560196711, 0.02148915771321664]`；
- utility delta=`0.002076308434788266`；run-CI
  `[-0.017060791108872136, 0.025849640614815577]`；task-CI
  `[-0.008503888655465223, 0.019741606156476296]`。

绝对 top-1、utility、任务一致性、两类效果量和四个 clustered-CI gate 均未通过。orientation oracle=1.0、
random pair control=`0.5036359371334741`、outer run overlap=0、所有 fits accepted，故不能把失败归因于
方向反转、程序没训、fold 泄漏或 optimizer failure。

## 机制解释与下一步

2×2 消融显示：task residual 在 top-centered 目标下几乎没有增益；top-centered 在 global 头下只有约
0.49 个百分点 top-1 / 0.40 个百分点 utility 的微平均变化，任务聚类区间仍跨零。因而继续扩大 task
residual 网格或对同一 OOF outcome 手工挑任务会构成调参污染。

当前允许的下一候选只有另立协议的 exact-same-pool 异构 predictor audit：在同一 5-fold run OOF 上生成
char-TFIDF 与 static family 的训练期预测，先冻结互补性标准；只有其错误确实补足 frozen head，才允许做
严格 nested ensemble。该步骤仍不接触 frozen 文件，也不能把 NAS 已有的 ensemble 技术包装成 novelty。

完整结果见 `phase1/results/task_topcenter_v11_20260814/`。
