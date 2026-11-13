import tempfile
import unittest
from pathlib import Path
import batch as B


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent,prefix='recovery_test_')
        self.folder=Path(self.temp.name).resolve()
        assert self.folder.is_relative_to(B.ROOT)
        self.code='module check(output diff);assign diff=0;endmodule\n'
        self.q=[dict(args='-prove diff 0')]
        p=self.folder
        (p/'model.v').write_text(self.code)
        script=[f'read_verilog "{B.N.P0.wsl(p/"model.v")}"','hierarchy -top check','proc','flatten','opt_clean','log Q0000',
                f'sat -prove diff 0 -timeout 5 -show-inputs -show-outputs -dump_json "{B.N.P0.wsl(p/"0.model.json")}"']
        (p/'run.ys').write_text('\n'.join(script)+'\n')
        (p/'run.log').write_text('Q0000\nno model found: SUCCESS\n')
        (p/'0.query.log').write_text('-prove diff 0\nno model found: SUCCESS')
        self.oldrows=B.N.ROWS;B.N.ROWS=[]

    def tearDown(self):
        B.N.ROWS=self.oldrows
        self.temp.cleanup()

    def test_identical_completed_execution_is_recovered_without_solver(self):
        result=B.checked_run(self.folder,self.code,self.q)
        self.assertEqual(result[0]['status'],'proved')
        self.assertTrue(result[0]['recovered_from_immutable_log'])

    def test_changed_model_is_rejected(self):
        with self.assertRaises(AssertionError):B.checked_run(self.folder,self.code+'// changed',self.q)

    def test_changed_constraint_is_rejected(self):
        with self.assertRaises(AssertionError):B.checked_run(self.folder,self.code,[dict(args='-prove diff 1')])

    def test_query_log_cannot_disagree_with_batch_log(self):
        (self.folder/'0.query.log').write_text('-prove diff 0\nmodel found: FAIL')
        with self.assertRaises(AssertionError):B.checked_run(self.folder,self.code,self.q)


if __name__=='__main__':unittest.main()
