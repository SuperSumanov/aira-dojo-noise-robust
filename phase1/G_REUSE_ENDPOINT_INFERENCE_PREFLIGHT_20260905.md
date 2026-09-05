# G-reuse 无标签 endpoint 推理适配器：执行前边界

日期：2026-09-05。继续 G0 + 同源隔离包，不改 queued job 12486 的 source/control/runtime。

1. **问题**：在同一模型和逐字相同编码下，不读取胜负方向，能否把每个 unique endpoint 的一次前向结果
   正确接入已冻结的五臂×三 seed + TF-IDF margin 物化层？不是测试真实 critic 准确率。
2. **改动预览**：新增 `g_reuse_endpoint_inference.py`、CPU 测试和独立源对照脚本；不修改旧 trainer、
   frozen effect/readout/margin 协议或 G0 文件。不添加训练、GPU 自动检测/提交、checkpoint 自动发现或数据文件 reader。
3. **输入**：内存中 exact-schema 的 endpoint_id/code/task_name；只有代码和任务名进入 tokenizer。
   不接受完整 Cards、better/worse、label/outcome、budget、split 等额外列；拒绝重复/空 endpoint。
4. **编码参照**：真实 G0 source `5f3bc362db922c8edee2ef134656dfdb9a2b74fb`，
   `train/dataset/pairs.py` SHA `3e1969499405199a187c12106d9f4d4a5542b4a1ecf094e0bd9f7c71514b4643`。
   task prefix、无 special token、25% head/75% tail、右 padding；max_len 由 caller 明确给定。
   v1 仅支持 task_cond=true / budget_cond=false；未来若输入依赖 pair budget，必须另冻 context-keyed 协议，不能复用 endpoint-only cache。
5. **模型**：caller 显式传入已加载且 eval 的模型；使用已有 `logits` scalar，不另造 reward head。
   不自动从训练切 eval、不替换/选择 checkpoint、不加载 pickle、不下载模型。adapter 不是 checkpoint 授权门。
6. **对照**：从已扫描的精确源码提取 CardEncoder 和原模型 forward；同 synthetic 输入比较逐 token 和
   直接 pair_collate 的 left-minus-right。另用随机初始化 tiny Qwen3 在 CPU 进行真实前向，所有参数不更新。
7. **矩阵**：软件测试 seeds 6/7/8，endpoint batch 1/2/4；原始与逆序输入、短/长/Unicode/空 code、共享 endpoint。
   准确率/utility 不计算；这不是 15-fit 的替代。float32 比较事前容差 atol=1e-6, rtol=1e-5。
8. **失败门**：非 eval、空输入、未知列、重复、坏 token、非有限或错误 shape 的 logits、矩阵 support 缺失/额外均拒绝。
   输入所有行先验证，才允许首次模型 forward；异常只给固定原因，不回显候选或代码。
9. **资源**：CPU correctness tests，单进程单线程，GPU/API/模型训练/protected read=0；不运行真实 1.7B/8B 推理。
   不做性能结论，不把 synthetic 多 seed 当真实训练复现；正式成本仍等待 G0。
10. **独立验证**：对照脚本从 hash-bound 源只提取类/函数，不 import 带数据 reader 的训练入口；固定依赖版本，
    记录确切 source SHA、命令、seed 和每个 correctness case。测试产物新目录写入，旧证据不覆盖。
11. **交付边界**：adapter 通过后也仍缺合法 checkpoint loader、OS 层读取隔离及 production caller。
    同 producer 来源包、G0、预算、15 个 final checkpoint 和 sealed cohort 关闭门未通过前，不读取真实评测输入。

与学长建议的关系：补齐实际 critic 使用路径，延续 init/query 成本分开记账；保持固定 agent 底座。
同一执行结果复用和真实效果门仍按既有 G-reuse 协议，不增加臂、不换方向、不以软件验证冒充正效果。
