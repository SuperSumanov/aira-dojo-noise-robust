# Too many threads / Resource is not available

在某些节点上启动了过多线程/进程的时候有可能遇到这个问题，可能直接报废一两个run，目前已知
的解决方法是用环境变量限制一下并发（放到.env里面导入）

```bash
# 1. 限制底层数学计算库与 PyTorch 算子内线程数
OMP_NUM_THREADS=1
MKL_NUM_THREADS=1
OPENBLAS_NUM_THREADS=1
VECLIB_MAXIMUM_THREADS=1
NUMEXPR_NUM_THREADS=1

# 2. 限制 HuggingFace 分词器并发线程
TOKENIZERS_PARALLELISM=false
RAYON_NUM_THREADS=1

# 3. 限制 vLLM 与编译相关的进程/线程数
VLLM_WORKER_MULTIPROC_METHOD=spawn
MAX_JOBS=2
TORCHINDUCTOR_COMPILE_THREADS=1
```