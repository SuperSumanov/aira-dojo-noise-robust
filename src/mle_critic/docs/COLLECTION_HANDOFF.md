# 数据采集交接指南(给学长 · 2026-07-24)

> **一句话**:用你的 `dojo-reproduce`(+ 我们的修复)在任意账号上自动化采 MLE-agent **MCTS 搜索树数据**;
> 一条命令启动,自链跑完整个 worklist,不需要人守。本文 = 现状汇报 + 上手指南 + 坑清单。

---

## 0. TL;DR(5 步上手)

```bash
# 1) 拿代码(本分支 = 你的 dojo-reproduce + 我们的修复与套件)
git clone -b dojo-reproduce-collect https://github.com/SuperSumanov/aira-dojo-noise-robust.git aira-dojo-reproduce
cd aira-dojo-reproduce

# 2) 环境:uv venv(managed python!系统 python 计算节点没有)+ 依赖,照 README/INSTALLATION;
#    .sif 放 build/superimage/superimage.root.2026-07-macos-v1.sif;.env 按 §2 模板填

# 3) 数据:Kaggle 网页逐个接受 12 个赛题规则(§2.4)后:
python scripts/collect/prep_tasks.py          # 下载+切分+public.tar,robust 验证,幂等

# 4) 两个路径变量(建议写进 ~/.bashrc)
export COLLECT_HOME=/research/.../<你的目录>   # 状态+日志放这
export DOJO_REPO=$PWD                          # 本仓库路径

# 5) 启动(之后全自动;此命令可重复跑/可放 cron 当心跳)
bash scripts/collect/pool_fill_once.sh
```

监控:`squeue -u $USER`;数产出:`find $LOGGING_DIR/aira-dojo -path '*mcts_data_*' -name journal.jsonl | wc -l`。

---

## 1. 现状汇报(截至 2026-07-24)

**目标**:方案 A = 发布大规模 MLE-agent 搜索树数据集(NeurIPS D&B / ICLR;计划全文见
`phase1/实验记录/2026-07-23/A计划汇报_20260723.md`,在 phase1-value-critic 分支)。

**已采集**(我的账号,可直接合并复用,runs root=`/research/d7/spc/yzyang4/aira-dojo-runs`):
- labeled(有外部真分)卡 **~700**,全节点 **~2200**:tps_may ~274 / spaceship 224 / tps_dec 137+ / nomad 38 + suite 首批;
- 双线产出 ~200 graded/天:非容器 sbatch 线(draft/debug/improve 用 v4-pro)+ 容器 pool 线(全 flash);
- 你的 split(12 任务)wave-1 正在我账号排队跑(suiteA-E+V1,seed 701-702)。

**效用证明(T1,已实测)**:真分预测 / 反作弊检测 / buggy 预测三条曲线**全部随数据量单调上升**
(亮点:hack@tps_may AUROC 0.80;诚实点:value 仍未超自报分、buggy 干净版 0.60 偏弱)。
复现:`sbatch scripts/t1_curves.sbatch`(phase1 分支),数据涨了重跑即自动延长曲线。

**你要跑的**:同一 split,更多 seed(wave 2+)。机制全自动,worklist 加行即可。

## 2. 一次性环境准备

### 2.1 venv
按 README 装;**必须 uv managed python**(`uv venv --python-preference only-managed --python 3.12`)——
系统 python 在计算节点不存在,venv 会变死链。已知坑已修:`srun_pool` 对 uv-symlink venv 的
`.resolve()` bug(见 §4-①,本分支已改 `.absolute()`)。

### 2.2 .env(仓库根;在 .env_default 基础上)
```dotenv
LOGGING_DIR=/你的/logs 根/                 # runs 落这里
MLE_BENCH_DATA_DIR=/你的/mle-bench-data
SUPERIMAGE_DIR=/你的/仓库/build/superimage/   # 必须以 / 结尾
PRIMARY_KEY_DEEPSEEK_V4_FLASH=sk-...          # 或 PRIMARY_KEY 兜底
DEFAULT_SLURM_ACCOUNT=gpu
DEFAULT_SLURM_PARTITION=gpu_24h
DEFAULT_SLURM_QOS=gpu
# ---- 容器内网络/HF(新 singularity server 只认 jupyter.yaml env + 这些;RAD_* 是 sand 老路径用的,一并给全)----
RAD_HTTP_PROXY="http://137.189.90.241:8000/"   # 用 IP!容器 --containall 下解析不了代理域名
RAD_HTTPS_PROXY="http://137.189.90.241:8000/"
RAD_NO_PROXY="localhost,127.0.0.1,.cse.cuhk.edu.hk,.cuhk.edu.hk"
RAD_HF_TOKEN=""
RAD_HF_HUB_OFFLINE="0"
RAD_HF_HUB_VERBOSITY="error"
RAD_NLTK_DATA=/你的/cache/nltk
# ---- prompt 真实算力({{hardware}} 从这读;别让 agent 以为有 H200)----
HARDWARE="1 NVIDIA GeForce RTX 3090 GPU (24GB VRAM) and 6 CPUs"
```
注:`jupyter.yaml` 里 `HF_HUB_OFFLINE: "1"` 是你定的离线设计,**保留**;
我们把「离线环境勿用预训练」写进了 operator prompt(本分支已含)——这一步让 NLP 任务从全崩变为能产真分。

