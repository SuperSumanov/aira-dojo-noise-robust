# FA2缺失修复：固定环境、独立附加目录

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

1. **CPU构建一次**：gpu_24h / gpu（不申请GPU），4CPU、24GiB、40min上限、0GPU。
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
