import ast
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from forets_deployment_precheck import CUDA_CODE, validate_allocation_identity


class DeploymentCheckTests(unittest.TestCase):
    def setUp(self):
        self.environment = dict(SLURMD_NODENAME='gpu28', SLURM_JOB_ID='123',
                                SLURM_STEP_ID='0', CUDA_VISIBLE_DEVICES='1')

    def test_allowed_allocated_node(self):
        validate_allocation_identity(self.environment, 'gpu28')

    def test_wrong_or_old_node_rejected(self):
        for node in ('gpu27', 'projgpu39'):
            with self.assertRaises(RuntimeError):
                validate_allocation_identity(self.environment, node)

    def test_batch_or_missing_gpu_rejected(self):
        for change in ({'SLURM_STEP_ID':'batch'}, {'CUDA_VISIBLE_DEVICES':''}):
            with self.assertRaises(RuntimeError):
                validate_allocation_identity(dict(self.environment, **change), 'gpu28')

    def test_embedded_cuda_program_parses_without_execution(self):
        ast.parse(CUDA_CODE)


if __name__ == '__main__':
    unittest.main()
