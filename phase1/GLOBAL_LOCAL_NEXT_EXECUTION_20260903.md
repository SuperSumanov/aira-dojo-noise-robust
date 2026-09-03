# 下一项效果实验：跨 seed、同预算的 global → local 迁移

2026-09-03；执行准备，不是效果结果或正式五臂预算授权。

优先验证真实 global 质量监督是否改善 local sibling 决策，并排除“只是多训练”“只是多见代码”及局部过拟合。
遵循 `global_local_calibration_candidate_protocol_v2.json` 的五臂，不恢复更早的 interleaved arm。

## 拟执行矩阵

| 臂 | 用途 | 拟 seed |
| --- | --- | --- |
| L1 | local 单遍，识别重复训练的伤害；不是同预算主对照 | 6、7、8 |
| Lbudget | local-only，同预算基线 | 6、7、8 |
| Gbudget | global-only，同预算迁移基线 | 6、7、8 |
| G_to_L | global 单遍后 local 单遍 | 6、7、8 |
| Ghash_to_L | 同样代码和顺序，global 标签改为端点一致的哈希排序 | 6、7、8 |

这是 15 个拟议训练单元，尚未授权。三个 seed 事前提出，不按结果换 seed；pivot model 和精确预算须根据
G0 墙钟而非 dev accuracy 确定。G0 本身只有 seed 6、十步，不是跨 seed 或效果验证。

## 运行前必须补齐的实质问题

1. **阶段顺序**：已读的 exact trainer 在数据加载后调用 `rng.shuffle(training_records)`，通用 Trainer
   还会执行训练采样。仅拼接两个来源不会实现“先 G 后 L”。必须提供显式、可恢复的阶段采样计划，并从
   实际 batch 回执验证顺序、消费次数、seed 和断点恢复，不靠文件名证明阶段训练。
2. **预算匹配**：同样 optimizer steps 不自动等于同样 token/计算量。需固定 tokenizer、序列化、batch 与
   实际消费预算；对所有 primary 同预算臂输出真实有效 token、padding、optimizer steps 与 allocation。
   在生成计划前定义末批处理，不能靠结果后改截断来“凑相同预算”。G_to_L/Ghash_to_L 的 row/order/token/step
   必须严格一致；L1 明确例外。若无法同时满足原预算契约，需先提出修订，不得悄悄放宽。
3. **数据边界**：现有 G0 的 4,689/551 train/dev 是历史开发数据。不能把已触碰的历史 outer test 或前瞻
   vault 直接升级成新的确认集。正式五臂仍需 producer provenance、experiment-closed split 和零重叠；
   如先做历史探索，应另立探索方案并保留它不能确认部署泛化的限制。
4. **成本与存储（本日后续状态覆盖旧阻碍）**：批准的单缓存清理已完成，4 GiB allocation/fsync 通过；
   唯一 G0 successor job 12288 已提交。2026-09-03 本轮只读核验仍为 PENDING/Resources、运行时间为零，
   调度器预计香港时间 9 月 4 日 12:14:15 开始，非保证。保留 2×PRO6000、117 分钟、no-requeue；包含
   job 12181 失败在内最多 3.986666666666667 GPU·h。不能重复提交，也不能把十步 dev 当方法效果。

## 本轮实质诊断：先让五臂能够回答原问题

本轮没有模型 fit、GPU/API 提交、真实训练数据或封存值读取。对 exact source 和 runtime 做只读检查，
从实际源码 AST 提取小函数、以合成输入在 CPU 执行。结构回执见
`results/global_local_execution_readiness_20260903/diagnostic.json`。不是训练性能或泛化效果结果。

绑定来源：critic source `5f3bc362db922c8edee2ef134656dfdb9a2b74fb`；
`bradley_terry.py` SHA=`d3cfd12602dc399a456810d4f706124df7117834ebba124813233f77ba043977`；
`pairs.py` SHA=`3e1969499405199a187c12106d9f4d4a5542b4a1ecf094e0bd9f7c71514b4643`。
runtime 仍是 G0 的 Transformers 5.12.1 / Accelerate 1.14.0，函数文件哈希另见回执。

### 1. 显式顺序还要覆盖多卡末批

`bradley_terry.py:181–183` 全池打乱；该 Trainer 没有阶段采样覆盖。
运行时 `Trainer._get_train_sampler` 支持 sequential，但只有关掉第一次 shuffle 并设置 sequential
仍不够：`BatchSamplerShard._iter_with_no_split` 的 even_batches 分支会从开头补齐末批。

源码函数的合成案例：G 为行 0–3，L 为行 4，双进程、每进程 batch=2，drop_last=false、even_batches=true。
实际交错消费顺序为 `[0,1,2,3,4,0,1,2]`：5 条输入产生 8 条消费、3 条重复，并在 L 后再次出现 G。
这是该分支的可复现性质；没有宣称 G0 的十步已经触发末批，也没有据此重提交 G0。

