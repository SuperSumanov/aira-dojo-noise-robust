import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import scheduling_opportunity_screen_20261012 as screen_module
from scheduling_opportunity_screen_20261012 import choice_points, journal_exposure
from live_admission import AdmissionState


def trace(width, actions):
    state = AdmissionState(width); events = []
    for t, (action, key) in enumerate(actions):
        if action == 'queued': state.request(key)
        elif action == 'admitted': assert state.admit(key)
        elif action == 'released': state.finish(key, cleanup_verified=True)
        elif action == 'queue_cancelled': state.cancel_waiting(key)
        events.append(dict(event=action, key=key, time=t, queued=len(state.queue),
                           active=len(state.active), limit=width))
    return events


class ScreenTests(unittest.TestCase):
    def test_two_waiters_two_free_is_not_scarcity(self):
        es = trace(2, [('queued','a'),('queued','b'),('admitted','a'),('admitted','b'),('released','a'),('released','b')])
        r = choice_points(es, 2, {'a':'candidate','b':'candidate'})
        self.assertEqual(r['multiple_waiters_at_admission'], 1)
        self.assertEqual(r['candidate_subset_choices'], 0)

    def test_real_choice_and_preview_distinction(self):
        es = trace(1, [('queued','a'),('queued','b'),('admitted','a'),('released','a'),('admitted','b'),('released','b')])
        self.assertEqual(choice_points(es,1,{'a':'candidate','b':'candidate'})['candidate_subset_choices'],1)
        r = choice_points(es,1,{'a':'preview','b':'candidate'})
        self.assertEqual(r['scarce_subset_choices'],1)
        self.assertEqual(r['candidate_subset_choices'],0)

    def test_cancelled_and_zero_events(self):
        es = trace(1,[('queued','a'),('admitted','a'),('queued','b'),('queue_cancelled','b'),('released','a')])
        self.assertEqual(choice_points(es,1,{'a':'candidate','b':'candidate'})['scarce_subset_choices'],0)
        self.assertEqual(choice_points([],2,{})['admissions'],0)

    def test_unknown_and_open_fail(self):
        es=trace(1,[('queued','a'),('admitted','a'),('released','a')])
        with self.assertRaises(ValueError): choice_points(es,1,{})
        with self.assertRaises(ValueError): choice_points(es[:-1],1,{'a':'candidate'})

    def test_future_queue_arrival_does_not_change_past_choice(self):
        prefix=[('queued','a'),('admitted','a'),('released','a')]
        suffix=[('queued','b'),('admitted','b'),('released','b')]
        self.assertEqual(choice_points(trace(1,prefix+suffix),1,{'a':'candidate','b':'candidate'})['scarce_subset_choices'],0)

    def test_journal_orientation_ties_and_rejection(self):
        nodes=[dict(step=i,operators_used=[role],is_buggy=bug,metric=x,metric_maximize=False)
               for i,(role,bug,x) in enumerate([('draft',False,.4),('improve',False,.4),
                    ('improve',True,.1),('improve',False,.2),('debug',False,.1)])]
        r=journal_exposure(nodes,-1)
        self.assertEqual(r['accepted_improve'],2)
        self.assertEqual(r['strict_record_improve'],1)
        self.assertEqual(r['strict_record_debug'],1)
        with self.assertRaises(ValueError): journal_exposure(nodes,1)
        with self.assertRaises(ValueError): journal_exposure(nodes[::-1],-1)

    def test_closed_batch_schemas_and_operation_namespace(self):
        # Two runs legitimately both have local operation zero. Queue keys
        # carry the run prefix. Also exercise the two historical closure keys.
        for job, summary_key in [('17592','readout_sha256'),('17670','summary_sha256')]:
            with self.subTest(job=job), TemporaryDirectory() as directory:
                base=Path(directory); root=base/'fixture'; root.mkdir()
                def save(name,value,jsonl=False):
                    path=root/name; path.parent.mkdir(parents=True,exist_ok=True)
                    path.write_text(('\n'.join(json.dumps(x) for x in value)+'\n') if jsonl else json.dumps(value))
                schedule=[dict(index=i,block=0,lane=0,task='aerial-cactus-identification',seed=i,arm='fixture') for i in range(2)]
                save('plan.json',dict(schedule=schedule,run_seconds=10,source_commit='fixture'))
                save('readout-v1/summary.json',{})
                pin=screen_module.sha(root/'plan.json'); primary=screen_module.sha(root/'readout-v1/summary.json')
                save('completion-closed.json',{summary_key:primary})
                for i in range(2):
                    save(f'episode-{i}/finished.json',dict(status='completed'))
                    save(f'episode-{i}/checkpoint/journal.jsonl',[],True)
                    save(f'episode-{i}/events.jsonl',[dict(event='operation_ready',kind='preview',operation=0,run=i,elapsed=0)],True)
                save('queue-0-0/state.json',dict(limit=1,queue=[],active=[],finished=['0:0','1:0']))
                actions=[(e,k) for k in ('0:0','1:0') for e in ('queued','admitted','released')]
                save('queue-0-0/events.jsonl',trace(1,actions),True)
                with patch.object(screen_module,'BASE',base):
                    result=screen_module.screen((job,'fixture',2,pin,primary))
                self.assertEqual(result['assigned'],2)
                self.assertEqual(result['aggregates'][0]['admissions'],2)
                self.assertEqual(result['aggregates'][0]['candidate_subset_choices'],0)


if __name__ == '__main__': unittest.main()
