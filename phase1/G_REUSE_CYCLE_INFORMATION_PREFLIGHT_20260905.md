# G-reuse cycle information：有效电阻结果前预检

日期：2026-09-05。状态：历史train、0-model-fit、结果前冻结的comparison-graph诊断。

## 1. 问题与可证伪假设

790-edge最小token森林与2745-edge full G-reuse具有相同逐任务incidence rank，但相同rank不等于相同统计信息。
本项检验full中的cycle edges是否在真实任务图上显著降低平均有效电阻。已有pairwise-ranking理论把Laplacian谱、
Fisher information与估计误差联系起来；本项只量化该已知理论在本语料上的headroom，不申新算法。

## 2. 输入、population与隔离

输入和SHA与`G_REUSE_MIN_TOKEN_BASIS_PREFLIGHT_20260905.md`相同；population仍是历史L train加固定2745条
记录相符G-reuse边，basis仍按16K cached valid-token的冻结Kruskal规则得到790条。禁止dev/test/vault、first960、
Target300/522、score、prediction、代码正文和方向值；不输出task、run、card、component或edge身份。

## 3. 唯一estimand

逐任务在endpoint层建立无权无向图。以`L + full G`定义最终连通块，只纳入至少含一条full G边的块；验证
`L + basis G`具有完全相同块划分。每个连通块以float64 Laplacian非零特征值计算Kirchhoff index
`n * sum(1/lambda_i)`，再按块内无序节点对数汇总为平均有效电阻。比较basis与full的相对下降。

不得收缩到connected-only任务、改成contracted图、改边权、删除小块或结果后换谱指标。数值零阈值固定为1e-10，
特征值负容差固定为1e-8。

## 4. Primary gates

四项必须同时成立：全任务pair-weighted平均有效电阻下降至少25%；28个任务的下降中位数至少15%；至少20/28任务
严格正下降；按每任务相对下降等权求和时，最大任务贡献不超过20%。另有完整性硬门：basis/full连通块逐任务一致、
790/2745边数与28任务不漂移。全过才称`G_REUSE_CYCLES_HAVE_BROAD_SPECTRAL_INFORMATION`。

## 5. 资源矩阵与ETA

单CPU；producer A/B各≤240秒、独立verifier A/B各≤240秒；BLAS线程固定1。预计正式5--10分钟，完整实现与复验
45--70分钟。GPU=0、API=0、model fit=0、agent底座更新=0。

## 6. 随机性与统计单位

无随机性、seed和warmup。A/B是确定性复验，不是独立样本。任务是广度诊断单位；endpoint pair只用于固定的
Kirchhoff汇总，不作独立显著性样本，不报伪p值。

## 7. 公平与解释口径

basis和full使用同一L图、端点、任务、边权和块population，唯一差异是full保留cycle edges。有效电阻是图拓扑代理，
不是神经critic的训练loss、泛化accuracy或墙钟。full成本更高，本项不声称它在成本收益上必胜。

## 8. 完整性与失败关闭

输入读前credential-shape+SHA、读后再验SHA；audit hook拒绝网络、子进程、未列数据和写入。新独占结果根，
producer A/B、独立数据重建verifier A/B、命令/环境/BLAS版本/耗时/stderr/source与结果manifest全部留档。
谱分解、连通块、hash或schema异常即失败关闭。

## 9. 输出约束

只输出aggregate及匿名数值排序逐任务行：节点/块/边计数、basis/full Kirchhoff、平均电阻和相对下降。不输出任何
身份或selected basis；匿名行不得跨产物稳定链接回任务。

## 10. 反例与失败解释

若全过，只能说cycle edges在本图上提供广泛的谱信息，支持full作为效果主臂、basis作为成本challenger。若门失败，
说明相同rank的便宜basis可能已保留大部分拓扑信息，或headroom集中；不得另改阈值。无论结果如何，谱代理与共享特征
神经模型并不等价，最终必须由同预算多seed模型效果验证。

## 11. 后续门与相关工作边界

Osting et al. ICML 2013、Shah et al. JMLR 2016、Hendrickx et al. ICML 2019均已建立pairwise comparison graph
谱/Fisher/电阻联系，因此不得宣称谱选边首创。通过只决定是否保留full与设计已有理论指导的稀疏ablation；不解除
source/config/experiment closure、G0计价或GPU批准门。
