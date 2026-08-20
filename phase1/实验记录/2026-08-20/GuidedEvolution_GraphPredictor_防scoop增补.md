# Guided Evolution / graph predictor：防 scoop 增补

日期：2026-08-20。口径：一手论文核查；不读取任何 v11 frozen、0812 label vault 或 first-960 outcome。

## 裁决

“把 ML program 编成图、训练二元 better/worse predictor，再用 predictor 跳过昂贵执行并引导搜索”已经被直接覆盖，
不能作为本项目的方法 novelty。最接近的先例是 Co-Reyes et al. 的
[Guided Evolution with Binary Discriminators for ML Program Search](https://arxiv.org/abs/2402.05821)：

- 它把 symbolic optimizer、RL loss、symbolic regression 与 NAS candidate 统一编码为 DAG；
- 在线训练二元图 predictor 判断一对程序谁更好；
- PAM/PAM-RT 反复 mutation，并用 predictor 比较 child 与 parent、拒绝预测较差的 child；
- 在 Hero 与 AutoRL 报告约 3.7× 与 4× 的搜索加速，并做 predictor accuracy/noisy-oracle 与 GNN 架构消融。

这比一般 NAS predictor 更贴近我们的 sibling/local-decision 设定。ICML 2024 的
[GRAF](https://proceedings.mlr.press/v235/kadlecova24a.html) 又表明便宜、可解释的 graph features 与其他 proxy
组合可成为很强的 NAS performance predictor。因此当前 WL/AST 四臂只能写成 benchmark baseline completeness，
即使未来取得正效果，也不能写成“首次 graph predictor”或“首次用 binary critic 加速 ML program search”。

## 仍可守住的边界

上述工作没有替代本项目的核心数据与审计资产：我们研究的是 LLM MLE agent 在真实 physical run 中生成的完整
Python solution、同 parent sibling、连续外部 evaluator score、run-clean 切分、label repeatability、gap/noise、
query/init/execution 成本，以及 outcome-unread 的时间外 first-960 confirmation。这些仍应是论文主贡献。

方法侧若以后做 end-to-end search，PAM-RT 应作为必须比较/适配的已知 baseline，而不是重新命名一个 heuristic。
可检验的新问题只能收窄为：该已知机制能否从 primitive DAG 迁移到长代码、LLM operator、强近平局与有缺失的
MLE-agent choice sets；正结果来自严谨的新 domain evidence，不来自算法首创。任何正式 end-to-end 实验仍须先给
固定 operator/base model/task/budget、PAM-RT 参数、run 数和 GPU·时矩阵，不因本次文献发现自动启动。

## 对当前实验的影响

- 正在构建的 `step_only / WL / WL+static / WL+static+TF-IDF` 配置不变，因为它本来就被预注册为 extension baseline；
- primary first-960 scorer、停止门和 closure 不变；
- 不根据该文献或当前 blind covariates 增加第五个 arm；
- 严格 temporal 方法效果只统计自动 activation receipt 之后的新 runs；当前前缀只作 outcome-unread 支持。
