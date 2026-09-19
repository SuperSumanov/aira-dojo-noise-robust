"""Common action-admission guards for BOTH continuation arms.

Development adapter, not deployed. This bounds admitted executions and new
repair/draft/improve admissions. It does NOT preempt in-flight work or independently
bound post-execution analysis: the same outer supervisor/cutoff is mandatory.
"""
from time import monotonic
from forets_cached_continuation_20260919 import make_cached_continuation

class _AdmissionStopped(BaseException):
    pass

def make_comparable_continuation(base_class, *, cache_enabled, seed, clock=monotonic):
    inner=make_cached_continuation(base_class,enabled=cache_enabled,seed=seed)

    class CommonAdmission(inner):
        def _continuation_admits(self):
            context=getattr(self,'_common_admission_context',None)
            if context is None:raise RuntimeError('admission outside expansion')
            return (self.remaining_steps>0 and
                context['prior_seconds']+clock()-context['start']<self.cfg.time_limit_secs)

        def debug_cycle(self,state,task,buggy_node):
            if not self._continuation_admits():return state,[],None
            return super().debug_cycle(state,task,buggy_node)

        def _debug(self,node):
            # A failed cache calls its base debug_cycle directly, bypassing this
            # class's debug_cycle entry. Guard the actual generator call as well.
            if not self._continuation_admits():raise _AdmissionStopped()
            return super()._debug(node)

        async def _draft(self,node):
            if not self._continuation_admits():raise _AdmissionStopped()
            return await super()._draft(node)

        async def _improve(self,node):
            if not self._continuation_admits():raise _AdmissionStopped()
            return await super()._improve(node)

        def _expand_leaf_and_backprop(self,path,state,task):
            if getattr(self,'_common_admission_context',None) is not None:raise RuntimeError('nested expansion')
            self._common_admission_context=dict(start=clock(),prior_seconds=self.state.running_time)
            original_count=self.num_children_to_choose
            owner=self
            class TaskProxy:
                def __init__(self):self.latest_state=state
                def __getattr__(self,name):return getattr(task,name)
                def step_task(self,current,code):
                    if not owner._continuation_admits():raise _AdmissionStopped()
                    next_state,result=task.step_task(current,code)
                    self.latest_state=next_state
                    return next_state,result
            proxy=TaskProxy()
            try:
                if not self._continuation_admits():return state
                # Native ForeTS otherwise samples two candidates from a pool of
                # one at the final remaining step. Apply the same boundary rule
                # to both arms and restore the configured count afterward.
                self.num_children_to_choose=min(original_count,self.remaining_steps,self.cfg.num_children)
                try:return super()._expand_leaf_and_backprop(path,state,proxy)
                except _AdmissionStopped:return proxy.latest_state
            finally:
                self.num_children_to_choose=original_count
                self._common_admission_context=None

    return CommonAdmission
