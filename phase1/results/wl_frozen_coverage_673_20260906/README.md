# 冻结 WL 覆盖补齐：517 → 673 runs

2026-09-06。已实际完成，不是计划或新训练结果。

## 结果和边界

- 原模型、协议、激活记录不变；新增覆盖156 runs，移除0，既有3325个共同pairs保持一致。
- producer、独立数值verifier、snapshot-chain三阶段均rc=0；另以独立postcheck核验50个manifest成员、
  52个只读文件与24个trace文件。credential和禁止路径扫描均0命中。
- 0 GPU作业、0 API调用、0模型拟合。保护标签/结果与预测数值未向agent暴露，未计算accuracy或utility。
- 当前673/960且closure=false，仍差287。覆盖支持仍为provisional，不是提前揭盲或确认成功。
- 本次是完整快照覆盖补算；不能将总时长除以新增runs，冒充critic的单次query latency。

## 实际时间和资源

原wrapper实耗4350.789625179023秒（72.51316041965038分钟），未触及7200秒上限。
三个计算阶段合计user+system CPU为4338.99秒；最大单阶段RSS为10336332 KiB
（9.857494354248047 GiB）。这些是本轮pipeline成本，不是GPU时间或模型选择收益。

|阶段|user CPU秒|system CPU秒|峰值RSS KiB|返回码|
|---|---:|---:|---:|---:|
|producer|1989.79|221.35|10303912|0|
|独立verifier|2061.5|64.83|10336332|0|
|snapshot-chain|1.18|0.34|99716|0|

中途本地SSH连接reset，但原远端child和超时wrapper均存活，未重启或重复提交。
最后terminal回执rc=0，原child已退出，WL state确实提升至673；其它transition/receipt monitor的state/log哈希不变。

## 绑定与复核

- 单次wrapper源码：`4395e1800bf8350cecc0ecd6513bf0c11722d3c2`。
- 原控制器：`bc362dfe95287f199f6bc4a1dc8f781f3b1b6ee0`；原scorer：`031edb34400781ca026bc9833ac7f850312ffb1c`。
- 输入snapshot：`cdae57a622cfa8e83b40e93f60dbd90045b4670c4e9050bf552ef689745a25f2`。
- 新WL artifact summary SHA：`1d7a63c7338673233432a26ae5c3b8dc1b745997ce5d8696fae5af038d2fc059`。
- 数值独立verifier回执SHA：`2d390e36b1938c7d5c7627ae60b8525770154c2d3155be18ea7400f7edceabf6`。
- 远端完整manifest SHA：`8de59dc34f5ec86dc38b12c23b8b6c6c629e749fb0ca272a3ae1b339d773c1da`。
- postcheck源码：`f9aecab8149b2055a96de1ec02bcca59cfd2b5b9`；脚本SHA：
  `a0ca6ef31b4b6a3c26979fe1168f4ed2e874472f474089810911af71939707e1`。
- postcheck回执SHA：`15afa0003c11f6a274d1c44a832c42edc97308ce5745c46d820162fa41674449`。
- 安全导出tar SHA：`701566e528b4fd6b548bd1baaca0cb8524ad430ac807e1036bb43a8189824afa`。
- 本目录原始manifest SHA：`d6ce3f4d7b390231ba446c04b49ed38db2c3503e28271b81fe67f7636e318021`。

12份安全原始回执加manifest共13文件逐字节导入。预测/候选身份/原始日志未导入Git。
postcheck只做字节hash/security扫描和安全结构回执读取，不反序列化预测或数值verifier私有内容；
原冻结数值verifier在远端内部作数值核对。这些不同权限边界不能混称为“所有程序都不读预测”。
README是解释，不在原始导出manifest中。首次导出后不重跑exclusive exporter，不重启已完成补算。
