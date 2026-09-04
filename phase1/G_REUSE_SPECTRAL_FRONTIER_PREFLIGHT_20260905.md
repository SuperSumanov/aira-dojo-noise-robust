# G-reuse spectral cost-information frontier：结果前预检

日期：2026-09-05。状态：0L21之后的结果前扩展；不得覆盖其中50%绝对门失败。

## 1. 问题与假设

0L21显示spectral在50%额外token上相对两baseline更高效，但未达到预设绝对D/中位保真度。这里不调低绝对门，
而检验相对优势是否贯穿固定的25%/50%/75%额外预算曲线：spectral能否在每一点同时提高D-opt与未直接优化的A-opt，
并具有跨任务广度。

## 2. 输入与隔离

输入/SHA、2745 full、790 basis、28 tasks及16K token成本与0L21完全相同。只读历史train结构；禁止dev/test/vault、
first960、Target300/522、score、prediction、代码正文和方向值。不输出任何task/run/card/component/edge身份或选择集。

## 3. 固定curve与arm

预算点恰为每任务`basis + floor((full-basis)*p/q)`，其中`p/q`为1/4、1/2、3/4。三个arm、15位score量化、
endpoint tie-break、不可分割edge和逐任务skip规则与0L21相同。每个预算点从同一basis重新开始，不沿用低预算选择状态；
不得结果后加点、删点、改成global budget、做插值选门或用高点覆盖50%失败。

## 4. Primary gates

全部成立才称`G_REUSE_SPECTRAL_FRONTIER_RELATIVE_DOMINANCE_SUPPORTED`：

1. 三arm每点逐任务不超预算，spectral每点全局预算利用率≥95%；
2. 在25/50/75每一点，spectral aggregate D-capture都严格高于cheapest和SHA-order；
3. 在每一点，spectral aggregate A-capture也严格高于两者；
4. spectral三个点D-capture算术平均与A-capture算术平均均严格高于两baseline；
5. 每一点27个cycle任务中，spectral D不劣于两baseline（容差1e-10）的任务数≥20；
6. 每个arm的aggregate D与A capture随预算点单调不减（容差1e-10）；固定边/任务/点计数不漂移。

不设置新的绝对capture门；0L21的75%和70%失败永久保留。

## 5. 资源矩阵与ETA

单CPU；producer A/B和独立verifier A/B各≤300秒，BLAS线程1。预计正式10--20分钟，实现/测试/复验60--95分钟。
GPU=0、API=0、model fit=0、agent底座更新=0。

## 6. 随机性与统计单位

无随机seed。SHA-order不是随机分布；A/B不是独立样本。任务只作广度诊断，edge/endpoint不作独立统计样本，不报p值。

## 7. 指标与公平

D/A capture定义、三个arm起点、候选边和成本口径与0L21一致；每一预算点三个arm使用同一逐任务上限。跨点平均只是
三个预定离散点的等权描述，不冒充连续AUC或训练utility。

## 8. 完整性

读前credential+SHA、读后再验；audit hook禁止网络/子进程/未列数据/写入。主实现复用shifted inverse核心，独立verifier
复用grounded inverse核心但不import producer；producer byte-A/B、verifier close-A/B与跨实现close全部保留。新结果根、
命令/环境/耗时/stderr/source/manifest完整记录。

## 9. 输出

只输出每点aggregate、匿名数值排序逐任务预算/spend/capture行、跨点平均与门。不得写selected edge、pool/checkpoint或身份。

## 10. 失败解释

若通过，只能说相对两个简单次序的图信息效率优势跨三个固定预算稳定；谱准则优化D，故D胜出不意外，A与任务广度是
较强检查。若任何点失败，总门失败；不得只报最好点。即使通过也不是critic accuracy或端到端收益。

## 11. 后续门

通过后可把full、basis、spectral-frontier选定点列入同预算模型候选，但最终臂数/预算仍须另行预注册；同producer来源、
config/experiment closure、G0成本和GPU批准不解除。谱图设计/有效电阻已有先例，不申算法首创。
