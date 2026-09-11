# 分析器类型修复后的真实四run开发对照

2026-09-12香港，继承用户继续推进、合理修改与总100人民币授权；不复用旧run。

问题：共同修复结果接纳路径后，固定执行上限下现成critic与random能否产生可比最终解？
这是端到端开发验证，不是训练/scaling、单seed方法确认或新算法主张。

已确认：seed10有两个exit0程序且外部valid_submission=1.0，但分析异常导致is_buggy=True。
原分析器两个真实人工示例均在metric字段string类型拒绝；v1数字/null转换成功例过、失败例未过。
v2对明确is_bug=True的文本metric置null，仍保留失败与原诊断文本；成功/失败两个真实示例均通过。
未知字符串在非明确失败时仍拒绝，布尔/非有限/百分数不当数值。没有给旧run回填分数。

## 固定矩阵与公平约束

- leaf-classification、spaceship-titanic × seed11 × random/critic，共4run，保留所有失败。
- seed奇偶交叉顺序：leaf critic→random，spaceship random→critic；不按结果挑任务或槽位。
- 原gpu28双RTX3090、同SIF/Torch；一张critic一张执行；固定8B/16K checkpoint不训练。
- 原收费Qwen3-Coder-Flash/Alibaba、温度、候选width4/top2择1、6step、300秒、worker3540秒、5fold不改。
- 共同改动：analyzer窄类型兼容；API每run责任上限1.10→1.50USD，支持一次未知请求后仍可预留重试。
  新增全块API责任最多2USD，旧全部费用与0.70未知项结转；不能把历史未知释放。
  增加的是安全预留余量，不是提高输出tokens/候选/步骤，实际请求数/费用另报。
- 这些改动共同用于两臂，只在本版本比较selector，不把seed10→11变化归因critic。

## 上限与读数

单块280分钟双卡，含退出余量最多新增10GPUh；此前两旧块+seed10实际4.331666666666667GPUh。
全组关闭后统一读final；同时给最终有效率、逐任务配对、actual API/程序/分配耗时，缺失不补零。
新旧所有API仍≤原10USD/100人民币授权，独立账本逐行继承，关闭旧scope，unknown完整保留。
无人工重试失败槽位，无更换模型/降CPU/fallback。只在安全的只读诊断修复后才启动。

## 开跑前检查

从实际打包源码证明仅parser、review helper及账本授权变；typed配置反序列化/配对归一化一致。
parser单测、真实人工示例已过；新包再做原两次有界路由调用，计入同一账本。
独立查13113终态及最新诊断账本，复制全部call和未知责任，source/commit/配置/命令固定并随产物保存。
新seed固定本地RNG，不假称远端API逐token可重放；没有新增训练/采样，训练split检查不适用，保护集不碰。
6step不额外最终重执行，300秒超时退出开销照实算；不靠worker exit0证明有final。
提交和推送前扫描凭据；接口故障保留，source/未知费用漂移即停止，不重复G0或训练验收。
