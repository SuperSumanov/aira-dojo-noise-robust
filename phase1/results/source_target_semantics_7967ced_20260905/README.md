# 当前成绩目标语义：固定源码合成复核

2026-09-05香港22:44。结果前checker commit：`7967ced39996173c0c921cedd3f1bcca7c260262`。
这补齐构建器的目标语义，不是新模型效果、实际生产回执或合格训练包。

## 结果

固定学长源码`b8d095180415957aa1bab31fa53ead1bba261c03`的`build_subtree_pairs.py`，
SHA-256=`3121b14703bcb67007c8070adb6e7a7dd8d4844c00a9d7de8621161fce7a73cf`。
先credential-shape扫描，无命中；仅编译原函数/类体，不编译CLI/main，不导入Cards文件读取器。

唯一执行的参数是`budget_steps=-1, budget_seconds=0`，仅合成Cards，cap=1000、seed=7：

- 两任务分别覆盖指标越大/越小越好，10个有穷成绩节点、18个不等成绩pair。
- 原构建器结果与不调用其树遍历/成绩/方向函数的直接当前成绩比较完全一致。
- 每个节点的目标等于自身成绩；更优后代、无标签连接节点、叶节点、并列与NaN均包含在样例中。
- 反转run/Card输入顺序后，完整未截断pair集合与方向不变；不声称cap截断时文件顺序也不影响抽样。
- 重复Card、跨physical-run父子关系两个负控制仍拒绝。
- A/B两个独立进程回执逐字节相同：
  `4c84cf610f6974f68cddd3a27174fee6c0c18cff2be8482c0455c645d726c52d`。

Checker字节SHA为`dfbd94a674d47a15fd55c4f80a2fcdd6b09e4a20a9ddf71fb7d18b349255e5be`，
上传前Git blob、远端文件和A/B回执内自报hash一致。执行环境为现有远端`venvs/exp/bin/python`，
只需标准库、无模型/张量训练。两次命令分别为：

```text
/research/d7/spc/yzyang4/venvs/exp/bin/python -B /tmp/source-target-7967ced.py --output /tmp/source-target-7967ced-A.json
/research/d7/spc/yzyang4/venvs/exp/bin/python -B /tmp/source-target-7967ced.py --output /tmp/source-target-7967ced-B.json
```

## 接入含义与边界

批处理`build_batch_value_pairs.sh`默认传`-1`。构建器本身CLI默认`0`，源码把`0`解释为不限后代深度，
**不是本项目口语中“K=0/只看当前节点”的同义值**。本轮没有执行`0`或任何正数预算，未恢复lookahead。
以后实际生产命令必须显式记录`-1`；不能因都叫“value”就混用目标。

源码还存在两点应知道的行为：其文档提到排除叶节点，但执行体实际上保留有自身成绩的叶节点；
即使传`-1`仍先遍历lineage/runtime再过滤后代。因此该构建器不是结果盲摄取工具，不能直接在保护全集运行。
没有修改学长源码，也没有改变任何冻结实验门。

额外只读Git blob对照：最新head与候选四LFS的发布commit
`5baccb170ce287f9c8eed7b23ccf693a0268515a`中，Cards、augmented decision、subtree三个构建器，
以及value/draft/improve三个batch脚本，六个源码文件逐字节相同。
这是发布树的源码一致性，不证明发布时实际执行了这些源码/参数。

实际开发范围、run→experiment/producer-instance映射、当时执行命令与评分出处仍待生产记录补齐。
真实payload读取0，模型fit/GPU/API新增0，未把声明包提升为可训练来源。
