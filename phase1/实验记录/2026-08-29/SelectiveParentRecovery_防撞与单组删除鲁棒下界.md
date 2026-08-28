# Selective parent recovery：防撞与单组删除鲁棒下界

日期：2026-08-29。性质：基于已公开 aggregate 的相关工作裁决与确定性代数推论；不是新的预注册实验，也未读取任何
新 stratum、identity、prospective value 或 Target-522 profile。

## 1. 防撞裁决

以下宽 novelty 必须关闭：

1. **代码相似性恢复软件 lineage 已有成熟先例。** [ILINE / IEVAL](https://www.usenix.org/conference/usenixsecurity13/technical-sessions/papers/jang)
   已在 straight-line 与 DAG 软件版本上做自动 lineage inference，并以 graph-arc edit、partial order 等指标评价；
   “根据程序相似度找 parent”不是我方首创。
2. **selective classification / reject option 是标准问题。** [Selective Classification via One-Sided Prediction](https://proceedings.mlr.press/v130/gangrade21a.html)
   明确研究 accuracy--coverage trade-off 与高精度 acceptance region；`top-second margin + abstain` 不能当一般方法创新。
3. **calibrated lineage verification 与诚实 abstention 已被直接覆盖。** [modelDNA](https://arxiv.org/abs/2607.10617)
   对模型 parentage 做 calibrated verification、hard negatives 与 abstention；
   [Attesting Model Lineage by Consisted Knowledge Evolution](https://www.usenix.org/system/files/conference/usenixsecurity26/sec26_prepub_shang.pdf)
   也利用 parent/非 lineage similarity 分布拒绝错误 lineage claim。
4. **agent execution provenance 已形成独立研究框架。** [From Agent Traces to Trust](https://arxiv.org/abs/2606.04990)
   已系统整理 execution graphs、provenance relations、trust functions、audit 与 recovery。不能申“首次审计 agent trace
   provenance”。

因此当前结果不能定位成新的 lineage/selective-classification 算法。可守差异化组合仍是：在自然产生的 MLE-agent
search physical tree 上，使用完整 same-run exact-depth 候选集，以 outcome-blind、run-disjoint、时间前瞻且失败保留的
协议交叉认证 recorded parent；同时绑定 benchmark split、三种 wrong-parent 分母和 append-only release provenance。

这也回答学长对 heuristic 的担忧：该规则不控制 agent、不改变搜索策略，也不冒充 agent 自然学得的能力；它是数据发布
完整性层。将来若做可学习 controller，必须另用固定预算端到端 utility 评价，不能拿本结果代替。

## 2. 已公开 aggregate 的精确错误下降

test 无 reject 的错误率为 `62/2907=0.021327829377364983`；固定 reject 后为
`7/2691=0.002601263470828688`。二者比值为：

`(7/2691)/(62/2907) = 2261/18538 = 0.12196569209191931`。

因此相对错误率下降为：

`1-2261/18538 = 16277/18538 = 0.87803430790808068`。

即 87.80% relative error reduction。该值是正式 aggregate 的确定性重表达，不是新增 readout；不能据此外推语义 ancestry
正确率。

## 3. 删除任一最大贡献 group 后的保守 precision 下界

正式结果给出 accepted total=`2691`、correct=`2684`、errors=`7`。最大 task accepted contribution share=`44/207`，
故最大 task 恰为 `2691×44/207=572` accepted edges；最大 run share=`55/897`，故最大 run 为
`2691×55/897=165`。

为了得到对 precision 最不利的删除，保守假设被删除最大 group 的每条 accepted edge 都正确，7 个错误全部保留在其余
population。于是：

- 删除任一单 task 后，remaining precision 至少
  `(2684-572)/(2691-572)=2112/2119=0.99669655497876353`；
- 删除任一单 physical run 后，remaining precision 至少
  `(2684-165)/(2691-165)=2519/2526=0.99722882026920034`。

两者仍严格高于预注册 `49/50` precision 门。这是只依赖总计数与最大贡献 share 的 worst-case lower bound，不需要知道
哪个 task/run 最大，也没有读取匿名 group profile 之外的新信息。它加强“结果不由一个大 task/run 撑起”的解释，但不替代
coverage、breadth 或真正 Target-522 前瞻确认。

## 4. 下一步裁决

- 继续等待已上线的 fixed-threshold Target-522 forward certificate；这是从开发正结果升级到真正未来 transport 的唯一
  高优先级实验。
- 可以把 validator 做成 benchmark release 工具，但只作为 artifact contribution，不称算法创新；canonical edge 永不
  静默改写。
- 暂不继续切 887 的更多漂亮子组；整体、task/run breadth、最大组删除下界已经足够，继续 post-hoc slicing 会增加
  researcher degrees of freedom。
- 不恢复旧 HCE、多保真、Probe、score-channel effect 或 K≥1 lookahead。
