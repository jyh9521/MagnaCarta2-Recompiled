import random,tempfile,unittest
from pathlib import Path
from tools.research.verify_bitfield_leaf import EXPECTED,execute,rotate_mask,fixtures,harness,extract_body,main,verify_original
class BitfieldOracleTests(unittest.TestCase):
    def regs(self):return [0xabcdef0000000000+i for i in range(32)]
    def test_all_relevant_bits_and_other_gprs(self):
        for bits in range(4):
            for so in range(2):
                original=self.regs();out=execute(EXPECTED,original,15,so,0xfffffcff|(bits<<8));expected=list(original);expected[3]=bits if bits&2 else (bits&1)*0x100000001;expected[10]=bits>>1;expected[11]=bits&1
                self.assertEqual(out['registers'],expected);self.assertEqual(original,self.regs());self.assertEqual(out['cr6'],(4 if bits&2 else 2)|so);self.assertEqual(out['return_path'],'bnelr' if bits&2 else 'blr');self.assertEqual(out['stores'],[])
    def test_powerpc64_wrapping_mask_regression(self):
        self.assertEqual(rotate_mask(1,0,31,29),0x100000001)
        out=execute(EXPECTED,self.regs(),0,0,0x100)
        self.assertEqual(out['registers'][3],0x100000001)
        self.assertNotEqual(out['registers'][3],1)
        self.assertEqual(out['registers'][3]&0xffffffff,1)
    def test_actual_bnelr_opcode_fields(self):
        word=int.from_bytes(EXPECTED[20:24],'big')
        self.assertEqual((word>>26,(word>>21)&31,(word>>16)&31,(word>>1)&1023,word&1),(19,4,26,16,0))
    def test_random_word_formula(self):
        rng=random.Random(1401)
        for _ in range(10000):
            word=rng.getrandbits(32);out=execute(EXPECTED,self.regs(),rng.randrange(16),rng.randrange(2),word)
            bits=word>>8&3;self.assertEqual(out['registers'][3],bits if bits&2 else (bits&1)*0x100000001);self.assertEqual(out['registers'][10],word>>9&1);self.assertEqual(out['registers'][11],word>>8&1)
    def test_wrapped_mask(self):
        self.assertEqual(rotate_mask(0xffffffff,0,31,29),0xfffffffffffffffd)
        self.assertEqual(rotate_mask(0x80000000,1,0,31),1)
        self.assertEqual(rotate_mask(1,0,0,31),1)
    def test_unknown_opcode_and_fields(self):
        for code in (b'',EXPECTED[:-1]+b'\x21',bytearray(EXPECTED)):
            with self.assertRaises(ValueError):execute(code,self.regs(),0,0,0)
        for field in (-1,16,True):
            with self.assertRaises(ValueError):execute(EXPECTED,self.regs(),field,0,0)
        for word in (-1,1<<32,False):
            with self.assertRaises(ValueError):execute(EXPECTED,self.regs(),0,0,word)
        with self.assertRaises(ValueError):execute(EXPECTED,[0]*31,0,0,0)
        with self.assertRaises(ValueError):execute(EXPECTED,[1<<64]*32,0,0,0)
        with self.assertRaises(ValueError):execute(EXPECTED,self.regs(),0,2,0)
    def test_rotate_guards(self):
        for args in ((1,32,0,31),(1,0,-1,31),(True,0,0,31)):
            with self.assertRaises(ValueError):rotate_mask(*args)
    def test_image_hash_guard(self):
        with self.assertRaisesRegex(ValueError,'unsupported original image hash'):verify_original(bytes(256))
    def test_fixture_matrix(self):
        rows=fixtures();self.assertEqual(len(rows),2048);self.assertEqual(sum(c['oracle']['return_path']=='bnelr' for c in rows),1024);self.assertEqual({c['cr6'] for c in rows},set(range(16)));self.assertEqual({c['so'] for c in rows},{0,1});self.assertEqual({c['guest'] for c in rows},{0x2000,0xfffee000})
        self.assertTrue(all(c['registers'][3]>>32 for c in rows))
    def test_real_memory_full_context_harness(self):
        text=harness({'body':'BODY'},fixtures()[:1]);self.assertNotIn('#undef',text);self.assertIn('std::memcmp(&ctx,&expected,sizeof(ctx))',text);self.assertIn('std::memcmp(before[i],base+pages[i],4096)',text);self.assertIn('ctx.fpscr.InitHost()',text);self.assertIn('expected.r10.u64',text)
    def test_shape_guards(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            with self.assertRaisesRegex(ValueError,'expected one complete'):extract_body(p)
            body='DEFINE_REX_FUNC(sub_82AC2810) {\nREX_LOAD_U32(x);if (x) return;\nreturn;\n}'
            (p/'one.cpp').write_text(body);(p/'mc2_probe_init.cpp').write_text('{0x82AC2810, sub_82AC2810}');(p/'mc2_probe_register.cpp').write_text('registrar->SetFunction(0x82AC2810, sub_82AC2810);');self.assertIn('body_sha256',extract_body(p))
            (p/'two.cpp').write_text(body)
            with self.assertRaisesRegex(ValueError,'expected one complete'):extract_body(p)
            (p/'two.cpp').unlink();(p/'one.cpp').write_text(body.replace('return;','REX_STORE_U32(a,b);return;',1))
            with self.assertRaisesRegex(ValueError,'unexpected dual-return'):extract_body(p)
    def test_partial_toolchain(self):
        with self.assertRaisesRegex(ValueError,'all toolchain options'):main(['--xex','x','--loader-source','l','--output','o','--generated','g'])

if __name__=='__main__':unittest.main()
