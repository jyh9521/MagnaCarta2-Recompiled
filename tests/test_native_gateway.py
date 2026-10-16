import struct
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from tools.research import verify_native_gateway as gateway


def code():return struct.pack('>6I',0x3D608325,0x80640008,0x394B0980,0x812A0118,0x7D2903A6,0x4E800420)


class NativeGatewayTests(unittest.TestCase):
    def test_four_cases_exact_64bit_state_and_no_memory_change(self):
        for case in gateway.cases():
            before=dict(case['memory']);registers=list(case['registers'])
            result=gateway.execute(code(),registers,case['memory'],case['lr'])
            self.assertEqual(result['registers'][3],case['object_word'])
            self.assertEqual(result['registers'][9],case['target'])
            self.assertEqual(result['registers'][10],0xFFFFFFFF83250980)
            self.assertEqual(result['registers'][11],0xFFFFFFFF83250000)
            self.assertEqual(result['ctr'],case['target']);self.assertEqual(result['lr'],case['lr'])
            for index in set(range(32))-{3,9,10,11}:self.assertEqual(result['registers'][index],registers[index])
            self.assertEqual(result['memory'],before);self.assertEqual(case['memory'],before)
            self.assertEqual(case['registers'],registers)

    def test_null_external_target_is_only_recorded(self):
        case=gateway.cases()[0]
        self.assertEqual(gateway.execute(code(),case['registers'],case['memory'],case['lr'])['dispatch'],0)

    def test_high_frame_uses_low_32bit_address(self):
        case=gateway.cases()[-1];self.assertGreater(case['registers'][4],1<<32)
        self.assertEqual(gateway.execute(code(),case['registers'],case['memory'],7)['registers'][3],0x80000000)

    def test_missing_word_or_invalid_word_fails(self):
        case=gateway.cases()[0]
        for memory in ({},{0x2008:0},{0x2008:True,gateway.SELECTOR:1},{0x2008:0,gateway.SELECTOR:-1}):
            with self.assertRaisesRegex(ValueError,'outside'):
                gateway.execute(code(),case['registers'],memory,7)

    def test_each_instruction_is_template_guarded(self):
        for offset in range(0,24,4):
            changed=bytearray(code());changed[offset+3]^=1
            with self.assertRaisesRegex(ValueError,'unknown'):gateway.execute(changed,[0]*32,{},7)

    def test_invalid_code_and_register_count(self):
        for blob,registers in ((b'',[]),(code()[:-1],[0]*32),(code(),[0]*31)):
            with self.assertRaises(ValueError):gateway.execute(blob,registers,{},7)

    def test_original_range_hash_guard(self):
        with patch.object(gateway,'RANGES',{0x82000000:(4,'0'*64)}):
            with self.assertRaisesRegex(ValueError,'witness mismatch'):gateway.verify_original(bytes(8))

    def test_mapping_and_unique_body_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with self.assertRaises(ValueError):gateway.extract_body(root)
            body='DEFINE_REX_FUNC(sub_82509380) {\nREX_LOAD_U32(0); REX_LOAD_U32(0); REX_CALL_INDIRECT_FUNC(0);\n}'
            (root/'a.cpp').write_text(body);(root/'mc2_probe_init.cpp').write_text('')
            with self.assertRaisesRegex(ValueError,'mapping missing'):gateway.extract_body(root)
            (root/'mc2_probe_init.cpp').write_text('{ 0x82509380, sub_82509380 },')
            (root/'mc2_probe_register.cpp').write_text('registrar->SetFunction(0x82509380, sub_82509380);')
            self.assertIn('body_sha256',gateway.extract_body(root))
            (root/'b.cpp').write_text(body)
            with self.assertRaises(ValueError):gateway.extract_body(root)

    def test_fatal_store_or_call_shape_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for body in ('REX_FATAL();','REX_STORE_U32(0,0);','return;'):
                (root/'a.cpp').write_text('DEFINE_REX_FUNC(sub_82509380) {\n'+body+'\n}')
                with self.assertRaises(ValueError):gateway.extract_body(root)

    def test_harness_reserves_sparse_memory_only_records_external_call_and_cleans_up(self):
        text=gateway.harness('/* generated fixture */',code())
        self.assertIn('0x100000000ull,MEM_RESERVE,PAGE_NOACCESS',text)
        self.assertIn('MEM_COMMIT,PAGE_READWRITE',text)
        self.assertIn('pages[i]=guest_pages[i]+REX_PHYS_HOST_OFFSET(guest_pages[i])',text)
        self.assertIn('VirtualFree(base,0,MEM_RELEASE)',text)
        self.assertIn('#define REX_CALL_INDIRECT_FUNC(address) do { recorded=(address); }',text)
        self.assertNotIn('LoadXexImage',text)
        self.assertNotIn('REX_STORE_U32(0x83250D80',text)
        self.assertIn('page!=0x83250000u || i<0xB00',text)
        self.assertEqual(text.count('bool good='),4)

    def test_toolchain_bundle_required_before_inputs(self):
        with self.assertRaisesRegex(ValueError,'all toolchain'):
            gateway.main(['--xex','missing','--loader-source','missing','--mapping','missing','--output','missing','--generated','missing'])

    def test_registration_missing_duplicate_and_wrong_symbol_rejected(self):
        mapping='{ 0x82509380, sub_82509380 },';registered='registrar->SetFunction(0x82509380, sub_82509380);'
        self.assertEqual(gateway.verify_metadata(mapping,registered)['function_registration_count'],1)
        for bad in ('',registered*2,registered.replace('sub_82509380','wrong')):
            with self.assertRaisesRegex(ValueError,'function registration'):gateway.verify_metadata(mapping,bad)
        for bad in ('',mapping*2,mapping.replace('sub_82509380','wrong')):
            with self.assertRaisesRegex(ValueError,'image mapping'):gateway.verify_metadata(bad,registered)


if __name__=='__main__':unittest.main()
