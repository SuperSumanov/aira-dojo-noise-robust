# 学长现有trainer与G-reuse效果协议的兼容性审查

审查对象是2026-09-04 22:18 UTC可见的公开`dojo-reproduce` head
`b8d095180415957aa1bab31fa53ead1bba261c03`。四个所读源码文件先做凭据形状扫描，均无命中；没有读取outcome文档。

结论：这些脚本可以保留作学长自己的探索性scaling记录，但**不能原样作为G-reuse正式效果训练或prediction escrow**：

1. `src/train/bradley_terry.py`读取`test_pairs`，把`intask_split==test`直接设为训练期`eval_dataset`；因此外层test会随
   `eval_steps`重复访问。它不符合whole-experiment train/dev/frozen和一次性冻结评测。
2. `scripts/train/h200/train_scale_reward.sh`的当前8000/16000臂把同一pair文件同时传给train/test，并设置
   `eval_steps=20`、`save_strategy=no`。即使训练内部按`intask_split`分行，outer test仍周期评估，且脚本本身不产出可锁定
   的final checkpoint，不能作为G-reuse 15-fit输入。
3. standalone `bradley_terry_evaluation.py`按`better/worse`有标签顺序编码，直接计算accuracy并打印原task名；它不是
   canonical label-blind scorer，也不产出我们需要的同池margin escrow。

这不撤回学长0820 scaling的探索性信号，只维持已有边界：cross-config mixing、outer test周期评估和部分未正常结束使其
不能直接确认scaling。我们独立的G0路径使用修订源`5f3bc362...`，已禁止test参数并固定唯一dev/final-only边界；但最近
作业在真正训练前失败，且该路径仍未实现label-blind margin exporter。

因此最短兼容路径不是修改学长现有outcome或反推旧accuracy，而是：同producer包到达→G0真实成功→锁定五臂全部final
checkpoint→仅给模型进程canonical无标签pairs+Cards+checkpoint→写margin escrow→认证后由另一个caller一次连接truth。
escrow schema/validator见`g_reuse_prediction_escrow_contract_v1.json`与
`results/g_reuse_prediction_escrow_3d75d2e_20260905/README.md`。这份审查不授权GPU或读取结果。
