import tempfile,unittest
from pathlib import Path
from tools.research.verify_indexed_tail import EXPECTED,ENTRY,CODE_BASE,execute,put32,exhaustive_matrix,fixtures,harness,extract_body,verify_original,main
class IndexedTailTests(unittest.TestCase):
    def fixture(self,count=2,selector=1):
        regs=[0xabcdef0000000000+i for i in range(32)];regs[3]=0x1234000000001000;regs[4]=0xfedcba9876540000|selector;memory={0x103c:count};put32(memory,0x1024,0x2000);put32(memory,0x2000+selector*8,0x3000);put32(memory,0x3000,0x4000);put32(memory,0x4010,0x822d0100);return regs,memory
    def test_all_65536_pairs(self):
        self.assertEqual(exhaustive_matrix(),{'count_values':256,'selector_values':256,'cases':65536,'valid':32640,'invalid':32896,'success':True})
    def test_invalid_raw64_and_early_arg_reorder(self):
        regs,mem=self.fixture(1,1);out=execute(EXPECTED,regs,15,1,mem,0xddddeeeeffffaaaa);expected=list(regs);expected[3]=0xffffffff80070057;expected[9]=regs[5];expected[5]=regs[6];expected[10]=1;expected[11]=1
        self.assertEqual(out['registers'],expected);self.assertEqual(out['cr6'],3);self.assertEqual(out['ctr'],0xddddeeeeffffaaaa);self.assertEqual(out['reads'],[{'address':0x103c,'size':1}]);self.assertEqual(out['stores'],[]);self.assertIsNone(out['tail_target'])
    def test_invalid_no_speculative_table_reads(self):
        regs,_=self.fixture(0,255);out=execute(EXPECTED,regs,0,0,{0x103c:0},5);self.assertEqual(out['path'],'invalid-return');self.assertEqual(out['cr6'],4)
    def test_valid_full_context_boundary(self):
        regs,mem=self.fixture(2,1);out=execute(EXPECTED,regs,0,1,mem,8);expected=list(regs);expected[3]=0x3000;expected[4]=regs[5];expected[5]=regs[6];expected[6]=regs[7];expected[9]=regs[5];expected[10]=0x822d0100;expected[11]=0x4000
        self.assertEqual(out['registers'],expected);self.assertEqual(out['ctr'],0x822d0100);self.assertEqual(out['cr6'],9);self.assertEqual(out['reads'],[{'address':a,'size':n} for a,n in ((0x103c,1),(0x1024,4),(0x2008,4),(0x3000,4),(0x4010,4))]);self.assertEqual(out['stores'],[])
    def test_low8_selector_masks_other_raw_bits(self):
        regs,mem=self.fixture(2,1)
        for r4 in (1,0xffffff01,0xffffffffffff0001,0x12345678abcdef01):
            regs[4]=r4;out=execute(EXPECTED,regs,15,0,mem,0);self.assertEqual(out['tail_target'],0x822d0100)
    def test_count255_selector255_invalid(self):
        regs,mem=self.fixture(255,255);v=execute(EXPECTED,regs,0,0,mem,0);self.assertEqual(v['path'],'invalid-return');self.assertEqual(v['registers'][3],0xffffffff80070057)
    def test_missing_memory_fails_closed(self):
        regs,mem=self.fixture();del mem[0x4010]
        with self.assertRaisesRegex(ValueError,'outside explicit fixture'):execute(EXPECTED,regs,0,0,mem,0)
    def test_input_type_guards(self):
        regs,mem=self.fixture()
        for bad in (EXPECTED[:-1],bytearray(EXPECTED)):
            with self.assertRaises(ValueError):execute(bad,regs,0,0,mem,0)
        for bad in (True,-1,1<<64):
            x=list(regs);x[4]=bad
            with self.assertRaises(ValueError):execute(EXPECTED,x,0,0,mem,0)
        with self.assertRaises(ValueError):execute(EXPECTED,regs,16,0,mem,0)
        with self.assertRaises(ValueError):execute(EXPECTED,regs,0,True,mem,0)
        with self.assertRaises(ValueError):execute(EXPECTED,regs,0,0,{0x103c:True},0)
        with self.assertRaises(ValueError):execute(EXPECTED,regs,0,0,mem,1<<64)
    def test_put32_guards(self):
        with self.assertRaises(ValueError):put32([],0,0)
        for a,v in ((0xffffffff,1),(True,1),(0,1<<32)):
            with self.assertRaises(ValueError):put32({},a,v)
    def test_original_hash_guard(self):
        with self.assertRaisesRegex(ValueError,'unsupported original image hash'):verify_original(bytes(100))
    def test_representative_matrix(self):
        rows=fixtures();self.assertEqual(len(rows),1008);self.assertEqual(sum(c['selector']<c['count'] for c in rows),432);self.assertEqual({c['cr6'] for c in rows},set(range(16)))
    def test_real_macro_mapped_boundary(self):
        text=harness({'body':'BODY'},fixtures()[:1]);self.assertNotIn('#undef',text);self.assertIn('REX_LOOKUP_FUNC(base,REX_CODE_BASE+i*0x100)=&Observe',text);self.assertIn('std::memcmp(&boundary,&expected,sizeof(ctx))',text);self.assertIn('std::memcmp(before[i],base+pages[i],4096)',text);self.assertIn('GetModuleFileNameW',text);self.assertIn('actual==csr',text)
    def test_shape_mapping_and_layout_guard(self):
        body='DEFINE_REX_FUNC(sub_82A3DEA0) {\nif (x)return;REX_CALL_INDIRECT_FUNC(x);return;\n}'
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            with self.assertRaisesRegex(ValueError,'expected one complete'):extract_body(p)
            (p/'one.cpp').write_text(body);(p/'mc2_probe_init.cpp').write_text('{0x82A3DEA0, sub_82A3DEA0}');(p/'mc2_probe_register.cpp').write_text('registrar->SetFunction(0x82A3DEA0, sub_82A3DEA0);');(p/'mc2_probe_pch.h').write_text('#define REX_CODE_BASE 0x822D0000ull\n#define REX_CODE_SIZE 0xBCE5A4ull\n#define REX_IMAGE_BASE 0x82000000ull\n#define REX_IMAGE_SIZE 0x1330000ull\n');self.assertIn('module_constants',extract_body(p))
            (p/'mc2_probe_pch.h').write_text('')
            with self.assertRaisesRegex(ValueError,'module constant'):extract_body(p)
            (p/'one.cpp').write_text(body.replace('if (x)return;','REX_STORE_U32(a,b);if (x)return;'))
            with self.assertRaisesRegex(ValueError,'unexpected indexed-tail'):extract_body(p)
    def test_half_toolchain(self):
        with self.assertRaisesRegex(ValueError,'all toolchain options'):main(['--xex','x','--loader-source','l','--output','o','--generated','g'])

if __name__=='__main__':unittest.main()
