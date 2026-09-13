import unittest
import hashlib
import json
from pathlib import Path
import tempfile
from analyze_scope_prefixes_20260914 import select_prefix,independent_records


class Tests(unittest.TestCase):
    def test_no_future_or_exact_deadline_delivery(self):
        rows=[(1,10,True,{'id':1}),(2,300_000_000_000,True,{'id':2}),(3,400_000_000_000,True,{'id':3})]
        self.assertEqual(select_prefix(rows,start_ns=0,seconds=300),{'id':1})
    def test_no_quality_based_selection(self):
        rows=[(1,10,True,{'score':.9}),(2,20,True,{'score':.1})]
        self.assertEqual(select_prefix(rows,start_ns=0,seconds=300),{'score':.1})
    def test_none_not_imputed(self):
        self.assertIsNone(select_prefix([],start_ns=0,seconds=300))
        self.assertIsNone(select_prefix([(1,10,False,{})],start_ns=0,seconds=300))
    def test_actual_frozen_reader_and_late_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)/'action-incumbents';directory.mkdir()
            code='print(1)';h=hashlib.sha256(code.encode()).hexdigest();nodes=[]
            for i,elapsed in enumerate((10,400,1200),1):
                node=dict(node_id=str(i),code_sha256=h,is_buggy=False,search_value=i,maximize=True)
                nodes.append(node)
                d=dict(protocol='original_search_visible_action_delivery_v1',schema=1,start_ns=0,
                    deadline_ns=1200*10**9,observation_ns=elapsed*10**9,action=i,observed_nodes=list(nodes),
                    node_id=str(i),code=code,submission=dict(code_sha256=h))
                raw=json.dumps(d).encode();name=f'action-{i:06d}.json';(directory/name).write_bytes(raw)
                c=dict(data_file=name,data_sha256=hashlib.sha256(raw).hexdigest(),deadline_ns=1200*10**9,
                    durable_ns=elapsed*10**9,eligible=elapsed<1200)
                (directory/f'action-{i:06d}.commit.json').write_text(json.dumps(c))
            records=independent_records(Path(temp),0)
            self.assertEqual(len(records),3)
            self.assertEqual(select_prefix(records,start_ns=0,seconds=300)['node_id'],'1')
            self.assertEqual(select_prefix(records,start_ns=0,seconds=1200)['node_id'],'2')


if __name__=='__main__':unittest.main()
