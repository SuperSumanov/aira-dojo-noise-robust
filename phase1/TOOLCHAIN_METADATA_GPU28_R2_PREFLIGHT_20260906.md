# GPU队列最小资源要求下的工具链诊断

原零GPU尝试被QOSMinGRES拒绝：无job id，queue仅12535，未占资源；失败证据保留，原source b7915f6不改历史。
用户本会话全面授权合理修复；现明确改成合规的单RTX3090分配、6CPU、1分钟/no-requeue，**即使不做GPU运算也计GPU时**。
仅执行系统CUDA安装目录元数据和nvcc --version，不导入框架、模型、checkpoint或语料，不安装环境。

诊断1作业、60秒Slurm墙钟+60秒退出+60秒安全余量=180 GPU秒上限。原12570失败实际2 GPU秒。
未来若发现完整匹配环境，最多另行裁决一次18分钟双卡工程检查，其上界2880 GPU秒；合计3062≤原独立3120。
本诊断不自动提交后续GPU尝试、不改变原12535或原0GPU失败记录；没有找到环境则停止该路径。

原13项检查见TOOLCHAIN_METADATA_GPU28_PREFLIGHT_20260906.md，以下覆盖资源和绑定部分：
held核1 GPU/6CPU/gpu28/1分钟/不重排/非运行；独立再次核source bytes和原12535配置后才release。
worker运行时再核实际allocation，隐藏CUDA devices。仅三个浅层目录，前缀≤20、nvcc二进制<128MiB，
版本查询总40秒截止、单次≤10秒；全作业仍受60秒Slurm硬上限。无成绩/seed/split/模型保存项。
终态sacct再核实际分配GPU秒，原始元数据与source hash保存。语法和纯函数测试先过；失败不盲目重投。
这只是工具链诊断，不构成GPU/1.7B16K/模型收益验收；不能把发现CUDA11/12其它版本说成固定12.8可用。
