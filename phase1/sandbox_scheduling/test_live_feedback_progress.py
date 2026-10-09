import unittest
from live_feedback_progress import progress,recorded_roles


class ProgressTests(unittest.TestCase):
    def test_next_execution_requires_admission_and_a_new_return(self):
        events=[dict(event='generation_started',elapsed=12,call=1),
                dict(event='generation_returned',elapsed=15,call=1),
                dict(event='operation_ready',elapsed=20,kind='candidate',operation=1),
                dict(event='admitted',elapsed=30,operation=1)]
        rows=progress(events,[dict(valid=True,elapsed_seconds=10),dict(valid=False,elapsed_seconds=40)],50)
        self.assertEqual(rows[0]['generation_calls_before_next_operation'],1)
        self.assertTrue(rows[0]['subsequent_candidate_returned'])
        self.assertFalse(rows[0]['next_return_valid'])
        self.assertIsNone(rows[1]['next_candidate_operation_ready_seconds'])

    def test_preview_is_not_candidate_progress(self):
        rows=progress([dict(event='operation_ready',elapsed=20,kind='preview',operation=1)],
                      [dict(valid=True,elapsed_seconds=10)],50)
        self.assertIsNone(rows[0]['next_candidate_operation_ready_seconds'])

    def test_incomplete_generation_is_not_completed(self):
        rows=progress([dict(event='generation_started',elapsed=45,call=2)],
                      [dict(valid=True,elapsed_seconds=40)],50)
        self.assertEqual(rows[0]['completed_generation_calls_before_next_operation'],0)
        self.assertTrue(rows[0]['next_generation_started'])

    def test_no_drop_of_late_return_and_monotonic_validation(self):
        with self.assertRaises(ValueError):progress([],[dict(valid=True,elapsed_seconds=51)],50)
        with self.assertRaises(ValueError):progress([dict(event='x',elapsed=2),dict(event='x',elapsed=1)],[])

    def test_role_counts_do_not_use_cumulative_usage(self):
        node=dict(operators_used=['draft','analysis'],operators_metrics=[
            dict(usage=dict(attempt_id='a',prompt_tokens=10,completion_tokens=20,latency=2,cumulative_num_llm_calls=99)),{}])
        result=recorded_roles([node])
        self.assertEqual(result['draft']['calls'],1)
        self.assertEqual(result['analysis']['missing_usage'],1)
        with self.assertRaises(ValueError):recorded_roles([node,node])


if __name__=='__main__':unittest.main()
