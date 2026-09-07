# 今天的完整执行环境：内容身份已核定，尚未运行历史程序

2026-09-07，source `d045abbddfd64ebabedf3cd919343bc68810db29`。
实际 Linux 16 测试通过；固定镜像 `19717783552` bytes，Python SHA-256 与独立 GNU sha256sum 一致，
文件设备/inode/size/mtime/ctime 前后不变，未复制或修改镜像。

SHA：`801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda`。
实际运行 `237.57036226499986` 秒；0 GPU、0 API、0 真实数据/候选程序读取或执行。
三份原始 JSON 已按 bytes/SHA 原样导出；executed_helper.py 与实际远端脚本 hash 相同。
第一次较短 bundle 缺少 Git 前置提交，在正式输出创建和镜像读取之前停止；补齐链后使用独立 r2 helper。

|角色|已验证范围|不能混称|
|---|---|---|
|critic 训练 runtime|另一路 R5 / Python 3.11 / Torch 2.11，正在补完整模型验收|不是本目录的执行镜像|
|候选完整执行镜像|Python 3.12.8 / Torch 2.5.1+cu124 等固定版本；两套内容 hash、benign 隔离门|不是过去实际 runtime 的证书，也没有历史候选成功结果|
|外部 grader|另有当前 187 个 MLE-bench Python 文件与记录 Git 的比对|镜像内无 mlebench distribution；未来评分依赖和实际执行还需单独固定|

容器只绑定自有 canary/output；只读写入被拒、五个宿主/保护路径不可见、独立网络空间仅 loopback、
已知 API 环境变量不存在。不是面对任意恶意程序的完整 sandbox 安全证明。
软件版本只通过 distribution metadata 查询，不称全部包已导入、所有任务兼容或实际 CUDA 可运行。

来源准入与四 fit 状态均未改变。完整后续路线见 ../../NEXT_REAL_DATA_ROUTE_20260907.md。
