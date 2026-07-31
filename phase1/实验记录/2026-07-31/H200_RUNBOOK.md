# H200 训练包 Runbook(给学长,周末 8×H200)

## 一次性准备

1. 拉代码:`git pull`(fork 的 `phase1-value-critic` 分支;训练脚本 = `phase1/rm_train_hf.py`,DS 配置 = `phase1/ds_zero3_offload.json`)
2. 环境需要:`torch>=2.4 + transformers>=4.45 + deepspeed>=0.14 + flash-attn2(可选,无则自动回退 sdpa)`
3. 数据(都在仓库 `phase1/` 下,无需另拿):
   - `rm_pairs_v2.jsonl` + `cards_merged_20260731.jsonl`(主语料,110k 对)
   - `rm_pairs_xgen_dsonly.jsonl` + `cards_for_crossgen.jsonl`(跨生成器:DS 训 / Qwen 测)
   - `cards_for_crossgen_NORM.jsonl`(风格归一化版卡片,同一份对文件可复用)
4. 模型:Qwen2.5-1.5B-Instruct(仓库外,HF 直接拉)/ 7B 同理;`--model` 指到本地路径或 HF id

## 实验菜单(按优先级;每条一条命令,从 repo 根目录跑)

**E1|跨生成器塌陷 @ 全 context(最重要——headline 的截断混杂排除)**
```
deepspeed --num_gpus 8 phase1/rm_train_hf.py \
  --pairs phase1/rm_pairs_xgen_dsonly.jsonl --cards phase1/cards_for_crossgen.jsonl \
  --sizes 8000 --max-len 8192 --deepspeed phase1/ds_zero3_offload.json \
  --bs 2 --accum 2 --lr 1e-5 --seed 7 --out phase1/rm_hf_h200.csv
```
对照数字(2048 截断 + LoRA + 手搓 trainer):0.499/0.535/0.491(3 seed)。读法:全 context 下仍 ~0.5 → 塌陷坐实;显著回升 → 截断是共犯,结论要改写(这正是要在写论文前知道的)。

**E2|同配置的分布内对照(和 E1 成对,缺它 E1 无法解读)**
```
deepspeed --num_gpus 8 phase1/rm_train_hf.py \
  --pairs phase1/rm_pairs_audit.jsonl --cards phase1/cards_for_crossgen.jsonl \
  --sizes 8000 --max-len 8192 --deepspeed phase1/ds_zero3_offload.json \
  --bs 2 --accum 2 --lr 1e-5 --seed 7 --out phase1/rm_hf_h200.csv
```
(混合测试集 = DS 留出 + Qwen;2048 版参照:DS 留出 0.64-0.76 / Qwen 0.47-0.50)

**E3|in-task 曲线 @ 全 context(天花板重估)**
```
deepspeed --num_gpus 8 phase1/rm_train_hf.py \
  --pairs phase1/rm_pairs_v2.jsonl --cards phase1/cards_merged_20260731.jsonl \
  --sizes "500;2000;8000;24000" --max-len 8192 --deepspeed phase1/ds_zero3_offload.json \
  --bs 2 --accum 2 --lr 1e-5 --seed 7 --out phase1/rm_hf_h200.csv
```
(2048 版参照:0.535→0.776±0.016)

**E4|7B 规模轴(你提的全精度大模型)**
```
deepspeed --num_gpus 8 phase1/rm_train_hf.py \
  --pairs phase1/rm_pairs_v2.jsonl --cards phase1/cards_merged_20260731.jsonl \
  --sizes 8000 --max-len 8192 --model Qwen/Qwen2.5-7B-Instruct \
  --deepspeed phase1/ds_zero3_offload.json --bs 1 --accum 4 --lr 5e-6 \
  --out phase1/rm_hf_h200.csv
```

**E5|机制探针 @ 全 context(归一化,若时间富余)**:E1 命令把 `--cards` 换成 `cards_for_crossgen_NORM.jsonl`,`--out` 加后缀。

## 说明与坑

- 全参微调是默认;加 `--lora` 才是 LoRA。全参用 `--lr 1e-5`(7B 用 5e-6),LoRA 用 1e-4;
- `--max-len 8192` 覆盖 p90(5,402 tokens);想全覆盖用 12288(最长 9,239);
- 结果逐行追加到 `--out` 的 CSV(带 trainer/max_len/lora 列,和旧数字可直接并表);
- eval 只在 rank0 跑(单卡串行,~10 分钟),多卡只加速训练——正常现象;
- ZeRO-3 下 `save_pretrained` 已配 gather;若不存权重可忽略;
- 我方 3090 冒烟(LoRA + 2048,与旧 trainer 同配置对齐验证)已在跑,绿了我会在群里说一声——**请等冒烟绿了再烧 H200**。
