import ast
import logging
from pathlib import Path
import sys
import tarfile
import types
import unittest
from unittest.mock import patch

PHASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PHASE))
import forets_selfhosted_guard_20260912 as guard


class LocalAuthTests(unittest.TestCase):
    def test_no_global_fallback_and_safe_errors(self):
        secret = 'synthetic-global-fixture'
        with self.assertRaises(ValueError) as exc:
            guard.selfhosted_key(guard.MODEL, 'http://127.0.0.1:8000/v1', {'PRIMARY_KEY': secret})
        self.assertNotIn(secret, str(exc.exception))

    def test_accepts_only_explicit_local_credential(self):
        env = {'PRIMARY_KEY': 'wrong-global-fixture', guard.VARIABLE: 'synthetic-local-fixture'}
        self.assertEqual(guard.selfhosted_key(guard.MODEL, 'http://localhost:8000/v1', env), env[guard.VARIABLE])
        for value in ('', ' ', 'value\n', 'sk-or-'+'synthetic-fixture'):
            with self.assertRaises(ValueError):
                guard.selfhosted_key(guard.MODEL, 'http://localhost:8000/v1', {guard.VARIABLE:value})

    def test_no_external_route_or_credential_in_url(self):
        for url in ('https://openrouter.ai/api/v1', 'http://gpu27:8000/v1',
                    'http://localhost:8000/v1?key=fixture', 'http://fixture@localhost:8000/v1',
                    'http://localhost:8001/v1', 'http://localhost:8000/v1#fragment',
                    'http://localhost:invalid/v1', 'http://localhost:8000/v1\n'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                guard.selfhosted_key(guard.MODEL, url, {guard.VARIABLE:'synthetic-local-fixture'})

    def test_actual_frozen_backend_constructor_and_paid_path_preserved(self):
        archive = PHASE/'releases/forets-parallel-source-20260912/source.tar'
        member = 'src/dojo/core/solvers/llm_helpers/backends/lite_llm.py'
        with tarfile.open(archive) as tar:
            source = tar.extractfile(member).read().decode()
        changed = guard.patch_backend(source)
        with self.assertRaises(ValueError):
            guard.patch_backend(changed)
        original_ast, changed_ast = ast.parse(source), ast.parse(changed)
        original_cls = next(n for n in original_ast.body if isinstance(n, ast.ClassDef) and n.name=='LiteLLMClient')
        cls = next(n for n in changed_ast.body if isinstance(n, ast.ClassDef) and n.name=='LiteLLMClient')
        init = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name=='__init__')
        # Every other class method stays byte-structure equivalent.
        for before, after in zip(original_cls.body, cls.body):
            if getattr(before, 'name', None) != '__init__':
                self.assertEqual(ast.dump(before), ast.dump(after))
        scope = {'os':types.SimpleNamespace(environ={}, getenv=lambda name, default='': scope['os'].environ.get(name, default)),
                 '__package__':'guard_fixture', 'logging':logging}
        exec(compile(ast.Module(body=[init], type_ignores=[]), member, 'exec'), scope)
        config = types.SimpleNamespace(model_id=guard.MODEL, base_url='http://localhost:8000/v1',
                                       provider='selfhosted', use_azure_client=False)
        module = types.ModuleType('guard_fixture.selfhosted_guard')
        module.selfhosted_key = guard.selfhosted_key
        with patch.dict(sys.modules, {'guard_fixture.selfhosted_guard':module}):
            target = types.SimpleNamespace()
            scope['os'].environ = {'PRIMARY_KEY':'synthetic-paid-fixture'}
            with self.assertRaises(ValueError):
                scope['__init__'](target, config)
            scope['os'].environ[guard.VARIABLE] = 'synthetic-local-fixture'
            scope['__init__'](target, config)
            self.assertEqual(target.api_key, 'synthetic-local-fixture')
            config.provider, config.model_id = 'alibaba', 'non-local-model'
            scope['__init__'](target, config)
            self.assertEqual(target.api_key, 'synthetic-paid-fixture')


if __name__ == '__main__':
    unittest.main()
