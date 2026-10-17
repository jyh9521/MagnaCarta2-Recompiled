"""Read-only consumer native sampling; synthetic threads and Windows API fixtures."""
import hashlib,json,os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HEADER=ROOT/'src/host/counter_worker_sample.h'
OBS=ROOT/'src/host/counter_observation.h'
class CounterWorkerTests(unittest.TestCase):
 def test_identity_before_suspend(self):
  s=HEADER.read_text();self.assertLess(s.index('GetThreadTimes('),s.index('SuspendThread('));self.assertLess(s.index('if(!same)'),s.index('SuspendThread('));self.assertIn('==w.creation',s)
 def test_resume_and_formatting_order(self):
  s=HEADER.read_text();region=s[s.index('  CONTEXT native{}'):s.index('const DWORD resumed=ResumeThread')]
  self.assertEqual(region.count('return'),0);self.assertNotIn('printf',region);self.assertLess(s.index('ResumeThread('),s.index('GetModuleHandleExA('));self.assertIn('resumed==prior+1',s)
 def test_readonly_context_and_no_repair(self):
  s=HEADER.read_text();self.assertIn('ReadProcessMemory(',s);self.assertIn('detail::Preflight',s)
  for bad in ['SetThreadContext','WriteProcessMemory','TerminateThread','ctx.r3.u64=']:self.assertNotIn(bad,s)
 def test_worker_publication_and_scope(self):
  s=OBS.read_text();self.assertIn('w.ready.store(2,std::memory_order_release)',s);self.assertIn('GetThreadTimes(GetCurrentThread()',s);self.assertIn('if(!phase && target==0x82399738)RememberWorker(c)',s)
  self.assertIn('workers_unavailable.fetch_add',s);self.assertIn('scheduling_perturbed=1',HEADER.read_text())
 def run_native(self,cpp,label):
  from tools.research.compile_module import vc_environment
  from tools.research.probe_route_a import CLANG_CL_SHA256
  cc=ROOT/'local/upstream/llvm/unpacked/bin/clang-cl.exe';sdk=ROOT/'local/upstream/rexglue/sdk/win-amd64'
  if not cc.exists() or not sdk.exists():self.skipTest('optional pinned compiler/SDK absent')
  self.assertEqual(hashlib.sha256(cc.read_bytes()).hexdigest(),CLANG_CL_SHA256)
  out=Path(tempfile.mkdtemp(prefix='counter-worker-'+label+'-',dir=ROOT/'local/analysis/phase24'));source=out/'fixture.cpp';source.write_text(cpp)
  hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [HEADER,OBS,ROOT/'src/host/counter_lifecycle_trace.h',ROOT/'src/host/panic_observation.h']}
  command=[str(cc),'/nologo','/std:c++latest','/EHa','/MD','/O2','/fp:strict','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/DSPDLOG_FMT_EXTERNAL','/DSPDLOG_COMPILED_LIB','/I'+str(sdk/'include'),'/I'+str(HEADER.parent),str(source),'/Fe'+str(out/'fixture.exe'),'/Fo'+str(out/'fixture.obj')];env=vc_environment(Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat'));v=subprocess.run(command,env=env,capture_output=True,text=True,timeout=120);r={'compile_command':command,'compile_exit':v.returncode,'inputs':hashes};(out/'compile.txt').write_text(v.stdout+v.stderr);(out/'verification.json').write_text(json.dumps(r,indent=2));self.assertEqual(v.returncode,0,v.stdout+v.stderr)
  v=subprocess.run([str(out/'fixture.exe')],cwd=out,capture_output=True,text=True,timeout=30);(out/'run.txt').write_text(v.stdout+v.stderr);r.update(run_command=[str(out/'fixture.exe')],run_exit=v.returncode,literal_output=v.stdout,inputs_unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items()));(out/'verification.json').write_text(json.dumps(r,indent=2));self.assertEqual(v.returncode,0,v.stdout+v.stderr);self.assertTrue(r['inputs_unchanged']);return v.stdout
 @unittest.skipUnless(os.name=='nt','Windows actual thread')
 def test_real_native_thread_readonly_and_prior_suspend_count(self):self.assertIn('WORKER_REAL readonly=1 creation=1 prior_suspend_restored=1 capacity=1',self.run_native(REAL,'real'))
 @unittest.skipUnless(os.name=='nt','Windows API fixture')
 def test_actual_header_mock_api_failures(self):self.assertIn('WORKER_API modes=9 suspend_resume=paired failure_closed=1',self.run_native(MOCK,'api'))

