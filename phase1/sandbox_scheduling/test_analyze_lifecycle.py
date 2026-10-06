import unittest
import analyze_lifecycle as a
from lifecycle_pilot import schedule


def fixture():
    plan=dict(schedule=schedule())
    episodes=[]
    for row in schedule():
        completed=dict(**row,complete=True,error_type=None,fixture_sha256=a.FIXTURE_SHA,
            gpu_uuid='GPU-same',source_commit='a'*40,close_start_to_no_client_seconds=1.,
            exec_seconds=3.,elapsed_seconds=20.)
        phases=['before_container','after_fetch_before_close','window','window','window',
                'release_verified','after_close_no_clients']
        values=[4.,200.,200.,200.,200.,4.,4.]
        if row['arm']=='close_now':values[2:5]=[4.]*3
        samples=[dict(elapsed_seconds=i+1.,phase=phase,status='ok',uuid='GPU-same',
            scope='whole_device_not_candidate',data=dict(driver_version='same',metrics=dict(memory_used_mib=v)))
            for i,(phase,v) in enumerate(zip(phases,values))]
        episodes.append(dict(completed=completed,samples=samples))
    return dict(plan=plan,plan_sha256=a.PLAN_SHA,closed=dict(complete=True,planned=6,attempted=6,returncodes=[0]*6),
                job='16624',episodes=episodes,preflight=dict(task_image_sha256='b'*64))


class Tests(unittest.TestCase):
    def test_pairing_and_denominator(self):
        rows,result=a.analyze(fixture())
        self.assertEqual(len(rows),6)
        self.assertEqual([p['window_delta_mib'] for p in result['paired']],[196.]*3)
        self.assertEqual(result['groups']['keep_10s']['window_median_above_baseline_mib']['n'],3)
    def test_incomplete_not_dropped(self):
        b=fixture();b['episodes'].pop()
        with self.assertRaises(ValueError):a.analyze(b)
        b=fixture();b['episodes'][0]['completed']['complete']=False
        with self.assertRaises(ValueError):a.analyze(b)
    def test_missing_not_zero(self):
        b=fixture();b['episodes'][0]['samples'][0]['data']['metrics']['memory_used_mib']=None
        with self.assertRaises(ValueError):a.analyze(b)
    def test_identity_output_and_time(self):
        b=fixture();b['episodes'][0]['completed']['fixture_sha256']='c'*64
        with self.assertRaises(ValueError):a.analyze(b)
        b=fixture();b['episodes'][0]['samples'][0]['uuid']='GPU-other'
        with self.assertRaises(ValueError):a.analyze(b)
        b=fixture();b['episodes'][0]['samples'][1]['elapsed_seconds']=0
        with self.assertRaises(ValueError):a.analyze(b)


if __name__=='__main__':unittest.main(verbosity=2)
