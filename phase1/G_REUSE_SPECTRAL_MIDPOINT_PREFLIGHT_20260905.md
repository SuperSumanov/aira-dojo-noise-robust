# G-reuse cost-aware spectral midpoint：结果前预检

日期：2026-09-05。状态：历史train、0-model-fit的方法候选结构预检。

## 1. 问题与假设

full G-reuse的cycle相对最小token basis具有广泛有效电阻信息，但full成本更高。固定问题是：在每任务只允许使用
`basis_tokens + floor((full_tokens-basis_tokens)/2)`的G-token上限时，按
`log(1+current effective resistance)/edge_tokens`贪心补cycle，能否比cheapest-first和固定SHA-order保留更多
D-opt信息，并在未直接优化的A-opt有效电阻上也更好。

## 2. 输入、population与隔离

输入/SHA、2745条full记录相符G边、790条16K最小token basis和28任务与0L20完全相同。只用历史train结构和
cached valid-token；禁止dev/test/vault、first960、Target300/522、score、prediction、代码正文和方向值。不输出
task/run/card/component/edge身份或selected set hash。

## 3. 唯一算法与三个arm

逐任务、逐`L+full G`最终G-touched连通块，以`L+basis G`初始化无权Laplacian。剩余cycle edge不可分割；若放不进
该任务额外token余额就跳过。三个arm使用完全相同的逐任务token上限：

- spectral：每步将`log1p(R_eff)/edge_tokens`四舍五入到小数点后15位后选最大者，endpoint ID升序仅作tie-break；
- cheapest：按`(edge_tokens, endpoint IDs)`升序；
- hash：按两端sorted ID的SHA-256升序。

spectral主实现用`L+J/n`逆与Sherman--Morrison更新。不得结果后换预算比例、混成global budget、加权边、改变
tie-break、补fractional edge或挑任务。数值容差固定`rel=1e-8, abs=1e-7`。
15位score量化只定义跨独立线性代数实现的确定性近似tie，不在结果后改变。

## 4. Primary gates

以下全部成立才称`G_REUSE_SPECTRAL_MIDPOINT_STRUCTURALLY_SUPPORTED`：

1. 三arm逐任务均不超预算，spectral全局额外预算利用率至少95%；
2. spectral汇总D-opt headroom capture至少75%；
3. spectral汇总D-opt capture严格高于cheapest和hash；
4. spectral汇总A-opt resistance-reduction capture严格高于cheapest和hash；
5. 在有cycle headroom的任务中，spectral D-capture不低于两baseline（容差1e-10）的任务至少20个；
6. spectral逐任务D-capture中位数至少70%。

## 5. 资源矩阵与ETA

单CPU；producer A/B各≤300秒，独立verifier A/B各≤300秒；BLAS线程1。预计正式8--16分钟，实现、测试与复验
70--110分钟。GPU=0、API=0、model fit=0、agent底座更新=0。

## 6. 随机性与统计单位

无随机seed；SHA arm只是确定性中性次序，不冒充随机分布或独立重复。A/B为复现检查。任务只作广度诊断，不把edge或
endpoint当独立统计样本，不报伪显著性。

## 7. 指标与公平口径

D-opt headroom是从basis到full的log pseudo-determinant增量，单边增量为`log1p(R_eff)`；A-opt capture是basis到
full Kirchhoff下降中被arm恢复的比例。所有arm同起点、同候选边、同逐任务上限、同16K token成本。谱arm优化D而非A，
故A门是非同义迁移检查。指标不是神经模型效果或GPU墙钟。

## 8. 完整性

输入读前credential+SHA、读后再验；audit hook拒绝网络、子进程、未列数据和写入。新独占结果根，producer A/B与
不import producer的独立grounded-Laplacian verifier A/B，记录源码/环境/BLAS/耗时/stderr/manifest。漂移、预算超限、
矩阵残差、selector重复或容差外差异均失败关闭。

## 9. 输出约束

只输出aggregate和匿名数值排序逐任务行：预算、spend、edge count、D/A capture；不输出任何身份、selected edges、
pool或checkpoint。匿名行不得跨产物稳定链接任务。

## 10. 反例与解释

若通过，只证明已有谱准则在本comparison graph上形成比简单baseline更有效的信息/成本候选；指标优化优势本身不等于
方法新颖或模型收益。若D过而A不过，关闭“跨指标”主张；若预算利用失败，不用fractional edge补救；若任务广度失败，
不以aggregate救回。

## 11. 后续门与先例

有效电阻采样/谱稀疏化、pairwise图设计和Fisher信息均有成熟先例；该selector只能作为工程化已有原则baseline/challenger。
通过后仍须同producer source/config/experiment closure、G0实测与明确GPU预算，再以full、basis、spectral三者做同预算
多seed模型A/B；不能替代未触碰前瞻确认。
