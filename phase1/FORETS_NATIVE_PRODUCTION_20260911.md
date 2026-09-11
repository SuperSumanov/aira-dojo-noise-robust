# ForeTS生产接线完成；固定免费路由未达到开跑条件

2026-09-11香港；最后现场核验08:29:04 UTC。

**本轮把已验证的GPU适配接入了真实生产控制器，但没有提交新的GPU作业。**
直接阻塞已从GPU映射转为固定免费生成路由在120秒/次限时下的可靠性。

## 实质完成

- 新鲜worker获得正确身份路径、适配器PATH、固定release和代码commit；原worker不传该路径的缺口已修。
  每个Jupyter子进程保存独立绑定文件，避免同一worker新建解释器时覆盖首次回执。
- 不恢复旧pool/旧13004，不改8配置、原SIF或任务payload；只在gpu28使用已实测的native选卡。
- 固定交付checkpoint及原部署输入。历史模板未知继续披露，但对这个收窄的现成系统探索不再无限等待；
  不修改/试选模板，不冒称历史匹配、干净scaling或最佳模型能力。详见[启动前裁决](FORETS_AS_DELIVERED_PREFLIGHT_20260911.md)。
- 10项新增CPU测试通过，含真实pinned pool代码的派发边界及身份/重放拒绝；不是10次模型实验。
- 远端两块静态预检均通过；22份发布文件逐字节对应Git，231份既有任务源码hash无漂移。
  8个实际config均关闭env导出、所有生成算子均固定零报价/无fallback。
- 新入口和接线已发布commit `5c8c07b711e7d3846fc5eda978f1efd6cd0b64ea`；学长分支仍`065b0fba`，未修改。

代码根：`/research/d7/spc/yzyang4/forets-native-release-20260911-dAKj2b`。
代码包SHA256：`d5b4ce057f50e418fb231cdb57ba6ada858b55a95a401f3b960e6d0afff92fc5`。
代码清单SHA256：`563416f98a3d2bff8963976dea1485f23bc706dddf8e4e032222fd97ea520637`。
探索release SHA256：`e7c64f43032901716f4f3d5abf75a3e7d15f6417bd44e7e6e37b5fc5f8983706`。

## 实际接口结果：不能写成已开跑

固定模型`nvidia/nemotron-3-ultra-550b-a55b:free`的账户认证与公开目录检查通过，
目录仍显示prompt/completion零报价、支持所需tools；这不是实际到账费用证明。
08:13:46 UTC启动有界人工请求检查：2个逻辑请求，最多6次传输尝试，每次限时120秒、8192输出token。

| 检查项 | 实测 |
| --- | ---: |
| 人工逻辑请求成功 | 1 / 2 |
| 已预留传输尝试 | 6 |
| TimeoutError | 5 |
| 成功返回 | 1 |
| 成功尝试耗时 | 112.47308019601041秒 |
| 各次尝试耗时之和 | 712.8678471809253秒 |

首次逻辑请求三次均超时；第二次在第三次尝试成功。不是完全断网，也不能据此唯一定位到provider故障。
预先要求两次均成功，故结果为`NOT_READY`；**没有写READY回执、没有block runtime目录、没有提交GPU。**
本轮GPU使用0，critic前向0、真实MLE运行0；API实际费用缺失，不能补记0。
队列只见12535 JobHeldUser，未操作它。13076是上一轮GPU验证，不能重复算本轮新进展。

证据：[接口回执](results/forets_native_production_20260911/route-finished.json)、
[目录检查](results/forets_native_production_20260911/catalog.json)、
[发布清单](results/forets_native_production_20260911/code-manifest.json)。
导出前凭据形状扫描0命中，不含密钥、余额、原始响应或推理文本。

## 失败记录与续跑边界

- 首次归档路径误写ICD目录，归档失败，未部署空包；随后修正路径。
- 首个远端代码包被Windows自动换行转换，shell语法预检拒绝，未执行任务。
  失败根`forets-native-release-20260911-FJDvAf`保留；禁止使用。
  后改为`git -c core.autocrlf=false archive`，新包与Git原始blob逐字节核对通过，不是现场偷偷改代码。
- 本次路由检查预算已用完；`block-1.route-check`与`block-1.catalog.json`存在，不覆盖、不原地重跑。
  固定执行入口仍拒绝没有READY回执的提交。后续恢复要另定有界的新路由检查窗口/回执，不能复用失败回执或只改状态。
- 不能因接口失败自动换付费模型/延长每次请求/改变任务预算；若改生成器，两臂须同时固定在新版本并明确记录。
- 这轮没有critic正收益。13004仅一个探索seed的负向结果仍保留；8run/4对尚未运行，不预报显著性。