### 2.3 .sif
`build/superimage/superimage.root.2026-07-macos-v1.sif`(19.7G;Google Drive 下法:`gdown --fuzzy <分享链接>`,~6 分钟)。

### 2.4 Kaggle 规则 + 数据 prep
网页逐个 Accept(12 个:leaf / kuzushiji / petfinder / random-acts-of-pizza / spooky / google-quest /
tabular-playground-series-may-2022 / text-normalization-challenge-english-language / mlsp-2013-birds /
text-normalization-challenge-russian-language / tweet-sentiment-extraction / whale-categorization-playground),
然后 `python scripts/collect/prep_tasks.py`。脚本幂等、robust 验证(description.md + 体积)、自动补 `public.tar`
(容器 sand 需要)。**空目录假阳性坑已在脚本里防掉。**

## 3. 采集机制与日常操作

```
pool_fill_once.sh ──提交──> pool_collect.sbatch(1 job=4 GPU allocation)
        ▲                        │ 内部 srun_pool 开 4 个 step,跑 2任务×2seed 的 MCTS-20步
        └────批尾+墙杀trap 自动回调(自链);QOS 满被拒不记账,重跑/cron 会补
```
- **worklist**:`$COLLECT_HOME/collect_state/pool_worklist.txt`(首跑自动从模板复制)。
  行格式:`seed1 seed2 唯一tag [任务;分号连接] [单步cap秒]`。加 seed = 加行。**tag 永不复用**。
- **心跳(推荐)**:`crontab -e` 加 `*/15 * * * * COLLECT_HOME=... DOJO_REPO=... bash .../pool_fill_once.sh >> $COLLECT_HOME/logs/heartbeat.log 2>&1`
  ——兜住 QOS 拒绝/节点死机后的断链。
- **监控**:`squeue -u $USER`;批日志 `$COLLECT_HOME/logs/pool_collect_<job>.out`;
  **真分只在 run 完成后的 `checkpoint/journal.jsonl`**(实时 `json/JOURNAL.jsonl` 永远没有 score,别用它数产出)。
- **吞吐参考**(单账号实测):4 GPU pool ≈ 每批 4 树/4.5h,~19 graded/批;tabular/text graded 率 23-32%。

## 4. 坑清单(全部实测踩过;★=本分支已修,你只需知道)

| # | 坑 | 处置 |
|---|---|---|
| ★1 | `srun_pool.py` 把 uv-symlink venv `.resolve()` 成基座解释器 → worker 丢 venv(No module named omegaconf) | 已改 `.absolute()` |
| ★2 | sbatch `--export` 值里的**逗号**会劈开参数(任务表/seed 列表) | 套件用 PC_S1/PC_S2 + 分号编码任务表 |
| ★3 | 同 config 重跑复用旧 batch/manifest,重试耗尽直接 fail | 每批唯一 `PC_ISSUE`(worklist tag) |
| ★4 | 提交撞 QOS 上限被拒但仍记"已提交" → 链毒化 | fill_once 只在 sbatch 成功后记账 + 心跳重试 |
| 5 | **坏节点**:gpu36(容器启动静默冻死)、gpu38(跑一半 node failure) | 默认排除(`POOL_EXCLUDE` 可改);projgpu8/33 也在列 |
| 6 | 登录节点上的 nohup 长循环会被会话清理杀掉 | 一切自链走 sbatch(集群驻留),别用登录节点 daemon |
| 7 | 容器内 DNS:`--containall` 用镜像 resolv.conf,解析不了代理域名 | 代理一律写 **IP**(见 .env 模板) |
| 8 | timm/EfficientNet 容器内必报错 | 双根因:HF 离线(设计如此)+ **镜像 GLIBC 过旧**(kuzushiji/petfinder 报 `GLIBC_2.3x not found`)→ 待镜像 v2;期间视觉任务失败如实记录 |
| 9 | kuzushiji 4.5G 数据 + 节点 tmp 盘满(`No space left`) | 大数据任务注意 /scratch 配额;失败会被记 buggy,不炸链 |
| 10 | sqlite-on-NFS 并发(多进程同 cache.db) | 每批独立 snapshot 天然隔离;同一 allocation 4 step 实测无碍 |
| 11 | statoil 数据是 .7z、detecting-insults 规则永久关 | 已从任务集剔除(你新 split 不含) |
| 12 | agent 拿老 API 写码必崩(transformers.AdamW / lgb early_stopping_rounds / ReduceLROnPlateau verbose) | prompt 约束已含(本分支);还会犯但 debug 循环能救 |

