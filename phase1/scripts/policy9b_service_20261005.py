"""Shared immutable BF16 base plus delivered LoRA; exact two allocated GPUs."""
import json,os,sys
def main():
    import torch
    expected=os.environ['EXPECTED_GPU_UUIDS'].split(',')
    assert torch.cuda.is_available() and torch.cuda.device_count()==2
    actual=[]
    for i in range(2):
        p=torch.cuda.get_device_properties(i);actual.append(str(p.uuid).lower().removeprefix('gpu-'))
        x=torch.tensor([[1.,2.],[3.,4.]],device='cuda:'+str(i));assert (x@x).cpu().tolist()==[[7.,10.],[15.,22.]]
    assert actual==[x.lower().removeprefix('gpu-') for x in expected]
    print('POLICY9B_SERVICE_CUDA '+json.dumps(dict(torch=torch.__version__,uuids=expected,correct=True)),flush=True)
    sys.argv=['vllm','serve','/model','--served-model-name','qwen3.5-9b','--host','127.0.0.1','--port','19475',
        '--tensor-parallel-size','2','--dtype','bfloat16','--max-model-len','32768','--gpu-memory-utilization','0.90',
        '--limit-mm-per-prompt','{"image":0,"video":0}','--max-num-seqs','2','--seed','108500','--enforce-eager',
        '--enable-lora','--max-lora-rank','64','--max-loras','1',
        '--lora-modules','qwen3.5-9b-mle-lora=/adapter']
    from vllm.entrypoints.cli.main import main as serve
    serve()
if __name__=='__main__':main()
