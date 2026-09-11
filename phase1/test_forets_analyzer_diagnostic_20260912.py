import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
from types import ModuleType, SimpleNamespace
import unittest

from forets_environment_build_20260912 import budget_source
from forets_analyzer_diagnostic_20260912 import fork_ledger, schema_failure


class DiagnosticTests(unittest.TestCase):
    def budget(self):
        module=ModuleType('fixture_budget')
        source=Path(__file__).with_name('forets_paid_budget_20260911.py').read_text()
        exec(compile(budget_source(source),'<budget fixture>','exec'),module.__dict__)
        return module

    def test_unknown_hold_preserved_old_scopes_closed_no_reset(self):
        budget=self.budget()
        with tempfile.TemporaryDirectory() as directory:
            parent=Path(directory)/'old.sqlite';child=Path(directory)/'new.sqlite'
            budget.initialize(parent,['a','b','c','d'])
            budget.reserve(parent,'a','unknown')
            before=budget.snapshot(parent);expected=budget.AUTH_SHA
            report=fork_ledger(parent,child,budget,expected_auth=expected)
            self.assertEqual(report['parent_unresolved'],1)
            self.assertEqual(budget.snapshot(child)['accounted_usd'],before['accounted_usd'])
            with closing(sqlite3.connect(parent)) as db:
                self.assertEqual(db.execute('SELECT stopped FROM auth').fetchone()[0],1)
                self.assertEqual(db.execute('SELECT state FROM calls WHERE id="unknown"').fetchone()[0],'unresolved')
            with self.assertRaises(budget.BudgetStopped):budget.reserve(child,'a','old-scope')
            budget.reserve(child,'fixture_success','new1')
            with self.assertRaises(budget.BudgetStopped):budget.reserve(child,'fixture_failure','new2')
            budget.settle(child,'new1',{'cost':'.001'})
            budget.reserve(child,'fixture_failure','new2')
            with self.assertRaises(FileExistsError):fork_ledger(parent,child,budget,expected_auth=expected)

    def test_wrong_parent_refused_without_sealing(self):
        budget=self.budget()
        with tempfile.TemporaryDirectory() as directory:
            parent=Path(directory)/'old.sqlite';child=Path(directory)/'new.sqlite'
            budget.initialize(parent,['a','b','c','d'])
            with self.assertRaises(ValueError):fork_ledger(parent,child,budget,expected_auth='wrong')
            self.assertFalse(budget.snapshot(parent)['stopped']);self.assertFalse(child.exists())

    def test_only_field_types_and_safe_schema_names_exported(self):
        exc=SimpleNamespace(validator='required',instance={'summary':'private text','unknown':'sensitive'},
            schema={'required':['summary','is_bug']},absolute_path=[],absolute_schema_path=['required'])
        report=schema_failure(exc)
        self.assertEqual(report['missing_required'],['is_bug'])
        self.assertEqual(report['object_field_types'],{'summary':'str'})
        self.assertNotIn('private',json.dumps(report));self.assertNotIn('sensitive',json.dumps(report))


if __name__=='__main__':unittest.main()
