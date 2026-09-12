from pathlib import Path
import sys
from types import SimpleNamespace as NS
import subprocess
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from forets_parent_policy_patch_20260913 import patched_sources


class PatchTests(unittest.TestCase):
    def test_actual_frozen_source_compiles_without_mutating_repository(self):
        tree = '1ec18564f176d58a3a7ac3a46852ad92044777b5'
        def source(path):
            return subprocess.check_output(['git', 'show', tree+':'+path],
                cwd=Path(__file__).resolve().parents[2]).decode()
        patches = patched_sources(source('src/dojo/config_dataclasses/solver/fore_ts.py'),
            source('src/dojo/solvers/fore_ts/fore_ts.py'))
        self.assertEqual(len(patches), 3)
        for path, raw in patches.items(): compile(raw, path, 'exec')

    def test_preserves_leaf_default_and_validates_policy(self):
        cfg = '''class Config:
    common_start_protocol: str = "none"
    def validate(self):
        if self.common_start_protocol not in ("none", "rf_common_v1"):
            raise ValueError("common start protocol")
'''
        solver = '''class ForeTS(MCTS):
    def __init__(self):
        pass
'''
        sources = patched_sources(cfg, solver)
        namespace = {}
        exec(sources['src/dojo/config_dataclasses/solver/fore_ts.py'], namespace)
        config = namespace['Config']()
        self.assertEqual(config.parent_selection_policy, 'uct_leaf')
        config.validate()
        for value in ('uct_leaf', 'incumbent'):
            config.parent_selection_policy = value
            config.validate()
        config.parent_selection_policy = 'unknown'
        with self.assertRaises(ValueError): config.validate()
        sentinel = object()
        class MCTS:
            def search_policy(self, root): return sentinel
        namespace = {'MCTS': MCTS}
        exec(sources['src/dojo/solvers/fore_ts/fore_ts.py'], namespace)
        child = namespace['ForeTS']()
        child.cfg = NS(parent_selection_policy='uct_leaf')
        self.assertIs(child.search_policy(object()), sentinel)
        child.cfg.parent_selection_policy = 'unknown'
        with self.assertRaises(ValueError): child.search_policy(object())


if __name__ == '__main__': unittest.main()
