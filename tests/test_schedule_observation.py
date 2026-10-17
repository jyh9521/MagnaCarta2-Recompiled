"""Read-only caller-frame samples; synthetic pages are not title/AV acceptance."""
import hashlib,json,os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HEADER=ROOT/'src/host/schedule_observation.h'
class ScheduleObservationTests(unittest.TestCase):
 def test_memory_policy(self):
  s=HEADER.read_text();self.assertIn('po::ReadBytes',s);self.assertIn('end<=0x7F000000ULL',s);self.assertIn('end<=0x83330000ULL',s);self.assertNotIn('WriteProcessMemory',s)
 def test_full_delay_guard_count(self):
  s=HEADER.read_text();self.assertIn('{0x82869800,0x7D8802A6}',s);self.assertIn('{0x8286988C,0x4E800020}',s);self.assertEqual(s.count('{0x'),74)
 def test_double_caller_gate(self):
  s=HEADER.read_text();self.assertIn('c.lr==0x82869854',s);self.assertIn('x.values[1]==0x823997AC',s)
 def test_frame_width(self):
  s=HEADER.read_text();self.assertIn('+0x68,4',s);self.assertIn('+0x60,8',s);self.assertIn('+0x58,8',s)
 def test_default_off_and_source_hash_dependencies(self):
  s=(ROOT/'src/host/title_probe.cpp').read_text();self.assertIn('MC2_SCHEDULE_TRACE',s);self.assertLess(s.index('const bool code=mc2::host::schedule_observation::OriginalBytes'),s.index('mc2::host::InstallScheduleImportTrace'))
  s=(ROOT/'tools/research/probe_title_entry.py').read_text();self.assertIn("('schedule_import_trace.h','schedule_observation.h')",s);self.assertIn("overrides['MC2_SCHEDULE_TRACE']='1' if schedule else '0'",s)
 @unittest.skipUnless(os.name=='nt' and (ROOT/'local/upstream/rexglue/sdk/win-amd64/include').exists(),'local Windows SDK fixture')
 def test_native_private_pages(self):
  from tools.research.compile_module import vc_environment
  from tools.research.probe_route_a import CLANG_CL_SHA256
  cc=ROOT/'local/upstream/llvm/unpacked/bin/clang-cl.exe';self.assertEqual(hashlib.sha256(cc.read_bytes()).hexdigest(),CLANG_CL_SHA256)
  out=Path(tempfile.mkdtemp(prefix='schedule-read-',dir=ROOT/'local/analysis/phase23'));source=out/'fixture.cpp';source.write_text(CPP)
  cmd=[str(cc),'/nologo','/std:c++latest','/EHa','/MD','/O2','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/I'+str(ROOT/'local/upstream/rexglue/sdk/win-amd64/include'),'/I'+str(HEADER.parent),str(source),'/Fe'+str(out/'fixture.exe'),'/Fo'+str(out/'fixture.obj')]
  env=vc_environment(Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat'))
  p=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=120);rows=[dict(command=cmd,exit=p.returncode,output=p.stdout+p.stderr)];(out/'results.json').write_text(json.dumps(rows,indent=2));self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  p=subprocess.run([str(out/'fixture.exe')],capture_output=True,text=True,timeout=30);rows.append(dict(command=[str(out/'fixture.exe')],exit=p.returncode,output=p.stdout+p.stderr));(out/'results.json').write_text(json.dumps(rows,indent=2));self.assertEqual(p.returncode,0,p.stdout+p.stderr);self.assertIn('SCHEDULE_READ fullcontext=unchanged memory=unchanged frame=verified range=guarded',p.stdout)
CPP=r'''
#include "schedule_observation.h"
#include <cassert>
#include <cstring>
using namespace mc2::host;
using namespace mc2::host::schedule_observation;
int main(){auto*p=(uint8_t*)VirtualAlloc(nullptr,0x3000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);assert(p);auto*base=(uint8_t*)(uintptr_t(p)-0x10000);auto put=[&](uint32_t a,uint64_t v,size_t n){for(size_t i=0;i<n;++i)p[a-0x10000+i]=uint8_t(v>>(8*(n-i-1)));};
PPCContext c{};c.lr=0x82869854;c.r1.u64=0x11000;c.r5.u64=0x11050;c.r29.u64=0x123456789ABCDEF0;put(0x11050,0,8);put(0x11058,1,8);put(0x11060,0x4000010080,8);put(0x11068,0x823997AC,4);put(0x110E8,0x82E2080C,4);put(0x10080,2,4);PPCContext original;std::memcpy(&original,&c,sizeof(c));uint8_t bytes[0x3000];std::memcpy(bytes,p,sizeof(bytes));
auto x=Sample(0,c,base);assert((x.flags&31)==31&&x.values[0]==0&&x.values[1]==0x823997AC&&x.values[2]==0x4000010080&&x.values[3]==1&&x.values[4]==2&&(x.flags&128)&&x.values[7]==0x82E2080C);assert(!std::memcmp(&original,&c,sizeof(c))&&!std::memcmp(bytes,p,sizeof(bytes)));c.lr=0x1234;assert(!(Sample(0,c,base).flags&31));c.lr=0x82869854;put(0x11068,0x823997A0,4);assert(!(Sample(0,c,base).flags&28));put(0x11068,0x823997AC,4);c.r1.u64=0xFFFFFFF0;assert(!(Sample(0,c,base).flags&30));c.r1.u64=0x11000;
assert(!DataRange(0x7FC80000,4)&&!DataRange(0x83330000,4)&&!DataRange(0xE0000000,4)&&!DataRange(0x7FFFFFFE,4)&&!DataRange(0xFFFFFFFF,8)&&!DataRange(0,4));uint64_t out=123;assert(!Read({base,0x100001000ULL},0xE0000000,4,out)&&out==123);assert(!OriginalBytes({base,0x100001000ULL}));
c.r3.u64=0x10040;put(0x10050,0xFFFFFFFE,4);put(0x10054,2,4);put(0x10058,0x30003000,4);x=Sample(1,c,base);assert((x.flags&7)==7&&x.values[0]==0xFFFFFFFE&&x.values[1]==2&&x.values[2]==0x30003000);DWORD old;assert(VirtualProtect(p,0x1000,PAGE_NOACCESS,&old));assert(!(Sample(1,c,base).flags&7));assert(VirtualProtect(p,0x1000,old,&old));assert(VirtualFree(p,0,MEM_RELEASE));std::puts("SCHEDULE_READ fullcontext=unchanged memory=unchanged frame=verified range=guarded");}
'''
