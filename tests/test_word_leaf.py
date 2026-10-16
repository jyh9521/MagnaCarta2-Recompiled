import tempfile,unittest
from pathlib import Path
from tools.research.verify_word_leaf import EXPECTED,execute,verify_original,fixtures,harness,extract_body,assess_run,main
class WordLeafTests(unittest.TestCase):
    def regs(self):return [0xabcdef1234000000+i for i in range(32)]
    def test_be32_zeroextension(self):
        regs=self.regs();regs[3]=0xffffffff00001000;mem={0x1034:0x80,0x1035:0x12,0x1036:0x34,0x1037:0x56};v=execute(EXPECTED,regs,mem);expected=list(regs);expected[3]=0x80123456
        self.assertEqual(v['registers'],expected);self.assertEqual(v['effective_address'],0x1034);self.assertEqual(v['stores'],[]);self.assertEqual(regs[3],0xffffffff00001000);self.assertEqual(mem[0x1034],0x80)
    def test_wrap_to_zero(self):
        regs=self.regs();regs[3]=0x12345678ffffffcc;v=execute(EXPECTED,regs,{i:b for i,b in enumerate(bytes.fromhex('01020304'))});self.assertEqual(v['effective_address'],0);self.assertEqual(v['registers'][3],0x01020304)
    def test_last_word_before_boundary(self):
        regs=self.regs();regs[3]=0xaaaaaaaaffffffc8;v=execute(EXPECTED,regs,{0xfffffffc+i:255 for i in range(4)});self.assertEqual(v['effective_address'],0xfffffffc);self.assertEqual(v['registers'][3],0xffffffff)
    def test_upper_r3_ignored(self):
        for high in (0,0xffffffff,0x80000000,0xdeadbeef):
            regs=self.regs();regs[3]=high<<32|0x2000;v=execute(EXPECTED,regs,{0x2034+i:0xaa for i in range(4)});self.assertEqual(v['registers'][3],0xaaaaaaaa)
    def test_payload_edges_and_random(self):
        rows=fixtures();self.assertEqual(len(rows),1536);self.assertEqual({c['payload'] for c in rows if c['index']<24},{0,1})
        self.assertTrue(all(c['oracle']['registers'][3]==c['payload'] for c in rows));self.assertTrue(any(c['ea']==0 for c in rows));self.assertTrue(any(c['ea']==0xfffffffc for c in rows));self.assertTrue(any(c['ea']==0xe0000000 for c in rows))
    def test_no_other_gpr_or_memory_changes(self):
        for c in fixtures()[::17]:
            before=dict(c['memory']);v=execute(EXPECTED,c['registers'],c['memory']);self.assertEqual(before,c['memory'])
            for i in range(32):
                if i!=3:self.assertEqual(v['registers'][i],c['registers'][i])
            for name in ('LR','CTR','allFPR','FPSCR','vectors'):self.assertIn(name,v['unchanged'])
    def test_bad_types(self):
        regs=self.regs();regs[3]=0
        for bad in (EXPECTED[:-1],bytearray(EXPECTED)):
            with self.assertRaises(ValueError):execute(bad,regs,{})
        for bad in (-1,1<<64,True):
            x=list(regs);x[3]=bad
            with self.assertRaises(ValueError):execute(EXPECTED,x,{})
        with self.assertRaises(ValueError):execute(EXPECTED,[0]*31,{})
        with self.assertRaises(ValueError):execute(EXPECTED,regs,{0x34:True})
        with self.assertRaises(ValueError):execute(EXPECTED,regs,bytearray(64))
    def test_absent_and_unaligned_memory(self):
        regs=self.regs();regs[3]=0
        with self.assertRaisesRegex(ValueError,'aligned explicit fixture'):execute(EXPECTED,regs,{0x34:1})
        regs[3]=1
        with self.assertRaisesRegex(ValueError,'aligned explicit fixture'):execute(EXPECTED,regs,{0x35+i:0 for i in range(4)})
    def test_original_hash_guard(self):
        with self.assertRaisesRegex(ValueError,'unsupported original image hash'):verify_original(bytes(128))
    def test_harness_reserves_bias_page_and_full_context(self):
        text=harness({'body':'BODY'},fixtures());self.assertIn('reserve=0x100001000ull',text);self.assertIn('pages[8]',text);self.assertIn('pages[i]=uint64_t(guests[i])+expected_bias',text);self.assertIn('REX_PHYS_HOST_OFFSET(guests[i])!=expected_bias',text);self.assertIn('target[j]=(c.payload>>(24-j*8))&255',text);self.assertNotIn('REX_STORE_U32(',text);self.assertIn('std::memcmp(&ctx,&expected,sizeof(ctx))',text);self.assertIn('std::memcmp(before[i],base+pages[i],4096)',text);self.assertIn('0x7FF0000000000001ull',text);self.assertNotIn('#undef',text)
    def test_extract_unique_exact_body(self):
        body='DEFINE_REX_FUNC(sub_82B7CCD0) {\nREX_FUNC_PROLOGUE();\n// load\nctx.r3.u64 = REX_LOAD_U32(ctx.r3.u32 + 52);\nreturn;\n}'
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            with self.assertRaisesRegex(ValueError,'one complete'):extract_body(p)
            (p/'one.cpp').write_text(body);(p/'mc2_probe_init.cpp').write_text('{0x82B7CCD0, sub_82B7CCD0}');(p/'mc2_probe_register.cpp').write_text('registrar->SetFunction(0x82B7CCD0, sub_82B7CCD0);');(p/'mc2_probe_pch.h').write_text('#define REX_PHYS_HOST_OFFSET(addr) (((u32)(addr) >= 0xE0000000u) ? 0x1000u : 0u)\n#define REX_LOAD_U32(x) __builtin_bswap32(*(volatile u32*)(base + (u32)(x) + REX_PHYS_HOST_OFFSET(x)))\n');self.assertFalse(extract_body(p)['macro_replacements'])
            (p/'two.cpp').write_text(body)
            with self.assertRaisesRegex(ValueError,'one complete'):extract_body(p)
            (p/'two.cpp').unlink();(p/'one.cpp').write_text(body.replace('return;','ctx.r4.u64=0;return;'))
            with self.assertRaisesRegex(ValueError,'unexpected generated'):extract_body(p)
    def test_half_toolchain(self):
        with self.assertRaisesRegex(ValueError,'all toolchain options'):main(['--xex','x','--loader-source','l','--output','o','--generated','g'])
    def line(self,i=0):return f'WORD_CASE {i} raw3=0000000000002000 ea=00002034 payload=80000000 r3=0000000080000000 memory=1 context=1 mxcsr=1 success=1'
    def test_completion_requires_zero_exit_and_final_evidence(self):
        full=self.line()+'\nWORD_MEMORY pages=1 cases=1 released=1 failures=0\n';self.assertEqual(assess_run(full,'',0,1,1),{'completed_without_fault':True,'success':True})
        for text,stderr,status in ((self.line()+'\n','',0),(full,'',0xc0000005),(full,'fault',0),('','',0)):
            self.assertEqual(assess_run(text,stderr,status,1,1),{'completed_without_fault':False,'success':False})
    def test_completion_rejects_duplicate_malformed_or_wrong_value(self):
        duplicate=self.line()+'\n'+self.line()+'\nWORD_MEMORY pages=1 cases=2 released=1 failures=0\n';self.assertFalse(assess_run(duplicate,'',0,2,1)['success'])
        wrong=self.line().replace('r3=0000000080000000','r3=FFFFFFFF80000000')+'\nWORD_MEMORY pages=1 cases=1 released=1 failures=0\n';self.assertFalse(assess_run(wrong,'',0,1,1)['success'])

if __name__=='__main__':unittest.main()
