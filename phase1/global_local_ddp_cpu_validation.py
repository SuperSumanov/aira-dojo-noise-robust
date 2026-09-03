"""Bounded 2/4-process Gloo test, synthetic two-parameter model only.

Not Transformers Trainer, ZeRO, bf16, or a real critic. Keeps the existing
single-CPU Trainer guard intact. Loopback communication is explicitly allowed;
no model download, real data, GPU or paid API. Own tiny checkpoints only.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
from dataclasses import asdict
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import random
import time

import numpy as np
import torch
import torch.distributed as dist
import torch.multiprocessing as mp

from phase1.global_local_batch_adapter import encoding_digest, pack_batch, observe_batch
from phase1.global_local_execution_plan import BatchShape, EncoderBinding, Endpoint, Pair, build_plan
from phase1.verify_global_local_execution_trace import BatchReceipt, verify_plan, verify_prefix


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixture(world, arm):
    if world not in (2, 4) or arm not in ('G_to_L', 'Ghash_to_L'):
        raise ValueError('unsupported_synthetic_case')
    h = lambda x: hashlib.sha256(x.encode()).hexdigest()
    context, encoded, truth, pools = h('synthetic:ddp-context'), {}, {}, []
    for source in ('G', 'L'):
        rows = []
        for i in range(16):
            endpoints = []
            for side, length in enumerate((3, 5)):
                cid = f'synthetic:ddp:{source}:{i}:{side}'
                ids = tuple(1 + ((i*7 + side*3 + j + (source == 'L')) % 19) for j in range(length))
                encoded[(context, cid)] = ids
                endpoints.append(Endpoint(cid, length, encoding_digest(ids)))
            pair = Pair.canonical(source, *endpoints, context)
            truth[pair.key] = 1 if i % 2 else -1
            rows.append(pair)
        pools.append(tuple(rows))
    plan = build_plan(arm, *pools, seed=6, shape=BatchShape(world, 4 // world, 2),
        encoder=EncoderBinding(h('synthetic:integer-encoder'), h('synthetic:ddp-serializer'), 8),
        protocol_sha256=h('synthetic:ddp-unit-test-not-research-v2'))
    verify_plan(plan, *pools)
    return plan, pools, encoded, truth


class Tiny(torch.nn.Module):
    def __init__(self, stochastic):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.tensor([0.17, -0.09], dtype=torch.float64))
        self.stochastic = stochastic
        self.dropout = torch.nn.Dropout(0.25 if stochastic else 0.0)
        self.observed = []

    def forward(self, ids, mask):
        self.observed.append(tuple(encoding_digest(x[:int(m.sum())].tolist()) for x, m in zip(ids, mask)))
        x = ids.double() * mask
        features = torch.stack((x.sum(1)/50, x.square().sum(1)/500), 1)
        if self.stochastic:
            features *= 0.8 + 0.2*random.random()
            features *= torch.from_numpy(np.random.uniform(0.9, 1.1, size=tuple(features.shape)))
        return self.dropout(features) @ self.weight


def rng_state():
    n = np.random.get_state()
    return {'python': random.getstate(), 'torch': torch.get_rng_state(),
            'numpy': (n[0], n[1].tolist(), n[2], n[3], n[4])}


def restore_rng(x):
    random.setstate(x['python']); torch.set_rng_state(x['torch'])
    n = x['numpy']; np.random.set_state((n[0], np.asarray(n[1], dtype=np.uint32), n[2], n[3], n[4]))


def binding(plan, rank, stochastic):
    return {'plan_sha256': plan.sha256, 'world': plan.shape.world_size, 'rank': rank,
            'stochastic': stochastic, 'script_sha256': sha(__file__), 'torch': str(torch.__version__),
            'lr': 0.02, 'scheduler': 'linear-four-updates', 'optimizer': 'AdamW-weight-decay-zero',
            'seed': 6, 'rank_rng_seed': 600 + rank}


def atomic_torch_save(x, path):
    # Atomic visibility and file fsync are tested; NOT a power-failure proof.
    tmp = path.with_suffix('.partial')
    with tmp.open('xb') as f:
        torch.save(x, f); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def worker(rank, world, arm, stochastic, output, resume, end_step, rendezvous):
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    dist.init_process_group('gloo', init_method='file://' + rendezvous, rank=rank,
                            world_size=world, timeout=timedelta(seconds=60))
    plan, pools, encoded, truth = fixture(world, arm)
    target_reads = []
    def target(key):
        if arm == 'Ghash_to_L' and key in {r.key for r in pools[0]}:
            raise ValueError('true_global_label_access_forbidden')
        target_reads.append(key)
        return truth[key]
    model = Tiny(stochastic)
    ddp = torch.nn.parallel.DistributedDataParallel(model)
    optimizer = torch.optim.AdamW(ddp.parameters(), lr=.02, weight_decay=0.0)
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lambda s: max(0., 1-s/4))
    random.seed(600+rank); np.random.seed(600+rank); torch.manual_seed(600+rank)
    events, start = [], 0
    if resume is not None:
        ck = Path(resume) / f'rank-{rank}.pt'
        manifest = json.loads((Path(resume)/'manifest.json').read_text())
        assert sha(ck) == manifest['rank_files'][ck.name]
        old = torch.load(ck, map_location='cpu', weights_only=True)
        assert old['binding'] == binding(plan, rank, stochastic)
        assert old['completed_steps'] == 2
        model.load_state_dict(old['model']); optimizer.load_state_dict(old['optimizer'])
        scheduler.load_state_dict(old['scheduler']); restore_rng(old['rng'])
        events, start = old['events'], old['completed_steps']
    new_events = []
    output = Path(output)
    for step in range(start, end_step):
        optimizer.zero_grad(set_to_none=True)
        for batch in (b for b in plan.batches if b.optimizer_step == step and b.rank == rank):
            packed = pack_batch(plan, batch, lambda c,n: encoded[(c,n)], target, pad_id=0)
            receipt = observe_batch(plan, batch, packed, target, pad_id=0)
            ids = torch.tensor(packed.input_ids); mask = torch.tensor(packed.attention_mask)
            ctx = ddp.no_sync() if batch.micro_step < plan.shape.accumulation-1 else nullcontext()
            with ctx:
                score = ddp(ids, mask)
                n = len(batch.rows); signs = torch.tensor(packed.signs, dtype=torch.float64)
                loss = torch.nn.functional.softplus(-signs*(score[:n]-score[n:])).mean()/plan.shape.accumulation
                loss.backward()
            event = asdict(receipt)
            actual = model.observed[-1]
            assert tuple(zip(actual[:n], actual[n:])) == receipt.encoded_digests
            events.append(event); new_events.append(event)
        optimizer.step(); scheduler.step()
    assert not torch.cuda.is_initialized()
    state = {'binding': binding(plan, rank, stochastic), 'completed_steps': end_step,
             'model': model.state_dict(), 'optimizer': optimizer.state_dict(), 'scheduler': scheduler.state_dict(),
             'rng': rng_state(), 'events': events, 'target_read_count_this_process': len(target_reads),
             'new_forward_calls': len(new_events)}
    atomic_torch_save(state, output/f'rank-{rank}.pt')
    gathered = [None]*world
    dist.all_gather_object(gathered, events)
    if rank == 0:
        receipts = []
        for rank_events in gathered:
            for x in rank_events:
                x = dict(x); x['pair_keys'] = tuple(x['pair_keys'])
                x['encoded_digests'] = tuple(tuple(p) for p in x['encoded_digests'])
                receipts.append(BatchReceipt(**x))
        verify_prefix(plan, receipts, completed_steps=end_step)
        manifest = {'world': world, 'arm': arm, 'stochastic': stochastic, 'completed_steps': end_step,
            'input_sha256': plan.input_sha256, 'plan_sha256': plan.sha256,
            'rank_files': {f'rank-{r}.pt': sha(output/f'rank-{r}.pt') for r in range(world)},
            'trace_verified': True, 'process_resume': resume is not None,
            'optimizer_updates_global': end_step-start,
            'forward_calls_all_ranks': (end_step-start)*world*plan.shape.accumulation}
        (output/'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2)+'\n')
    dist.barrier(); dist.destroy_process_group()


def same_tree(a, b):
    if isinstance(a, torch.Tensor):
        return isinstance(b, torch.Tensor) and a.dtype == b.dtype and a.shape == b.shape and torch.equal(a,b)
    if type(a) is not type(b): return False
    if isinstance(a, dict): return a.keys()==b.keys() and all(same_tree(a[k],b[k]) for k in a)
    if isinstance(a, (tuple,list)): return len(a)==len(b) and all(same_tree(x,y) for x,y in zip(a,b))
    return a==b


def states(root):
    m=json.loads((root/'manifest.json').read_text())
    if m['world'] not in (2,4) or set(m['rank_files'])!={f'rank-{r}.pt' for r in range(m['world'])}:
        raise ValueError('rank_manifest_mismatch')
    result=[]
    # Hash all ranks before deserializing even the first one.
    for name, expected in m['rank_files'].items():
        if sha(root/name)!=expected: raise ValueError('checkpoint_hash_mismatch')
    for name, expected in m['rank_files'].items():
        result.append(torch.load(root/name,map_location='cpu',weights_only=True))
    return result


def reference(world, arm):
    plan, _, encoded, truth=fixture(world,arm)
    model=Tiny(False)
    opt=torch.optim.AdamW(model.parameters(),lr=.02,weight_decay=0)
    scheduler=torch.optim.lr_scheduler.LambdaLR(opt,lambda s:max(0.,1-s/4))
    for step in range(plan.steps):
        opt.zero_grad(set_to_none=True)
        scores_a,scores_b,ys=[],[],[]
        for batch in (b for b in plan.batches if b.optimizer_step==step):
            packed=pack_batch(plan,batch,lambda c,n:encoded[(c,n)],truth.__getitem__,pad_id=0)
            s=model(torch.tensor(packed.input_ids),torch.tensor(packed.attention_mask))
            n=len(batch.rows); scores_a.append(s[:n]); scores_b.append(s[n:]); ys.extend(packed.signs)
        loss=torch.nn.functional.softplus(-torch.tensor(ys)*(torch.cat(scores_a)-torch.cat(scores_b))).mean()
        loss.backward(); opt.step(); scheduler.step()
    return model.weight.detach()


def run(root):
    assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and os.environ.get('GLOO_SOCKET_IFNAME')=='lo'
    assert root.is_relative_to(Path('/tmp')) and not root.exists()
    root.mkdir(mode=0o700)
    started=time.monotonic(); trials=[]; resumed=[]; reference_checks=[]
    def launch(world,arm,stochastic,tag,steps=4,resume=None):
        if resume is not None:
            plan,_,_,_=fixture(world,arm)
            previous=states(resume)
            assert len(previous)==world
            for rank,state in enumerate(previous):
                assert state['binding']==binding(plan,rank,stochastic) and state['completed_steps']==2
        path=root/f'w{world}-{arm}-{tag}'; path.mkdir(mode=0o700)
        # FileStore rendezvous unique per process group; Gloo binds loopback only.
        rdv=str(path/'gloo-rendezvous')
        mp.spawn(worker,args=(world,arm,stochastic,str(path),None if resume is None else str(resume),steps,rdv),
                 nprocs=world,join=True)
        m=json.loads((path/'manifest.json').read_text()); trials.append(m)
        (root/'progress.json').write_text(json.dumps({'completed_distributed_trajectories':len(trials)}))
        return path
    for world in (2,4):
        for arm in ('G_to_L','Ghash_to_L'):
            det=launch(world,arm,False,'deterministic')
            ref=reference(world,arm)
            for s in states(det): torch.testing.assert_close(s['model']['weight'],ref,rtol=1e-12,atol=1e-12)
            reference_checks.append({'world':world,'arm':arm,'matches_full_batch_reference':True})
            full=launch(world,arm,True,'stochastic-full')
            prefix=launch(world,arm,True,'prefix',steps=2)
            restored=launch(world,arm,True,'fresh-process-resume',resume=prefix)
            left,right=states(full),states(restored)
            for a,b in zip(left,right):
                for key in ('binding','completed_steps','model','optimizer','scheduler','rng','events'):
                    assert same_tree(a[key],b[key]), 'resume_state_mismatch:'+key
            for s in left[1:]:
                for key in ('model','optimizer','scheduler'): assert same_tree(left[0][key],s[key])
            assert len({hashlib.sha256(bytes(x['rng']['torch'].tolist())).hexdigest() for x in left})==world
            resumed.append({'world':world,'arm':arm,'per_rank_complete_state_equal':True,
                            'rank_rng_distinct':True,'new_process_group':True,'cut_step':2})
        # Exact same encoded inputs between true and hash labels, all ranks.
        a=states(root/f'w{world}-G_to_L-stochastic-full')
        b=states(root/f'w{world}-Ghash_to_L-stochastic-full')
        for x,y in zip(a,b):
            for u,v in zip(x['events'],y['events']):
                assert {k:q for k,q in u.items() if k!='plan_sha256'}=={k:q for k,q in v.items() if k!='plan_sha256'}
    report={'status':'PASS_SYNTHETIC_GLOO_NOT_ZERO_OR_RESEARCH_FIT',
        'script_sha256':sha(__file__),'torch':torch.__version__,'seed':6,
        'world_sizes':[2,4],'reference_checks':reference_checks,'resume_cases':resumed,'trials':trials,
        'distributed_trajectories':len(trials),'global_optimizer_updates':sum(x['optimizer_updates_global'] for x in trials),
        'all_rank_forward_calls':sum(x['forward_calls_all_ranks'] for x in trials),
        'research_model_fits':0,'real_data_opened':False,'gpu_context_created':False,'api_calls':0,
        'loopback_gloo_communications':True,'zero3_or_bf16_verified':False,'power_failure_verified':False,
        'wall_seconds_not_throughput_benchmark':time.monotonic()-started}
    (root/'summary.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('status','distributed_trajectories','global_optimizer_updates','all_rank_forward_calls')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--output-root',required=True,type=Path)
    args=p.parse_args(); run(args.output_root.resolve())
