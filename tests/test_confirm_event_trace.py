"""Owned synthetic external-adapter/SDK RAW BE-read fixtures; no title execution."""
import hashlib,json,os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HEADER=ROOT/'src/host/confirm_event_trace.h'
class ConfirmEventTraceTests(unittest.TestCase):
 def test_default_off_attestation(self):
  s=HEADER.read_text();self.assertIn('active{false}',s);self.assertIn('enabled&&!codeverified',s);self.assertIn('configured.exchange(true)',s)
 def test_original_delegate_only(self):
  s=HEADER.read_text();self.assertNotIn('REX_HOOK_RAW(',s);self.assertNotIn('REX_EXTERN(',s);self.assertIn('Invoke(PPCContext& ctx,uint8_t* base,PPCFunc* original)',s);self.assertIn('original(ctx,base)',s)
 def test_exact_filter_and_user_guard(self):
  s=HEADER.read_text();self.assertIn('ctx.r4.u32!=10 || ctx.lr!=0x827B4DEC',s);self.assertIn('ctx.r5.u64>3',s)
 def test_readonly_bounded_word(self):
  s=HEADER.read_text();self.assertIn('0x4C0+uint64_t(user)*0xC0',s);self.assertIn('0xFFFFFFFCULL',s);self.assertIn('0x7F000000ULL',s)
  for t in ['REX_STORE','WriteProcessMemory','VirtualProtect','SetThreadContext','REX_CALL_INDIRECT_FUNC']:self.assertNotIn(t,s)
 def test_publication_freeze_and_pending(self):
  s=HEADER.read_text()
  for t in ['kCapacity=16384','memory_order_release','memory_order_acquire','fetch_or(kFrozen','CONFIRM_EVENT_PENDING','weak_snapshot=1','suppressed.fetch_add']:self.assertIn(t,s)
 def test_error_and_exception_transparency(self):
  s=HEADER.read_text();self.assertIn('errno=before_errno;SetLastError(before_error)',s);self.assertIn('errno=result_errno;SetLastError(result_error)',s);self.assertIn('if(!returned)unwound.fetch_add',s)
 @unittest.skipUnless(os.name=='nt','Windows pinned SDK RAW dual-TU fixture')
 def test_native_actual_sdk_hook(self):
  from tools.research.compile_module import vc_environment
  from tools.research.probe_route_a import CLANG_CL_SHA256
  cc=ROOT/'local/upstream/llvm/unpacked/bin/clang-cl.exe';sdk=ROOT/'local/upstream/rexglue/sdk/win-amd64';pch=ROOT/'local/analysis/phase20/strict-codegen/project/generated/default-disc1';vc=Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat')
  if not cc.exists() or not (pch/'mc2_probe_pch.h').exists():self.skipTest('optional pinned SDK/compiler absent')
  sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();self.assertEqual(sha(cc),CLANG_CL_SHA256)
  parent=ROOT/'local/analysis/phase27';parent.mkdir(parents=True,exist_ok=True);out=Path(tempfile.mkdtemp(prefix='confirm-event-mock-',dir=parent));main=out/'main.cpp';weak=out/'weak.cpp';main.write_text(MOCK);weak.write_text(WEAK)
  inputs={str(p):sha(p) for p in [HEADER,ROOT/'src/host/panic_observation.h',sdk/'include/rex/hook.h',pch/'mc2_probe_pch.h',main,weak]};r={'scope':'Actual SDK RAW/DEFINE weak alias two-TU linkage with owned synthetic private pages and delegates. No original game function/title execution.','success':False,'inputs':inputs}
  try:
   cmd=[str(cc),'/nologo','/std:c++latest','/EHa','/MD','/O2','/fp:strict','/arch:AVX2','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/DSPDLOG_FMT_EXTERNAL','/DSPDLOG_COMPILED_LIB','/I'+str(sdk/'include'),'/I'+str(HEADER.parent),'/I'+str(pch),str(main),str(weak),'/Fe'+str(out/'mock.exe'),'/Fo'+str(out)+'\\','/link','/MAP:'+str(out/'mock.map')]
   v=subprocess.run(cmd,cwd=out,env=vc_environment(vc),capture_output=True,text=True,timeout=120);(out/'compile.txt').write_text(v.stdout+v.stderr);r.update(compile_command=cmd,compile_exit=v.returncode);self.assertEqual(v.returncode,0,str(out)+'\n'+v.stdout+v.stderr)
   v=subprocess.run([str(out/'mock.exe')],cwd=out,capture_output=True,text=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW);(out/'run.txt').write_text(v.stdout+v.stderr);r.update(run_exit=v.returncode,literal_output=v.stdout,stderr=v.stderr);self.assertEqual(v.returncode,0,str(out)+'\n'+v.stdout+v.stderr)
   self.assertIn('CONFIRM_EVENT_MOCK equivalence=1 mxcsr=1 filter=1 user=1 be=1 readonly=1 noaccess=1 guard=1 overflow=1 mmio=1 throw=1 concurrent=1 capacity=1 frozen=1 pending=1',v.stdout)
   r['inputs_unchanged']=all(sha(Path(p))==v for p,v in inputs.items());self.assertTrue(r['inputs_unchanged']);r['exe_sha256']=sha(out/'mock.exe');r['success']=True
  finally:
   p=out/'verification.json';p.write_text(json.dumps(r,indent=2)+'\n');json.loads(p.read_text())

