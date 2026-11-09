# AI4Code：notebook、cell 顺序与跨样本累计 Kendall tau

状态：数据与评测逻辑参考，尚未接入转换代码。下述转换步骤用于后续实现和人工审查。

## 原始准备与当前文件排列

代码依据：`src/dojo/tasks/mlebench/mle-bench/mlebench/competitions/AI4Code/prepare.py`、同目录 `grade.py` 和 `config.yaml`。

上游先以 seed 0 打乱 `train_ancestors.csv`，按 `ancestor_id` 聚组，依次放入完整组，直到得到 20,000 个测试 notebook；其余为训练。当前公开训练 119,256 个 notebook，训练 ancestor 有 111,433 个不同值。

| 文件 | 排列与含义 |
| --- | --- |
| `public/train/<id>.json` | 一份 notebook；顶层 `cell_type` 和 `source` 都以 cell ID 为键，分别给出 code/markdown 类型和源文本 |
| `public/train_orders.csv` | `id,cell_order`；每行是一份 notebook 的正确完整 cell 顺序，以空格连接 cell ID |
| `public/train_ancestors.csv` | `id,ancestor_id,parent_id`；用于辨认有关联的 notebook，不是预测标签 |
| `public/test/<id>.json` | 同样结构的无顺序标签输入 |
| `public/sample_submission.csv` | `id,cell_order`；使用 JSON 内 cell_type 键的既有顺序生成示例 |
| `private/test_orders.csv` | 原测试正确完整 cell 顺序 |

JSON 的键顺序只是文件里已有的排列，不可拿 train_orders 的正确顺序重写 warmup JSON。模型通常利用 code cell 的相对顺序预测 markdown 的位置，但最终提交需要每个 notebook 的**全部 cell ID 的一个排列**，不是只交 markdown，也不是每个 cell 一行。

## grader 如何对齐和计分

1. 检查提交/答案行数相同，含 `id,cell_order`，notebook ID 集合相同。
2. 将 cell_order 转为字符串，按 notebook ID 排序，按空格拆出 cell ID 序列；检查每份预测长度与答案相同。
3. 将预测中每个 cell ID 映射到答案序列中的下标，计算该下标序列的逆序数 S_i。一对 cell 的相对顺序颠倒算一次。
4. 跨 notebook 求和，计算 `K = 1 - 4 * sum(S_i) / sum(n_i * (n_i - 1))`，越大越好。全部正确为 1，全部反序为 -1。

这是按 cell 对数加权的整体指标，不是每份 notebook 的 Kendall tau 再等权平均。比如 100-cell notebook 的分母贡献是 9,900，10-cell notebook 是 90。warmup 子集必须直接调用 grader，不能从混合总分按 notebook 数相减。

当前 grader 的限制也要记录：它只检查 cell 列表长度，不显式检查每个 notebook 的预测 cell ID 唯一且集合完整。未知 cell 会在查找答案下标时触发异常，而重复已知 cell、遗漏另一个 cell 但总长度相同，可能没有被拒绝。转化测试要覆盖这个案例；若外层要新增严格排列校验，应明确作为规则强化，并对原测试和 warmup 一致执行，不修改上游文件，也不悄悄宣称这是现有 grader 的行为。

## 转化步骤

目标 W 为 500 个 notebook。以 ancestor_id 为组，用固定 seed 选取完整组，总 notebook 数不超过 500，记录实际数。缺失 ancestor、同一 ID 多条祖先记录等情况先报错分析，不把空值随意当成独立组。

1. 检查 JSON 文件、train_orders 行和 train_ancestors 行的 notebook ID 一致；正确 cell_order 恰好覆盖 JSON 中的 cell ID。
2. 在新版本将选中 notebook JSON 从 `train/` 移到 `test/`，保持 JSON 内容和键顺序不变。
3. 从新 train_orders 和 train_ancestors 删除对应行；原 cell_order 写入私有 warmup 答案。
4. 按 JSON 既有顺序为新增 notebook 生成 sample 行，检查其 ID/cell 集合有效。
5. 检查剩余训练和 warmup 没有共享 ancestor，三个 notebook ID 集合互斥；分块复用原 grader。

## 人工检查重点与可能问题

- notebook ID、cell ID 和 ancestor ID 是三个层级；不能按 cell 抽样，也不能把 ancestor 的数量当成 warmup notebook 数。
- 分组不等于清除了所有相似内容：ancestor 元数据能提供的关联范围需要如实说明，不应凭文件名推断独立性。
- 报告 notebook 大小、code/markdown 数、文件字节数与 `sum(n_i*(n_i-1))`，帮助解释负担和分数权重。
- 常见问题包括只输出 markdown、丢 cell、重复 cell、code 相对顺序错误、按不同 ID 排序后错配。外层全局 ID 唯一性检查仍然必要，因为上游集合检查不等于严格逐项唯一校验。
