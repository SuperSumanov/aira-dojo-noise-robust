# Prospective drop 原子评分与 score registry：实现前预注册

日期：2026-08-14。协议：`prospective_drop_scoring_v1`。本协议发生在任何 activation 后新 drop 的 outcome
解封之前；写入时当前合格 run 数为 0，未读取 0812 label vault、论文 frozen pairs 或任何 activation 后 outcome。

## 1. 目标与不变量

目标是把每个 `prospective_drop_intake_v1` 的 label-free eligible manifest 与已经激活的固定 scorer 做不可歧义、
原子且可跨批复核的绑定。它不修改 scorer bundle、特征、模型、first-240/first-960 排序、支持门或论文 estimand。

固定对象：

- scorer activation receipt SHA-256：
  `cfab01a80536a50ef21c47ac269c7ce54a11a3b1f0b6daa5700873cbb02ce178`；
- fixed scorer bundle SHA-256：
  `c4b9713d5a994c90ac8e24674154ae78d39f7c7961473078c1c7d61ce1c15d23`；
- pre-cutoff run denylist SHA-256：
  `94c39feda828ed19e4a543b2abd7ad07bfb1e7266883bf49d0193cf48cbf012a`；
- pre-cutoff endpoint/exact-code denylist SHA-256：
  `2f0cc4f3dc203801c569237716ba82cbc2bde2f854b67eee6efa9452e92447e6`。

## 2. 单 drop 原子事务

输入只允许是：`drop_id`、intake 目录及其预期 summary SHA、固定 scorer 目录、固定 endpoint denylist、输出目录与
repo root。程序必须：

1. 先核对 intake summary 的 SHA、protocol/status、当前代码 commit/source SHA、activation receipt SHA、盲态字段、
   eligible manifest SHA 与 inventory；eligible manifest 必须是该 intake 目录下的固定 basename，CLI 不能另指一份。
2. 不 stat、不打开 `label_vault.jsonl`；summary 中的 vault SHA 只可作为不透明字符串转录。
3. eligible endpoint 为 0 时产生明确的 `NO_ELIGIBLE_ENDPOINTS` 完整事务，不调用 scorer、不制造空的科学预测；
   非 0 时调用现有固定 scorer，随后逐行复核 score CSV 与 eligible manifest 的 endpoint、task、run、parent、
   generation time、source SHA 完全一一对应，两个分数均 finite。
4. 所有文件先写到同文件系统临时目录，全部验证通过后一次 rename；输出目录已存在即拒绝覆盖。中途失败不留下
   看似完成的正式目录。
5. 顶层 summary 必须绑定 intake summary/manifest、scorer receipt/bundle、nested scorer summary/CSV 的全部 SHA，
   并记录 `labels_read=false`、`label_vault_opened=false`、`outcome_files_opened=[]`。

## 3. 跨 drop score registry

人工维护、append-only 的输入 registry 每行严格只有：

`drop_id/intake_dir/intake_summary_sha256/score_dir/score_summary_sha256`。

registry validator 对每个 drop 重新执行第 2 节的 hash/schema/card-level binding 检查，拒绝重复 drop、source archive、
physical run 或 endpoint；要求所有非空 drop 使用同一固定 receipt/bundle。输出只含每 drop 的 hash-locked index 与
summary，不合并或打开 label vault。registry 可以在收样期间重复运行，但不能决定生产停止，也不能改变 accumulator
冻结顺序。

## 4. 验证与杀死条件

实现阶段只允许：

- synthetic 非空 intake：至少两个 endpoint、一个 run，完整走 active bundle 推理与逐行复核；
- synthetic 篡改：intake summary/manifest、score CSV、metadata、重复 run/endpoint、额外 label 字段、错误 receipt
  任一出现必须 fail closed；
- 0812 真实 schema：只能得到 0-eligible 事务与 registry，通过且不读取 vault。

若不能证明临时目录失败不发布、card-level 一一对应，或任何测试需要读取 label/outcome，协议即不投入生产。这里
0 GPU、0 API、0 base-LLM update；synthetic/0812 结果只证明工程链，不构成论文效果证据。
