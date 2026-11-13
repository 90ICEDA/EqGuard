"""Offline regression tests; fixtures retained, no SAT or graph/model loading."""
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import k4_runtime as R

sys.path.insert(0, str(R.ROOT/'phase2/ys'))
from sat_boundary_semantics import parse_query_results

FIXTURES = R.fresh_dir(Path(__file__).parent/'repair_tests', 'run')


def plan(path, views):
    p = dict(views=views)
    p['plan_sha'] = hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest()
    R.write_new(path, p)


class RepairTests(unittest.TestCase):
    def fixture(self):
        return R.fresh_dir(FIXTURES, 'case')

    def batch(self, folder, complete=True):
        code = 'module check; endmodule\n'
        script = 'read_verilog "' + str(folder/'model.v') + '"\nlog SATQ000000\nsat\n'
        (folder/'model.v').write_text(code, newline='\n')
        # Legacy Windows scripts contain CRLF, but script_sha hashes logical LF.
        (folder/'run.ys').write_bytes(script.replace('\n', '\r\n').encode())
        log = 'SATQ000000\n' + ('SAT proof finished - no model found: SUCCESS!\n' if complete else '')
        (folder/'run.log').write_text(log)
        saved = dict(model_sha=R.sha(folder/'model.v'),
                     script_sha=hashlib.sha256(script.encode()).hexdigest(),
                     log_sha=R.sha(folder/'run.log'),source_sha='src',raw_sha='raw',
                     queries=[dict(status='proved')],tables={})
        return code, script, saved

    def test_legacy_crlf_success_is_reused(self):
        f=self.fixture();code,script,saved=self.batch(f)
        R.write_new(f/'results.json',saved)
        found=R.find_bound_batch(f,code,script,'src','raw',1,parse_query_results)
        self.assertEqual(found[0],f)
        self.assertEqual(found[1],saved)

    def test_complete_orphan_log_can_be_recovered_without_solver(self):
        f=self.fixture();code,script,_=self.batch(f)
        before=R.sha(f/'run.log')
        found=R.find_bound_batch(f,code,script,'src','raw',1,parse_query_results)
        self.assertIsNone(found[1]);self.assertEqual(found[2],['proved'])
        self.assertEqual(R.sha(f/'run.log'),before)
        self.assertFalse((f/'results.json').exists())

    def test_incomplete_failure_retained_and_new_attempt_unique(self):
        f=self.fixture();code,script,_=self.batch(f,False)
        before=R.sha(f/'run.log')
        self.assertIsNone(R.find_bound_batch(f,code,script,'src','raw',1,parse_query_results))
        a=R.fresh_dir(f);b=R.fresh_dir(f)
        self.assertNotEqual(a,b);self.assertEqual(R.sha(f/'run.log'),before)

    def test_wrong_source_or_model_cannot_reuse(self):
        f=self.fixture();code,script,saved=self.batch(f);R.write_new(f/'results.json',saved)
        self.assertIsNone(R.find_bound_batch(f,code,script,'changed','raw',1,parse_query_results))
        self.assertIsNone(R.find_bound_batch(f,code+'x',script,'src','raw',1,parse_query_results))

    def test_missing_or_duplicate_markers_fail_closed(self):
        for log in ['no model found: SUCCESS',
                    'SATQ000000\nno model found: SUCCESS\nSATQ000000\nno model found: SUCCESS',
                    'SATQ000000\nERROR: x']:
            with self.assertRaises(ValueError):R.complete_statuses(log,1,parse_query_results)

    def test_successful_sat_with_trailing_wsl_warning_is_not_recomputed(self):
        log='SATQ000000\nno model found: SUCCESS\nEnd of script.\nw\x00s\x00l\x00: network notice'
        self.assertEqual(R.complete_statuses(log,1,parse_query_results),['proved'])

    def test_attempt_directory_script_binding_is_reusable(self):
        f=self.fixture();a=R.fresh_dir(f)
        wsl=lambda p:'/mnt/'+str(p).replace('\\','/')[0].lower()+str(p).replace('\\','/')[2:]
        code='module check; endmodule\n'
        script=f'read_verilog "{wsl(f)}/model.v"\nlog SATQ000000\nsat\n'
        actual=script.replace(wsl(f),wsl(a))
        (a/'model.v').write_text(code,newline='\n')
        (a/'run.ys').write_text(actual,newline='\n')
        (a/'run.log').write_text('SATQ000000\nno model found: SUCCESS\n')
        found=R.find_bound_batch(f,code,script,'src','raw',1,parse_query_results)
        self.assertEqual(found[0],a)

    def test_prepare_small_views_once_and_worker_streams_names(self):
        f=self.fixture();views=[dict(view='a'),dict(view='b')]
        plan(f/'plan.json',views)
        for item in views:
            d=f/'views'/item['view'];d.mkdir(parents=True);plan(d/'plan.json',[item])
        np.savez_compressed(f/'base_inputs.npz',global_ids=np.array([0,1,3,4]),
            view_index=np.array([0,0,1,1]),x=np.arange(12).reshape(4,3),
            edge_index=np.array([[0,2],[1,3]]))
        R.prepare_inputs(f)
        before={str(p):R.sha(p) for p in f.rglob('*') if p.is_file()}
        R.prepare_inputs(f)
        self.assertTrue(all(R.sha(p)==h for p,h in before.items()))
        names=f/'names.txt';names.write_text('n0\nn1\nn2\nn3\nn4\n')
        ids,by,local,selected=R.load_view_inputs(f/'views/b',f,names)
        np.testing.assert_array_equal(ids,[3,4]);self.assertEqual(selected,{3:'n3',4:'n4'})
        with np.load(f/'views/b/base_inputs.npz') as z:
            np.testing.assert_array_equal(z['edge_index'],[[0],[1]])
            np.testing.assert_array_equal(z['x'],np.arange(12).reshape(4,3)[[2,3]])

    def test_coverage_marker_alone_never_counts_as_complete(self):
        f=self.fixture();plan(f/'plan.json',[dict(view='a',source='missing',source_sha='bad')])
        R.write_new(f/'coverage.json',{})
        self.assertFalse(R.validate_complete(f)[0])

    def test_legacy_edge_transpose_is_repaired_without_touching_original(self):
        f=self.fixture();item=dict(view='a');plan(f/'plan.json',[item])
        folder=f/'views/a';folder.mkdir(parents=True);plan(folder/'plan.json',[item])
        original=folder/'base_inputs.npz'
        data=dict(global_ids=np.array([0,1,2]),x=np.zeros((3,39)),view_index=np.zeros(3,int))
        edges=np.array([[0,1,2],[1,2,0]])
        np.savez_compressed(f/'base_inputs.npz',**data,edge_index=edges)
        np.savez_compressed(original,**data,edge_index=edges.T)
        before=R.sha(original);R.prepare_inputs(f)
        self.assertEqual(R.sha(original),before)
        self.assertNotEqual(R.view_base_path(folder),original)
        with np.load(R.view_base_path(folder)) as z:
            np.testing.assert_array_equal(z['edge_index'],edges)
        normalized=R.sha(R.view_base_path(folder));R.prepare_inputs(f)
        self.assertEqual(R.sha(R.view_base_path(folder)),normalized)

    def test_fast_dependency_index_retains_cycle_rejection(self):
        m=dict(cells={'c':dict(type='OR2X1',connections={'IN1':[4],'IN2':[3],'Q':[4]})})
        with self.assertRaises(ValueError):R.dependency_index_fast(m)

    def test_os_lock_releases_without_deleting_file(self):
        f=self.fixture()/'lock'
        with R.exclusive_lock(f):
            with self.assertRaises(RuntimeError):
                with R.exclusive_lock(f):pass
        with R.exclusive_lock(f):pass
        self.assertTrue(f.exists())

    def test_failed_wsl_preserves_raw_log_and_return_code(self):
        f=self.fixture()
        class Failed:
            pid=123
            def __init__(self,*args,**kwargs):kwargs['stdout'].write(b'WSL failure\x00')
            def wait(self,timeout=None):return 42
        with patch.object(R.subprocess,'Popen',Failed):
            with self.assertRaises(RuntimeError):R.checked_yosys('test\n',f/'run.log')
        self.assertEqual((f/'run.log').read_bytes(),b'WSL failure\x00')
        self.assertEqual(json.loads((f/'run.execution.json').read_text())['rc'],42)

    def test_extractor_resumes_same_batch_without_additional_solver_call(self):
        import extract_k4_alltrain as E
        f=self.fixture();source=f/'synthetic.v';source.write_text('synthetic fixture')
        item=dict(view='fixture',source=str(source.relative_to(R.ROOT)),
                  source_sha=R.sha(source),split='train',family='fixture')
        plan(f/'plan.json',[item])
        raw=f/'raw';raw.mkdir();(raw/'raw.json').write_text('{}')
        m=dict(ports={'A':dict(direction='input',bits=[2]),
                      'B':dict(direction='input',bits=[3])},
               cells={'c':dict(type='OR2X1',connections={'IN1':[2],'IN2':[3],'Q':[4]})})
        np.savez_compressed(f/'base_inputs.npz',global_ids=[0],x=np.zeros((1,39)),
                            edge_index=np.empty((2,0),int),view_index=[0])
        calls=[]
        def fake_solver(script,log,timeout):
            calls.append(str(log));log.with_suffix('.ys').write_text(script,newline='\n')
            lines=[];qid=None
            for line in script.splitlines():
                if line.startswith('log SATQ'):qid=line[4:]
                if line.startswith('sat '):
                    pat=re.search(r"pattern 4'b([01]+)",line)[1]
                    prove=int(re.search(r'-prove target\[0\] ([01])',line)[1])
                    truth=int(pat[-2:]!='00')
                    lines += [qid,'no model found: SUCCESS' if truth==prove else 'model found: FAIL']
            text='\n'.join(lines)+'\n';log.write_text(text);return text
        with patch.object(E,'T',f),patch.object(E,'raw_snapshot',return_value=(m,raw)),\
             patch.object(E,'load_view_inputs',return_value=(np.array([0]),{0:'fixture'},{0:0},{0:'c'})),\
             patch.object(E,'checked_yosys',side_effect=fake_solver):
            E.main()
            outputs={str(p):R.sha(p) for p in (f/'queries').rglob('*') if p.is_file()}
            E.main()
        self.assertEqual(len(calls),1)
        self.assertTrue(all(R.sha(p)==h for p,h in outputs.items()))
        self.assertEqual(json.loads((f/'coverage.json').read_text())['actual_sat_queries'],8)
        self.assertTrue(np.load(f/'real.npy')[0,18])


if __name__=='__main__':unittest.main(verbosity=2)