推荐实现预览：生成显式的 global-step / micro-step / rank 行计划；禁止 sampler 再次随机打乱或偷偷补样。
阶段末尾不足完整 effective batch 时先拒绝，等待事前确定的共同末批策略；不能默默丢弃、复制或掺入
下一阶段。resume 收据绑定计划摘要和已完成 optimizer step，分布式优化器/RNG 恢复必须另测，不能由
“计划切片相同”冒充真实训练可恢复。

### 2. 局部阶段可能落在几乎衰减完的学习率上

从实际 `transformers/optimization.py` 提取最终生效的 cosine 函数。固定一个**示例**：总共 1,000 步，
warmup=30，半周期 cosine；逐步调用值与独立连续积分近似对照。以下不是当前真实 G/L 比例。

| L 起始步 | L 步数 | 起始 LR / peak LR | L 平均 LR / peak LR |
| --- | --- | --- | --- |
| 500 | 500 | 0.5242811110572242 | 0.19212824940713447 |
| 800 | 200 | 0.1012785947186397 | 0.03449247328496857 |
| 900 | 100 | 0.025995410021864784 | 0.008825954842948262 |

若 L 只占末段，阶段文件虽存在，也可能没有足够更新幅度完成适配。**这是优化暴露风险，不证明真实训练
必然失败**；也不授权按 dev 数字搜索阶段长度/学习率。当前精确 G/L 身份和长度尚未冻结，不能把例子
写成实际比例。

另外，L1 用自身长度生成 cosine、Lbudget 用较长长度生成 cosine，即使调度器名称和 warmup ratio 相同，
二者最初 local 一遍的学习率也不同。原有“是否只是 local overtraining”解释因此需要先明确对照契约。

推荐的事前协议澄清（**未采用、未修改 v2**）：

- 所有 compute-matched 臂使用同一份、事前固定的逐步 LR 表及相同阶段边界；如采用局部阶段 LR restart，
  Lbudget/Gbudget/Ghash_to_L 也在同一步 restart，不能只给 G_to_L 加这一优势。
- L1 作为截短对照，应先决定是否严格复用 Lbudget 第一遍的行顺序、LR 和优化器初始状态；如不复用，
  不能把差异单独归因于训练遍数。
- 模型、预算和上述取舍在任何新效果读数之前确定。保留 v2 原成功门、全部五臂与全部 seed，不因结果增删臂。

### 3. exact token budget 不是总能靠末行截断实现

合成反例：global 一行消耗 4 tokens、local 一行消耗 6 tokens，G_to_L 一遍总共 10；local-only 按完整
pair 循环只能到 0、6、12…，没有 10 的前缀。这只证明**不能一般性保证**，不是说真实输入必定不兼容。
只匹配 optimizer steps 同样不保证有效 tokens 或 padding 相同；有效 tokens 相同也不保证 attention
计算量或 GPU 墙钟相同。

推荐先有只读预算可行性报告，分开记录真实 pair 次数、有效 tokens、padding、optimizer steps 和实测
allocation。禁止为凑预算截掉单个程序额外 token、丢掉 pair 标签、改变固定序列化或重复隐藏样本。
如果原 exact-token 契约不可满足，应另提版本修订并批准，例如预先限定预算差容忍度；不能在看效果后
将“近似”改称“相同”。固定 padded-token slots 也只是候选计算口径，不自动等于真实有效 token 或 FLOPs。

### 4. 哈希标签控制：区分字节顺序和 token 总数

现有 PairDataset 按 better/worse 编码，collator 将 better 序列放在前半 batch，loss 隐含标签全为正。
源码 collator 的两对合成案例表明：改标签方向改变 batch 行顺序，但**不改变**端点 token 多重集、有效
token 总数 10 或 padded-token 数 16；这里每个端点独立编码，不能错误声称翻转本身改变截断长度。
本次为 Python 容器替代 torch.tensor 的打包测试，不是 PyTorch 数值 forward/backward 测试。

更严格的控制接口预览：端点 A/B 按与 grade 无关的顺序固定，目标 sign 独立传入，loss 使用
`softplus(-sign * (score_A - score_B))`。真实与 hash 两臂只换全局 sign；局部阶段保持完全相同。
哈希仍严格使用 v2 的共享端点效用 `sha256('20260823|' + card_id)`，不是逐 pair 独立随机翻转。
此接口尚未落代码；需先验证真标签路径与旧损失/梯度等价，且不能影响已排队 G0 的 exact source。

## 正方向的推荐执行顺序与边界

**优先级一：一个 pivot 的跨 seed 迁移验证，而不是同时扩模型和扩算法。** 最窄的可验证假设是：
历史 global 真实执行质量监督，能否在相同、明确核算的资源下改善 local sibling 决策；并且收益不能用
多看代码、训练更久、局部重复训练伤害或某一个任务/seed 解释。CPU 准备消除上述执行歧义后，G0 只提供
成本信息；预算批准后才进入拟定五臂 × seed 6/7/8。不能提前按某个 seed 的准确率删除对照或换 pivot。

