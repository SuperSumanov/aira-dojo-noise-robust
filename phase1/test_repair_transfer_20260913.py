import unittest
import prepare_repair_transfer_20260913 as m


class SelectionTest(unittest.TestCase):
    def example(self, rid, task='leaf-classification', code='x=1'):
        return dict(root='old', run_id=rid, task=task, parent_step=1, parent_code=code,
                    observed_successful_child_code='x=2', diff_sha256=m.sha(rid.encode()),
                    parent_families=['a'], error='TypeError foo', observed_diff='diff')

    def test_ast_ignores_comments_and_spacing(self):
        self.assertEqual(m.ast_key('x=1'), m.ast_key('# noise\nx = 1\n'))

    def test_block_whole_run_and_ast_alias(self):
        mem = self.example('source')
        rows = [dict(root='old',run_id=r,task='leaf-classification',step=1,exit_nonzero=True,message_families=[])
                for r in ('source','alias','new')]
        nodes = {('old',r['run_id'],1):dict(code=('x=1' if r['run_id']!='new' else 'y=3'),term_out='fail') for r in rows}
        got, available, _ = m.select_targets(rows,nodes,[mem])
        self.assertEqual([r['run_id'] for r in got], ['new'])
        self.assertEqual(available['leaf-classification'],1)

    def test_earliest_failure_not_best_later_node(self):
        rows = [dict(root='old',run_id='target',task='leaf-classification',step=s,exit_nonzero=True,message_families=[]) for s in (8,2)]
        nodes = {('old','target',s):dict(code=f'y={s}',term_out='fail') for s in (8,2)}
        got, _, _ = m.select_targets(rows,nodes,[self.example('source')])
        self.assertEqual(got[0]['step'],2)

    def test_retrieval_has_no_target_outcome(self):
        a,b = self.example('a'),self.example('b')
        b.update(parent_families=['b'],error='Other')
        target=dict(root='old',run_id='target',task='leaf-classification',code='z=4',error='TypeError foo',message_families=['a'])
        first=m.choose_memories(target,[a,b])
        target.update(final_score=999,child_score=-999)
        self.assertEqual(first,m.choose_memories(target,[a,b]))
        self.assertEqual(first[0]['run_id'],'a')

    def test_no_heldout_task_fallback(self):
        target=dict(root='old',run_id='target',task='spaceship-titanic',code='z=4',error='x',message_families=[])
        with self.assertRaises(ValueError): m.choose_memories(target,[self.example('a')])

    def test_secret_rejected_before_selection(self):
        row=dict(root='old',run_id='target',task='leaf-classification',step=1,exit_nonzero=True,message_families=[])
        node=dict(code='x='+repr('sk-'+'z'*18),term_out='fail')
        with self.assertRaises(ValueError):m.select_targets([row],{('old','target',1):node},[self.example('a')])

    def test_parser_rejects_truncation_and_wrong_tool(self):
        from run_repair_transfer_20260913 import parse_code
        import json
        raw=dict(choices=[dict(finish_reason='tool_calls',message=dict(tool_calls=[dict(function=dict(name='emit_repair',arguments=json.dumps(dict(code='x=1'))))]))])
        self.assertEqual(parse_code(raw),'x=1')
        raw['choices'][0]['finish_reason']='length'
        with self.assertRaises(ValueError):parse_code(raw)
        raw['choices'][0]['finish_reason']='tool_calls'
        raw['choices'][0]['message']['tool_calls'][0]['function']['name']='other'
        with self.assertRaises(ValueError):parse_code(raw)

    def test_unknown_not_success_and_full_denominator(self):
        from readout_repair_transfer_20260913 import summarize
        rows=[dict(case=i,task=m.TASKS[i//4],arm=a,repair_success=False,score=None) for i in range(8) for a in m.ARMS]
        for r in rows:
            if r['arm']=='retrieved_repair':r.update(repair_success=True,score=.5)
        self.assertTrue(summarize(rows)['development_expansion_gate'])
        rows[0]['repair_success']=None
        self.assertFalse(summarize(rows)['development_expansion_gate'])
        with self.assertRaises(ValueError):summarize(rows[:-1])


if __name__ == '__main__': unittest.main()
