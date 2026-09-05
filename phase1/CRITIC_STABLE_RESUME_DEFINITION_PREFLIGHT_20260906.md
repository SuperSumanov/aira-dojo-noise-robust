# 续跑身份修复：固定训练定义与单次作业分开

2026-09-06，启动前登记。用户持续工作授权内的代码修复，不新增GPU/API或来源准入。

1. 主线不变。当前生产入口用整个launch文件SHA作为checkpoint训练身份；合法续跑换output/resume后SHA必变。
2. 问题是生产入口未覆盖的契约连接，不是已经保存的CPU checkpoint损坏，也不是GPU12535的新失败。
3. launch-v2只引用逐字节固定的training definition；四计划、来源、模型、encoder、runtime/code绑定均留在definition。
4. 续跑作业安排和launch SHA单独记录。科学定义SHA变仍拒绝原checkpoint。不开兼容绕过，不改原session校验器。
5. ADMITTED_RELEASES仍空；schema/hash不能证明实际生产、预算、隔离或硬件资格。没有真实v1生产合同需迁移。
6. 本地复现旧whole-launch SHA随合法目录改变；负例覆盖科学字段变动、未知字段、丢失计划/恢复SHA和越界步数。
7. 同一合成accum8 fixture，2 CPU rank，4433参数随机Qwen、AdamW、dropout0.1、seed6；不读真实语料或checkpoint。
8. 两臂各full/prefix/resume，新进程与新launch文件实际恢复；A/B共12工程轨迹，最多32自有小checkpoint。
9. 独立重读实际model/AdamW/RNG、精确消费拼接及每份manifest。各臂3个launch SHA不同但definition SHA相同。
10. 不计算模型效果；工程状态按字节/精确比较，不以合成任务准确率代替真实收益。
11. 两次CPU执行各最多900秒、每child150秒；控制器限定进程组终止。GPU/API/model-effect-fit均零。
12. 记录exact commit、命令、版本、源文件SHA和原始失败；输入只为自有fixture与固定senior forward定义。trace检查为路径负扫描，不声称OS沙箱。
13. 任一失败保留原产物，不改容差或冒充完成。真实ZeRO3/16K和qualified-source四fit仍未准入；不触碰12535目录。

本修复仅解开合法作业重启与科学身份之间的耦合，不能解决排队或生产端证据缺失。

首次执行e5c9b69在fit1-full训练前因工程观察列表遗漏新增definition.json而失败；原失败保留。
修正后仍精确检查definition→topology→必要targets的读取次序；不放宽到任意文件，也不打开dev。
固定同一fixture和原容差，在新目录重复A/B，不覆盖首次失败。