DELEGATES=r'''
extern "C" void __imp__sub_82399650(PPCContext&,uint8_t*){std::abort();}
extern "C" void __imp__sub_82399738(PPCContext&,uint8_t*){std::abort();}
extern "C" void __imp__sub_822D0A68(PPCContext&,uint8_t*){std::abort();}
'''
REAL=r'''
#include "counter_worker_sample.h"
#include <cassert>
#include <atomic>
#include <thread>
#include <cstdlib>
using namespace mc2::host;
using namespace mc2::host::counter_observation;
int main(){auto* page=(uint8_t*)VirtualAlloc(nullptr,4096,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);assert(page);std::memset(page,0xA5,4096);auto* base=(uint8_t*)(uintptr_t(page)-0x10000);std::atomic<bool> ready=false,stop=false;PPCContext finished{},expected{};
std::thread t([&]{PPCContext c{};for(size_t i=0;i<sizeof(c);++i)((uint8_t*)&c)[i]=uint8_t(i*13+7);c.r1.u64=0x10000;std::memcpy(&expected,&c,sizeof(c));RememberWorker(c);ready=true;while(!stop.load())Sleep(1);std::memcpy(&finished,&c,sizeof(c));});while(!ready.load())std::this_thread::yield();auto& w=workers[0];assert(w.ready==2);HANDLE h=OpenThread(THREAD_SUSPEND_RESUME|THREAD_QUERY_INFORMATION,FALSE,w.thread);assert(h);FILETIME a{},b{},k{},u{};assert(GetThreadTimes(h,&a,&b,&k,&u));assert(w.creation==((uint64_t(a.dwHighDateTime)<<32)|a.dwLowDateTime));assert(SuspendThread(h)==0);assert(SampleCounterWorkers(base));assert(ResumeThread(h)==1);
const auto saved=w.creation;w.creation^=1;assert(SampleCounterWorkers(base));w.creation=saved;PPCContext self{},other{},third{},fourth{};RememberWorker(self);RememberWorker(self);RememberWorker(other);RememberWorker(third);RememberWorker(fourth);assert(workers_unavailable==1);assert(SampleCounterWorkers(base));stop=true;t.join();assert(!std::memcmp(&expected,&finished,sizeof(expected)));for(size_t i=0;i<4096;++i)assert(page[i]==0xA5);CloseHandle(h);assert(VirtualFree(page,0,MEM_RELEASE));std::puts("WORKER_REAL readonly=1 creation=1 prior_suspend_restored=1 capacity=1");}
''' + DELEGATES
MOCK=r'''
#include "counter_observation.h"
#include <cassert>
#include <cstdlib>
using namespace mc2::host;
using namespace mc2::host::counter_observation;
int mode=0,opened=0,suspended=0,resumed=0,closed=0,lookups=0;
std::array<uint8_t,512> native_stack{};
HANDLE MockOpenThread(DWORD,BOOL,DWORD){++opened;return mode==1?nullptr:(HANDLE)uintptr_t(123);}
DWORD MockCurrentId(){return mode==8?7:1;}
BOOL MockTimes(HANDLE,LPFILETIME a,LPFILETIME,LPFILETIME,LPFILETIME){a->dwLowDateTime=mode==2?2:1;a->dwHighDateTime=0;return TRUE;}
DWORD MockSuspend(HANDLE){++suspended;return mode==3?DWORD(-1):mode==7?2:0;}
DWORD MockResume(HANDLE){++resumed;return mode==6?DWORD(-1):mode==7?2:1;}
BOOL MockContext(HANDLE,LPCONTEXT c){c->Rip=0;c->Rsp=uintptr_t(native_stack.data());return mode==4?FALSE:TRUE;}
BOOL MockClose(HANDLE){++closed;return TRUE;}
BOOL MockModule(DWORD,LPCSTR,HMODULE*){assert(resumed==1);++lookups;return FALSE;}
#define OpenThread MockOpenThread
#define GetCurrentThreadId MockCurrentId
#define GetThreadTimes MockTimes
#define SuspendThread MockSuspend
#define ResumeThread MockResume
#define GetThreadContext MockContext
#define CloseHandle MockClose
#define GetModuleHandleExA MockModule
#include "counter_worker_sample.h"
#undef OpenThread
#undef GetCurrentThreadId
#undef GetThreadTimes
#undef SuspendThread
#undef ResumeThread
#undef GetThreadContext
#undef CloseHandle
#undef GetModuleHandleExA
int main(){PPCContext c{};auto before=c;for(mode=0;mode<9;++mode){for(auto& w:workers)w.ready=0;auto& w=workers[0];w.thread=7;w.context=mode==5?1:uintptr_t(&c);w.creation=1;w.ready=2;opened=suspended=resumed=closed=lookups=0;const bool paired=SampleCounterWorkers(nullptr);assert(!std::memcmp(&before,&c,sizeof(c)));if(mode==6||mode==7)assert(!paired);else assert(paired);if(mode==1||mode==2||mode==8)assert(suspended==0&&resumed==0);else if(mode==3)assert(suspended==1&&resumed==0);else assert(suspended==1&&resumed==1);if(mode==8)assert(opened==0);if(mode==4)assert(lookups==0);}std::puts("WORKER_API modes=9 suspend_resume=paired failure_closed=1");}
''' + DELEGATES
