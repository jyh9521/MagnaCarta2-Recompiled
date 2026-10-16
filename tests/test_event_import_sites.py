"""Synthetic PPC/import/registry contracts, no game or SDK inputs needed."""
import copy
import struct
import unittest
from tools.research import verify_event_import_sites as event


def bl(address,target,link=True):return 0x48000000|((target-address)&0x3FFFFFC)|int(link)
def words(*values):return struct.pack('>'+str(len(values))+'I',*values)
def registry():
    rows=event.scan_direct_calls(words(0x38600000,bl(0x1004,0x2000)),0x1000,{0x2000:'NtCreateEvent'},[(0x1000,0x1008)])
    return event.seal_registry(dict(schema_version=1,profile='MC2-original-event-import-direct-calls',image_sha256=event.IMAGE_SHA256,direct_calls=rows))


class EventImportSiteTests(unittest.TestCase):
    def test_direct_call_lr_and_pdata(self):
        row=registry()['direct_calls'][0]
        self.assertEqual((row['call'],row['caller_lr'],row['thunk']),(0x1004,0x1008,0x2000))
        self.assertEqual(row['function_boundary']['evidence'],'original-PDATA')
        self.assertEqual(row['context']['size'],8)
    def test_backward_and_absolute_branch(self):
        self.assertEqual(event.branch(0x2000,bl(0x2000,0x1000)),0x1000)
        self.assertEqual(event.branch(0x1000,0x48002003),0x2000)
    def test_nonlinked_branch_not_a_call(self):
        self.assertEqual(event.scan_direct_calls(words(bl(0x1000,0x2000,False)),0x1000,{0x2000:'NtCreateEvent'}),[])
    def test_nonbranch_not_a_call(self):
        self.assertIsNone(event.branch(0x1000,0x4E800020))
    def test_unknown_boundaries_not_invented(self):
        row=event.scan_direct_calls(words(bl(0x1000,0x2000)),0x1000,{0x2000:'NtCreateEvent'})[0]
        self.assertEqual(row['function_boundary'],{'evidence':'unknown-no-containing-PDATA'})
    def test_ambiguous_pdata_rejected(self):
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            event.scan_direct_calls(words(bl(0x1000,0x2000)),0x1000,{0x2000:'NtCreateEvent'},[(0x1000,0x1010),(0x1000,0x1020)])
    def test_alignment_and_overflow_rejected(self):
        for code,base in [(b'x',0x1000),(b'',0x1001),(bytes(8),0xFFFFFFFC),(b'',True)]:
            with self.assertRaises(ValueError):event.scan_direct_calls(code,base,{})
    def test_lr_matches_only_same_import(self):
        r=registry()
        self.assertEqual(event.match_caller_lr(r,'NtCreateEvent',0x1008)['status'],'validated-original-direct-call')
        self.assertEqual(event.match_caller_lr(r,'NtSetEvent',0x1008)['status'],'unresolved-indirect-or-unlisted')
    def test_unknown_lr_not_guessed_from_context(self):
        self.assertIsNone(event.match_caller_lr(registry(),'NtCreateEvent',0x1004)['matched'])
    def test_registry_mutation_rejected(self):
        r=registry();r['direct_calls'][0]['call']=0x1000
        with self.assertRaisesRegex(ValueError,'integrity'):event.match_caller_lr(r,'NtCreateEvent',0x1008)
    def test_invalid_lr_type_and_alignment(self):
        for value in (True,-4,0x1001,0x100000000):
            with self.assertRaisesRegex(ValueError,'LR'):event.match_caller_lr(registry(),'NtCreateEvent',value)
    def test_unknown_import_rejected(self):
        with self.assertRaisesRegex(ValueError,'import name'):event.match_caller_lr(registry(),'OtherEvent',0x1008)
    def test_registry_identity_rejected(self):
        r=registry();r['image_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'identity'):event.match_caller_lr(r,'NtCreateEvent',0x1008)
    def test_boolean_schema_rejected(self):
        r=registry();r['schema_version']=True
        with self.assertRaisesRegex(ValueError,'identity'):event.match_caller_lr(r,'NtCreateEvent',0x1008)
    def test_wrong_original_image_rejected(self):
        with self.assertRaisesRegex(ValueError,'image SHA'):event.build_registry(b'fixture',{},'')
    def test_wrong_sdk_rejected_before_parse(self):
        with self.assertRaisesRegex(ValueError,'SDK runtime SHA'):event.sdk_contracts(b'fixture')


class EventImportMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image=bytearray(max(address for ordinal,address in event.IMPORTS.values())-event.BASE+16)
        cls.register=''
        cls.addresses=[]
        for name,(ordinal,address) in event.IMPORTS.items():
            offset=address-event.BASE
            cls.image[offset:offset+16]=words(0x01010000|ordinal,0x02010000|ordinal,0x7D6903A6,0x4E800420)
            cls.register+=f'registrar->SetFunction(0x{address:08X}, __imp__{name});\n'
            cls.addresses.append(address)
        cls.metadata={'import_libraries':[{'name':'xboxkrnl.exe','import_record_addresses':cls.addresses}]}
    def test_exact_import_contract(self):
        rows=event.verify_imports(self.image,self.metadata,self.register)
        self.assertEqual(len(rows),8)
        self.assertEqual(rows[0]['ordinal'],0xD1)
        self.assertEqual(rows[0]['argument_registers']['r5'],'event_type_0_manual_1_auto_request')
    def test_wrong_thunk_bytes_rejected(self):
        image=bytearray(self.image);image[event.IMPORTS['NtCreateEvent'][1]-event.BASE]^=1
        with self.assertRaisesRegex(ValueError,'thunk bytes'):event.verify_imports(image,self.metadata,self.register)
    def test_duplicate_record_rejected(self):
        meta=copy.deepcopy(self.metadata);meta['import_libraries'][0]['import_record_addresses'].append(self.addresses[0])
        with self.assertRaisesRegex(ValueError,'duplicate original'):event.verify_imports(self.image,meta,self.register)
    def test_generated_name_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError,'name mismatch'):
            event.verify_imports(self.image,self.metadata,self.register.replace('__imp__NtCreateEvent','__imp__WrongEvent'))
    def test_wrong_import_library_rejected(self):
        meta=copy.deepcopy(self.metadata);meta['import_libraries'][0]['name']='xam.xex'
        with self.assertRaisesRegex(ValueError,'xboxkrnl'):event.verify_imports(self.image,meta,self.register)
    def test_nonobject_library_rejected(self):
        with self.assertRaisesRegex(ValueError,'library row'):event.verify_imports(self.image,{'import_libraries':[1]},self.register)


if __name__=='__main__':unittest.main()
