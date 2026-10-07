"""CPU-only tests; no SLURM, GPU, remote inputs, or candidate execution."""
import csv
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, mock_open
import io

import throughput_pilot as p


class QualificationTests(unittest.TestCase):
    def test_complete_denominator(self):
        rows=p.schedule()
        self.assertEqual(len(rows),36)
        self.assertEqual([r['index'] for r in rows],list(range(36)))
        for repeat in range(3):
            for arm in ('serial','share2'):
                self.assertEqual(sorted(r['program'] for r in rows if r['repeat']==repeat and r['arm']==arm),list(range(6)))

    def test_same_fifo_and_seed(self):
        rows=p.schedule()
        for repeat in range(3):
            a=[[r['program'] for r in rows if r['repeat']==repeat and r['arm']==arm] for arm in ('serial','share2')]
            self.assertEqual(a[0],a[1])
        self.assertEqual({r['seed'] for r in rows},{p.SEED})
        self.assertEqual([rows[i]['arm'] for i in range(0,36,6)],['serial','share2','share2','serial','serial','share2'])

    def test_fixed_sources(self):
        self.assertEqual(len(p.SOURCES),6)
        self.assertEqual(len({r[2] for r in p.SOURCES}),6)
        self.assertEqual(len({r[1] for r in p.SOURCES}),3)
        self.assertEqual(sum(r[3] is None for r in p.SOURCES),3)
        for row in p.SOURCES:self.assertRegex(row[2],r'^[0-9a-f]{64}$')

    def test_fixtures_compile(self):
        compile(p.WARMUP,'warmup','exec');compile(p.GPU_RECEIPT,'receipt','exec')
        p.code_safe(b'import numpy as np\nx=np.ones(3)\n')
        with self.assertRaises(ValueError):p.code_safe(b'x="https://example.org"')

    def test_output_contract(self):
        query=Path('test.csv');out=Path('submission.csv')
        def readers(value):
            return [io.StringIO(value),io.StringIO('Id,x\n1,0\n2,0\n')]
        with patch.object(Path,'open',side_effect=readers('Id,p\n1,0.2\n2,0.7\n')),patch.object(p,'sha',return_value='fixture'):
            self.assertEqual(p.output_structure(out,query)['rows'],2)
        for bad in ('Id,p\n1,nan\n2,0.7\n','Id,p\n2,0.2\n1,0.7\n','Id,p\n1,0.2\n'):
            with patch.object(Path,'open',side_effect=readers(bad)),patch.object(p,'sha',return_value='fixture'):
                with self.assertRaises(ValueError):p.output_structure(out,query)


if __name__=='__main__':unittest.main()
