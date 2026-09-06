# FA2缺失修复：固定环境、独立附加目录

## 2026-09-07 R2：覆盖下文构建状态与旧预算

12635实际运行89秒后FAILED 1:0，编译日志明确为默认gcc无法启动cc1plus；
不是CUDA架构不支持或模型失败。默认gcc9与可用g++13不一致，未复用已有显式C++绑定是本次预检漏项。
新尝试固定CC/CXX/NVCC_CCBIN及nvcc -ccbin为/usr/bin/g++，并绑定其SHA
1353e9bdd29a7295c7226bf6c63abccce056d8cac31f112e5cdbecc3f28c2769。
已在Linux纯CPU实际编译含CUDA/bf16/C++标准库的sm120对象成功，6.143286120146513秒。
对象SHA d96f6e40bcf21a74a562e1d63556a07e9ce9de2bd802a7fe0fc5ba37a23d895b；未创建CUDA context。
每个真实构建节点开跑后必须重复同一编译器哈希和编译门，失败即停，不自动换compiler。

新目录flash-attn-build-20260907-r2，固定官方包重新解压；旧构建/日志完整保留，不清理或覆盖。
矩阵仍1保留GPU/4CPU/gpu37/mem0/40min，内层源码编译2100秒；无CUDA kernel、模型或语料读写。
实际历史费用7291GPU秒（此前7202加12635的89）；新构建保守2760，加后续双卡尺寸3840，
组合13891≤14400GPU秒。0秒取消的12634未计执行费用。尚不提交四fit效果训练。

完整预检逐项：固定源码/host compiler/Torch2.11/cu128/ABI/架构；CPU正负控；
无数据故去重/分布/配平/统计功效项不适用且不宣称收益；新专属输出/有界超时/无重试；
哈希与退出码回执；发布凭据扫描；冻结评测不读；后续真实尺寸仍需checkpoint与64GiB容量门。
FA2 GPU检验预先固定bf16 GQA/causal dense和varlen数学参考，forward/dq/dk/dv同时要求
relative-L2≤0.02且max-absolute≤0.05；16K只检查实际kernel前后向及有限性，不冒称全量数学对照。
Linux CPU的overlay/漂移/参考/负控8项已通过；GPU数值检查尚未运行。

数据解释校正：24个exact strata均只有一个保守组件，只排除“现成同配置独立组件重复”这一窄条件。
冻结协议的pair两端配置一致，不自动等于train/dev必须同配置；跨配置开发是一种不同estimand，
不能冒称同配置确认，也不能因此自动合并配置或绕过evaluator/完整experiment来源门。

## 历史调度记录（保留，不代表当前运行状态）

调度校正：12634未启动，因节点RealMemory=1占位值与24GiB请求冲突，处于BadConstraints。
本轮自行scontrol hold后，Slurm19.05写入JobHeldAdmin；release被拒，未尝试修改priority或越权解除。
已取消我方这个从未启动的作业，保留0秒记录。后继改为已核验空闲ubuntu24节点gpu37、mem=0，
同样保留1卡/4CPU/40min；从新的提交目录重新创建user-held作业，避免重复排队。
mem=0是本集群已有作业的调度方式，不声称得到了24GiB内存硬限额；编译并发仍固定2×2。

第二项调度实证：gpu_24h/gpu拒绝0GPU请求（QOSMinGRES），仍未产生job。
最终后继遵守最少GPU规则，申请gpu28一张卡并**按占卡时间计费**；编译仍纯CPU、不创建CUDA context。
矩阵为1保留GPU/4CPU/24GiB/40min，保守2760GPU秒（含300秒退出与60秒余量），不把未执行kernel当免费。
此前工程实际7202GPU秒，连本构建与后续双卡尺寸上限3840，组合保守13802≤14400GPU秒。
两次被拒的提交回执保留；新的submission-single-gpu目录不能与旧失败目录混用。

执行前权限修正：首次batch_72h/ex_batch提交被Invalid qos specification拒绝，未产生job；
实际sacctmgr显示账号仅有gpu QOS。因此后继只将调度入口改为gpu_24h/gpu，仍无GRES、0GPU、
4CPU/24GiB/40min，旧sbatch返回码与stderr保留。独立新提交目录，不重用失败SUBMISSION_INTENT。

用户2026-09-07要求积极推进critic收益准备；本轮只解决12577明确缺失的attention依赖，
不换FA2为SDPA、不改变1.7B/16K/双卡/8×8/seed6、优化器或数据准入。

## 已查明

实际运行栈PyTorch2.11.0+cu128 / Python3.11.15 / CXX11 ABI=true，FA2包与模块均不存在。
官方GitHub release v2.8.3没有匹配torch2.11/cp311/ABI=true的wheel；v2.8.4/v2.8.5 API返回404。
不得使用旧torch2.8 wheel。官方2.8.3源码setup已包含FLASH_ATTN_CUDA_ARCHS与sm_120编译项。
来源：[官方release](https://github.com/Dao-AILab/flash-attention/releases/tag/v2.8.3)、
[固定PyPI元数据](https://pypi.org/pypi/flash_attn/2.8.3/json)。

## 实际矩阵与验收

1. **CPU构建一次**：gpu_24h / gpu / gpu28，保留1GPU、4CPU、24GiB、40min上限。
   只用固定FA2 2.8.3官方sdist和wheel0.45.1构建工具，2个编译worker、各2个nvcc线程。
   编译阶段最多2100秒；失败保留，不自动重试。训练/模型权重/语料/保护评测集均不读。
2. 安装到`flash-attn-build-20260907/overlay`，不写原r5环境；同一Torch/CUDA编译，
   指定sm_120；保存源码包hash、wheel hash、模块/二进制hash和编译日志。
   CPU导入成功只能证明加载和ABI初检，不能证明GPU前向/反向或生产尺寸成功。
3. 构建完成后才能准备**独立的一次原尺寸GPU验收**：2PRO6000、26min，
   先两卡分别实际执行bf16/GQA/causal前向反向，与小尺寸FP32数学参考比较，再进入原1.7B/16K保存恢复链。
   数学参考仅用于正确性检查，不作训练后端；无自动后端fallback。
   GPU尚未提交，提交前另固定代码/FA2附加目录及数值阈值、CPU负控、模型/空间/资源/费用门。

FA2 sdist SHA：1e71dd64a9e0280e0447b8a0c2541bad4bf6ac65bdeaa2f90e51a9e57de0370d。
wheel工具 SHA：708e7481cc80179af0e556bbf0cc00b8444c7321e2700b8d8580231d13017248。
CUDA编译工具用已存在的private-cuda128-toolchain-20260906/prefix；这是login/CPU节点上的工具路径，
不把该节点无/usr/local/cuda-12.8误判为projgpu39也无CUDA（12577已验证projgpu39的系统工具通过）。

## 数据侧同时推进

固定84run的12个commit，逐个检查所有`src/dojo`树成员对应blob都存在。
初查24 recorded exact strata各只有1个保守组件；同task有多个组件不等于同exact-stratum有独立train/dev。
接下来只查明分层字段差异及完整来源，不改变旧hold、不按效果挑范围、不擅自合并科学配置。
若现有范围确实无同配置独立重复，则必须安排独立开发生产，不能把保护前瞻run改名进训练。
以上是数据资格诊断，不是新的模型收益、负面方法结论或统计功效结论。
