# 修复块关闭后的投资顺序（未启动后继实验）

写定时间2026-09-11 22:06 UTC／2026-09-12香港；13115尚未闭合，未读取本组最终成绩。
目的仍是同执行预算下critic是否改善最终成绩，而不是用更多工程测试冒充正结果。

1. 若本组产生可比最终成绩对，无论单次差值方向，优先保持当前科学条件，在原两任务做小规模新seed重复；
   不只选critic赢的任务，不反转分数，不按本组结果调top-k。保留失效run与真实成本。
2. 若仍没有可比对，先从完整关闭记录定位失败。只有共同生成可运行性仍为主要障碍时，
   才考虑两臂共同换更强生成器；不是从Flash旧run与Plus新run的差值中声称critic收益。
   模型能力改善不能预先保证，API成功/人工schema成功也不等于MLE成功。
3. 若候选已可运行、且新seed复验仍没有critic收益，不继续盲目扩大相同配方。完整候选池诊断用于分辨
   生成分布与选择质量，沿已有解释文档的全池/固定任务规则，而不挑漂亮候选。

后继真实矩阵必须等13115完全关闭并核算累计费用后才决定/提交。本文不激活账本、API或GPU。
可选的下一块仍为两任务×一个新seed×两臂4run，原gpu28双卡、镜像、critic、6step/300秒/3540秒。
具体seed、源版本、是否共同换生成器与新增GPU/API上限须随当时裁决冻结，不能事后追认。

## 只读核查的Plus选项与预算陷阱

2026-09-11 22:04 UTC读取OpenRouter公开Alibaba endpoint元数据，无凭据、无生成请求：

- Flash：输入/输出每百万token基础价0.195/0.975USD；32K档0.325/1.625；128K档0.52/2.6。
- Plus：基础价0.65/3.25USD；32K档1.17/5.85；128K档1.95/9.75。
- 两者context上限1,000,000、公开completion上限65,536；本项目输出上限仍8192。
- 在全context和最贵cache-write输入价下，计算上界Flash=0.6712992USD，Plus=2.517372USD。
  因此Plus不能直接使用当前0.70USD预留、1.50USD/run与新增2USD全块上限；会在发出请求前停止。
  若采用Plus，必须先重算并冻结整条费用上限、scope和未知请求余量，仍不超过原100人民币/10USD总授权。
  历史未知0.70USD继续结转，不能为腾预算释放或重置。

这是最坏责任上界，不是实际单次费用预测；更强模型可能改变输出长度，不能简单按基础单价倍数保证总花费。
Provider仍仅Alibaba、禁止fallback；上线前重新核实catalog，价格上升即拒绝。

来源：[Flash官方endpoint](https://openrouter.ai/api/v1/models/qwen/qwen3-coder-flash/endpoints)、
[Plus官方endpoint](https://openrouter.ai/api/v1/models/qwen/qwen3-coder-plus/endpoints)、
[Plus模型说明](https://openrouter.ai/qwen/qwen3-coder-plus)。
