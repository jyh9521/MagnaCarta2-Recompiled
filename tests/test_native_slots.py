"""Redistribution-neutral table and provenance fixtures, standard library only."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from tools.research import reconcile_native_slots as native


def fixture():
    indices=[i for i in range(302) if i not in (1,0x52,0x61)]
    targets={i:0x82520000+4*i for i in range(302)}
    rows=[dict(initializer=0x822D0000+i*128,native_index=i,source_pointer_slot=0x83200000+i*4,
               implementation=targets[i],destination=native.GNATIVES+i*4,
               initialization_flag=0x8327B660,fallback=native.FALLBACK,table_entries=4096,
               duplicate_index_slot=0x83263F1C,instruction_sha256='a'*64,
               status='verified-instruction-template-not-executed') for i in indices]
    static=dict(schema_version=1,profile='MC2-name-lookup-static',image_sha256=native.IMAGE_SHA256,
                base=native.BASE,inputs_unchanged=True,indexed_initializers=rows,
                summary=dict(recovered_indexed_initializers=299,runtime_gnatives_address=native.GNATIVES))
    values=[targets.get(i,native.FALLBACK) for i in range(4096)]
    dump=struct.pack('>4096I',*values)
    log=f'TITLE_NATIVES guard=1 bound=4096 fallback=3794 int_const={values[0x1D]:08X} add={values[0x92]:08X}\n'.encode()
    report=dict(schema=1,image_loaded=True,guest_entrypoint_launched=True,inputs_unchanged=True,
                runtime_assets_unchanged=True,game_input_unchanged=True,exit_status=3221226505,
                image=dict(sha256=native.XEX_SHA256),natives=dict(guard=1,bound=4096,fallback=3794,int_const=values[0x1D],add=values[0x92]))
    report['title-natives.bin']=dict(size=len(dump),sha256=native.sha(dump))
    report['run.txt']=dict(size=len(log),sha256=native.sha(log))
    run=dict(exit_status=3221226505,log_sha256=native.sha(log),stdin='DEVNULL')
    return static,dump,report,run,log


class NativeSlotTests(unittest.TestCase):
    def setUp(self):self.args=list(fixture())
    def reconcile(self):return native.reconcile(*self.args)
    def test_historical_difference(self):
        r=self.reconcile()
        self.assertEqual(r['runtime_nonfallback_slots'],302)
        self.assertEqual([v['index'] for v in r['missing_old_indices']],[1,0x52,0x61])
        self.assertEqual(r['old_runtime_mismatches'],[])
        self.assertEqual(r['old_indices_not_active'],[])
        self.assertFalse(r['automatic_hints_written'])
    def test_optional_mapping_is_separate(self):
        target=0x82520004
        r=native.reconcile(*self.args,f'registrar->SetFunction(0x{target:08X}, sub_{target:08X});')
        self.assertTrue(r['missing_old_indices'][0]['mapped'])
        self.assertFalse(r['missing_old_indices'][1]['mapped'])
    def test_snapshot_mutation_rejected(self):
        self.args[1]=bytes(16384)
        with self.assertRaisesRegex(ValueError,'artifact identity'):self.reconcile()
    def test_snapshot_size_rejected(self):
        self.args[1]=self.args[1][:-1]
        with self.assertRaisesRegex(ValueError,'16384'):self.reconcile()
    def test_boolean_index_rejected(self):
        self.args[0]['indexed_initializers'][0]['native_index']=True
        with self.assertRaisesRegex(ValueError,'native index'):self.reconcile()
    def test_out_of_range_index_rejected(self):
        self.args[0]['indexed_initializers'][0]['native_index']=4096
        with self.assertRaisesRegex(ValueError,'native index'):self.reconcile()
    def test_duplicate_index_rejected(self):
        self.args[0]['indexed_initializers'][1]=deepcopy(self.args[0]['indexed_initializers'][0])
        with self.assertRaisesRegex(ValueError,'duplicate static'):self.reconcile()
    def test_destination_mismatch_rejected(self):
        self.args[0]['indexed_initializers'][0]['destination']+=4
        with self.assertRaisesRegex(ValueError,'profile fields'):self.reconcile()
    def test_wrong_static_profile_rejected(self):
        self.args[0]['image_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'identity'):self.reconcile()
    def test_wrong_static_count_rejected(self):
        self.args[0]['indexed_initializers'].pop()
        with self.assertRaisesRegex(ValueError,'299'):self.reconcile()
    def test_runtime_flag_rejected(self):
        self.args[2]['guest_entrypoint_launched']=False
        with self.assertRaisesRegex(ValueError,'provenance'):self.reconcile()
    def test_runtime_xex_rejected(self):
        self.args[2]['image']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'XEX identity'):self.reconcile()
    def test_run_exit_status_rejected(self):
        self.args[3]['exit_status']=0
        with self.assertRaisesRegex(ValueError,'process/log'):self.reconcile()
    def test_run_log_mutation_rejected(self):
        self.args[4]+=b'changed'
        with self.assertRaisesRegex(ValueError,'artifact identity'):self.reconcile()
    def test_table_address_outside_code_rejected(self):
        dump=bytearray(self.args[1]);struct.pack_into('>I',dump,0,0x83200000);self.args[1]=bytes(dump)
        self.args[2]['title-natives.bin']['sha256']=native.sha(dump)
        with self.assertRaisesRegex(ValueError,'executable sections'):self.reconcile()
    def test_native_summary_rejected(self):
        self.args[2]['natives']['fallback']=1
        with self.assertRaisesRegex(ValueError,'summary'):self.reconcile()
    def test_duplicate_json_fields_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fixture.json';path.write_text('{"x":1,"x":2}')
            with self.assertRaisesRegex(ValueError,'duplicate JSON'):native.read_json(path)
    def test_registration_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError,'registration template'):
            native.reconcile(*self.args,'registrar->SetFunction(0x82520004, sub_82520008);')


if __name__=='__main__':unittest.main()
