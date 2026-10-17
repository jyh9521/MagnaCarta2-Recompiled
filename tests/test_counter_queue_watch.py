"""Bounded queue snapshots on synthetic private pages, never title execution."""
import hashlib,json,os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HEADER=ROOT/'src/host/counter_queue_watch.h'
class QueueWatchTests(unittest.TestCase):
 def test_default_off(self):self.assertIn('active{false}',HEADER.read_text())
 def test_bound_and_immutable_ready(self):
  s=HEADER.read_text()
  for v in ['kCapacity=128','memory_order_release','memory_order_acquire','QUEUE_WATCH_ENTRY','weak_snapshot=1']:self.assertIn(v,s)
 def test_readonly_and_bounded_image_table(self):
  s=HEADER.read_text();self.assertIn('po::ReadBytes',s);self.assertIn('0x83330000',s)
  for v in ['WriteProcessMemory','std::thread','std::jthread','VirtualProtect','PPCContext']:self.assertNotIn(v,s)
 @unittest.skipUnless(os.name=='nt','Windows fixture')
 def test_real_private_pages(self):
  from tools.research.compile_module import vc_environment
  from tools.research.probe_route_a import CLANG_CL_SHA256
  cc=ROOT/'local/upstream/llvm/unpacked/bin/clang-cl.exe';sdk=ROOT/'local/upstream/rexglue/sdk/win-amd64'
  if not cc.exists() or not sdk.exists():self.skipTest('optional SDK/compiler absent')
  self.assertEqual(hashlib.sha256(cc.read_bytes()).hexdigest(),CLANG_CL_SHA256)
  root=ROOT/'local/analysis/phase24';out=Path(tempfile.mkdtemp(prefix='queue-watch-',dir=root));source=out/'fixture.cpp';source.write_text(CPP)
  command=[str(cc),'/nologo','/std:c++latest','/EHa','/MD','/O2','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/I'+str(sdk/'include'),'/I'+str(HEADER.parent),str(source),'/Fe'+str(out/'fixture.exe'),'/Fo'+str(out/'fixture.obj')];env=vc_environment(Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat'));v=subprocess.run(command,env=env,capture_output=True,text=True,timeout=120);r={'compile_command':command,'compile_exit':v.returncode};(out/'compile.txt').write_text(v.stdout+v.stderr);(out/'verification.json').write_text(json.dumps(r,indent=2));self.assertEqual(v.returncode,0,v.stdout+v.stderr)
  before=hashlib.sha256(HEADER.read_bytes()).hexdigest();v=subprocess.run([str(out/'fixture.exe')],cwd=out,capture_output=True,text=True,timeout=30);(out/'run.txt').write_text(v.stdout+v.stderr);r.update(run_exit=v.returncode,literal_output=v.stdout,header_sha256=before,inputs_unchanged=hashlib.sha256(HEADER.read_bytes()).hexdigest()==before);(out/'verification.json').write_text(json.dumps(r,indent=2));self.assertEqual(v.returncode,0,v.stdout+v.stderr);self.assertTrue(r['inputs_unchanged']);self.assertIn('QUEUE_WATCH_MOCK readonly=1 bounds=1 noaccess=1 imageguard=1 truncation=1 append=1',v.stdout)
CPP=r'''
#include "counter_queue_watch.h"
#include <cassert>
#include <vector>
using namespace mc2::host;
using namespace mc2::host::queue_watch;
int main(){auto* base=(uint8_t*)VirtualAlloc(nullptr,0x100001000ull,MEM_RESERVE,PAGE_NOACCESS);assert(base);std::array<uint32_t,5> pages={0x83265000,0x83263000,0x83276000,0x10000,0x82001000};for(auto p:pages)assert(VirtualAlloc(base+p,4096,MEM_COMMIT,PAGE_READWRITE)==base+p);auto put=[&](uint32_t a,uint32_t v){for(unsigned i=0;i<4;++i)base[a+i]=uint8_t(v>>(24-i*8));};put(kCounter,2);put(kGlobal,1);const uint32_t words[]={0x10000,0x11000,0x10040,0,0x10040,0x10020,16};for(unsigned i=0;i<7;++i)put(kManager+4*i,words[i]);put(0x10020,0x82001000);put(0x82001000,0x82399738);put(0x82001004,0x825C3508);put(0x82001008,0x82399768);std::vector<uint8_t> before;for(auto p:pages)before.insert(before.end(),base+p,base+p+4096);
auto disabled=CaptureQueueWatch(base);assert(!std::strcmp(disabled.status,"disabled")&&disabled.flags==0);assert(!StoreQueueWatch(disabled));assert(!ConfigureQueueWatch(false,true));configured=false;assert(ConfigureQueueWatch(true,true));auto s=CaptureQueueWatch(base);assert(!std::strcmp(s.status,"captured")&&s.head_captured==32&&s.table_captured==12&&s.fields[7]==0x10020&&s.fields[9]==0x82001000&&s.fields[11]==0x825C3508);size_t n=0;for(auto p:pages){assert(!std::memcmp(before.data()+n,base+p,4096));n+=4096;}
auto invalid=s;invalid.head_captured=33;assert(!StoreQueueWatch(invalid));invalid=s;invalid.table_captured=13;assert(!StoreQueueWatch(invalid));assert(StoreQueueWatch(s));put(kManager+20,0x10040);assert(!std::strcmp(CaptureQueueWatch(base).status,"empty"));put(kManager+20,0xFFFF);assert(!std::strcmp(CaptureQueueWatch(base).status,"bounds-invalid"));put(kManager+20,0x10020);put(kManager+4,0x10024);put(kManager+8,0x10024);s=CaptureQueueWatch(base);assert(s.head_captured==4&&s.table_captured==12);put(kManager+4,0x11000);put(kManager+8,0x10040);put(0x10020,0x7FC80000);s=CaptureQueueWatch(base);assert(s.head_captured==32&&s.table_captured==0&&!std::strcmp(s.table_status,"outside-image"));put(0x10020,0x82001000);DWORD old;assert(VirtualProtect(base+0x10000,4096,PAGE_NOACCESS,&old));s=CaptureQueueWatch(base);assert(s.head_captured==0&&s.table_captured==0);assert(VirtualProtect(base+0x10000,4096,old,&old));assert(VirtualProtect(base+0x82001000,4096,PAGE_NOACCESS,&old));s=CaptureQueueWatch(base);assert(s.head_captured==32&&s.table_captured==0);assert(VirtualProtect(base+0x82001000,4096,old,&old));s=CaptureQueueWatch(base);for(unsigned i=1;i<kCapacity+2;++i)StoreQueueWatch(s);assert((reserved.load()&~kFrozen)==kCapacity+2&&dropped==2);FreezeQueueWatch();assert(!StoreQueueWatch(s));FILE*f=std::fopen("synthetic-queue-watch.txt","wb");assert(f);DumpQueueWatch(f);assert(std::ftell(f)>0);std::fclose(f);DumpQueueWatch(nullptr);assert(VirtualFree(base,0,MEM_RELEASE));std::puts("QUEUE_WATCH_MOCK readonly=1 bounds=1 noaccess=1 imageguard=1 truncation=1 append=1");}
'''
