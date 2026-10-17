import hashlib,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tools.research import verify_byte_flag_leaf as v


class ByteFlagLeafTests(unittest.TestCase):
    def regs(self):return [0xabcdef1234000000+i for i in range(32)]

    def test_exhaust_all_bytes_and_full64_sideeffects(self):
        for payload in range(256):
            r=self.regs();r[3]=0xffffffff00002000;m={0x41ac:payload};before=dict(m)
            got=v.execute(v.EXPECTED,r,m);expected=list(r);expected[3]=payload&1;expected[11]=payload
            self.assertEqual(got['registers'],expected);self.assertEqual(got['reads'],[{'address':0x41ac,'size':1}]);self.assertEqual(got['stores'],[]);self.assertEqual(m,before)

    def test_wrap_to_zero_and_last_byte(self):
        for ea in [0,0xffffffff,0xdfffffff,0xe0000000]:
            r=self.regs();r[3]=0xdeadbeef00000000|((ea-0x21ac)&0xffffffff)
            got=v.execute(v.EXPECTED,r,{ea:255});self.assertEqual(got['effective_address'],ea);self.assertEqual(got['registers'][3],1);self.assertEqual(got['registers'][11],255)

    def test_upper_r3_ignored(self):
        for high in [0,0xffffffff,0x80000000,0xdeadbeef]:
            r=self.regs();r[3]=high<<32|0x2000;self.assertEqual(v.execute(v.EXPECTED,r,{0x41ac:254})['registers'][3],0)

    def test_fixtures_all_byte_address_crossproduct(self):
        cases=v.fixtures();self.assertEqual(len(cases),3072);self.assertEqual({(c['payload'],c['ea']) for c in cases},{(b,a) for b in range(256) for a in v.ADDRESSES})
        for c in cases:
            self.assertEqual(c['oracle']['registers'][3],c['payload']&1);self.assertEqual(c['oracle']['registers'][11],c['payload'])

    def test_no_other_register_or_memory_changes(self):
        for c in v.fixtures()[::19]:
            r=list(c['registers']);m=dict(c['memory']);got=v.execute(v.EXPECTED,r,m)
            self.assertEqual(r,c['registers']);self.assertEqual(m,c['memory'])
            for i in range(32):
                if i not in (3,11):self.assertEqual(got['registers'][i],r[i])
            self.assertIn('allCR',got['unchanged']);self.assertIn('LR',got['unchanged']);self.assertIn('CTR',got['unchanged'])

    def test_unknown_bytes_and_types_fail(self):
        for code in [v.EXPECTED[:-1],bytearray(v.EXPECTED)]:
            with self.assertRaises(ValueError):v.execute(code,self.regs(),{})
        for bad in [-1,True,1<<64]:
            r=self.regs();r[3]=bad
            with self.assertRaises(ValueError):v.execute(v.EXPECTED,r,{})
        with self.assertRaises(ValueError):v.execute(v.EXPECTED,[0]*31,{})
        for mem in [{1:True},{-1:0},{1<<32:0},{1:256},bytearray(3)]:
            with self.assertRaises(ValueError):v.execute(v.EXPECTED,self.regs(),mem)

    def test_missing_memory_rejected_unaligned_byte_allowed(self):
        r=self.regs();r[3]=1
        with self.assertRaisesRegex(ValueError,'explicit byte'):v.execute(v.EXPECTED,r,{})
        self.assertEqual(v.execute(v.EXPECTED,r,{0x21ad:3})['registers'][11],3)

    def test_original_hash_guard(self):
        with self.assertRaisesRegex(ValueError,'original image hash'):v.verify_original(bytes(64))

    def test_original_boundary_metadata(self):
        off=v.ENTRY-v.BASE;data=bytearray(off+64);struct.pack_into('<I',data,0x3c,0x80)
        data[off-16:off]=bytes.fromhex('81630000814b014c7d4903a64e800420');data[off:off+12]=v.EXPECTED;data[off+12:off+28]=bytes.fromhex('000000008063221c4e8000203d608325');data=bytes(data)
        with patch.object(v,'IMAGE_SHA256',hashlib.sha256(data).hexdigest()):
            got=v.verify_original(data);self.assertEqual(got['size'],12);self.assertEqual(got['after']['start'],v.ENTRY+12);self.assertEqual(got['containing_pdata'],[])
        # Synthetic parser contract: PDATA starting INSIDE the leaf must also reject.
        overlap=bytearray(data);struct.pack_into('<II',overlap,0x80+24+96+24,0x200,8);struct.pack_into('>II',overlap,0x200,v.ENTRY+4,1<<8);overlap=bytes(overlap)
        with patch.object(v,'IMAGE_SHA256',hashlib.sha256(overlap).hexdigest()),self.assertRaisesRegex(ValueError,'containing PDATA'):v.verify_original(overlap)
        for offset,label in [(off,'bytes mismatch'),(off-4,'neighbor mismatch')]:
            bad=bytearray(data);bad[offset]^=1;bad=bytes(bad)
            with patch.object(v,'IMAGE_SHA256',hashlib.sha256(bad).hexdigest()),self.assertRaisesRegex(ValueError,label):v.verify_original(bad)

    def test_harness_preserves_macros_memory_and_full_context(self):
        text=v.harness({'body':'BODY'},v.fixtures());self.assertIn('reserve=0x100001000ull',text);self.assertIn('target[0]=static_cast<unsigned char>(c.payload)',text);self.assertIn('expected.r11.u64=c.payload',text);self.assertIn('std::memcmp(&ctx,&expected,sizeof(ctx))',text);self.assertIn('std::memcmp(before[i],base+pages[i],4096)',text);self.assertIn('actual==csr',text);self.assertNotIn('#undef',text);self.assertNotIn('REX_STORE_',text)

    def test_exact_unique_extraction_and_mapping(self):
        body='DEFINE_REX_FUNC(sub_82E078C0) {\nREX_FUNC_PROLOGUE();\nctx.r11.u64=REX_LOAD_U8(ctx.r3.u32+8620);\nctx.r3.u64=ctx.r11.u32&0x1;\nreturn;\n}'
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            with self.assertRaises(ValueError):v.extract_body(p)
            (p/'one.cpp').write_text(body);(p/'mc2_probe_init.cpp').write_text('{0x82E078C0, sub_82E078C0}');(p/'mc2_probe_register.cpp').write_text('registrar->SetFunction(0x82E078C0, sub_82E078C0);');(p/'mc2_probe_pch.h').write_text('#define REX_PHYS_HOST_OFFSET(addr) (((u32)(addr) >= 0xE0000000u) ? 0x1000u : 0u)\n#define REX_LOAD_U8(x) (*(volatile u8*)(base + (u32)(x) + REX_PHYS_HOST_OFFSET(x)))\n')
            self.assertFalse(v.extract_body(p)['macro_replacements']);(p/'two.cpp').write_text(body)
            with self.assertRaises(ValueError):v.extract_body(p)
            (p/'two.cpp').unlink();(p/'one.cpp').write_text(body.replace('return;','ctx.r4.u64=0;return;'))
            with self.assertRaises(ValueError):v.extract_body(p)

    def test_half_toolchain_rejected(self):
        with self.assertRaisesRegex(ValueError,'all toolchain'):v.main(['--xex','x','--loader-source','l','--output','o','--generated','g'])

    def line(self):return 'BYTE_FLAG_CASE 0 raw3=FFFFFFFFFFFFDE53 ea=FFFFFFFF payload=000000FF r3=0000000000000001 r11=00000000000000FF memory=1 context=1 mxcsr=1 success=1'

    def test_completion_requires_zero_exit_end_and_no_stderr(self):
        line=self.line();full=line+'\nBYTE_FLAG_MEMORY pages=1 cases=1 released=1 failures=0\n';self.assertTrue(v.assess_run(full,'',0,1,1)['success'])
        for text,err,status in [(line,'',0),(full,'',0xc0000005),(full,'fault',0),('','',0)]:self.assertFalse(v.assess_run(text,err,status,1,1)['completed_without_fault'])

    def test_completion_rejects_wrong_r11_r3_duplicate(self):
        full=self.line()+'\nBYTE_FLAG_MEMORY pages=1 cases=1 released=1 failures=0\n'
        for old,new in [('r11=00000000000000FF','r11=FFFFFFFF000000FF'),('r3=0000000000000001','r3=00000000000000FF')]:self.assertFalse(v.assess_run(full.replace(old,new),'',0,1,1)['success'])
        self.assertFalse(v.assess_run(self.line()+'\n'+self.line()+'\nBYTE_FLAG_MEMORY pages=1 cases=2 released=1 failures=0\n','',0,2,1)['success'])


if __name__=='__main__':unittest.main()
