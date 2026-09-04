# G-reuse效果读出统计核预检

冻结于2026-09-04 22:08 UTC，在任何新模型效果或保护结果读数前。

1. **问题**：把已冻结五臂效果门中尚未机器定义的聚合、CI、tie、LOTO、任务贡献和L1层级补齐。
2. **输入范围**：统计核只接受匿名SHA cluster ID、严格非tie truth sign及完整同池margin；正式caller尚未实现。
3. **禁止输入**：本轮不读取任何真实label、prediction、accuracy、utility、原始身份或保护cohort。
4. **估计量**：每任务先做pair-micro、再平均seed，最后任务等权；TF-IDF同池单预测从每个full seed分别相减。
5. **不确定性**：固定20,000次task-cluster percentile bootstrap、固定hash索引和type-7分位；不使用pair-i.i.d.区间。
6. **稳健性**：同时给三个seed符号、全部LOTO及按未归一化正确数增益定义的单任务正贡献份额。
7. **层级**：deployment与L1重复训练混淆先过，之后才允许计算hash质量对照；后级不能救前级。
8. **成功定义**：只在全部deployment、必要的full>L1以及full>hash门通过时给core positive；synthetic pass不算效果。
9. **安全**：输出不得含row truth、row prediction或原始task/parent/run/endpoint ID；正式unseal仍需另一个认证caller。
10. **复现与资源**：纯stdlib、合成fixture测试；GPU/API/model fit/base update/protected read均为0。
11. **停止条件**：schema/同池/哈希/有限性/重复/tie/任务数/协议语义任一不符即fail-closed；结果后不得改门。
