import ast,inspect,os,subprocess,types,unittest
from pathlib import Path
import factory_integration_v2_20261011 as d

def guard():
    if os.environ.get('R14_SERVER_SOURCE'):
        source=Path(os.environ['R14_SERVER_SOURCE']).read_text()
    else:
        source=subprocess.check_output(['git','show','f7ccd79323112b10ccc82d8e9ec9d6cf089df607:src/dojo/core/interpreters/jupyter/singularity_jupyter_server.py']).decode()
    node=next(x for x in ast.parse(source).body if isinstance(x,ast.FunctionDef) and x.name=='_build_container_environment')
    import re
    scope=dict(Mapping=dict,os=os,_CONTAINER_HOME=Path('/workspace/.home'),_JUPYTER_RUNTIME_DIR=Path('/workspace/runtime'),_PYTHON_USER_BASE=Path('/workspace/.local'),_ENV_NAME_PATTERN=re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$'))
    exec(compile(ast.Module(body=[node],type_ignores=[]),'exact-f7-environment-guard','exec'),scope)
    return scope['_build_container_environment']

class Tests(unittest.TestCase):
    def test_original_guard_rejects_conflicting_representation(self):
        with self.assertRaisesRegex(ValueError,'cannot override launcher-assigned CUDA_VISIBLE_DEVICES'):
            guard()({'CUDA_VISIBLE_DEVICES':'GPU-unit-test'},{'CUDA_VISIBLE_DEVICES':'0'})
    def test_same_verified_uuid_keeps_original_guard(self):
        self.assertEqual(guard()({'CUDA_VISIBLE_DEVICES':'GPU-unit-test'},{'CUDA_VISIBLE_DEVICES':'GPU-unit-test'})['CUDA_VISIBLE_DEVICES'],'GPU-unit-test')
    def test_one_device_check_precedes_normalization(self):
        value=d.fixed_run(inspect.getsource(d.old.run))
        self.assertLess(value.index('gpu_uuids(1)'),value.index("os.environ['CUDA_VISIBLE_DEVICES']=device"))
        self.assertIn('traceback.extract_tb(exc.__traceback__)',value)
        self.assertIn('timeout=450',value)
        with self.assertRaises(AssertionError):d.fixed_run(value)

if __name__=='__main__':unittest.main()
