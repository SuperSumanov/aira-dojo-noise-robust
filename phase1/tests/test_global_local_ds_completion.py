from dataclasses import replace
from types import SimpleNamespace as NS
import unittest

from phase1.global_local_ds_completion import begin_deepspeed_update, finish_deepspeed_update
from phase1.global_local_accelerate_update_adapter import finish_non_deepspeed_update
from phase1.global_local_execution_plan import PlanError


def fixture():
    raw=NS(overflow=False)
    engine=NS(optimizer=raw,global_steps=5,skipped_steps=0,micro_steps=5,lr_scheduler=None,
              gradient_clipping=lambda:1.0,_step_applied=True)
    optimizer=NS(optimizer=raw,step_was_skipped=False)
    accelerator=NS(distributed_type='DEEPSPEED',deepspeed_engine_wrapped=NS(engine=engine),
                   _optimizers=[optimizer],optimizer_step_was_skipped=False,sync_gradients=True)
    before=begin_deepspeed_update(accelerator,engine,optimizer,max_grad_norm=1.0)
    return accelerator,engine,optimizer,before


def complete(a,e,o,skipped=False):
    e.global_steps+=1;e.micro_steps+=1;e.skipped_steps+=int(skipped)
    e._step_applied=not skipped
    e.optimizer.overflow=o.step_was_skipped=a.optimizer_step_was_skipped=skipped


class CompletionTest(unittest.TestCase):
    def test_success_can_commit(self):
        a,e,o,b=fixture();complete(a,e,o)
        r=finish_non_deepspeed_update(a,e,o,max_grad_norm=1.0,deepspeed_before=b)
        self.assertFalse(r['optimizer_step_skipped']);self.assertTrue(r['can_commit_plan_cursor'])

    def test_skip_is_not_success_even_though_global_steps_advanced(self):
        a,e,o,b=fixture();complete(a,e,o,True)
        r=finish_non_deepspeed_update(a,e,o,max_grad_norm=1.0,deepspeed_before=b)
        self.assertTrue(r['optimizer_step_skipped']);self.assertFalse(r['can_commit_plan_cursor'])
        self.assertEqual(r['attempted_update_delta'],1);self.assertEqual(r['applied_update_delta'],0)

    def test_missing_snapshot_fails(self):
        a,e,o,b=fixture();complete(a,e,o)
        with self.assertRaisesRegex(PlanError,'before_receipt'):finish_non_deepspeed_update(a,e,o,max_grad_norm=1.0)

    def test_missing_duplicate_and_replayed_step_fail(self):
        for delta in (0,2):
            a,e,o,b=fixture();e.global_steps+=delta;e.micro_steps+=delta
            with self.assertRaisesRegex(PlanError,'missing_or_duplicate'):finish_deepspeed_update(a,e,o,b)
        a,e,o,b=fixture();complete(a,e,o)
        newer=replace(b,global_steps=e.global_steps,micro_steps=e.micro_steps)
        with self.assertRaises(PlanError):finish_deepspeed_update(a,e,o,newer)

    def test_disagreeing_skip_signals_fail(self):
        for field in ('accelerator','optimizer','raw'):
            a,e,o,b=fixture();complete(a,e,o)
            if field=='accelerator':a.optimizer_step_was_skipped=True
            elif field=='optimizer':o.step_was_skipped=True
            else:e.optimizer.overflow=True
            with self.assertRaisesRegex(PlanError,'skip_signal_disagreement'):finish_deepspeed_update(a,e,o,b)

    def test_unobserved_flag_fails(self):
        a,e,o,b=fixture();complete(a,e,o);del e.optimizer.overflow
        with self.assertRaisesRegex(PlanError,'unobserved'):finish_deepspeed_update(a,e,o,b)

    def test_applied_and_skipped_count_must_agree(self):
        for field in ('applied','skipped_count','micro_count'):
            a,e,o,b=fixture();complete(a,e,o)
            if field=='applied':e._step_applied=False
            elif field=='skipped_count':e.skipped_steps+=1
            else:e.micro_steps+=1
            with self.assertRaises(PlanError):finish_deepspeed_update(a,e,o,b)

    def test_unrelated_engine_or_optimizer_fails(self):
        for field in ('engine','optimizer','snapshot'):
            a,e,o,b=fixture();complete(a,e,o)
            if field=='engine':a.deepspeed_engine_wrapped.engine=NS()
            elif field=='optimizer':a._optimizers=[]
            else:b=replace(b,engine_identity=0)
            with self.assertRaises(PlanError):finish_deepspeed_update(a,e,o,b)

    def test_clipping_scheduler_and_prior_skip_fail_before_update(self):
        for field in ('clipping','scheduler','prior_skip'):
            a,e,o,b=fixture()
            if field=='clipping':e.gradient_clipping=lambda:0.0
            elif field=='scheduler':e.lr_scheduler=NS()
            else:complete(a,e,o,True)
            with self.assertRaises(PlanError):begin_deepspeed_update(a,e,o,max_grad_norm=1.0)

    def test_no_finish_before_sync(self):
        a,e,o,b=fixture();complete(a,e,o);a.sync_gradients=False
        with self.assertRaises(PlanError):finish_deepspeed_update(a,e,o,b)

    def test_same_attempt_cannot_be_committed_twice(self):
        a,e,o,b=fixture();complete(a,e,o)
        finish_deepspeed_update(a,e,o,b)
        with self.assertRaisesRegex(PlanError,'already_consumed'):finish_deepspeed_update(a,e,o,b)

    def test_engine_sample_count_does_not_masquerade_as_consumed_pairs(self):
        a,e,o,b=fixture();e.global_samples=128000000;complete(a,e,o)
        r=finish_deepspeed_update(a,e,o,b)
        self.assertEqual(r['applied_update_delta'],1)
        self.assertNotIn('pairs',r)


if __name__=='__main__':unittest.main()
