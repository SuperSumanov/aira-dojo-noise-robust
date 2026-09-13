# 可选执行后端：默认关闭，未来协议显式选择

现有Jupyter配置及实验不变。新Hydra组为`interpreter=fresh_container`，继承当前Jupyter组的镜像、环境与挂载，只替换解释器类型。必须在已验证的Singularity/native-GPU适配环境中使用；不是任意机器的独立安装说明。

新实现保持IPython单次cell语法，但每次调用启动新容器进程，不通过Jupyter HTTP/WebSocket；不支持跨调用解释器状态，`reset_session=False`会拒绝。启动、运行及清理成本包含在真实时间内；不宣称同Jupyter零开销等价、任意程序全语义等价或安全沙箱。两臂若启用，必须同时启用，单独冻结为新协议。

这不是“已有源码包自动支持”的开关：未来实验的不可变源码包必须明确包含新增类、registry映射与配置文件，并记录新commit；当前8bb325fa源码包不含这些变更，不能只改现有run配置就重用它。

13286/13287验证记录在results/fresh_container_integration_20260914。其上新增真实Hydra配置构建、数据类roundtrip、工厂选择及默认不变四项CPU测试，23:08通过；隔离副本`forets-fresh-config-20260914-k5wxhy2a`，overlay SHA `2ac0a2b354777b62a6d37b8decad8561705fa684473387b968c21ceff2443729`。

第一次配置测试失败：本地默认HF_HUB_OFFLINE为1，而固定搜索源码为0，直接复制环境会顺带改变行为。改为继承原配置后通过；失败副本`forets-fresh-config-20260914-76eedx8k`保留。未修改实际正在运行的源码、请求计数或任何费用账。新源码的解释器主体与13287验证过的实现做AST等价检查；仅模块文档字符串不同。

这是可复用的运行修复和接口验证，不是论文方法效果。不据此恢复旧kernel recovery、补跑EScope失败seed或绕过原扩大门。
