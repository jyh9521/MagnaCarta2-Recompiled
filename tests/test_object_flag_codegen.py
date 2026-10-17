"""Object flag discovery guard contracts; no real generator or title execution."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch
from tools.research import probe_callback_codegen as p

ENTRY=0x8233D3D8
CODE=bytes.fromhex('816301bc55630ffe4e800020')
SHA='503327950481e96a1cd186562cf11bc48315b21d3b6aeae17d94b7ddd908dd30'
PROFILE='object-flag-leaf'
OLD=['callback','virtual-thunk','compare','native-gateway','extended-native','float-leaf','bitfield-leaf','conditional-tail','indexed-tail','word-leaf','byte-flag-leaf']

class ObjectFlagCodegenTests(unittest.TestCase):
 def test_profile_identity(self):self.assertEqual(p.profile_fields(PROFILE),(ENTRY,12,SHA))
 def test_hint_file_and_exact_original(self):
  text=(p.ROOT/'research/xex/disc1-object-flag-leaf.toml').read_text()
  with patch.object(p,'BASE',ENTRY):self.assertEqual(p.verify_hint(CODE,text,PROFILE),{'entry':ENTRY,'size':12,'range_sha256':SHA})
 def test_reject_truncated_size(self):
  with self.assertRaises(ValueError):p.verify_hint(CODE,'[functions.0x8233D3D8]\nsize=8',PROFILE)
 def test_reject_extra_hint(self):
  with self.assertRaises(ValueError):p.verify_hint(CODE,'[functions.0x8233D3D8]\nsize=12\n[functions.0x8233D3E4]\nsize=4',PROFILE)
 def test_reject_changed_bytes(self):
  with patch.object(p,'BASE',ENTRY),self.assertRaisesRegex(ValueError,'range hash'):p.verify_hint(CODE[:-1]+b'\x21','[functions.0x8233D3D8]\nsize=12',PROFILE)
 def test_reject_truncated_image(self):
  with patch.object(p,'BASE',ENTRY),self.assertRaisesRegex(ValueError,'range hash'):p.verify_hint(CODE[:-1],'[functions.0x8233D3D8]\nsize=12',PROFILE)
 def test_cli_profile(self):
  with patch.object(p,'execute',return_value={'success':True}) as call:
   self.assertEqual(p.main(['--xex','x','--sdk-exe','s','--loader-source','l','--output','o','--entry-profile',PROFILE]),0)
  self.assertEqual(call.call_args.args[0].entry_profile,PROFILE)
 def test_generated_requires_unique_body_and_mapping(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);body=f'DEFINE_REX_FUNC(sub_{ENTRY:08X}) {{\n ctx.r3.u64 = 1;\n}}';mapping=f'registrar->SetFunction(0x{ENTRY:08X}, sub_{ENTRY:08X});'
   (r/'mc2_probe_recomp.0.cpp').write_text(body);(r/'mc2_probe_register.cpp').write_text(mapping)
   self.assertTrue(p.verify_entry(r,ENTRY)['registered'])
   for broken in ['',mapping+'\n'+mapping]:
    (r/'mc2_probe_register.cpp').write_text(broken)
    with self.assertRaises(ValueError):p.verify_entry(r,ENTRY)
   (r/'mc2_probe_register.cpp').write_text(mapping);(r/'mc2_probe_recomp.0.cpp').write_text(body.replace('ctx.r3.u64 = 1;','REX_FATAL("missing");'))
   with self.assertRaises(ValueError):p.verify_entry(r,ENTRY)
 def simulate(self,profile,success):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);meta=root/'meta/research/xex';meta.mkdir(parents=True)
   for src in (p.ROOT/'research/xex').glob('disc1-*.toml'):(meta/src.name).write_bytes(src.read_bytes())
   inputs=root/'inputs';inputs.mkdir()
   for name in ['input.xex','sdk.exe','loader.cc']:(inputs/name).write_bytes(b'synthetic')
   output=root/'out';args=SimpleNamespace(xex=inputs/'input.xex',sdk_exe=inputs/'sdk.exe',loader_source=inputs/'loader.cc',output=output,entry_profile=profile)
   def digest(path):return p.SDK_EXE_SHA256 if Path(path).name=='sdk.exe' else p.XEX_SHA256
   def step(exe,argv,out,label,timeout):
    if not success:return {'returncode':1}
    project=out/'project';project.mkdir(exist_ok=True)
    if label=='init':(project/'mc2_probe_manifest.toml').write_text('includes = []')
    else:
     gen=project/'generated/default-disc1';gen.mkdir(parents=True)
     entries=[p.profile_fields(x)[0] for x in OLD+[PROFILE]]
     (gen/'mc2_probe_recomp.0.cpp').write_text('\n'.join(f'DEFINE_REX_FUNC(sub_{e:08X}) {{\n ctx.r3.u64 = 1;\n}}' for e in entries))
     (gen/'mc2_probe_register.cpp').write_text('\n'.join(f'registrar->SetFunction(0x{e:08X}, sub_{e:08X});' for e in entries))
    return {'returncode':0}
   with patch.object(p,'ROOT',root/'meta'),patch.object(p,'digest',side_effect=digest),patch.object(p,'image_from_xex',return_value=b''),patch.object(p,'verify_hint',side_effect=lambda image,text,profile='callback':{'profile':profile}) as guard,patch.object(p,'run_step',side_effect=step),patch.object(p,'verify_generated',return_value={}):
    result=p.execute(args)
   includes=[]
   if success:
    import tomllib
    includes=tomllib.loads((output/'project/mc2_probe_manifest.toml').read_text())['includes']
   return result,[c.args[2] if len(c.args)>2 else 'callback' for c in guard.call_args_list],includes
 def test_inherits_all_twelve_prior_hints_and_registration(self):
  result,guards,includes=self.simulate(PROFILE,True)
  self.assertTrue(result['success']);self.assertTrue(result['proof']['object_flag_leaf']['generated']['registered']);self.assertEqual(guards,OLD+[PROFILE]);self.assertEqual(len(includes),13);self.assertEqual(includes[-2:],['disc1-byte-flag-leaf.toml','disc1-object-flag-leaf.toml']);self.assertEqual(len(set(includes)),13)
 def test_all_old_profile_chains_unchanged(self):
  for i,profile in enumerate(OLD):
   with self.subTest(profile=profile):
    result,guards,_=self.simulate(profile,False);self.assertFalse(result['success']);self.assertEqual(guards,OLD[:i+1]);self.assertNotIn('object_flag_leaf',result['proof'])

if __name__=='__main__':unittest.main()
