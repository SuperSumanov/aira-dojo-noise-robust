from types import SimpleNamespace as NS

import pytest

from phase1.global_local_ds_completion import observe_deepspeed_restore
from phase1.global_local_execution_plan import PlanError


class Engine:
    def __init__(self, failure=None):
        self.optimizer=NS();self.global_steps=0;self.skipped_steps=0;self.lr_scheduler=None
        self.failure=failure;self.fallback_used=False

    def _load_zero_checkpoint(self,*args,**kwargs):
        return False if self.failure=='zero_false' else True

    def load_checkpoint(self,root,tag,**kwargs):
        if self.failure=='missing': return None,None
        if self.failure!='skip_zero':
            if not self._load_zero_checkpoint(root,tag):
                self.fallback_used=True
        self.global_steps=7 if self.failure=='wrong_step' else 3
        state={'contract':'changed' if self.failure=='wrong_binding' else 'fixed'}
        return root+'/'+tag+'/model_states.pt',{'critic_session':state}


def fixture(failure=None):
    e=Engine(failure);o=NS(optimizer=e.optimizer)
    a=NS(distributed_type='DEEPSPEED',deepspeed_engine_wrapped=NS(engine=e),_optimizers=[o])
    return a,e,o


def test_verified_completion_and_hooks_removed():
    a,e,o=fixture()
    with observe_deepspeed_restore(a,e,o,completed_steps=3,client_binding={'contract':'fixed'}) as observed:
        e.load_checkpoint('/our/previously_verified_checkpoint','pytorch_model')
    assert observed=={'load_calls':1,'zero_calls':1,'restore_completed':True}
    assert 'load_checkpoint' not in vars(e) and '_load_zero_checkpoint' not in vars(e)


@pytest.mark.parametrize('failure',['zero_false','missing','skip_zero','wrong_step','wrong_binding'])
def test_hidden_failure_cannot_complete(failure):
    a,e,o=fixture(failure)
    with pytest.raises(PlanError):
        with observe_deepspeed_restore(a,e,o,completed_steps=3,client_binding={'contract':'fixed'}):
            e.load_checkpoint('/our/previously_verified_checkpoint','pytorch_model')
    assert not e.fallback_used
    assert 'load_checkpoint' not in vars(e) and '_load_zero_checkpoint' not in vars(e)


@pytest.mark.parametrize('flags',[{'load_optimizer_states':False},{'load_module_only':True},{'load_module_strict':False}])
def test_wrong_restore_flags_rejected_before_load(flags):
    a,e,o=fixture()
    with pytest.raises(PlanError,match='weight_only'):
        with observe_deepspeed_restore(a,e,o,completed_steps=3,client_binding={'contract':'fixed'}):
            e.load_checkpoint('/our/previously_verified_checkpoint','pytorch_model',**flags)
    assert e.global_steps==0


def test_no_call_or_duplicate_or_missing_tag_rejected():
    for kind in ('none','twice','no_tag'):
        a,e,o=fixture()
        with pytest.raises(PlanError):
            with observe_deepspeed_restore(a,e,o,completed_steps=3,client_binding={'contract':'fixed'}):
                if kind=='no_tag': e.load_checkpoint('/our/previously_verified_checkpoint')
                if kind=='twice':
                    e.load_checkpoint('/our/previously_verified_checkpoint','pytorch_model')
                    e.load_checkpoint('/our/previously_verified_checkpoint','pytorch_model')


def test_used_engine_rejected():
    a,e,o=fixture();e.global_steps=1
    with pytest.raises(PlanError,match='fresh_engine'):
        with observe_deepspeed_restore(a,e,o,completed_steps=3,client_binding={'contract':'fixed'}):pass


def test_failed_attempt_cannot_be_retried_with_same_engine():
    a,e,o=fixture('missing')
    with pytest.raises(PlanError):
        with observe_deepspeed_restore(a,e,o,completed_steps=3,client_binding={'contract':'fixed'}):
            e.load_checkpoint('/our/previously_verified_checkpoint','pytorch_model')
    with pytest.raises(PlanError,match='already_attempted'):
        with observe_deepspeed_restore(a,e,o,completed_steps=3,client_binding={'contract':'fixed'}):pass


def test_catching_duplicate_exception_does_not_make_context_successful():
    a,e,o=fixture()
    with pytest.raises(PlanError,match='exactly_once'):
        with observe_deepspeed_restore(a,e,o,completed_steps=3,client_binding={'contract':'fixed'}):
            e.load_checkpoint('/our/previously_verified_checkpoint','pytorch_model')
            try:e.load_checkpoint('/our/previously_verified_checkpoint','pytorch_model')
            except PlanError:pass
