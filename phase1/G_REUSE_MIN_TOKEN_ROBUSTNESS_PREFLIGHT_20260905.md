# G-reuse minimum-token basis：长度口径与任务支配稳健性预检

日期：2026-09-05。状态：历史 train、0-model-fit 的结果前冻结敏感性；不改变上一项主结果。

## 1. 问题与可证伪假设

上一项在16K有效长度下得到70.54%的G阶段token减少。这里检验该数是否依赖16K截断，或由单个任务制造。
固定假设是：在4K、8K、16K和不截断raw四种口径下，确定性最小生成森林都保留逐任务全部rank gain，
总G-token减少均至少60%，且节省具有跨任务广度。任一冻结门失败即收缩主张，不另选cap或门槛。

## 2. Population、输入与隔离

输入与`G_REUSE_MIN_TOKEN_BASIS_PREFLIGHT_20260905.md`完全相同：历史L train、G train、92a9651 grouped
Cards、a466888-v3 batch manifest/上游manifest、4095端点length CSV及其既有SHA。候选仍是固定2745条
`equal observed config + unique projected source`记录相符边。禁止读取dev/test/vault、first960、Target300/522、
score、prediction、代码正文或方向值；不输出task、run、card或edge身份。

## 3. 唯一算法与固定口径

长度口径恰为`min(raw,4096)`、`min(raw,8192)`、`min(raw,16384)`、`raw`。每个口径都重新按
`(两端长度和, sorted endpoint IDs)`做Kruskal；L边先合并。不得结果后补cap、改tie-break、删任务或换basis。

## 4. Primary gates

四个cap必须全部满足：

1. basis逐任务rank gain与2745条full逐项相等，且总gain均为790；
2. G-stage token reduction均至少60%；
3. 删除任一任务后重新汇总的token reduction仍至少60%；
4. 任一任务占总saved tokens不超过20%；
5. 至少20/28个任务在四种cap下都各自减少至少50%的G tokens。

全部通过才称`G_REUSE_MIN_TOKEN_BASIS_COST_ROBUST_ACROSS_CAPS_AND_TASKS`。这里的“稳健”只指结构成本，
不指模型效果。

## 5. 资源矩阵与ETA

单CPU；producer A/B各不超过180秒，独立verifier A/B各不超过180秒，数学线程固定1。预计正式4--7分钟，
实现、测试、远端复验和留档35--55分钟。GPU=0，API=0，model fit=0，agent底座更新=0。

## 6. 随机性、重复与统计单位

算法无随机性、seed或warmup。A/B只是确定性复验，不是独立样本；edge、endpoint和task均不冒充独立统计样本。
逐任务门用于支配诊断，不做多重检验后的显著性主张。

## 7. 成本与公平口径

每次pair访问成本仍定义为两端token长度之和；四种cap只是预先固定的计量敏感性，不是GPU时间。L阶段保持不变，
比较的唯一旋钮是G basis构造使用的长度cap。raw口径不表示实际模型会吃无限上下文。

## 8. 完整性与失败关闭

读前credential-shape及SHA，读后再次验SHA；Python audit hook拒绝网络、子进程、未列数据与写入。新独占结果根，
producer A/B、独立实现verifier A/B、命令、解释器、耗时、stderr、源码和输出manifest全部留档。漂移或重复即失败关闭。

## 9. 输出约束

仅输出每cap的aggregate、匿名数值排序task rows、冻结门和计数。不输出selected edges、task/card/run身份或训练pool；
不写checkpoint。匿名逐任务行不能跨文件稳定链接到任务身份。

## 10. 混杂与反例解释

保rank是生成森林的不变量，不能当实证突破；实证部分是不同cap与leave-one-task下的真实token节省。如果任务广度门失败，
就明确报告成本节省集中；如果低cap失败，就只能保留16K单口径结论。即使全过，cycle edges仍可能帮助噪声鲁棒与优化。

## 11. 后续决策门

通过不解除source/config/experiment closure，不授权训练。只有同producer版本包、G0实测成本与明确GPU预算批准后，
该basis才可作为预先指定的成本challenger；full G-reuse仍应保留为效果主候选/对照，不能因本实验被静默替换。
