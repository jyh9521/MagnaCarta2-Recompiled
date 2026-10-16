"""Synthetic contract tests; real SDK/197-object link is a separate experiment."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from tools.research import link_module as lm
from tools.research.compile_module import digest, inventory


class HostLinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.gen=self.root/'generated'; self.gen.mkdir()
        self.build=self.root/'build'; (self.build/'objects').mkdir(parents=True)
        records=[]
        for i in range(197):
            name=f'unit{i}.cpp'; (self.gen/name).write_text('test',encoding='utf8')
            obj=self.build/'objects'/f'unit{i}.obj';obj.write_bytes(b'fixture')
            records.append(dict(source=name,object=str(obj.resolve()),object_size=7,object_sha256=digest(obj),success=True,exit_status=0))
        self.records=records
        self.report=dict(success=True,inputs_unchanged=True,records=records)
        self.inputs=dict(generated=inventory(self.gen))
        self.save()
    def save(self):
        (self.build/'module-build.json').write_text(json.dumps(self.report))
        (self.build/'inputs.json').write_text(json.dumps(self.inputs))
    def test_full197_inputs_retained(self):
        objects,_=lm.verified_objects(self.build,self.gen)
        command=lm.link_command('link.exe',self.root,objects,['host.obj'],self.root)
        self.assertEqual(len(objects),197)
        self.assertTrue(all(str(p) in command for p in objects))
        for flag in ('/OPT:NOREF','/OPT:NOICF','/INCREMENTAL:NO'):self.assertIn(flag,command)
        self.assertFalse(any('/FORCE' in x for x in command))
    def test_failed_build_rejected(self):
        self.report['success']=False;self.save()
        with self.assertRaisesRegex(ValueError,'complete'):lm.verified_objects(self.build,self.gen)
    def test_missing_object_record_rejected(self):
        self.report['records'].pop();self.save()
        with self.assertRaisesRegex(ValueError,'197'):lm.verified_objects(self.build,self.gen)
    def test_duplicate_source_rejected(self):
        self.records[1]['source']=self.records[0]['source'];self.save()
        with self.assertRaisesRegex(ValueError,'duplicate'):lm.verified_objects(self.build,self.gen)
    def test_outside_object_rejected(self):
        self.records[0]['object']=str(self.root/'outside.obj');self.save()
        with self.assertRaisesRegex(ValueError,'escapes'):lm.verified_objects(self.build,self.gen)
    def test_corrupt_object_rejected(self):
        Path(self.records[0]['object']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'identity'):lm.verified_objects(self.build,self.gen)
    def test_modified_generated_tree_rejected(self):
        (self.gen/'unit0.cpp').write_text('modified')
        with self.assertRaisesRegex(ValueError,'generated tree'):lm.verified_objects(self.build,self.gen)
    def test_failed_object_record_rejected(self):
        self.records[0]['exit_status']=1;self.save()
        with self.assertRaisesRegex(ValueError,'unsuccessful'):lm.verified_objects(self.build,self.gen)
    def test_source_set_mismatch_rejected(self):
        self.records[0]['source']='absent.cpp';self.save()
        with self.assertRaisesRegex(ValueError,'inventory'):lm.verified_objects(self.build,self.gen)
    def test_runtime_path_case_and_no_mutation(self):
        env={'Path':'original'}; out=lm.runtime_path(env,self.root)
        self.assertEqual(env,{'Path':'original'})
        self.assertEqual(out['Path'],str(self.root/'bin')+os.pathsep+'original')
        self.assertNotIn('PATH',out)
    def test_process_failure_preserved(self):
        def run(*args,**kwargs):
            kwargs['stdout'].write('real failure detail\n');return subprocess.CompletedProcess(args[0],9)
        with patch.object(lm.subprocess,'run',side_effect=run):record=lm.run_record(['fake'],self.root,'failure',{})
        self.assertEqual(record['exit_status'],9)
        self.assertEqual((self.root/'failure.txt').read_text(),'real failure detail\n')
        self.assertEqual(record['log_sha256'],digest(self.root/'failure.txt'))
        self.assertEqual(json.loads((self.root/'failure.json').read_text())['stdin'],'DEVNULL')
    def test_timeout_preserved(self):
        with patch.object(lm.subprocess,'run',side_effect=subprocess.TimeoutExpired(['fake'],1)):
            record=lm.run_record(['fake'],self.root,'timeout',{},1)
        self.assertEqual(record['exit_status'],124)
        self.assertIn('HOST_TIMEOUT',(self.root/'timeout.txt').read_text())
    def test_launch_failure_preserved(self):
        with patch.object(lm.subprocess,'run',side_effect=OSError('fixture launch failure')):
            record=lm.run_record(['fake'],self.root,'launch',{})
        self.assertEqual(record['exit_status'],127)
        self.assertIn('fixture launch failure',(self.root/'launch.txt').read_text())
    def test_supported_native_profile(self):
        lm.validate_native_profile({'tree_sha256':lm.NATIVE_GENERATED_TREE})
    def test_unknown_native_profile_rejected(self):
        for identity in ({}, {'tree_sha256':'unknown'}):
            with self.assertRaisesRegex(ValueError,'verified generated game profile'):
                lm.validate_native_profile(identity)
    def test_existing_log_not_overwritten(self):
        (self.root/'run.txt').write_text('keep')
        with self.assertRaises(FileExistsError):lm.run_record(['fake'],self.root,'run',{})
        self.assertEqual((self.root/'run.txt').read_text(),'keep')


if __name__=='__main__':unittest.main()
