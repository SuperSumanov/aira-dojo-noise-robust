# 研究盘清理完成 — 2026-09-14

12:10:25 UTC完成用户授权的清理。**本轮回收44,771,426,304 bytes（44.77 GB / 41.70 GiB），实际40 GiB空间分配测试通过，测试文件已释放。**

## 删除与保留

仅删除研究盘`/research/d7/spc/yzyang4/models/`内两份7月下载的公开生成器权重：

- `Qwen2.5-Coder-14B-Instruct`：6个分片，固定revision `aedcc2d42b622764e023cf882b6652e646b95671`。
- `Qwen2.5-Coder-7B-Instruct`：4个分片，固定revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`。

10个分片删除前逐字节SHA256均与上游固定版本的LFS摘要一致；路径、单硬链接、文件身份和活动依赖检查通过后才逐文件删除，没有递归删除目录。
本轮删除的内容字节数为44,771,405,824，前述回收量按文件实际分配块计。之前已经回收的旧critic压缩包不重复计入本轮。

保留并复核两目录中54个配置、tokenizer、许可证与下载元数据文件；保留固定版本恢复命令。
现用Qwen3-8B critic、已下载vLLM镜像、原MLE任务镜像的文件身份未变；语料、训练产物、实验结果、venv均未清理。
执行前调度器仅有旧12535 `PENDING(JobHeldUser)`，未修改/释放该作业，未发现本次目标被当前配置或我方Linux5进程引用。

## 空间阻塞已解除，但不是推理验收

删除后实际非稀疏分配42,949,672,960 bytes成功，独立核实临时文件已不存在；不是用共享盘`df`空闲推算用户配额。
现有计划尚缺27B文件28,868,542,488 bytes，这一容量测试比它多14,081,130,472 bytes。
因此，**截至此次观察，27B下载所需空间已具备**；不是永久预留或配额上限测量，下载前仍需检查容量以防其他写入。

27B权重本轮未下载，没有新增GPU任务、推理或训练。服务加载与真实任务接入仍待验证，不能把空间修复算作模型收益。

## 恢复方法与证据

删除不可本地撤销，但可从上游按原revision重新下载；固定版本公开页已核实可访问：
[14B](https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct/tree/aedcc2d42b622764e023cf882b6652e646b95671)、
[7B](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct/tree/c03e6d358207e414f1eca0bb1891e29f1db0e242)。恢复会重新占用上述空间，不自动执行。

```bash
hf download Qwen/Qwen2.5-Coder-14B-Instruct --revision aedcc2d42b622764e023cf882b6652e646b95671 --local-dir /research/d7/spc/yzyang4/models/Qwen2.5-Coder-14B-Instruct
hf download Qwen/Qwen2.5-Coder-7B-Instruct --revision c03e6d358207e414f1eca0bb1891e29f1db0e242 --local-dir /research/d7/spc/yzyang4/models/Qwen2.5-Coder-7B-Instruct
```

远端回执目录：`/research/d7/spc/yzyang4/research-storage-cleanup-20260914-mlaygiaj`。
本地逐字节相同副本在[清理回执](results/research_storage_cleanup_20260914/)。

|回执|SHA256|
|---|---|
|plan.json|`f2ac6247a4d4c00c8787dc67c0c8e66aa09d3eb9ee8d01daa4da1faa2d7c9b80`|
|reclaimed.json|`0c6f9d1c3cb7b0cac13e175d7c573c5c60008339303a5535ed044809d771cf9e`|
|capacity-after.json|`1ece8dace830567c29a115c90db3b5cf606145eb89dbedaea7fd853a8aa79c57`|

清理脚本`reclaim_obsolete_public_weights_20260914.py`是本次固定目标的一次性操作；已有删除回执，不得重跑或据此扩大范围。
