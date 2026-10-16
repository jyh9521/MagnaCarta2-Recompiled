import random
import struct
import unittest
import tempfile
from pathlib import Path
from tools.research.verify_float_leaf import extract_body,differential_fixtures,harness,main,fp_flags
from unittest.mock import patch
from tools.research.verify_float_leaf import widen32,narrow64,simulate_leaf,verify_original,uint

class FloatLeafTests(unittest.TestCase):
    def test_exact_known_vectors(self):
        pairs={0:0,0x80000000:0x8000000000000000,1:0x36a0000000000000,0x007fffff:0x380fffffc0000000,0x00800000:0x3810000000000000,0x3f800000:0x3ff0000000000000,0x7f7fffff:0x47efffffe0000000,0x7f800000:0x7ff0000000000000,0xff800000:0xfff0000000000000}
        for word,bits in pairs.items():
            with self.subTest(word=hex(word)):self.assertEqual(widen32(word),bits);self.assertEqual(narrow64(bits),word)
    def test_all_classes_random_roundtrip(self):
        rng=random.Random(1301)
        words=[rng.getrandbits(32) for _ in range(20000)]+[s|e<<23|f for s in (0,0x80000000) for e in (0,1,126,127,254,255) for f in (0,1,0x3fffff,0x400000,0x7fffff)]
        for word in words:
            self.assertEqual(narrow64(widen32(word)),word)
            expected=word|0x400000 if word&0x7f800000==0x7f800000 and word&0x7fffff else word
            self.assertEqual(narrow64(widen32(word,'quiet'),'quiet'),expected)
    def test_finite_against_host_struct(self):
        rng=random.Random(1302)
        for _ in range(5000):
            word=rng.getrandbits(32)
            if word&0x7f800000==0x7f800000:continue
            value=struct.unpack('>f',word.to_bytes(4,'big'))[0]
            self.assertEqual(widen32(word),int.from_bytes(struct.pack('>d',value),'big'))
    def test_narrow_host_finite(self):
        rng=random.Random(1303)
        for _ in range(5000):
            word=rng.getrandbits(64)
            if word>>52&2047==2047:continue
            value=struct.unpack('>d',word.to_bytes(8,'big'))[0]
            try:expected=int.from_bytes(struct.pack('>f',value),'big')
            except OverflowError:expected=(word>>63)<<31|0x7f800000
            self.assertEqual(narrow64(word),expected)
    def test_round_ties(self):
        self.assertEqual(narrow64(0x3ff0000010000000),0x3f800000)
        self.assertEqual(narrow64(0x3ff0000030000000),0x3f800002)
        self.assertEqual(narrow64(0x3690000000000000),0)
        self.assertEqual(narrow64(0x3690000000000001),1)
    def test_nan_policies(self):
        for word in (0x7f800001,0x7fbfffff,0xff812345,0x7fc00000):
            self.assertEqual(narrow64(widen32(word)),word)
            self.assertEqual(narrow64(widen32(word,'quiet'),'quiet'),word|0x400000)
        self.assertEqual(narrow64(0x7ff0000000000001),0x7f800001)
        self.assertEqual(narrow64(0x7ff0000000000001,'quiet'),0x7fc00001)
    def fixture(self,a=0x3f800000,b=0x40000000):
        memory=bytearray(128);memory[0x30:0x34]=a.to_bytes(4,'big');memory[0x34:0x38]=b.to_bytes(4,'big');return bytes(memory)
    def test_order_and_final_fpr(self):
        original=self.fixture();v=simulate_leaf(original,0,64,68)
        self.assertEqual(v['memory'][64:72],original[0x30:0x38]);self.assertEqual(v['fpr0_bits'],widen32(0x40000000));self.assertEqual(original,self.fixture())
    def test_first_write_aliases_second_source(self):
        v=simulate_leaf(self.fixture(),0,0x34,68)
        self.assertEqual(v['memory'][68:72],bytes.fromhex('3f800000'));self.assertEqual(v['fpr0_bits'],widen32(0x3f800000))
    def test_same_destination_last_write_wins(self):
        v=simulate_leaf(self.fixture(),0,64,64)
        self.assertEqual(v['memory'][64:68],bytes.fromhex('40000000'))
    def test_output_alias_source_first_after_read(self):
        v=simulate_leaf(self.fixture(),0,0x30,0x30)
        self.assertEqual(v['memory'][0x30:0x34],bytes.fromhex('40000000'))
    def test_signed_nan_alias_policy(self):
        v=simulate_leaf(self.fixture(0xff800001,0),0,0x34,68,'quiet')
        self.assertEqual(v['memory'][68:72],bytes.fromhex('ffc00001'));self.assertEqual(v['fpr0_bits'],0xfff8000020000000)
    def test_guards(self):
        for value in (-1,1<<32,True,'1',None):
            with self.assertRaises(ValueError):widen32(value)
        for value in (-1,1<<64,False,'1'):
            with self.assertRaises(ValueError):narrow64(value)
        with self.assertRaises(ValueError):widen32(0,'host')
        for args in ((0,1,68),(0,-4,68),(0,124,128),(True,64,68),(0,True,68)):
            with self.assertRaises(ValueError):simulate_leaf(self.fixture(),*args)
        with self.assertRaises(ValueError):simulate_leaf(bytearray(128),0,64,68)
    def test_original_hash_guard(self):
        with self.assertRaisesRegex(ValueError,'unsupported original image hash'):verify_original(bytes(256))