**优先级二：把已验证 proxy 收益连接到真实 label allocation，而非改回多保真。** 如果五臂通过原门，
再单独冻结固定 generator / 算子 / 任务 / 每任务执行预算的选择实验，问同样完整执行次数或明确成本下
能否得到更好的候选。历史 replay 只能验证数据流/离线选择，不能证明自适应搜索的反事实轨迹收益。
该扩展目前没有新增授权，也不能使用 first-960 或旧 Target-300/522 救结果。

**优先级三：clean scaling 继续等来源条件，不能靠旧数据补写。** 2026-09-03T11:58:27Z 核验仍为
306 archives、589/960 eligible runs、closure=false、canonical config-v2 sidecars=0；学长分支仍为
`b8d095180415957aa1bab31fa53ead1bba261c03`，没有新提交或 outcome。摄取 PID 1692885 已核验 live，
poll 78 rc=0。这不是无数据资产，而是规范确认数据的来源门仍未满足。

## 相关工作核验：不能把一般迁移或 agent/critic 共进化称首次

本轮为有针对性的第一手来源检索，不是完整排除所有近作的 scoop 保证。

- [Arch-Graph, CVPR 2022](https://arxiv.org/html/2204.05941v1) 已将成对关系预测器从源任务迁移到目标任务，
  并用少量目标评估适配后选架构。因此“成对 predictor + 迁移 + 少量监督”的一般组合不是我们的新颖性。
- [Multi-Predict, AutoML 2023](https://proceedings.mlr.press/v224/akhauri23a.html) 研究跨任务、搜索空间和
  硬件的 predictor 适配与样本效率；它支持 NAS 对照框架，也限制“可迁移 predictor”这一宽主张。
- [Mokrii et al., SIGIR 2021](https://arxiv.org/abs/2103.03335) 在神经排序迁移中报告过少样本适配可能
  退化；这支持保留 local-only / global-only / local 单遍等强对照，但不证明 MLE 必然同样退化。
- [CAFE, 2026-08-25 preprint](https://arxiv.org/html/2608.24794v1) 在 SearchQA 中让共享模型交替担当
  agent 和 critic，通过在线 RL 与离线偏好更新共进化。它不是这里固定 MLE generator 的直接同设定
  实验，但足以警示：宽泛“反馈带动 agent 自我进步”已很拥挤；不能改名恢复或违反底座不更新边界。
- [White et al., NeurIPS 2021](https://proceedings.neurips.cc/paper/2021/hash/ef575e8837d065a1683c022d2077d342-Abstract.html)
  将 predictor initialization/query 成本分开，并检验其搜索价值。我们也必须区分预训练成本、在线预测
  成本与完整 execution 成本，不能把已有语料的生成费用当作免费新增预算。

据此维持 v2 的 **D&B mechanism ablation、method_novelty_allowed=false**。我们能争取的正贡献是
可复现的 MLE decision corpus 上得到跨 seed、同预算、抗混淆的实测迁移收益，并在另行批准和冻结的实验
中证明真实 execution-label 效率；目前尚未取得这两项效果结论。

## 当前改动范围和下一批准点

本轮只记录诊断与执行预览，没有改训练代码、冻结 v2、G0 source/runtime 或任何模型；现有协议回归
`python -B -m pytest -p no:cacheprovider phase1/tests/test_global_local_calibration_candidate_protocol.py -q`
实跑为 5 passed。CPU 计划生成器/测试的具体落代码批准已通过异步问题请求，尚未收到回复。
连同 `phase1/tests/test_verify_critic_component_g0.py` 的第二次组合回归实跑为 17 passed / 0.39 秒。
预算口径和 LR 契约的上述修订是另一项事前协议决定；不能把 CPU 实现批准理解成采纳修订或准许 15 fits。
正式训练还需 producer/split 身份门、G0 成本和精确 GPU·h 授权，任何一项不能用“希望正结果”替代。

## 原成功门保持不变

G_to_L 相对 Lbudget 平均至少 +2 个百分点、每 seed 同向、task-clustered CI 下界大于 0；还须超过
Gbudget 和同池 TF-IDF。只有这些通过后才检验相对 Ghash_to_L 的真实质量标签收益。完整报告
Draft/Improve、task macro、seed 离散度、LOTO 和单任务贡献，不把单 seed、挑任务或局部过拟合回避当迁移。

## scaling 支线

沿用 v2 的 0.6B/4B/8B × seed 6/7 六-run 矩阵，但规范、outcome-before 的 config-v2 sidecar 当前为 0。
缺失来源条件不能通过补写历史配置来满足；因此现在不启动 clean scaling、不复用已撤回旧 checkpoint。
