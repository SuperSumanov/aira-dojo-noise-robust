# 新完整重执行的环境指纹：仅准备，不追认历史、不准入训练

2026-09-07，用户本次六小时会话授权下的有界 CPU 准备。
唯一问题：现有完整执行镜像能否固定内容指纹，并在已验证的隔离模式中报告实际软件版本？
不再扫描同一批历史 grading 文件；本次不打开历史代码/成绩或任何真实任务数据，不启动候选程序。

固定输入为现有约 20GB 的 `superimage.root.2026-07-macos-v1.sif`。
先验证普通文件、无符号链接、owner/link count，再分别用 Python SHA-256 与独立 GNU sha256sum 读全文件，
要求两次 SHA 相同且设备/inode/size/mtime/ctime 前后不变。不复制镜像、不修改权限或原环境。
单次 Python 读最多 600 秒、GNU 最多 600 秒；整个指纹工作最多 1,300 秒、单 CPU、0 GPU/API。
这会读取约两遍镜像字节，不是零 I/O 的元数据检查，也不是历史镜像身份的证明。

容器继承空白白名单环境，`--containall --cleanenv --net --network none`，
禁默认 hostfs/bind-paths/cwd 挂载，工作位置为本次独占目录；只绑定自己的只读测试文件和可写输出目录。
仍用 benign canary 检查已知宿主/保护路径不可见、只读绑定和独立 loopback-only 网络空间。
通过 importlib.metadata 只读固定软件名字对应的版本；不导入 torch 创建 GPU，不枚举环境变量值。
最多 90 秒。缺软件保留 null，不临时联网安装，不把 version 字符串当作运行正确性。

结果只证明“今天有可内容寻址、基本隔离检查通过的候选执行环境”。
仍未证明真实候选成功、模型收益、历史 runtime、一致外部评分或完整 source admission。
若转向历史程序完整重执行，必须另立候选冻结、原始 run/experiment/旧 hold 闭包、
统一资源与完整 wall-time、新执行 seed、public-only worker/private-only pristine grader、
实际输入/代码/预测/评分哈希链及所有失败保留协议；不能从这里自动启动重执行。

固定 scope：本次不改 first960/Target300/Target522，不重选失败 S0，不恢复多保真/Probe。
不改变四 fit 或五臂模型效果矩阵。测试覆盖路径逃逸、link、文件漂移、规模上界与两实现 hash 不一致。
首次本地测试有六项因 Windows 无 os.getuid 而失败；仅在 Windows 单元测试中显式模拟 UID 查询，
生产代码仍保持 Linux 实际 owner 门。符号链接能力缺失的本地跳过不计为 Linux 通过。
