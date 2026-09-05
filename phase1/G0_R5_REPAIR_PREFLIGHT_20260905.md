# G0 R5：用户已批准修复依赖与受控重试

用户本轮明确批准按推荐修复并解决问题。范围是 G0 工程恢复，不是揭盲、扩展15-fit或agent底座更新。

## 配置与预算（结果前固定）

- 原source `5f3bc362db922c8edee2ef134656dfdb9a2b74fb`、Qwen3-1.7B-Base原snapshot、三份工程输入不变。
- seed6、16K、两PRO6000/projgpu39、microbatch8、accum8、有效pair batch128、10步、单次step10 dev/final保存。
- 新建独立R5环境，复用原依赖闭包和所有backing包；只补确切SHA的ninja原生入口，原环境保留。
- 先CPU工程检查：32元素小张量，seed6，CPUAdam对AdamW三步误差≤1e-6，最多两编译线程；不读语料、不拟合模型。
- 原计划零GPU诊断被集群test-only拒绝；没有产生作业。短/完整主机名的只读SSH均因主机密钥校验失败停止，未绕过验证。
- 随后在对用户明确披露的修订方案下，提交单卡、1CPU、最多60秒的目录检查12497，不加载模型或CUDA上下文。
  held检查后才release，实际1秒完成，sacct为1 GPU-second；确认目标/usr/local/cuda-12.8有nvcc/headers/libs。
- 旧四次失败加12497检查累计965 GPU-seconds。新G0一次两卡、6300秒（01:45:00），no-requeue；
  加KillWait300秒及调度余量60秒，合计上界 `965+2*(6300+300+60)=14285 < 14400`。
- 任何后续尝试均先核sacct实际消耗，不重叠、不对不明提交重投，不突破原4 GPU·h总额。

## 强制预检

1. fetch最新方向、保留protected cohort及关闭路线；重读本轮失败根因。
2. 固定control/source提交，原代码/依赖版本不变，新环境路径/工具入口单独绑定。
3. 核ninja实际PATH、二进制SHA和版本，不用dist-info存在替代可执行性。
4. 实际CPUAdam编译、初始化、三步更新参照；记录目标节点与login差异，CPU缓存不带入GPU作业。
5. 在目标节点检查CUDA_HOME/nvcc/headers/libs与C++工具链，发现缺口先停，不通过绕过版本检查掩盖。
6. 校验原模型及三输入SHA、source只读；不触及保护结果。
7. 4GiB真实预留、输出独立、trace私有、依赖绑定和CPU保存回归仍有效。
8. R5精确时限正反例及既有worker/输出隔离测试；R4与legacy契约不改。
9. squeue无未知重复，sacct预算核对；作业先held核实际Slurm字段，再release同一个job。
10. warmup与后续步分开计时；双卡采样；实际10步/一次dev/checkpoint文件必须齐全。
11. 终态后核源码/输入/model、访问trace与回执；Slurm COMPLETED不等于验收。

工程失败继续保留，不把tiny tensor正确性或历史dev分数写成方法效果。

## 已完成、但不冒充GPU训练成功的CPU检查

新环境已建立；65包版本和symlink backing与原依赖闭包相同，仅补原生ninja入口及新环境console shebang。
实际CPUAdam编译/初始化/三步对照通过，逐步最大误差为
`[1.1920928955078125e-07, 2.384185791015625e-07, 3.5762786865234375e-07]`，预设容差1e-6。
该检查在linux5、无GPU上下文下用145.09968986734748秒完成，编译缓存不带入GPU作业。
G0在目标节点将额外记录实际ninja、g++、nvcc版本与二进制哈希；CUDA_HOME显式固定为/usr/local/cuda-12.8。
