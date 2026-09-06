# 实际检查点内容核验：结果前限定

2026-09-07，六小时会话工作，补齐1.7B/16K双卡尺寸验收的独立读取端。
不改训练、FA2构建/数值门、真实数据准入或科学矩阵，不新增GPU/API/model-fit。

先在已验收的自有tiny job12575上检查序列化schema（只输出类型和shape），
原终态SHA14dae4dbc7e1497695d1081517a1603833f4a6f97bd8ac3d534b5e0debdffaa2，
各文件先按该终态绑定的manifest验hash，之后才在CPU加载；不是任意pickle安全沙箱。

新独立检查端从模型client-state、FP32 master、AdamW moments/step、scaler和RNG payload
重构六个可直接还原的状态role，与保存前live-state指纹比较，并核对分片shape/完整参数总数。
BF16 live shards并未以独立完整tensor写入该格式，不能把FP32内容重构称为七role独立证明；
原恢复程序仍校验全部七role，这里只称六role payload观察核验。
无本尺寸uninterrupted对照，不能据此宣称本尺寸最终bitwise restart parity或模型收益。

执行顺序：本地负控→固定提交→Linux CPU负控→固定tiny两个rank九套已验收bundle只读检查。
首次实际tiny验证限1CPU线程/180秒，任何不符保留证据，不修改已验收tiny产物。
全部输入前后hash；CUDA_VISIBLE_DEVICES为空，HF offline；不读语料、label或预测值。
实尺寸作业完成后另绑定其实际job/commit/manifest，用相同检查端核两套bundle四rank。
检查点不能只验JSON标志：实际payload必须有限、优化器step正确且与live指纹一致。
没有训练seed sweep或效果统计，因此不把CPU检查时间当性能、不给accuracy。

本地结果：1通过，12因无Torch跳过；Linux真实结果尚未产生。