class GeneratedContractTests(unittest.TestCase):
    def test_missing_and_wrong_body(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            with self.assertRaisesRegex(ValueError,'expected one complete'):extract_body(p)
            (p/'one.cpp').write_text('DEFINE_REX_FUNC(sub_82AC1DE8) {\nREX_FATAL("bad");\n}')
            with self.assertRaisesRegex(ValueError,'unexpected generated'):extract_body(p)
    def test_mapping_and_duplicate_body(self):
        body='DEFINE_REX_FUNC(sub_82AC1DE8) {\nPPCRegister f0;\nREX_LOAD_U32(a);REX_LOAD_U32(b);REX_STORE_U32(a,b);REX_STORE_U32(a,b);\n}'
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'one.cpp').write_text(body)
            (p/'mc2_probe_init.cpp').write_text('{0x82AC1DE8, sub_82AC1DE8}')
            (p/'mc2_probe_register.cpp').write_text('registrar->SetFunction(0x82AC1DE8, sub_82AC1DE8);')
            v=extract_body(p);self.assertTrue(v['f0_local'])
            (p/'two.cpp').write_text(body)
            with self.assertRaisesRegex(ValueError,'expected one complete'):extract_body(p)
            (p/'two.cpp').unlink();(p/'mc2_probe_register.cpp').write_text('')
            with self.assertRaisesRegex(ValueError,'one-to-one'):extract_body(p)
    def test_matrix_and_real_macros(self):
        fixtures=differential_fixtures();self.assertEqual(len(fixtures),768)
        text=harness({'body':'BODY','f0_local':False},fixtures[:1])
        self.assertIn('ctx.fpscr.InitHost()',text);self.assertIn('std::memcmp(&ctx,&expected_ctx,sizeof(ctx))',text)
        self.assertNotIn('#undef',text);self.assertIn('MEM_RESERVE',text);self.assertIn('expected_ctx.f0.u64',text)
        text=harness({'body':'BODY','f0_local':True},fixtures[:1]);self.assertNotIn('expected_ctx.f0.u64',text)
    def test_float_compilation_flags(self):
        self.assertEqual(fp_flags(),['/Od'])
        self.assertEqual(fp_flags('O2',True),['/O2','/fp:strict'])
        self.assertEqual(fp_flags('O2',False),['/O2'])
        with self.assertRaises(ValueError):fp_flags('fast',False)
        with self.assertRaises(ValueError):fp_flags('Od',1)
    def test_cli_separates_title_and_generated_evidence(self):
        import io,json,contextlib
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);x=p/'sample.xex';x.write_bytes(b'fixture');loader=p/'loader';loader.write_bytes(b'fixture');out=p/'out.json'
            with patch('tools.research.verify_branch_ranges.image_from_xex',return_value=b''),patch('tools.research.verify_float_leaf.verify_original',return_value={'synthetic':True}),contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(main(['--xex',str(x),'--loader-source',str(loader),'--output',str(out)]),0)
            v=json.loads(out.read_text());self.assertEqual(v['title_runtime_execution'],'NOT-TESTED');self.assertEqual(v['generated_execution'],'not-requested');self.assertIn('generated_run=not-requested',stdout.getvalue())
    def test_partial_toolchain(self):
        with self.assertRaisesRegex(ValueError,'all toolchain options'):main(['--xex','input','--loader-source','source','--output','output','--generated','tree'])

if __name__=='__main__':unittest.main()
