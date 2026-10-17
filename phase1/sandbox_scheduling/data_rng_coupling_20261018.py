"""Experimental CPU-data randomness coupling, not a new CRN principle.

Qualified scope: zero-worker map datasets exposing CPU images or deterministic
noisy-image patches. Does not touch model initialization, CUDA kernels, labels,
optimizer settings, time limits, or an agent model. Unknown datasets fail closed.
"""
import hashlib
import json
import struct


def keyed_seed(*parts):
    h=hashlib.sha256()
    for value in parts:
        b=str(value).encode();h.update(struct.pack('!Q',len(b)));h.update(b)
    return int.from_bytes(h.digest()[:8],'big') & ((1<<63)-1)


def install(mode, seed):
    import torch
    import numpy as np
    from torch.utils.data import DataLoader, Dataset, Sampler
    import inspect
    assert mode in ('global','sampler','addressed')
    original=DataLoader.__init__
    assert not getattr(original,'_coupling_installed',False)
    signature=inspect.signature(original)
    logs=[]

    def raw_keys(dataset):
        # A fixed qualification boundary, NOT inference that arbitrary datasets
        # have stable identities. Only raw input is hashed; targets are not used.
        if hasattr(dataset,'images'):
            raw=dataset.images
            def get(i):return raw[i]
        elif all(hasattr(dataset,n) for n in ('patches','noisy_list','patch_size')):
            def get(i):
                k,r,c=dataset.patches[i];s=dataset.patch_size
                return dataset.noisy_list[k][r:r+s,c:c+s]
        else:raise ValueError('dataset outside fixed raw-input identity scope')
        counts={};keys=[]
        for i in range(len(dataset)):
            v=get(i)
            if isinstance(v,torch.Tensor):
                assert v.device.type=='cpu';v=v.detach().numpy()
            v=np.ascontiguousarray(v)
            h=hashlib.sha256(str((v.shape,v.dtype.str)).encode()+v.tobytes()).hexdigest()
            occurrence=counts.get(h,0);counts[h]=occurrence+1
            keys.append(h+':'+str(occurrence))
        assert len(set(keys))==len(keys)
        return keys,hashlib.sha256('\n'.join(sorted(keys)).encode()).hexdigest()

    class AddressedDataset(Dataset):
        def __init__(self,source,keys,key):
            self.source=source;self.keys=keys;self.key=key;self.epoch=0
        def __len__(self):return len(self.source)
        def __getitem__(self,index):
            # The four prequalified sources use torch/torchvision augmentation,
            # never numpy/Python/CUDA random transforms inside __getitem__.
            with torch.random.fork_rng(devices=[]):
                torch.random.default_generator.manual_seed(keyed_seed(seed,self.keys[index],self.epoch,'augment'))
                return self.source[index]

    class AddressedSampler(Sampler):
        def __init__(self,source,keys,key,log):
            self.source=source;self.canonical=sorted(range(len(keys)),key=keys.__getitem__)
            self.key=key;self.log=log;self.epoch=0
        def __len__(self):return len(self.source)
        def __iter__(self):
            epoch=self.epoch;self.epoch+=1;self.source.epoch=epoch
            # Random priorities preserve relative order for shared raw inputs
            # even when candidate code changes the training subset/fold.
            order=sorted(self.canonical,key=lambda i:(keyed_seed(seed,self.source.keys[i],epoch,'order'),self.source.keys[i]))
            return iter(order)

    class ReportingSampler(Sampler):
        # Pass-through iteration, no pre-materialization or extra RNG draws.
        def __init__(self,source,keys,log):self.source=source;self.keys=keys;self.log=log
        def __len__(self):return len(self.source)
        def __iter__(self):
            h=hashlib.sha256();n=0
            rec=dict(epoch=len(self.log['epochs']),n=0,completed=False,order_sha256=None)
            self.log['epochs'].append(rec)
            try:
                for i in self.source:
                    h.update((self.keys[i]+'\n').encode());n+=1
                    yield i
                rec['completed']=True
            finally:rec.update(n=n,order_sha256=h.hexdigest())

    def init(self,*args,**kwargs):
        bound=signature.bind(self,*args,**kwargs);bound.apply_defaults();a=bound.arguments
        if not a['shuffle']:
            return original(*bound.args,**bound.kwargs)
        assert a['num_workers']==0 and a['sampler'] is None and a['batch_sampler'] is None
        assert a['generator'] is None,'do not overwrite explicit user randomness'
        dataset=a['dataset'];keys,key=raw_keys(dataset)
        log=dict(mode=mode,loader=len(logs),samples=len(keys),input_multiset_sha256=key,epochs=[])
        logs.append(log)
        # Input-identity instrumentation is identical across all three arms.
        # Its wall-clock cost is included; no speedup claim is made.
        if mode=='sampler':
            a['generator']=torch.Generator().manual_seed(keyed_seed(seed,len(logs)-1,'loader'))
        elif mode=='addressed':
            dataset=AddressedDataset(dataset,keys,key)
            a['dataset']=dataset;a['shuffle']=False
            a['sampler']=AddressedSampler(dataset,keys,key,log)
            a['generator']=torch.Generator().manual_seed(keyed_seed(seed,key,'loader'))
        result=original(*bound.args,**bound.kwargs)
        assert self.batch_sampler is not None and self.batch_sampler.sampler is self.sampler
        self.batch_sampler.sampler=ReportingSampler(self.sampler,keys,log)
        return result
    init._coupling_installed=True
    DataLoader.__init__=init
    return logs


