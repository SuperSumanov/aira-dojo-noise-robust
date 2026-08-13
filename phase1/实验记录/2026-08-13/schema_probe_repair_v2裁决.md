# Schema/probe-first V2 冻结裁决

日期：2026-08-13
状态：**正式 PASS；仅通过可行性门，不是方法收益结论**

## 1. 冻结判据与裁决

预注册唯一 PASS 条件是：两个新任务都在 host 120 秒内产生合法、候选特异、可由 pristine grader
评分且随后不变的 `candidate_probe.csv`，并且至少一个任务在同一进程中于 600 秒内产生合法 full
transition。

正式验证器输出：`PASS, probes=2/2, full_transitions=2/2`。独立验证脚本没有导入项目验证器或
worker，直接重算 manifest、source/code/artifact、marker 与 CSV 哈希，检查拓扑和时限，并重新调用
pristine grader；独立结果同样为 PASS。

| task | generation topology | probe host capture | probe pristine score | full first seen | full pristine score | probe→full |
|---|---|---:|---:|---:|---:|---:|
| spaceship-titanic | root→valid draft | 12.542975 s | 0.77241 | 21.483079 s | 0.81494 | +0.04253 |
| tweet-sentiment-extraction | root→valid draft | 11.046629 s | 0.43082 | 99.575390 s | 0.53027 | +0.09945 |

两个任务的 candidate 和 full 均为不同内容哈希；probe 在 full 写出后保持不变。Spaceship probe
相对 sample 的预测列有 434/870 行不同，tweet 为 2749/2749 行不同，且两者预测均非常数。四个冻结
artifact 的独立重新评分逐位复现上述分数。

## 2. 语义代码审计

静态检查之外，冻结 leaf 的代码在 outcome 后做了只读语义核对：

- Spaceship probe 从 `train.csv` 的 `Transported` 标签与实际特征训练 50-round LightGBM，再预测 test；
  full 阶段继续做交叉验证与 LightGBM/HistGradientBoosting 集成。
- Tweet probe 从训练集 `selected_text` 构造字符级标签，在 1,024 个训练样本上训练一轮同族 Char-BiLSTM；
  full 阶段继续五折训练与测试集集成。
- 两者都在同一 Python 进程中先原子写 probe、提升同一字节为 `submission.csv`，之后才进入 full；没有
  sample-copy、常数、随机或 task-independent fallback。

因此，本轮通过的不只是 CSV schema，而是“由候选方法和真实训练标签产生的早期可评分工件”这一工程门。

## 3. 必须保留的边界

1. 样本量只有两个预冻结任务；不能估计总体 compliance rate、置信区间或 venue-level 效果。
2. 两个 draft 都第一次执行成功，完全没有触发 debug。因此本轮虽然按预注册命名为 conditional-debug gate，
   **不提供任何 debug 有效性的证据**。
3. 两个 probe 分数都低于 full，说明 probe 不是 full 的替代；是否能正确排序真实 siblings 尚未检验。
4. 本轮没有 original-prompt 对照，不能把成功归因于 contract，也不能声称 coverage、final quality、regret
   或固定预算搜索收益改善。
5. 自报 elapsed 比 host capture 短约 6–7 秒；后续一律以容器外 monotonic host time 为主。
6. API client 的记录中 `cost=0.0` 只是自定义 endpoint 未配置价格，不能解释成无货币成本。

## 4. 资源与可复现性

- 生成：job 10630，两个 scientific steps 均 `COMPLETED 0:0`；父 allocation 13:11、2 GPU。
- replay：array elements 10635/10636，分别 3:06 与 1:42，均 `COMPLETED 0:0`。
- scheduler allocation 总计 0.519444 GPU·h；scientific step 口径为 0.463333 GPU·h，前者作为成本主口径。
- LLM 共 4 次成功调用、154,799 tokens；Spaceship 74,460，Tweet 80,339。未发生候选 retry。
- frozen commit：`c1dc17420e95b9e2994a474c25afdcb85063ab36`。
- replay manifest SHA256：`77b4f35f7db224cd0d80fad4df1f6862a171d951a6d061fcc3f626c64ad738b0`。
- runtime image SHA256：`801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda`。
- 密钥只从远端 `.env` 注入运行环境，归档中不包含密钥或 `.env`。

## 5. 下一步裁决

按预注册，PASS 只授权在全新任务、全新 seed 上做小规模 causal safety/discovery A/B：标准 draft prompt
对比只增加 artifact contract 的 probe-first prompt。先比较 time-to-first-scoreable artifact、120 秒 coverage、
失败率和 full quality；只有 coverage 上升且 full quality 没有方向性损害，才冻结多候选固定预算搜索确认。

不能在这两个任务上继续调 prompt，也不能把它们并入后续 A/B 的推断分母。
