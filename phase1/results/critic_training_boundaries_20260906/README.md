# 完整累积与分片读出边界补齐

2026-09-06香港凌晨。当前训练主候选不变：同执行记录/valid-token预算的full G-reuse→L。
本次是消除正式训练接口缺口，不是模型收益、scaling或来源资格。

## 真实CPU累积和恢复

结果前code：064da23b6643437d8f7aca4dc393e7b58989c456；沿用已验收TRAIN投影、consumer、AdamW和session。
只扩展工程fixture，不改生产算法。随机4433参数Qwen、float32、dropout0.1、seed6，world2×8pairs×8accum。
32合成endpoint，G130/L134不重边且G只复用L端点；完整轨迹264pair/20064valid tokens。
Lbudget更新实际pair数128/6/128/2，full为128/2/128/6；均覆盖8/1/8/1 microbatch。

A/B各两臂full、prefix2、resume2→4，共12轨迹；独立检查32个完整checkpoint bundle。
模型、AdamW、Python/NumPy/Torch RNG的8组实际状态比较逐位相同；8次rank final-state相同；
恢复消费序列精确拼接，A/B工程状态逐字节相同。
独立回执SHA：ded24aa6a16af3ae1f33a50ecf466be0cbd640ebcd8a9558a43c81f0ef9d1bf4。

这12条轨迹检验8-microbatch路径能运行且完整恢复一致，本身不是独立整批梯度对照。
因此同晚另以decfcb4f571f81134fcef0f9208f9fad8edd1ac4扩展此前整批oracle到2×8×8：
五臂A/B各38条rank-update检查，summary/cases逐字节相同；最大绝对梯度差4.76837158203125e-07，
参数差9.313225746154785e-10，均通过结果前原容差。
该独立参照使用SGD/no-dropout/8-token合成输入，不能改称生产AdamW或GPU验收；
G/L端点在oracle中不复用，只测试梯度数学；前一32endpoint的入口fixture则真实复用其合成端点。
两项功能互补但不是研究效果。实际短序列不证明1.7B/16K/ZeRO3内存可行；同seed的A/B不是科研seed重复。

## final ZeRO-3分片转CPU推理模型

code：8f96819c2361fe752c3c25063fdaa6e57fde9ac7。
新接口只接受已锁定的final step/token/SHA，验证双rank完整文件，再由固定DeepSpeed库lazy合并FP32 master，
逐参数转为caller模型的声明dtype。拒绝prefix、latest猜选、错误hash/shape和nonfinite；不执行checkpoint内Python。
它不恢复optimizer/RNG，不能用于训练resume；异常后caller必须丢弃模型。

CPU实际使用固定DeepSpeed转换器，验证自己生成的ZeRO3格式：26参数BF16网络、1个FP32 buffer、奇数分片padding。
权重和两条输入的前向与已知完整模型精确相同；9 tests passed in 44.53s。
这**不是实际DS engine写出的checkpoint**，尚须12535真正完成后用其工程checkpoint复验。
哈希不提供pickle沙箱；函数不是生产准入器，ADMITTED_RELEASES保持空。

## 失败、限制与复现

- 新fixture本地第一次错用了不存在的BatchShape字段，1失败/2通过；修正字段后相关30测试通过。
  预检时间曾误填03:24，开跑前独立提交改为时钟实际03:16。
- 分片读出本地因缺Torch/DeepSpeed仅skip，未宣称通过。远端第一轮R5缺pytest，在测试开始前失败。
  该失败receipt里actual_deepspeed_converter=true是启动器错误的意图字段，**不表示实际执行**；原回执保留，
  后续receipt明确prior_failure_did_not_execute_converter=true。
- 修复仅在测试进程末尾追加已有exp环境以导入pytest7.4.3，不安装/改动R5；Torch仍2.11.0+cu128，
  DeepSpeed转换器源码SHA固定为2859057b959683c8aff715cec1691c9c46bf75b14859003202f561df2be3b1fb。
- 累积trace禁止路径字面扫描0命中，不是完整路径/OS/网络隔离；转换器测试未做strace。
- 各阶段CPU硬时限、固定seed、实际命令见operations；计时分离首次update，完整框架启动时间未包含在runs.csv段计时。
  不从这些合成小模型时间外推GPU预算。未改排队12535/实际生产环境，没有新增GPU/API作业。

远端CPU根为/tmp/critic-entry-cpu-accum8-064da23-a、-b；converter根为/tmp/critic-zero3-readout-code-8f96819。
源代码22/15文件运行后与原Git blob导出包一致。结果tar SHA：
36fa33d521a3b94284c0b36aee65bcf24fe80d878425b360d583c316d3654bd6，40960bytes。
manifest绑定10份原始结果；本README与后来附上的operations不在其原始清单中。
gradient/独立清单另绑定4份原始结果，summary SHA=eee2f008e4874541780d6897bcab38d66cf6df712ade15ddc2922fd62cc14891，
其独立下载tar SHA=33aa39cbc2d51a99209dced5419cc46e699fcbe31f570ffe90988588ca8cda0b。
梯度oracle未额外做strace；只按固定自生成输入运行，不扩大上一项trace覆盖声明。

研究盘完整占用查询240秒超时；不据partial输出推算剩余额度。三个指定checkout的只读metadata查询完成，
原控制checkout约831MB，多数为Git直接跟踪的历史JSONL；未修改其文件或清理原始语料/检查点/封存数据。
这些重复来源文件不能未经依赖核实就删掉。正式四fit完整resume checkpoint所需空间仍未成功预留。