## 5. 数据怎么数 / 怎么合并

- 数产出:`find $LOGGING_DIR/aira-dojo -path '*mcts_data_*' -name journal.jsonl | wc -l`(每个=1 完成树)。
- 出卡片(代码/自报分/真分/算子/血缘):phase1-value-critic 分支
  `python -m phase1.build_cards <runs_root> out.jsonl` + `python -m phase1.relabel_minmax out.jsonl out_mm.jsonl`
  (**min-max 必做**:medal 归一会把"没拿牌"任务压成常数标签)。
- 多账号合并:各自 runs root 直接并列扫即可(build_cards 按 card id 去重;seed 段错开:我 5xx/6xx/701-702,建议你从 703+)。

## 6. 待办里属于你的三件

1. **借账号规模拍板**(P1 采集 2 周 vs 50 天的分水岭);
2. **镜像 v2**(修 GLIBC → kuzushiji/petfinder/whale 才能真正产出;顺带 timm);
3. mlsp-2013-birds / whale 我们刚 prep 完还没跑过端到端 —— 你 wave-1 先各跑 1 seed 验证(audio 域是全新的,可能有新依赖坑)。

---
*代码:`dojo-reproduce-collect` 分支(=你的 dojo-reproduce + ①③修复 + prompt 约束 + 12 任务 yaml + 本套件);
研究侧(build_cards/T1 曲线/A 计划文档)在 `phase1-value-critic` 分支。有问题随时找我们。*

> **坑 #13(2026-07-24 补)**:偶发 worker step 在 solver 结束后**僵尸挂起**(不退出,journal 已写完)。
> 设计上无害:批达 8h 墙 → TERM trap 自动补链;想省时间可直接 `scancel <job>`(确认该批各 run 目录下
> `checkpoint/journal.jsonl` 都在即安全),trap 同样会触发自链。


> **2026-07-24 运维补充(学长反馈)**:
> - 学长侧已改 `HF_HUB_OFFLINE` 允许容器内下载 → 采集 regime(在线/离线)按 run 记录在 dojo_config,
>   合并数据时它是一个正式的分布轴;**agent 运行目录用完即删**(re-grade worker 已内建),注意内存清理;
> - 坑 #6 更正:长驻进程用 **tmux**(不要 nohup);
> - GLIBC(坑 #8):学长经验=**降级某个组件可解**(conda 下降级 cryptography 生效);uv 环境等效方案待定;
> - 坑 #14:多账号合并 card id 无需加盐(32-hex uuid,碰撞概率可忽略,已核)。

> **2026-07-25 侦察快报(排卡前必读)**:
> - **视觉任务退化但未死**:suiteD(kuzushiji/petfinder,exec cap 3600s)跑 5h,40 节点 78% buggy(其中 13 个 exec 超时、4 个 GLIBC/libGL,其余混合),**有 9 个正常节点**。含义:当前镜像上视觉任务吞吐差、性价比低——优先跑 NLP/表格,视觉等镜像 v2 或把 exec cap 提到 5400s+ 再试;音频(mlsp-birds)结果今日出。
> - **混环境重评会假失败**:tabular 老线(非容器 venv)的解在容器里重跑,18 个撞 LightGBM OpenCL 缺失、3 个撞新 sklearn 删除 multi_class 参数——同一份代码换环境 ~1/3 假阵亡。含义:①re-grade/复现必须与采集同环境;②datasheet 里"环境敏感性"是真实的一根轴。
