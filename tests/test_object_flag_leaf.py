"""Portable guarded oracle/protocol tests; native generated-body evidence is separate."""
import hashlib,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tools.research import verify_object_flag_leaf as v
class ObjectFlagLeafTests(unittest.TestCase):
 def regs(self):return [0xabcdef1234000000+i for i in range(32)]
 def mem(self,ea,value):return {ea+i:b for i,b in enumerate(value.to_bytes(4,'big'))}
 def test_be32_edges_and_complete_gpr_sideeffects(self):
  for value in [0,1,0x7fffffff,0x80000000,0xffffffff,0x81234567,0x01020304]:
   regs=self.regs();regs[3]=0xffffffff00002000;memory=self.mem(0x21bc,value);before=dict(memory);got=v.execute(v.EXPECTED,regs,memory);expected=list(regs);expected[3]=value>>31;expected[11]=value
   self.assertEqual(got['registers'],expected);self.assertEqual(got['reads'],[{'address':0x21bc,'size':4}]);self.assertEqual(got['stores'],[]);self.assertEqual(memory,before)
 def test_wrap_and_last_aligned_word(self):
  for ea in [0,0xfffffffc,0xdffffffc,0xe0000000]:
   r=self.regs();r[3]=0xdeadbeef00000000|((ea-0x1bc)&0xffffffff);got=v.execute(v.EXPECTED,r,self.mem(ea,0x80000000));self.assertEqual(got['effective_address'],ea);self.assertEqual(got['registers'][3],1);self.assertEqual(got['registers'][11],0x80000000)
 def test_upper_raw_object_bits_ignored(self):
  for high in [0,0xffffffff,0x80000000,0xdeadbeef]:
   r=self.regs();r[3]=high<<32|0x2000;self.assertEqual(v.execute(v.EXPECTED,r,self.mem(0x21bc,0x7fffffff))['registers'][3],0)
 def test_random_fixtures_all_addresses(self):
  cases=v.fixtures();self.assertEqual(len(cases),1536);self.assertEqual(len({c['payload']for c in cases}),128);self.assertEqual({c['ea']for c in cases},set(v.ADDRESSES))
  for c in cases:self.assertEqual(c['oracle']['registers'][3],c['payload']>>31);self.assertEqual(c['oracle']['registers'][11],c['payload'])
 def test_no_input_or_other_gpr_changes(self):
  for c in v.fixtures()[::19]:
   r=list(c['registers']);m=dict(c['memory']);got=v.execute(v.EXPECTED,r,m);self.assertEqual(r,c['registers']);self.assertEqual(m,c['memory'])
   for i in range(32):
    if i not in [3,11]:self.assertEqual(got['registers'][i],r[i])
   for field in ['allCR','XER','LR','CTR','allFPR','FPSCR','vectors','memory']:self.assertIn(field,got['unchanged'])
 def test_unknown_bytes_and_types_fail(self):
  for code in [v.EXPECTED[:-1],bytearray(v.EXPECTED),bytes(12)]:
   with self.assertRaises(ValueError):v.execute(code,self.regs(),{})
  for bad in [-1,True,1<<64]:
   r=self.regs();r[3]=bad
   with self.assertRaises(ValueError):v.execute(v.EXPECTED,r,{})
  with self.assertRaises(ValueError):v.execute(v.EXPECTED,[0]*31,{})
  for mem in [{1:True},{-1:0},{1<<32:0},{1:256},bytearray(3)]:
   with self.assertRaises(ValueError):v.execute(v.EXPECTED,self.regs(),mem)
 def test_missing_unaligned_and_cross_boundary_rejected(self):
  for ea in [0x21bc,0xffffffff,0x21bd]:
   r=self.regs();r[3]=(ea-0x1bc)&0xffffffff
   memory={}if ea==0x21bc else {ea+i:0 for i in range(4)if ea+i<1<<32}
   with self.assertRaisesRegex(ValueError,'aligned explicit fixture'):v.execute(v.EXPECTED,r,memory)
 def test_original_hash_guard(self):
  with self.assertRaisesRegex(ValueError,'original image hash'):v.verify_original(bytes(64))
 def test_original_boundary_and_pdata_overlap(self):
  off=v.ENTRY-v.BASE;data=bytearray(off+64);struct.pack_into('<I',data,0x3c,0x80);data[off-16:off]=bytes.fromhex('81630000814b03207d4903a64e800420');data[off:off+12]=v.EXPECTED;data[off+12:off+28]=bytes.fromhex('0000000082a55aa88224cf287d8802a6');data=bytes(data)
  with patch.object(v,'IMAGE_SHA256',hashlib.sha256(data).hexdigest()):self.assertEqual(v.verify_original(data)['containing_pdata'],[]);self.assertEqual(v.verify_original(data)['size'],12)
  overlap=bytearray(data);struct.pack_into('<II',overlap,0x80+24+96+24,0x200,8);struct.pack_into('>II',overlap,0x200,v.ENTRY+4,1<<8);overlap=bytes(overlap)
  with patch.object(v,'IMAGE_SHA256',hashlib.sha256(overlap).hexdigest()),self.assertRaisesRegex(ValueError,'containing PDATA'):v.verify_original(overlap)
  for offset,label in [(off,'bytes mismatch'),(off-4,'neighbor mismatch')]:
   bad=bytearray(data);bad[offset]^=1;bad=bytes(bad)
   with patch.object(v,'IMAGE_SHA256',hashlib.sha256(bad).hexdigest()),self.assertRaisesRegex(ValueError,label):v.verify_original(bad)
 def test_harness_uses_unchanged_body_macros_fullcontext_memory(self):
  text=v.harness({'body':'ACTUAL_BODY'},v.fixtures());self.assertIn('ACTUAL_BODY',text)
  for needle in ['reserve=0x100001000ull','expected.r11.u64=c.payload','expected.r3.u64=c.payload>>31','target[j]=(c.payload>>(24-j*8))&255','std::memcmp(&ctx,&expected,sizeof(ctx))','std::memcmp(before[i],base+pages[i],4096)','actual==csr','ctx.fpscr.InitHost()','0x7FF0000000000001ull','REX_PHYS_HOST_OFFSET(guests[i])!=expected_bias']:self.assertIn(needle,text)
  self.assertNotIn('#undef',text);self.assertNotIn('REX_STORE_',text)
 def generated_fixture(self,p):
  body='DEFINE_REX_FUNC(sub_8233D3D8) {\nREX_FUNC_PROLOGUE();\nctx.r11.u64=REX_LOAD_U32(ctx.r3.u32+444);\nctx.r3.u64=__builtin_rotateleft64(ctx.r11.u32|(ctx.r11.u64<<32),1)&0x1;\nreturn;\n}'
  (p/'one.cpp').write_text(body);(p/'mc2_probe_init.cpp').write_text('{0x8233D3D8, sub_8233D3D8}');(p/'mc2_probe_register.cpp').write_text('registrar->SetFunction(0x8233D3D8, sub_8233D3D8);');(p/'mc2_probe_pch.h').write_text('#define REX_PHYS_HOST_OFFSET(addr) (((u32)(addr) >= 0xE0000000u) ? 0x1000u : 0u)\n#define REX_LOAD_U32(x) __builtin_bswap32(*(volatile u32*)(base + (u32)(x) + REX_PHYS_HOST_OFFSET(x)))\n');return body
 def test_exact_unique_extraction(self):
  with tempfile.TemporaryDirectory()as td:
   p=Path(td)
   with self.assertRaises(ValueError):v.extract_body(p)
   body=self.generated_fixture(p);self.assertFalse(v.extract_body(p)['macro_replacements']);(p/'two.cpp').write_text(body)
   with self.assertRaises(ValueError):v.extract_body(p)
   (p/'two.cpp').unlink();(p/'one.cpp').write_text(body.replace('return;','ctx.r4.u64=0;return;'))
   with self.assertRaises(ValueError):v.extract_body(p)
 def test_missing_duplicate_mapping_or_altered_macro_rejected(self):
  for filename,content in [('mc2_probe_init.cpp',''),('mc2_probe_register.cpp',''),('mc2_probe_init.cpp','{0x8233D3D8, sub_8233D3D8}, {0x8233D3D8, sub_8233D3D8}'),('mc2_probe_pch.h','')]:
   with tempfile.TemporaryDirectory()as td:
    p=Path(td);self.generated_fixture(p);(p/filename).write_text(content)
    with self.assertRaises(ValueError):v.extract_body(p)
 def test_half_toolchain_rejected(self):
  with self.assertRaisesRegex(ValueError,'all toolchain'):v.main(['--xex','x','--loader-source','l','--output','o','--generated','g'])
 def test_optimization_rejects_unbounded_or_unknown_switch(self):
  with self.assertRaises(SystemExit):v.main(['--xex','x','--loader-source','l','--output','o','--optimization','O3'])
 def line(self):return 'OBJECT_FLAG_CASE 0 raw3=FFFFFFFFFFFFFE40 ea=FFFFFFFC payload=80000000 r3=0000000000000001 r11=0000000080000000 memory=1 context=1 mxcsr=1 success=1'
 def test_completion_requires_zero_exit_end_no_stderr(self):
  line=self.line();full=line+'\nOBJECT_FLAG_MEMORY pages=1 cases=1 released=1 failures=0\n';self.assertTrue(v.assess_run(full,'',0,1,1)['success'])
  for text,err,status in [(line,'',0),(full,'',0xc0000005),(full,'fault',0),('','',0)]:self.assertFalse(v.assess_run(text,err,status,1,1)['completed_without_fault'])
 def test_completion_rejects_wrong_r11_r3_duplicates(self):
  full=self.line()+'\nOBJECT_FLAG_MEMORY pages=1 cases=1 released=1 failures=0\n'
  for old,new in [('r11=0000000080000000','r11=FFFFFFFF80000000'),('r3=0000000000000001','r3=0000000080000000')]:self.assertFalse(v.assess_run(full.replace(old,new),'',0,1,1)['success'])
  self.assertFalse(v.assess_run(self.line()+'\n'+self.line()+'\nOBJECT_FLAG_MEMORY pages=1 cases=2 released=1 failures=0\n','',0,2,1)['success'])
if __name__=='__main__':unittest.main()
