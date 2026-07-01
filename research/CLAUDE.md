# CLAUDE.md — 项目规则（Claude Code 自动读取，全程遵守）

## 项目是什么

研究项目主题：**穷算力（单卡/商用 3090）下的噪声鲁棒 MLE 搜索**。
在 `facebookresearch/aira-dojo` 基线上做，底座用 DeepSeek（OpenAI 兼容 API，
绝不微调 LLM 权重，model-agnostic 是卖点）。当前定了**两条线、一主一备**：

- **主线（Line 2，默认朝它铺代码）：多保真 + 保真度一致评估**。
  穷算力下只能用便宜带噪的低保真试跑（多保真）来搜得广，但 AIRA_2 证明搜索退化的
  病根是「评估不一致/噪声」。核心问题：**在单卡 + 廉价噪声评分下，怎样保住 HCE 式
  「评估一致 → 长程稳定」**。做法 = 给评估加保真度旋钮 + 方差感知/一致性选择
  （均值 − λ×波动），三臂对照（完整评估 / 朴素 proxy-HCE / 一致性 proxy）。
  详见 `研究提案 v2…md`。**它的保底（方差感知选择降方差）不依赖树深，几乎必成立。**

- **扩展线（Line 1，gated，别默认动它）：完整 RL 搜索控制器**。
  在搜索控制器层引入 RL credit assignment（TD/advantage）/ 探索（Thompson）/
  预算分配（BAI），检验能否推翻 AIRA-dojo「搜索策略不重要」的负结论。
  **仅当预实验 0.5 绿灯（TD 在真实树上确实降方差）且算力有余时才做**。
  详见 `EXPERIMENT_PROMPTS.md`。

> 执行第一步对两条线相同：先跑 `planning/TD_保底验证_预实验.md` 的 Prompt 0.5，
> 它同时是两条线之间的裁决器。预算/关口次序见 `planning/预算与可行性估算.xlsx`。
> 多保真组件（BAI 预算分配）是两条线共用的地基，先做主线不浪费。

## 绝对不做（hard NO）

- **不微调 / 不 RL-finetune 底座 LLM**。所有「学习」只发生在轻量搜索控制器里
  （价值回传、选择策略、预算分配）。这是本项目与 TreeRL/TEMPO/AceGRPO 的根本区别。
- **不破坏公平契约**：对照实验中**只有被研究的那一个旋钮允许变**（主线=评估/选择
  协议；扩展线=搜索控制器）。算子集、底座、每任务预算、任务集、HCE 数据划分必须
  固定且逐项记录。任何会顺带改变其他变量的改动，先停下来提示我。
- **不把 MLEvolve 当实验台**。实验台 = `facebookresearch/aira-dojo`（干净拆分
  search×operator、自带 Greedy/UCT-MC/Evo 基线、是负结论的同一框架）。**MLEvolve
  仅作 SOTA 现状对照 / 快速 sandbox，绝不在其上做公平对照实验。** 切换步骤见
  `planning/切回aira-dojo_Prompt.md`。
- **不在未经我批准时启动长/贵实验**。先给配置矩阵 + 总 run 数 + 预计 GPU·时。
- **不只报均值、不报单次数字**。

## 评估完整性（full_locked / HCE，强制）

- 数据划分 80/10/10 = `D_train` / `D_search`（对 agent 隐藏，外部化评分）/
  `D_val`（对搜索也隐藏，只用于最终选择）。`D_test` 既不给 agent 也不给 orchestrator。
- 评分一律由**外部 pristine 代码**计算，不读 workspace 里可能被改过的评估脚本。
- **禁止训练期访问 held-out / test 路径**；instrument 文件访问，违例即标记。
- agent 永远只看到分数、看不到标签。

## 复现默认值（每个实验都要）

- pin 依赖版本 + 记录 git commit，写进产物文件本身。
- 设定并记录所有 seed（python / numpy / 框架 / 采样温度）。
- 把确切命令、config、环境与 seed 存到产物旁边。
- 结果写 **CSV，一行一个 run**，所有旋钮与指标作为列（含 seed、commit、预算、臂名）。
- warmup 与测量分离；报 median + 跨 seed 方差。

## 诚实与怀疑（协作风格）

- 做一个怀疑的协作者：主动指出 confound、measurement artifact、「好得不真实」的结果。
- 实验日志要诚实记录**实际跑了什么**，包括失败和废弃的配置，不只记漂亮数字。
- 任何「策略不重要(B≈C)」或「我们赢了(C>B)」的结论，先排除：是噪声？seed 太少？
  被某个任务主导？
- 区分**真解决**与**掩盖问题的 workaround**，并说清楚。

## 工作流默认

- 改动前先给设计 / diff 预览，我批准再落代码。
- 长任务必须支持 checkpoint/resume（集群有单作业时限）。
- 每个 RL 组件用配置开关独立可关，保证可逐组件消融。

## 关键前置工作（related work，别重复造轮子）

- AIRA-dojo (2507.02554)：搜索 policy×operator 形式化；**负结论**（脏评估下策略不重要）。本项目的靶子。
- AIRA_2 (2603.26499)：HCE 协议；把退化诊断为评估噪声而非记忆。本项目的干净评估底座。
- ArchPilot (2511.03985)：proxy 多保真（1 epoch/10% 数据）。BAI 多保真档参照它。
- RewardHackingAgents (2603.11337)：full_locked 防作弊。完整性方案来源。
- MLEvolve (2606.06473)：MCGS + UCT + 稀疏 reward。现状对照。
