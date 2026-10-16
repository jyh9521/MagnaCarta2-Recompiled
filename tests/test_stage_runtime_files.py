import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from tools.research.stage_runtime_files import stage, member_path, plan


class RuntimeStagingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.iso=self.root/'fixture.iso';self.iso.write_bytes(b'headPAYLOADtail')
        self.inventory=self.root/'inventory.json';self.output=self.root/'game-root'
        self.data={'schema_version':1,'errors':[],'files':[{'path':'fixture.iso','offset':0,'size':15,'type':'xdvdfs',
                             'sha256':hashlib.sha256(self.iso.read_bytes()).hexdigest()},
                            {'path':'fixture.iso::Game/TOC.txt','offset':4,'size':7,
                             'sha256':hashlib.sha256(b'PAYLOAD').hexdigest()}]}
        self.write_manifest()

    def write_manifest(self):self.inventory.write_text(json.dumps(self.data),encoding='utf-8')

    def run_stage(self,**kwargs):
        return stage(self.iso,self.inventory,self.output,['Game/TOC.txt'],**kwargs)

    def test_copy_renaming_and_reopen(self):
        before=self.iso.read_bytes();result=self.run_stage(renames={'Game/TOC.txt':'MC2Game/Xbox360TOC.txt'})
        self.assertEqual(result['status'],'verified')
        self.assertEqual((self.output/'MC2Game/Xbox360TOC.txt').read_bytes(),b'PAYLOAD')
        self.assertEqual(self.iso.read_bytes(),before)
        self.assertEqual(json.loads((self.output/'.staging.json').read_text())['status'],'verified')

    def test_existing_directory_rejected_without_changes(self):
        self.output.mkdir();(self.output/'sentinel').write_text('original')
        with self.assertRaisesRegex(ValueError,'already exists'):self.run_stage()
        self.assertEqual((self.output/'sentinel').read_text(),'original')

    def test_source_alias_rejected(self):
        with self.assertRaises(ValueError):stage(self.iso,self.inventory,self.iso,['Game/TOC.txt'])
        self.assertEqual(self.iso.read_bytes(),b'headPAYLOADtail')

    def test_iso_mismatch_leaves_failure_record(self):
        self.data['files'][0]['sha256']='0'*64;self.write_manifest()
        with self.assertRaisesRegex(ValueError,'ISO hash mismatch'):self.run_stage()
        report=json.loads((self.output/'.staging.json').read_text())
        self.assertEqual(report['status'],'failed');self.assertFalse((self.output/'Game').exists())

    def test_member_mismatch_leaves_partial_and_failure_record(self):
        self.data['files'][1]['sha256']='0'*64;self.write_manifest()
        with self.assertRaisesRegex(ValueError,'member hash mismatch'):self.run_stage()
        report=json.loads((self.output/'.staging.json').read_text())
        self.assertEqual(report['status'],'failed');self.assertEqual((self.output/'Game/TOC.txt').read_bytes(),b'PAYLOAD')

    def test_escape_and_windows_names(self):
        for path in ('/a','a//b','../a','a/./b','C:/a','a\\b','NUL.txt','com1','LPT9.log',
                     'a.','a ','a/<b>','a/\x00b','a:b','a|b','a?b','a*b',''):
            with self.subTest(path=path),self.assertRaises(ValueError):member_path(path)

    def test_invalid_member_ranges(self):
        for offset,size in ((-1,1),(0,-1),(12,9),(True,1),(0,1.1)):
            self.data['files'][1].update(offset=offset,size=size)
            with self.assertRaises(ValueError):plan(self.data,self.iso,['Game/TOC.txt'],{})

    def test_selection_required_and_duplicate_rejected(self):
        for names in ([],['missing'],['Game/TOC.txt']*2):
            with self.assertRaises(ValueError):plan(self.data,self.iso,names,{})

    def test_rename_collision_record_reserved_and_parent_collision(self):
        second=dict(self.data['files'][1],path='fixture.iso::Other')
        self.data['files'].append(second)
        for renames in ({'Game/TOC.txt':'.staging.json'},
                        {'Game/TOC.txt':'file','Other':'FILE'},
                        {'Game/TOC.txt':'dir','Other':'dir/a'}):
            with self.assertRaises(ValueError):plan(self.data,self.iso,['Game/TOC.txt','Other'],renames)

    def test_rename_unselected_rejected(self):
        with self.assertRaises(ValueError):self.run_stage(renames={'Other':'dest'})

    def test_duplicate_inventory_rejected(self):
        self.data['files'].append(self.data['files'][1].copy())
        with self.assertRaises(ValueError):plan(self.data,self.iso,['Game/TOC.txt'],{})

    def test_inventory_schema_rejected_before_directory_creation(self):
        for schema in (None,99,True,'1'):
            with self.subTest(schema=schema):
                self.data['schema_version']=schema;self.write_manifest()
                with self.assertRaisesRegex(ValueError,'incomplete inventory'):self.run_stage()
                self.assertFalse(self.output.exists())

    def test_inventory_errors_rejected_before_directory_creation(self):
        for errors in (None,['failed traversal'],{},''):
            with self.subTest(errors=errors):
                self.data['errors']=errors;self.write_manifest()
                with self.assertRaisesRegex(ValueError,'incomplete inventory'):self.run_stage()
                self.assertFalse(self.output.exists())

    def test_inventory_envelope_and_rows_rejected(self):
        for data in ([],None,{'schema_version':1,'errors':[],'files':{}},
                     {'schema_version':1,'errors':[],'files':[None]},
                     {'schema_version':1,'errors':[],'files':[{'path':23}]},
                     {'schema_version':1,'errors':[],'files':[{}]}):
            with self.subTest(data=data),self.assertRaises(ValueError):
                plan(data,self.iso,['Game/TOC.txt'],{})

    def test_output_is_independent_regular_file(self):
        self.run_stage();p=self.output/'Game/TOC.txt'
        self.assertEqual(p.stat().st_nlink,1)
        self.assertFalse(p.samefile(self.iso))

    def test_hard_link_input_rejected(self):
        alias=self.root/'alias.iso';os.link(self.iso,alias)
        with self.assertRaisesRegex(ValueError,'regular non-link'):
            stage(alias,self.inventory,self.output,['Game/TOC.txt'])
        self.assertFalse(self.output.exists())

    def test_symlink_parent_rejected(self):
        link=self.root/'link'
        try:link.symlink_to(self.root,target_is_directory=True)
        except OSError:self.skipTest('symlink creation not supported by host')
        with self.assertRaisesRegex(ValueError,'linked output ancestor'):
            stage(self.iso,self.inventory,link/'out',['Game/TOC.txt'])


if __name__=='__main__':unittest.main()
