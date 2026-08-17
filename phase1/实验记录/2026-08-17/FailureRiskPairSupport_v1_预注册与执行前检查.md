# Failure-risk parent-matched pair support v1：预注册与执行前检查

日期：2026-08-17。状态：`NOT RUN`。本文件冻结在读取 691 个 failure nodes 的 code 之前；不训练模型，
不改变 score-channel 主实验，不授权 GPU/API。

## 唯一问题

train-only source opportunity 中，是否能构造足够多“同 parent、同 physical run、一个 retained success sibling、
一个 execution-failure sibling”的静态代码对，支撑后续 learned failure-risk controller？本轮只审计支持度，
不报告 accuracy 或 search utility。

## 十三项执行前检查

1. Inputs：v11 cards SHA `6794acbf...c5701b75`；status per-child SHA `bfb9870d...fde0d2`；taxonomy
   per-child SHA `a5f46021...ca2087`；frozen b0/b1/b2 SHA 固定为既有三份 frozen test。
2. Scope：只取 status 中 `role=train`、execution error、parent match 的 691 children。
3. Security：先对完整 journal bytes 做 credential scan；命中整 journal skip，绝不 parse；只在通过后读目标 code。
4. No output code：只在内存计算 code bytes/SHA；产物不含原始代码、diagnostic、grade 或 pair orientation。
5. Success definition：retained v11 child card；不读取 numeric grade，且 lineage parent 与 failure 的 expected parent 相同。
6. Run contract：parent、retained child 必须同 physical run；该 run 不得属于 frozen b0/b1/b2 的 92 runs。
7. Dedup：每 parent 只选字典序最小的 nonempty failure；success 取字典序最小、同 run 且 code SHA 不同的 retained child。
8. Identical code：若 parent 的 retained code 全与 failure 完全相同，则不构对并单列，不把随机执行差异伪装成可预测信号。
9. Size gate：eligible unique-parent pairs >=300，且占 unique failure parents >=0.50。
10. Diversity：>=8 tasks；>=6 tasks 各至少 20 pairs；dominant task share <=0.35。
11. Integrity：failure code refind >=0.95；credential target SHA=0；frozen run overlap=0；identical-only parent share<=0.10。
12. Resources：CPU-only，预计每次 <10 分钟；双跑逐字节一致；完整测试；GPU=0、API=0。
13. Stop：任一门失败则关闭 controller 训练；通过也只允许另写模型预注册，不自动启动训练或声称方法收益。
