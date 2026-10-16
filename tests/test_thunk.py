import struct
import tempfile
from pathlib import Path
import unittest
from tools.research import verify_thunk as thunk


def code(offset=12):return struct.pack('>4I',0x81630000,0x814B0000|offset,0x7D4903A6,0x4E800420)


class ThunkTests(unittest.TestCase):
    def fixture(self):
        image=bytearray(128);image[28:32]=struct.pack('>I',0x4E800020);image[32:48]=code()
        image[64:68]=struct.pack('>I',32)
        sections=[{'name':'.text','start':16,'end':64,'flags':0x60000020},
                  {'name':'.rdata','start':64,'end':128,'flags':0x40000040}]
        return image,sections

    def test_exact_oracle_dispatch_only_and_memory_unchanged(self):
        memory={0x100:0x200,0x20C:0xFFFFFFFF};before=dict(memory)
        result=thunk.execute_thunk(code(),0x100,memory,0x1122334455667788)
        self.assertEqual(result,dict(r10=0xFFFFFFFF,r11=0x200,ctr=0xFFFFFFFF,
                         lr=0x1122334455667788,dispatch=0xFFFFFFFF,memory=before))
        self.assertEqual(memory,before)

    def test_null_dispatch_is_recorded_not_executed(self):
        self.assertEqual(thunk.execute_thunk(code(),0x100,{0x100:0x200,0x20C:0},7)['dispatch'],0)

    def test_missing_memory_and_invalid_word_rejected(self):
        for memory in ({},{0x100:0x200},{0x100:-1},{0x100:True}):
            with self.assertRaises(ValueError):thunk.execute_thunk(code(),0x100,memory,7)

    def test_register_and_instruction_template_guard(self):
        original=code()
        for offset in (0,4,8,12):
            damaged=bytearray(original);damaged[offset]^=1
            with self.assertRaises(ValueError):thunk.thunk_offset(damaged)
        for blob in (original[:-1],code(1),code(0xFFFC)):
            with self.assertRaises(ValueError):thunk.thunk_offset(blob)

    def test_aligned_slots_including_zero(self):
        for offset in (0,4,12,0x7FFC):self.assertEqual(thunk.thunk_offset(code(offset)),offset)

    def test_candidate_requires_pattern_code_boundary_readonly_reference_and_missing_mapping(self):
        image,sections=self.fixture();result=thunk.scan_candidates(image,sections,[],set(),base=0)
        self.assertEqual(len(result),1);self.assertEqual(result[0]['address'],32)
        self.assertEqual(result[0]['readonly_pointer_references'],[64])
        self.assertIn('not executed',result[0]['status'])

    def test_existing_mapping_not_candidate(self):
        image,sections=self.fixture();self.assertEqual(thunk.scan_candidates(image,sections,[],{32},base=0),[])

    def test_writable_data_ref_or_exception_metadata_ref_not_sufficient(self):
        image,sections=self.fixture()
        for name,flags in (('.data',0xC0000040),('.pdata',0x40000040)):
            sections[1].update(name=name,flags=flags)
            self.assertEqual(thunk.scan_candidates(image,sections,[],set(),base=0),[])

    def test_nonterminal_predecessor_not_boundary(self):
        image,sections=self.fixture();image[28:32]=struct.pack('>I',0x60000000)
        self.assertEqual(thunk.scan_candidates(image,sections,[],set(),base=0),[])
        # A true exception entry is another accepted independent boundary.
        self.assertEqual(len(thunk.scan_candidates(image,sections,[(32,16)],set(),base=0)),1)

    def test_inside_another_pdata_range_rejected(self):
        image,sections=self.fixture()
        self.assertEqual(thunk.scan_candidates(image,sections,[(16,48)],set(),base=0),[])

    def test_noncode_pattern_not_candidate(self):
        image,sections=self.fixture();sections[0]['flags']=0x40000040
        self.assertEqual(thunk.scan_candidates(image,sections,[],set(),base=0),[])

    def test_terminal_helper_does_not_accept_linked_branch(self):
        for word in (0x4E800020,0x4E800420,0x48000010):self.assertTrue(thunk.terminal(word))
        for word in (0x48000011,0x4E800421,0x60000000):self.assertFalse(thunk.terminal(word))

    def test_generated_body_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with self.assertRaises(ValueError):thunk.extract_body(root)
            body='DEFINE_REX_FUNC(sub_823C2740) {\nREX_LOAD_U32(1); REX_LOAD_U32(2); REX_CALL_INDIRECT_FUNC(3);\n}'
            (root/'a.cpp').write_text(body);self.assertIn('body_sha256',thunk.extract_body(root))
            (root/'b.cpp').write_text(body)
            with self.assertRaises(ValueError):thunk.extract_body(root)
            (root/'b.cpp').unlink();(root/'a.cpp').write_text(body+'\n')
            (root/'a.cpp').write_text(body.replace('REX_CALL_INDIRECT_FUNC','REX_FATAL'))
            with self.assertRaises(ValueError):thunk.extract_body(root)

    def test_harness_records_dispatch_and_never_calls_external_target(self):
        text=thunk.harness('/* generated fixture */',code())
        self.assertIn('#undef REX_CALL_INDIRECT_FUNC',text)
        self.assertIn('recorded=(address)',text)
        self.assertNotIn('reinterpret_cast',text)
        self.assertEqual(text.count('bool good='),4)

    def test_invalid_pe_input_rejected(self):
        with self.assertRaises(ValueError):thunk.sections_and_pdata(bytes(64))


if __name__=='__main__':unittest.main()
