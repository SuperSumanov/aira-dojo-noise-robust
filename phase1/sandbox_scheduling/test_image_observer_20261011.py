"""Small CPU correctness check of common passive optimizer wrapping."""
import unittest
from image_gpu_observation_20261011 import INSTRUMENT

class ObserverTests(unittest.TestCase):
    def test_common_optimizers_unchanged(self):
        import torch
        kinds=(torch.optim.Adam,torch.optim.AdamW,torch.optim.SGD)
        def train(kind):
            torch.manual_seed(27011)
            model=torch.nn.Linear(3,1);opt=kind(model.parameters(),lr=.01)
            x=torch.tensor([[.1,.2,.3],[.5,-.4,.8]]);y=torch.tensor([[.3],[-.2]])
            for _ in range(3):
                opt.zero_grad();loss=((model(x)-y)**2).mean();loss.backward();opt.step()
            return [p.detach().clone() for p in model.parameters()]
        baseline={kind:train(kind) for kind in kinds}
        saved={kind:kind.step for kind in vars(torch.optim).values() if isinstance(kind,type) and 'step' in kind.__dict__}
        ns={}
        try:
            exec(INSTRUMENT,ns)
            for kind in kinds:
                actual=train(kind)
                for left,right in zip(baseline[kind],actual):self.assertTrue(torch.equal(left,right))
            self.assertGreaterEqual(len(ns['_r14_steps']),9)
            self.assertTrue(all(r['devices']==['cpu'] for r in ns['_r14_steps']))
        finally:
            for kind,step in saved.items():kind.step=step

if __name__=='__main__':unittest.main()
