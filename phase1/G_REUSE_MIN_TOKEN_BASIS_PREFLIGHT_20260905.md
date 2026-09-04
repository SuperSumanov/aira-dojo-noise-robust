# G-reuse 最小 token comparison basis：结果前预检

日期：2026-09-05。状态：历史 train、0-model-fit 的结构/成本候选，结果前冻结。

## 1. 问题与假设

当前记录相符敏感性集合有2745条边，在固定L节点上提供790 incidence-rank gain。问题是能否只保留连接
L连通分量所必需、pair-token成本最低的一组真实G边，同时逐任务保留全部790 rank gain，并将G阶段有效
token至少降低60%。这将形成待验证的训练成本候选，不是模型效果。

## 2. 输入与 population

输入固定为历史L train、G train、92a9651 grouped Cards、a466888-v3 batch manifest/上游manifest及已验的
4095端点length CSV；所有SHA沿用既有回执。先用上一项同一规则得到2745条`equal observed config +
unique projected source`边，不读dev/test/vault、first960、Target300/522、代码、方向值、score或prediction。

## 3. 唯一算法

以L全部4095端点建立并查集，先合并全部L边；将2745条候选按
`(valid_tokens(a)+valid_tokens(b), sorted endpoint IDs)`升序做Kruskal。只有连接当前不同分量的边入basis。
端点ID仅作确定性tie-break，不输出。不得结果后更换权重、加入方向、删任务或做二次优化。

## 4. Primary gates

三项必须同时成立：basis在每任务与full-filtered的rank gain逐项完全相等；总gain仍为790；basis G-stage
pair-token相对2745条至少减少60%。通过只称`G_REUSE_MIN_TOKEN_BASIS_STRUCTURAL_COST_SUPPORTED`。

## 5. 资源矩阵

单CPU，producer A/B各≤180秒、完全独立实现verifier A/B各≤180秒；数学线程1。预计正式4--7分钟，
实现/复验25--35分钟。GPU/API/model fit/base update=0。

## 6. 随机性与重复

无随机性、seed或warmup。A/B只验确定性，不计独立样本。边、端点和任务不能当独立统计样本。

## 7. 公平与成本口径

成本严格为每次pair访问两端`valid_tokens`之和，不冒充GPU时间；L一次成本保持32187742作上下文。
basis减少G pair访问和部分G endpoint exposure，但随后L阶段仍覆盖原4095端点；不能称所有训练曝光相同。

## 8. 完整性

输入读取前credential-shape+SHA、读取后再验SHA；Python audit hook拒绝网络、子进程、未列数据和写入。
新独占结果根；A/B、独立复算、命令/解释器/耗时/stderr和SHA256SUMS全记录。

## 9. 输出

只输出edge/token/rank/endpoint-exposure aggregate及数值排序的匿名逐任务gain行，不输出被选edge、card/run/task
身份、配置值或任何训练文件。pool/checkpoint不写。

## 10. 混杂与失败解释

Kruskal保连通是已知图论，rank保留本身是算法不变量；非平凡实证只有真实token降低量。cycle边可能为噪声鲁棒性
或优化提供信息，故basis即使省token也可能伤模型。若token门失败则关闭此成本候选，不以edge count救回。

## 11. 后续门

通过不解除旧版本source/config/experiment closure，不授权训练，也不申图算法新颖性。只有同版本producer包、G0
实测成本和明确GPU·时批准后，basis才可作为预先指定的成本候选进入历史开发对照；正式效果必须另冻协议。
