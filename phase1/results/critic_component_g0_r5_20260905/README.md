# G0 R5：ninja修复与真实CPUAdam通过；双卡12499已放行、仍排队

2026-09-05 13:42 Hong Kong现场核验。用户明确批准修复与受控重试。

## 已完成

- 新建 `/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260905-r5`，原selective/overlay环境不变。
  65包版本与原闭包、symlink backing一致，补上确切SHA的原生ninja可执行文件；不改变模型或训练超参数。
- linux5实际CPUAdam编译、初始化与32元素seed6三步AdamW参照通过：最大误差
  `3.5762786865234375e-07`，容差`1e-6`；无GPU上下文、无语料/模型拟合。
  小张量更新只是依赖/算子校验，不是critic效果。
- 零GPU目标节点test-only被集群CPU:GPU比例规则拒绝，没有生成作业；短名/FQDN的SSH主机密钥检查均失败，未绕过验证。
  事先向用户披露改用一分钟单卡目录检查12497，实际只占1秒，未加载模型或访问GPU上下文。
  目标节点 `/usr/local/cuda` 指向12.8，nvcc、cuda/runtime头文件、cudart/curand库均存在。
- 本地35测试通过（0.55秒），Linux相同35测试通过（0.19秒）；未改legacy/R4时限契约。
- 4GiB真实空间预留、原source/model/三输入哈希、65依赖与关键文件、既有CPU保存回归绑定通过。
  真实模型/source和输入仍是旧G0工程校准配置，不能升级为正式G-reuse或scaling资格包。

## 实际提交

- control `90cd91058fd03e86185d42c14704845827259655`，路径`/research/d7/spc/yzyang4/worktrees/g0_r5_90cd910_sparse`。
- source `5f3bc362db922c8edee2ef134656dfdb9a2b74fb` 不变。
- 单个G0 job **12499**，held独立核12CPU、mem0、2 PRO6000/projgpu39、gpu_24h/gpu、01:45:00、
  Requeue=0、Restarts=0后才release；不是重复投递旧job。
- seed6、16K、microbatch8、accum8、effective pair batch128、10步、单次step10 dev/final-only不变。
- CUDA_HOME显式固定 `/usr/local/cuda-12.8`；新增入场检查在模型/数据加载前记录ninja/g++/nvcc版本与哈希。
  登录节点编译缓存不带入GPU作业；实际GPU条件下的编译与训练仍需由12499验证。
- 当前PENDING/Resources/0秒。节点另一作业占一张卡，双卡同时可用前不能启动。
  调度器暂估9月6日13:35:46开始，非保证；不会取消他人作业或擅改为单卡来绕过双卡验收。

旧四次失败964 + 12497目录检查1 = **965 GPU-seconds**。
新作业上限6300秒，加300秒KillWait与60秒余量，累计上界 **14285 GPU-seconds < 14400**。
实际消费以sacct逐作业核算。未启动15-fit、付费API或agent底座更新，保护cohort仍保持盲态。

## 核验过的关键哈希

|文件|SHA-256|
|---|---|
|READY.json|14d082e2e6680def32b625c94f89ca0ee944b7e9566351333899fa340670b836|
|assets.json|c9dc6236678c34fbc905a71e4a6afab2f4a4a5cc43737c0f8befbe09033907e0|
|RELEASED.json|56757e8f8d6060c928fe835cc9169c173d9a6dadb5e16201d1f565616932e26b|
|ninja executable|696f9628a79d9ce50314cf9556d7cd1a1d1ec52b8fd52828f6f9db1719565b67|

运行后只有10步、唯一dev、完整checkpoint-10、源码/输入/model未漂移、双卡资源与私有访问trace独立审查通过，
才称G0工程跑通。当前结论只能是**已修复已知依赖缺口、已通过CPU校验、已提交真实验证**。

后续守护`g0-r5`已建立，每15分钟检查，排队/健康且未变化时不通知；终态或实质变化才汇报。
首个创建请求缺少线程目标被工具拒绝，没有创建实例；补`destination=thread`后实际创建成功，没有重复守护。
用户本轮批准的G0修复授权会随守护保留，但总预算、盲态、公平配置与不可改运行中源码的边界不变。
