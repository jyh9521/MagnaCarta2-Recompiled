import random,tempfile,unittest
from pathlib import Path
from tools.research.verify_conditional_tail import EXPECTED,TAIL,execute,rotate_mask,fixtures,harness,extract_body,verify_original,main
class ConditionalTailTests(unittest.TestCase):
    def regs(self):return [0xabcdef0000000000+i for i in range(32)]
    def test_full64_mask(self):
        self.assertEqual(rotate_mask(0xffffffff),0xffffffffdfffffff)
        self.assertEqual(rotate_mask(0x20000000),0x2000000000000000)
        self.assertEqual(rotate_mask(1),0x100000001)
    def test_null_write_before_return_and_exact_gprs(self):
        regs=self.regs();regs[3]=0xdeadbeef00002000;v=execute(EXPECTED,regs,15,1,0xffffffff,0);expected=list(regs);expected[3]=0;expected[9]=0xffffffffdfffffff;expected[10]=0xffffffff;expected[11]=regs[3]
        self.assertEqual(v['registers'],expected);self.assertEqual(v['cr6'],3);self.assertEqual(v['return_path'],'beqlr');self.assertIsNone(v['tail_target']);self.assertEqual(v['stores'],[{'address':0x2108,'value':0xdfffffff}]);self.assertLess(v['ordering'].index('store low32 r9 to object+108'),len(v['ordering'])-1)
    def test_nonnull_tail_full64_object_and_abi_preserved(self):
        regs=self.regs();regs[3]=0x12345678fffee000;v=execute(EXPECTED,regs,2,0,0x20000000,0xffffffff)
        self.assertEqual(v['registers'][3],0xffffffff);self.assertEqual(v['registers'][9],0x2000000000000000);self.assertEqual(v['registers'][11],regs[3]);self.assertEqual(v['tail_target'],TAIL);self.assertEqual(v['cr6'],4)
        for i in (1,4,5,6,7,8,12,31):self.assertEqual(v['registers'][i],regs[i])
        self.assertIn('LR',v['unchanged']);self.assertIn('CTR',v['unchanged'])
    def test_random_flags_oracle(self):
        rng=random.Random(1501)
        for _ in range(10000):
            flags=rng.getrandbits(32);member=rng.getrandbits(32);v=execute(EXPECTED,self.regs(),rng.randrange(16),rng.randrange(2),flags,member)
            self.assertEqual(v['registers'][9],(flags<<32)|(flags&0xdfffffff));self.assertEqual(v['stores'][0]['value'],flags&0xdfffffff);self.assertEqual(v['registers'][10],flags)
    def test_original_opcode_control_fields(self):
        c=int.from_bytes(EXPECTED[24:28],'big');self.assertEqual((c>>26,c>>21&31,c>>16&31,c>>1&1023,c&1),(19,12,26,16,0))
        b=int.from_bytes(EXPECTED[28:32],'big');self.assertEqual(b>>26,18);self.assertEqual(b&3,0)
    def test_bad_input(self):
        with self.assertRaises(ValueError):execute(EXPECTED[:-1],self.regs(),0,0,0,0)
        for x in (True,-1,1<<32):
            with self.assertRaises(ValueError):rotate_mask(x)
            with self.assertRaises(ValueError):execute(EXPECTED,self.regs(),0,0,0,x)
        with self.assertRaises(ValueError):execute(EXPECTED,[0]*31,0,0,0,0)
        with self.assertRaises(ValueError):execute(EXPECTED,[1<<64]*32,0,0,0,0)
        with self.assertRaises(ValueError):execute(EXPECTED,self.regs(),16,0,0,0)
        with self.assertRaises(ValueError):execute(EXPECTED,self.regs(),0,True,0,0)
    def test_image_guard(self):
        with self.assertRaisesRegex(ValueError,'unsupported original image hash'):verify_original(bytes(64))
    def test_matrix(self):
        rows=fixtures();self.assertEqual(len(rows),2560);self.assertEqual(sum(c['member']==0 for c in rows),512);self.assertEqual({c['cr6'] for c in rows},set(range(16)))
    def test_harness_boundary_contract(self):
        text=harness({'body':'BODY'},fixtures()[:1]);self.assertIn('External tail ABI observer ONLY',text);self.assertIn('std::memcmp(&boundary,&expected,sizeof(ctx))',text);self.assertIn('observed_flags==(uint32_t)c.r9',text);self.assertIn('std::memcmp(&ctx,&expected,sizeof(ctx))',text);self.assertIn('std::memcmp(before[i],base+pages[i],4096)',text);self.assertNotIn('#undef',text)
    def test_generated_shape_mapping(self):
        body='DEFINE_REX_FUNC(sub_826A9EC8) {\nREX_LOAD_U32(a);REX_LOAD_U32(b);REX_STORE_U32(a,b);if(x)return;sub_826C9920(ctx, base);return;\n}'
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            with self.assertRaisesRegex(ValueError,'expected one complete'):extract_body(p)
            (p/'one.cpp').write_text(body);(p/'mc2_probe_init.cpp').write_text('{0x826A9EC8, sub_826A9EC8}\n{0x826C9920, sub_826C9920}');(p/'mc2_probe_register.cpp').write_text('registrar->SetFunction(0x826A9EC8, sub_826A9EC8);\nregistrar->SetFunction(0x826C9920, sub_826C9920);');self.assertTrue(extract_body(p)['tail_mapped_but_not_executed'])
            (p/'mc2_probe_register.cpp').write_text('')
            with self.assertRaisesRegex(ValueError,'unique entry and mapped tail'):extract_body(p)
            (p/'one.cpp').write_text(body.replace('sub_826C9920(ctx, base);','REX_FATAL("bad");'))
            with self.assertRaisesRegex(ValueError,'unexpected conditional-tail'):extract_body(p)
    def test_half_toolchain(self):
        with self.assertRaisesRegex(ValueError,'all toolchain options'):main(['--xex','x','--loader-source','l','--output','o','--generated','g'])

if __name__=='__main__':unittest.main()
