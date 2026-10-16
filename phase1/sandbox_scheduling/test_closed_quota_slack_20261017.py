import unittest
from closed_quota_slack_20261017 import measure,segments,summarize

class SlackTests(unittest.TestCase):
    def test_cut_inside_interval(self):
        s=dict(seconds=100,spare=1,blocked=[dict(slack_at_start=350,role='improve')])
        self.assertEqual(measure(s,300),dict(wall=50,permits=50,requests=50))
    def test_two_deadlines_one_slot(self):
        s=dict(seconds=100,spare=1,blocked=[dict(slack_at_start=30),dict(slack_at_start=80)])
        self.assertEqual(measure(s,0),dict(wall=80,permits=80,requests=110))
        s['spare']=2;self.assertEqual(measure(s,0)['permits'],110)
    def test_expired_and_empty(self):
        self.assertEqual(measure(dict(seconds=50,spare=2,blocked=[]),300)['wall'],0)
        self.assertEqual(measure(dict(seconds=50,spare=2,blocked=[dict(slack_at_start=-1)]),0)['wall'],0)
    def test_closed_stream(self):
        ev=[]
        for i in range(3):
            ev.append(dict(event='queued',time=i,request=dict(key=str(i),run=i,task=0,role='improve')))
            if i<2:ev.append(dict(event='admitted',time=i,key=str(i)))
        ev += [dict(event='released',time=10,key='0'),dict(event='admitted',time=10,key='2'),
               dict(event='released',time=20,key='1'),dict(event='released',time=30,key='2')]
        s=segments(ev,{i:100 for i in range(3)},0,40)
        self.assertEqual(sum(x['seconds'] for x in s),8)
        self.assertEqual(summarize(s)[1]['wall'],8)
        self.assertEqual(summarize(s)[2]['wall'],0)
        with self.assertRaises(AssertionError):segments(ev[:-1],{i:100 for i in range(3)},0,40)

if __name__=='__main__':unittest.main()
