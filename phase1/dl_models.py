"""Download HF code-LLMs (safetensors only) for the multi-backbone H1 test. Robust: uses the Python API."""
from huggingface_hub import snapshot_download

M = "/research/d7/spc/yzyang4/models"
JOBS = [
    ("deepseek-ai/deepseek-coder-6.7b-instruct", f"{M}/deepseek-coder-6.7b-instruct"),
    ("codellama/CodeLlama-7b-Instruct-hf",       f"{M}/CodeLlama-7b-Instruct-hf"),
]
PATTERNS = ["*.safetensors", "*.json", "*.model", "tokenizer*", "*.txt"]

for repo, out in JOBS:
    try:
        snapshot_download(repo_id=repo, local_dir=out, allow_patterns=PATTERNS, max_workers=4)
        print("OK", repo, flush=True)
    except Exception as e:
        print("FAIL", repo, type(e).__name__, str(e)[:300], flush=True)
print("ALL_DONE", flush=True)
