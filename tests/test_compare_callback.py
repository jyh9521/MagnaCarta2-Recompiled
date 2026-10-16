import struct
import tempfile
from pathlib import Path
import unittest
from tools.research import verify_compare_callback as compare


def words(*values):return struct.pack('>'+str(len(values))+'I',*values)


class CompareCallbackTests(unittest.TestCase):
    def registers(self):return [0]*32

    def test_sign_and_unsigned_branch_displacements(self):
        self.assertEqual(compare.branch_target(0x1000,0x4BFFFFF0),0xFF0)
        self.assertEqual(compare.branch_target(0x1000,0x409A000C),0x100C)
        self.assertEqual(compare.branch_target(0x1000,0x48000022),0x20)
        with self.assertRaises(ValueError):compare.branch_target(0,0)

    def test_zero_extended_negative_result_and_carry(self):
        tail=words(0x7D685810,0x7D6B5910,0x556B003C,0x386B0001,0x4E800020)
        for first,second,result,ca in ((9,3,0xFFFFFFFF,0),(3,9,1,1)):
            registers=self.registers();registers[8]=first;registers[11]=second
            run=compare.execute(tail,registers,{})
            self.assertEqual(run['registers'][3],result)
            self.assertEqual(run['ca'],ca)
            self.assertLess(run['registers'][3],1<<32)

    def test_unsigned_compare_four_cr_bits(self):
        instruction=(31<<26)|(6<<23)|(8<<16)|(11<<11)|(32<<1)
        for a,b,expected in ((0xFFFF,1,(False,True,False)),(1,0xFFFF,(True,False,False)),(7,7,(False,False,True))):
            regs=self.registers();regs[8]=a;regs[11]=b
            result=compare.execute(words(instruction,0x4E800020),regs,{},initial_ca=1,initial_so=1)
            self.assertEqual(tuple(result['cr6'][key] for key in (24,25,26)),expected)
            self.assertTrue(result['cr6'][27]);self.assertEqual(result['ca'],1)

    def test_lwz_addi_and_mr(self):
        regs=self.registers();regs[3]=0x100
        # lwz r10,0(r3); mr r8,r10; addi r3,r8,1; blr.
        code=words(0x81430000,0x7D485378,0x38680001,0x4E800020)
        run=compare.execute(code,regs,{0x100:0xFFFFFFFF})
        self.assertEqual(run['registers'][8],0xFFFFFFFF)
        self.assertEqual(run['registers'][3],0x100000000)

    def test_cycle_rejected(self):
        regs=self.registers();regs[11]=0x100
        with self.assertRaisesRegex(ValueError,'cycle'):
            compare.execute(words(0x816B0004,0x4BFFFFFC),regs,{0x104:0x100})

    def test_out_of_fixture_and_invalid_word_rejected(self):
        for memory in ({},{0:True},{0:-1}):
            with self.assertRaisesRegex(ValueError,'read outside'):
                compare.execute(words(0x81630000,0x4E800020),self.registers(),memory)

    def test_unknown_store_and_linked_branch_rejected(self):
        for instruction in (0,0x60000000,0x90630000,0x48000005):
            with self.assertRaises(ValueError):compare.execute(words(instruction),self.registers(),{})

    def test_malformed_registers_code_and_branch_out_of_range(self):
        for code,regs in ((b'',self.registers()),(b'123',self.registers()),(words(0x4E800020),[0]*31),
                          (words(0x48000100),self.registers())):
            with self.assertRaises(ValueError):compare.execute(code,regs,{})

    def test_step_limit(self):
        with self.assertRaisesRegex(ValueError,'step limit'):
            compare.execute(words(0x38630001,0x4BFFFFFC),self.registers(),{},max_steps=5)

    def test_fixture_empty_lists_and_independent_maximum(self):
        empty=compare.fixture([],[]);self.assertEqual(empty['memory'][0x220],0);self.assertEqual(empty['expected_result'],0)
        s=lambda v:v<<13
        self.assertEqual(compare.fixture([s(5),s(65535)],[s(32768)])['expected_result'],0xFFFFFFFF)
        self.assertEqual(compare.fixture([0xE0001FFF],[0])['expected_result'],0)
        self.assertEqual(len(compare.cases()),14)

    def test_immutable_inputs(self):
        regs=self.registers();memory={0:123};before=list(regs)
        compare.execute(words(0x81630000,0x4E800020),regs,memory)
        self.assertEqual(regs,before);self.assertEqual(memory,{0:123})

    def test_tail_audit_marks_external_direct_reference_and_data(self):
        image=bytearray(160);image[16:20]=words(0x48000010);image[128:132]=words(32)
        sections=[{'name':'.text','start':16,'end':64,'flags':0x60000020},
                  {'name':'.rdata','start':128,'end':160,'flags':0x40000040}]
        report=compare.audit_tail(image,sections,target=32,base=0)
        self.assertEqual(report['direct_encoding_references'],[{'site':16,'link':False,'internal':False}])
        self.assertEqual(report['noncode_aligned_pointer_references'],[{'site':128,'section':'.rdata'}])
        self.assertTrue(report['independent_external_entry_observed'])

    def test_extract_rejects_store_and_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with self.assertRaises(ValueError):compare.extract_body(root)
            body='DEFINE_REX_FUNC(sub_82C1C1A0) {\nreturn;\n}'
            (root/'a.cpp').write_text(body);self.assertIn('body_sha256',compare.extract_body(root))
            (root/'b.cpp').write_text(body)
            with self.assertRaises(ValueError):compare.extract_body(root)
            (root/'b.cpp').unlink();(root/'a.cpp').write_text(body.replace('return;','REX_STORE_U32(0,0);'))
            with self.assertRaises(ValueError):compare.extract_body(root)

    def test_new_registration_required(self):
        with self.assertRaisesRegex(ValueError,'registration missing'):
            compare.verify_new_mapping('{ 0x82C1C214, old_tail },','loc_82C1C214:')

    def test_internal_tail_label_required_but_optional_alias_allowed(self):
        mapping='{ 0x82C1C1A0, complete }, { 0x82C1C214, alias },'
        with self.assertRaisesRegex(ValueError,'tail label missing'):
            compare.verify_new_mapping(mapping,'return;')
        result=compare.verify_new_mapping(mapping,'loc_82C1C214:')
        self.assertTrue(result['tail_present'])


if __name__=='__main__':unittest.main()
