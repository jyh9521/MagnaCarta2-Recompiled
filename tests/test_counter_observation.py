"""Synthetic guarded pages, not original PPC execution or title acceptance."""
import hashlib,json,os,subprocess,tempfile,unittest,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];HEADER=ROOT/'src/host/counter_observation.h'
class CounterObservationTests(unittest.TestCase):
 def test_original_ranges_complete(self):
  s=HEADER.read_text();self.assertEqual(s.count('{0x'),227);self.assertIn('{0x82399650,0x7D8802A6}',s);self.assertIn('{0x8215363C,0x82399738}',s)
 def test_known_manager_and_bounded_reads(self):
  s=HEADER.read_text();self.assertIn('so::Read',s);self.assertIn('x.values[4]==kManager',s);self.assertNotIn('WriteProcessMemory',s)
 def test_actual_reservation_gate(self):
  s=HEADER.read_text();self.assertIn('reservation.call==call',s);self.assertIn('reservation.record==c.r1.u32-0x20',s);self.assertIn('CurrentCounterParentCall()!=0',s)
 def test_saved_original_callback_argument(self):
  s=HEADER.read_text();self.assertIn('known(5,uint32_t(args[0]))',s);self.assertNotIn('known(5,c.r3',s)
 def test_trace_inputs_are_hashed(self):
  s=(ROOT/'tools/research/probe_title_entry.py').read_text();self.assertIn("('counter_lifecycle_trace.h','counter_observation.h','counter_queue_watch.h','counter_worker_sample.h')",s);self.assertIn("overrides['MC2_COUNTER_TRACE']='1' if counter else '0'",s)
 @unittest.skipUnless(os.name=='nt'and(ROOT/'local/upstream/rexglue/sdk/win-amd64/include').exists(),'local Windows SDK fixture')
 def test_native_readonly_frames(self):
  from tools.research.compile_module import vc_environment
  from tools.research.probe_route_a import CLANG_CL_SHA256
  cc=ROOT/'local/upstream/llvm/unpacked/bin/clang-cl.exe';self.assertEqual(hashlib.sha256(cc.read_bytes()).hexdigest(),CLANG_CL_SHA256)
  out=Path(tempfile.mkdtemp(prefix='counter-read-',dir=ROOT/'local/analysis/phase24'));source=out/'fixture.cpp';g=HEADER.read_text().split('guards[][2]={',1)[1].split(' };',1)[0];source.write_text(CPP.replace('GUARDS_HERE',g))
  cmd=[str(cc),'/nologo','/std:c++latest','/EHa','/MD','/O2','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/DSPDLOG_FMT_EXTERNAL','/DSPDLOG_COMPILED_LIB','/I'+str(ROOT/'local/upstream/rexglue/sdk/win-amd64/include'),'/I'+str(HEADER.parent),str(source),'/Fe'+str(out/'fixture.exe'),'/Fo'+str(out/'fixture.obj')];env=vc_environment(Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat'))
  p=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=120);rows=[dict(command=cmd,exit=p.returncode,output=p.stdout+p.stderr)];(out/'results.json').write_text(json.dumps(rows,indent=2));self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  p=subprocess.run([str(out/'fixture.exe')],capture_output=True,text=True,timeout=30);rows.append(dict(command=[str(out/'fixture.exe')],exit=p.returncode,output=p.stdout+p.stderr));(out/'results.json').write_text(json.dumps(rows,indent=2));self.assertEqual(p.returncode,0,p.stdout+p.stderr);self.assertIn('COUNTER_READ readonly=1 reservation_gate=1 callback_arg=original guards=227',p.stdout)
CPP=r'''
#include "counter_observation.h"
#include <cassert>
#include <vector>
REX_EXTERN(__imp__sub_82399650){ctx.r3.u64^=1;}
REX_EXTERN(__imp__sub_82399738){ctx.r3.u64^=2;}
REX_EXTERN(__imp__sub_822D0A68){ctx.r3.u64^=3;}
using namespace mc2::host;using namespace mc2::host::counter_observation;
int main(){auto*base=(uint8_t*)VirtualAlloc(nullptr,0x84000000ULL,MEM_RESERVE,PAGE_NOACCESS);assert(base);const uint32_t pages[]={0x10000,0x20000,0x83265000,0x83276000,0x83263000,0x82399000,0x822D0000,0x82153000};for(auto p:pages)assert(VirtualAlloc(base+p,4096,MEM_COMMIT,PAGE_READWRITE));auto put=[&](uint32_t a,uint32_t v){for(unsigned i=0;i<4;++i)base[a+i]=uint8_t(v>>(24-i*8));};uint32_t guards[][2]={GUARDS_HERE};for(auto&g:guards)put(g[0],g[1]);assert(OriginalBytes({base,0x100001000ULL}));put(0x82399650,0);assert(!OriginalBytes({base,0x100001000ULL}));put(0x82399650,0x7D8802A6);
put(kCounter,1);put(0x83263ACC,1);for(unsigned i=0;i<7;++i)put(kManager+i*4,0x10000);put(kManager+0x18,8);PPCContext c{};c.r1.u64=0x20020;c.lr=0x82E20800;std::array<uint64_t,8>a{};a[0]=kCounter;CounterExtra empty{};auto inc=Sample(0x82399650,0,c,base,a,1,empty);assert(inc.selection==1&&inc.values[1]==1&&!(inc.flags&8));
std::array<uint64_t,8>q{};q[0]=0x20000;q[1]=8;c.lr=0x8239969C;c.r31.u64=kCounter;assert(Sample(0x822D0A68,0,c,base,q,2,empty).selection==0);counter_trace::parent_call=1;auto queue=Sample(0x822D0A68,0,c,base,q,2,empty);assert(queue.selection==1);put(0x20000,kManager);put(0x20004,0x10000);put(0x20008,8);put(kCounter,2);auto queuepost=Sample(0x822D0A68,1,c,base,q,2,queue);assert(queuepost.values[5]==0x10000&&queuepost.values[6]==8);put(0x10000,0x82153638);put(0x10004,kCounter);put(kManager+8,0x10008);put(kManager+0x10,0);counter_trace::parent_call=0;c.lr=0x82E20800;
std::vector<uint8_t>before;for(auto p:pages)before.insert(before.end(),base+p,base+p+4096);PPCContext original;std::memcpy(&original,&c,sizeof(c));auto post=Sample(0x82399650,1,c,base,a,1,inc);assert(post.values[5]==0x10000&&post.values[7]==0x82153638&&post.values[8]==kCounter&&post.values[19]==1);assert(!std::memcmp(&c,&original,sizeof(c)));size_t n=0;for(auto p:pages){assert(!std::memcmp(before.data()+n,base+p,4096));n+=4096;}
std::array<uint64_t,8>d{};d[0]=0x10000;c.r3.u64=0x10000;auto dec=Sample(0x82399738,0,c,base,d,3,empty);assert(dec.selection==1&&dec.values[1]==2);put(kCounter,1);c.r3.u64=8;auto decpost=Sample(0x82399738,1,c,base,d,3,dec);assert(decpost.selection==1&&decpost.values[5]==0x10000&&decpost.values[1]==1);d[0]=0xE0000000;assert(Sample(0x82399738,0,c,base,d,4,empty).selection==2);
put(0x83263ACC,0);auto fallback=Sample(0x82399650,0,c,base,a,5,empty);assert(fallback.selection==1);assert(!(Sample(0x82399650,1,c,base,a,5,fallback).flags&8));assert(VirtualFree(base,0,MEM_RELEASE));std::puts("COUNTER_READ readonly=1 reservation_gate=1 callback_arg=original guards=227");}
'''
