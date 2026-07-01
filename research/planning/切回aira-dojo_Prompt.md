# 切回 aira-dojo：给 Claude Code 的 Prompt（含复用环境 / 跑通 baseline / 修 torch）

> 背景决定（2026-06-22）：**实验台 = `facebookresearch/aira-dojo`**（干净拆分 search×operator、
> 自带基线、是 AIRA-dojo 负结论的同一框架）。**MLEvolve 仅作 SOTA 现状对照 / 快速 sandbox，
> 不在其上做公平对照实验。** 这一步把实验台从 MLEvolve 切回 aira-dojo，最大化复用已部署环境。
> 顺序：本步替代/补在 `EXPERIMENT_PROMPTS.md` 的 Prompt 0 位置，先侦察 + 跑通 smoke，别写大改。

---

## 可直接粘进 Claude Code 的 Prompt

```
我们把实验台从 MLEvolve 切回 facebookresearch/aira-dojo（理由：要守公平契约做干净消融、
需要它自带的 Greedy/MCTS/Evo 基线、且我们的靶子就是它产生的“搜索策略不重要”负结论）。
这一步只做侦察 + 复用已部署环境 + 跑通一个 baseline smoke，先给我计划/diff，我批准再落代码。
不要动 MLEvolve 的目录；它保留作 SOTA 对照。

## 0. 复用已部署的环境（不要重搭，直接接上）
- venv：/research/d7/spc/yzyang4/venvs/exp（已装 torch 等；aira-dojo 若 pin 了不同版本，先告诉我再改）
- 环境：~/env_setup.sh 已设代理(proxy.cse.cuhk.edu.hk:8000)、缓存全在 /research、SLURM_CONF
- 数据：mle-bench 已装、nomad2018 已下载切分在 /research/d7/spc/yzyang4/mle-bench-data
  （aira-dojo 用同样的 MLE-bench 格式，直接复用，别重下）
- 底座：DeepSeek（OpenAI 兼容），code=deepseek-v4-pro / feedback=deepseek-v4-flash，
  base_url=https://api.deepseek.com，key 只在远端 config、绝不写进本地或仓库
- Kaggle 凭证已配（~/.kaggle/kaggle.json）

## 1. 侦察 aira-dojo（读代码，先别改）
clone aira-dojo 到 /research/d7/spc/yzyang4/aira-dojo，读它的 Solver/搜索策略/评估(fitness)/
数据划分/执行环境(Apptainer) 抽象，给我【精确集成点】并贴文件路径 + 关键类/函数签名：
  (a) 在哪切换/插入节点价值回传与选择策略（Line 1 扩展用）；
  (b) 在哪插入 HCE 的 train/search/val 划分 + 外部化 pristine 评分（两条线都要）；
  (c) 在哪挂 proxy/低保真评估钩子、以及每节点“完整评估”当前在哪做（Line 2 主线从这往下减保真度）；
  (d) 它自带哪几个 baseline（确认有 Greedy/AIDE、UCT+MC=负结论条件、Evolutionary）。

## 2. 接 DeepSeek 底座
aira-dojo 默认底座大概率不是 DeepSeek。找到它的 LLM 客户端层，改成走 OpenAI 兼容端点
（base_url + key 从远端 config/env 读，不硬编码）。确认 code/feedback 两路都能用 v4-pro/v4-flash。

## 3. 修 torch（重要：当前是假 GPU）
现状：venv 里 torch 是 cu128，但 GPU 节点驱动 565（CUDA 12.7），导致 torch.cuda.is_available()=False，
实际在 CPU 上跑。修法：把 torch 换成 cu126 构建（驱动 565≥560，cu126 可用；如 2.x+cu126，
或与 aira-dojo pin 对齐的版本）。验证：srun 上一块 3090，python 里打印 torch.cuda.is_available()==True
和 get_device_name(0)。改之前先告诉我会动哪些包版本。

## 4. 让 Apptainer/Singularity 执行环境在 CSE 跑通
aira-dojo 用 Apptainer 隔离执行 agent 生成的代码。CSE 用 Singularity（兼容），缓存已指向
/research（SINGULARITY_* 在 env_setup.sh 里）。确认它能 pull/build 并 exec --nv 起容器；
若有 root/权限问题，停下来报告，别用 workaround 绕过隔离。

## 5. 跑通一个 baseline smoke（最小预算，端到端）
选最轻的 tabular 任务（nomad2018，已就绪），用 aira-dojo 自带的一个 baseline（如 Greedy 或
UCT+MC），steps 极小、time_limit≤30min、关掉一切非必要组件，srun 上 3090 后台跑。目标只证
“端到端通”：DeepSeek→执行(容器)→评分→搜索循环→产物落盘。报：是否产出非 buggy 有 metric 的节点、
节点数/树深、墙钟、以及实测每-run 的 DeepSeek 美元（回填 planning/预算与可行性估算.xlsx 的 B6）。

## 贯穿硬约束（沿用 CLAUDE.md）
- 公平契约：对照里只有被研究的那一个旋钮变（主线=评估/选择协议；扩展线=搜索控制器），
  算子集/底座/每任务预算/任务集/HCE 划分全固定且记录。
- 复现：pin 依赖 + git commit、记录所有 seed、命令/config/环境/seed 写进产物、结果 CSV 一行一 run。
- 诚实：报 median + 跨 seed 方差；长/贵实验前先给配置矩阵 + 总 run 数 + 预计 GPU·时，我批准再跑；
  主动标 confound / measurement artifact / “好得不真实”。
- 完整性：full_locked / HCE——外部 pristine 评分、固定隐藏 split、禁训练期读 held-out/test。
- 别动 MLEvolve 目录；它是 SOTA 对照，不是实验台。

## 这一步的产物
- aira-dojo 集成点报告（含三处钩子位置 + 自带 baseline 清单）。
- DeepSeek 接入 + torch cu126 修好 + Singularity 跑通的确认。
- 一个 baseline smoke 的产物 + 实测每-run 成本（回填预算表）。
做完停下来等我确认，再进 Prompt 0.5（在 aira-dojo 上采树，做 TD/MC 裁决）。
```

## 给我（你）的提醒

- **torch 这次一起修掉**：之前 cu128 是按 CUDA 12.8 装的，但节点驱动只到 12.7，所以一直假 GPU。
- **Prompt 0.5 要在 aira-dojo 上采树**：树形依赖搜索算法，裁决 TD 死活要用你真正会用的平台的树。
- **MLEvolve 的 pilot 成本数仍有效**（底座事实，与 harness 无关），照样回填预算表。