def selftest():
    import torch
    import numpy as np
    from torch.utils.data import DataLoader,Dataset
    class Data(Dataset):
        def __init__(self):self.images=torch.arange(24,dtype=torch.float32).reshape(12,2)
        def __len__(self):return len(self.images)
        def __getitem__(self,i):return self.images[i]+torch.rand(2),i
    before=DataLoader.__init__;out={}
    def collect(mode,distract,epoch=0):
        DataLoader.__init__=before;log=install(mode,1701)
        torch.manual_seed(29);torch.rand(distract)
        loader=DataLoader(Data(),batch_size=3,shuffle=True,num_workers=0)
        for _ in range(epoch):list(loader)
        vals=list(loader)
        return torch.cat([x for x,y in vals]),torch.cat([y for x,y in vals]),log
    for mode in ('global','sampler','addressed'):
        a,b=collect(mode,0),collect(mode,31)
        out[mode]=dict(order_equal=bool(torch.equal(a[1],b[1])),samples_equal=bool(torch.equal(a[0],b[0])))
        assert all(v['epochs'][0]['completed'] for v in a[2])
    a,b=collect('addressed',0,0),collect('addressed',0,1)
    assert out['addressed']==dict(order_equal=True,samples_equal=True)
    assert out['sampler']['order_equal'] and not out['sampler']['samples_equal']
    assert not out['global']['order_equal']
    assert not torch.equal(a[1],b[1]) and not torch.equal(a[0],b[0])
    # Address keys never depend on the whole dataset multiset.
    full=[str(i) for i in range(12)];subset=full[::2]
    order=lambda keys:sorted(keys,key=lambda k:(keyed_seed(1701,k,0,'order'),k))
    assert [k for k in order(full) if k in subset]==order(subset)
    instrumented=collect('global',0)
    DataLoader.__init__=before;torch.manual_seed(29)
    vals=list(DataLoader(Data(),batch_size=3,shuffle=True,num_workers=0))
    assert torch.equal(instrumented[0],torch.cat([x for x,y in vals]))
    assert torch.equal(instrumented[1],torch.cat([y for x,y in vals]))
    DataLoader.__init__=before
    print(json.dumps(dict(selftest=True,conditions=out,epochs_differ=True)))

if __name__=='__main__':selftest()