WEAK=r'''
#include "mc2_probe_pch.h"
extern "C" void TestDelegate(PPCContext&,uint8_t*);
DEFINE_REX_FUNC(sub_827B4938){TestDelegate(ctx,base);}
'''
MOCK=r'''
#include "confirm_event_trace.h"
REX_EXTERN(__imp__sub_827B4938);
REX_HOOK_RAW(sub_827B4938){mc2::host::confirm_event_trace::Invoke(ctx,base,&__imp__sub_827B4938);}
#include <cassert>
#include <thread>
#include <vector>
#include <set>
using namespace mc2::host;
using namespace mc2::host::confirm_event_trace;
std::atomic<unsigned> delegates{0};std::atomic<bool> writes{false},throwing{false},blocking{false},entered{false},released{false};
uint8_t* memory=nullptr;
constexpr uint32_t object=0x40001000,field=object+0x4C0;
void SetWord(uint32_t value){for(int n=0;n<4;++n)memory[field+n]=uint8_t(value>>(24-8*n));}
void Init(PPCContext& c){for(size_t i=0;i<sizeof(c);++i)((uint8_t*)&c)[i]=uint8_t(i*7+11);c.r3.u64=object;c.r4.u64=10;c.r5.u64=0;c.r6.u64=0x12345678ABCDEF01;c.r7.u64=255;c.lr=0x827B4DEC;}
extern "C" void TestDelegate(PPCContext& c,uint8_t* base){assert(errno==EAGAIN&&GetLastError()==0x1234);delegates.fetch_add(1);if(blocking){entered=true;while(!released)std::this_thread::yield();}if(writes)SetWord(255);for(size_t i=0;i<sizeof(c);++i)((uint8_t*)&c)[i]^=uint8_t(i*3+5);errno=ERANGE;SetLastError(0x5678);if(throwing)throw 42;}
void Reset(){active=false;configured=false;reserved=0;calls=0;posts=0;selected=0;selected_posts=0;invalid_user=0;unknown=0;unwound=0;inflight=0;dropped=0;suppressed=0;sequences=0;for(auto& e:entries)e.ready=false;writes=false;throwing=false;blocking=false;entered=false;released=false;}
void Call(){PPCContext c;Init(c);errno=EAGAIN;SetLastError(0x1234);sub_827B4938(c,memory);assert(errno==ERANGE&&GetLastError()==0x5678);}
int main(){
 memory=(uint8_t*)VirtualAlloc(nullptr,0x100001000ULL,MEM_RESERVE,PAGE_NOACCESS);assert(memory);assert(VirtualAlloc(memory+object,4096,MEM_COMMIT,PAGE_READWRITE));
 assert(&sub_827B4938!=&__imp__sub_827B4938);SetWord(0x12345678);
 const auto csr=PPCFPSCRRegister::Platform::getcsr();
 for(unsigned enabled=0;enabled<2;++enabled){Reset();assert(ConfigureConfirmEventTrace(enabled,enabled));assert(!ConfigureConfirmEventTrace(true,true));PPCContext a,b;Init(a);std::memcpy(&b,&a,sizeof(a));writes=true;SetWord(7);errno=EAGAIN;SetLastError(0x1234);const auto before=delegates.load();PPCFPSCRRegister::Platform::setcsr(0x9FC0);__imp__sub_827B4938(a,memory);assert(errno==ERANGE&&GetLastError()==0x5678);uint8_t snapshot[4096];std::memcpy(snapshot,memory+object,4096);SetWord(7);errno=EAGAIN;SetLastError(0x1234);sub_827B4938(b,memory);assert(errno==ERANGE&&GetLastError()==0x5678);assert(PPCFPSCRRegister::Platform::getcsr()==0x9FC0);assert(std::memcmp(&a,&b,sizeof(a))==0&&std::memcmp(snapshot,memory+object,4096)==0&&delegates==before+2);assert(calls==enabled&&posts==enabled);if(enabled){assert(entries[0].old_known&&entries[0].old_word==7&&entries[1].old_word==255);assert(entries[0].args[3]==0x12345678ABCDEF01);}}
 Reset();assert(!ConfigureConfirmEventTrace(false,true));Call();assert(calls==0);
 Reset();assert(ConfigureConfirmEventTrace(true,true));PPCContext c;Init(c);c.r4.u64=4;errno=EAGAIN;SetLastError(0x1234);sub_827B4938(c,nullptr);Init(c);c.lr+=4;errno=EAGAIN;SetLastError(0x1234);sub_827B4938(c,nullptr);Init(c);c.r5.u64=0x100000000ULL;errno=EAGAIN;SetLastError(0x1234);sub_827B4938(c,nullptr);assert(calls==0&&reserved==0&&invalid_user==1);
 Reset();assert(ConfigureConfirmEventTrace(true,true));SetWord(0x12345678);Call();assert(entries[0].old_word==0x12345678&&entries[1].old_word==0x12345678);
 for(unsigned user=1;user<=3;++user){Reset();assert(ConfigureConfirmEventTrace(true,true));const uint32_t at=field+0xC0*user,value=0x12345678+user;for(int n=0;n<4;++n)memory[at+n]=uint8_t(value>>(24-8*n));Init(c);c.r5.u64=user;errno=EAGAIN;SetLastError(0x1234);sub_827B4938(c,memory);assert(entries[0].old_known&&entries[0].old_word==value&&entries[1].old_word==value);}
 DWORD old=0;assert(VirtualProtect(memory+object,4096,PAGE_READONLY,&old));Reset();assert(ConfigureConfirmEventTrace(true,true));Call();assert(entries[0].old_known&&entries[1].old_known);
 assert(VirtualProtect(memory+object,4096,PAGE_NOACCESS,&old));Reset();assert(ConfigureConfirmEventTrace(true,true));Call();assert(unknown==2&&!entries[0].old_known&&entries[0].old_word==0);
 assert(VirtualProtect(memory+object,4096,PAGE_READWRITE|PAGE_GUARD,&old));Reset();assert(ConfigureConfirmEventTrace(true,true));Call();MEMORY_BASIC_INFORMATION info{};assert(VirtualQuery(memory+object,&info,sizeof(info)));assert(info.Protect&PAGE_GUARD);assert(unknown==2);assert(VirtualProtect(memory+object,4096,PAGE_READWRITE,&old));
 Reset();assert(ConfigureConfirmEventTrace(true,true));Init(c);c.r3.u64=0xFFFFFFF0;errno=EAGAIN;SetLastError(0x1234);sub_827B4938(c,nullptr);assert(unknown==2&&std::strcmp(entries[0].old_status,"address-overflow")==0);
 Reset();assert(ConfigureConfirmEventTrace(true,true));Init(c);c.r3.u64=0x80000000;errno=EAGAIN;SetLastError(0x1234);sub_827B4938(c,nullptr);assert(unknown==2&&std::strcmp(entries[0].old_status,"outside-ram")==0);
 Reset();assert(ConfigureConfirmEventTrace(true,true));throwing=true;Init(c);errno=EAGAIN;SetLastError(0x1234);try{sub_827B4938(c,memory);assert(false);}catch(int n){assert(n==42);}assert(errno==ERANGE&&GetLastError()==0x5678&&unwound==1&&inflight==0&&calls==1&&posts==0);
 Reset();assert(ConfigureConfirmEventTrace(true,true));std::vector<std::thread> workers;for(int t=0;t<4;++t)workers.emplace_back([]{for(int n=0;n<100;++n)Call();});for(auto& t:workers)t.join();assert(calls==400&&posts==400&&reserved==800);std::set<uint64_t> seq;for(size_t i=0;i<800;++i){assert(entries[i].ready);assert(seq.insert(entries[i].seq).second);}
 Reset();assert(ConfigureConfirmEventTrace(true,true));reserved=kCapacity-1;Call();assert(dropped==1&&reserved==kCapacity+1);
 Reset();assert(ConfigureConfirmEventTrace(true,true));blocking=true;std::thread pending([]{Call();});while(!entered)std::this_thread::yield();assert(inflight==1&&reserved==1&&entries[0].ready);FreezeConfirmEventTrace();released=true;pending.join();assert(inflight==0&&posts==1&&suppressed==1&&(reserved.load()&~kFrozen)==1);auto saved=calls.load();Call();assert(calls==saved);
 FILE* f=std::fopen("trace.txt","wb");assert(f);DumpConfirmEventTrace(f);assert(std::fclose(f)==0);Reset();reserved=1;FreezeConfirmEventTrace();f=std::tmpfile();assert(f);DumpConfirmEventTrace(f);std::rewind(f);char text[8192]{};auto n=std::fread(text,1,sizeof(text)-1,f);text[n]=0;assert(std::strstr(text,"CONFIRM_EVENT_PENDING slot=0"));std::fclose(f);DumpConfirmEventTrace(nullptr);
 PPCFPSCRRegister::Platform::setcsr(csr);VirtualFree(memory,0,MEM_RELEASE);
 std::puts("CONFIRM_EVENT_MOCK equivalence=1 mxcsr=1 filter=1 user=1 be=1 readonly=1 noaccess=1 guard=1 overflow=1 mmio=1 throw=1 concurrent=1 capacity=1 frozen=1 pending=1");
}
'''
if __name__=='__main__':unittest.main()
