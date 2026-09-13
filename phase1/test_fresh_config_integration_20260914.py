"""CPU-only test of the real Hydra/dataclass/factory path; never runs a container."""
import dataclasses
import inspect
import os
from pathlib import Path
import sys
import tempfile
import unittest

SOURCE=Path(os.environ['FORETS_CONFIG_TEST_SOURCE']).resolve(strict=True)
sys.path.insert(0,str(SOURCE/'src'))
os.environ['PYTHON_DOTENV_DISABLED']='1'
from hydra.utils import instantiate
from hydra import compose, initialize_config_dir
from omegaconf import OmegaConf
from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
from dojo.config_dataclasses.interpreter.fresh_container import FreshContainerInterpreterConfig
from dojo.config_dataclasses.interpreter.jupyter import JupyterInterpreterConfig
from dojo.core.interpreters.fresh_container import FreshContainerInterpreter
from dojo.core.interpreters.jupyter.jupyter_interpreter import JupyterInterpreterFactory
from dojo.utils.config import build


class Integration(unittest.TestCase):
    def test_source_and_default_unchanged(self):
        self.assertTrue(Path(inspect.getfile(FreshContainerInterpreter)).resolve().is_relative_to(SOURCE))
        self.assertIs(INTERPRETER_MAP['JupyterInterpreterConfig'],JupyterInterpreterFactory)
        self.assertIs(INTERPRETER_MAP['FreshContainerInterpreterConfig'],FreshContainerInterpreter)
        with initialize_config_dir(config_dir=str(SOURCE/'src/dojo/configs/interpreter'),version_base='1.3'):
            fresh=compose(config_name='fresh_container')
            prior=compose(config_name='jupyter')
        a=OmegaConf.to_container(fresh,resolve=False);b=OmegaConf.to_container(prior,resolve=False)
        a.pop('_target_');b.pop('_target_')
        self.assertEqual(a,b)

    def test_hydra_roundtrip_actual_factory(self):
        with tempfile.TemporaryDirectory() as tmp:
            public=Path(tmp)/'public';public.mkdir()
            options=dict(working_dir=str(Path(tmp)/'work'),timeout=30,
                superimage_directory='/research/d7/spc/yzyang4/aira-dojo/build/superimage',
                superimage_version='2026-07-macos-v1',container_runtime='singularity',
                env={'HF_HUB_OFFLINE':'1','NLTK_DATA':'/root/.nltk_data'})
            cfg=instantiate(OmegaConf.create(dict(_target_='dojo.config_dataclasses.interpreter.fresh_container.FreshContainerInterpreterConfig',**options)))
            cfg=OmegaConf.to_object(OmegaConf.structured(cfg));cfg.validate()
            self.assertIsInstance(cfg,FreshContainerInterpreterConfig)
            self.assertEqual(dataclasses.asdict(cfg),dataclasses.asdict(JupyterInterpreterConfig(**options)))
            interpreter=build(cfg,INTERPRETER_MAP,data_dir=public)
            self.assertIsInstance(interpreter,FreshContainerInterpreter)
            self.assertIsNone(interpreter.process)
            self.assertEqual(interpreter.data_dir,public.resolve())
            self.assertEqual(interpreter.env,options['env'])
            self.assertEqual(interpreter.timeout,30)
            interpreter.close()

    def test_unsupported_config_rejected(self):
        for runtime,timeout in (('apptainer',30),('singularity',0),('singularity',-1),('singularity',float('inf'))):
            cfg=FreshContainerInterpreterConfig(container_runtime=runtime,timeout=timeout,working_dir='/tmp/not-created')
            with self.assertRaises(ValueError):cfg.validate()

    def test_core_matches_verified_implementation(self):
        import ast
        def semantic(raw):
            tree=ast.parse(raw)
            if ast.get_docstring(tree):tree.body.pop(0)
            return ast.dump(tree,include_attributes=False)
        actual=Path(inspect.getfile(FreshContainerInterpreter)).read_text()
        verified=Path(__file__).with_name('forets_process_interpreter_20260914.py').read_text()
        self.assertEqual(semantic(actual),semantic(verified))


if __name__=='__main__':unittest.main()
