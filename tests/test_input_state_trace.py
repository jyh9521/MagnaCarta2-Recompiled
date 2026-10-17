"""Read-only SDK/PCH RAW input tracing; fixtures never launch the title."""
import hashlib,json,os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HEADER=ROOT/'src/host/input_state_trace.h'
class InputStateTraceTests(unittest.TestCase):
 def test_exact_target_and_original_delegate(self):
  s=HEADER.read_text();self.assertIn('REX_HOOK_RAW(sub_82868178)',s);self.assertIn('&__imp__sub_82868178',s)
 def test_default_off_bounded_ready(self):
  s=HEADER.read_text()
  for x in ['active{false}','kCapacity=8192','fetch_or(kFrozen','memory_order_release','memory_order_acquire','INPUT_STATE_PENDING','suppressed','weak_snapshot=1']:self.assertIn(x,s)
 def test_reads_only_after_success_through_existing_safe_reader(self):
  s=HEADER.read_text()
  for x in ['e.status!=0','DataRange(address,16)','po::ReadBytes','value.captured==16','not-read-status']:self.assertIn(x,s)
  for x in ['WriteProcessMemory','VirtualProtect','REX_STORE_','SetThreadContext','ctx.r3.u64=']:self.assertNotIn(x,s)
 def test_ordinary_range_and_errors_preserved(self):
  s=HEADER.read_text();self.assertIn('address>UINT32_MAX',s);self.assertIn('address+16>0x7F000000ULL',s);self.assertIn('SetLastError(result_error)',s);self.assertIn('errno=result_errno',s)
 @unittest.skipUnless(os.name=='nt','Windows SDK/COFF fixture')
 def test_actual_sdk_pch_dual_tu_fixture(self):
  from tools.research.compile_module import vc_environment
  from tools.research.probe_route_a import CLANG_CL_SHA256
  cc=ROOT/'local/upstream/llvm/unpacked/bin/clang-cl.exe';sdk=ROOT/'local/upstream/rexglue/sdk/win-amd64';pch=ROOT/'local/analysis/phase20/strict-codegen/project/generated/default-disc1';vc=Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat')
  if not cc.exists() or not sdk.exists() or not pch.exists() or not vc.exists():self.skipTest('optional pinned compiler/SDK/generated PCH/VC missing')
  self.assertEqual(hashlib.sha256(cc.read_bytes()).hexdigest(),CLANG_CL_SHA256)
  parent=ROOT/'local/analysis/phase26';parent.mkdir(parents=True,exist_ok=True);out=Path(tempfile.mkdtemp(prefix='input-state-mock-',dir=parent));(out/'main.cpp').write_text(MOCK);(out/'weak.cpp').write_text(WEAK)
  deps=[HEADER,ROOT/'src/host/schedule_observation.h',ROOT/'src/host/panic_observation.h',sdk/'include/rex/hook.h',pch/'mc2_probe_pch.h'];hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in deps}
  cmd=[str(cc),'/nologo','/std:c++latest','/EHa','/MD','/O2','/fp:strict','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/DSPDLOG_FMT_EXTERNAL','/DSPDLOG_COMPILED_LIB','/I'+str(sdk/'include'),'/I'+str(HEADER.parent),'/I'+str(pch),str(out/'main.cpp'),str(out/'weak.cpp'),'/Fe'+str(out/'mock.exe'),'/Fo'+str(out)+'\\','/link','/MAP:'+str(out/'mock.map')]
  v=subprocess.run(cmd,cwd=out,env=vc_environment(vc),capture_output=True,text=True,timeout=120);(out/'compile.txt').write_text(v.stdout+v.stderr);record={'compile_command':cmd,'compile_exit':v.returncode,'inputs':hashes};(out/'verification.json').write_text(json.dumps(record,indent=2));self.assertEqual(v.returncode,0,v.stdout+v.stderr)
  v=subprocess.run([str(out/'mock.exe')],cwd=out,capture_output=True,text=True,timeout=30);(out/'run.txt').write_text(v.stdout+v.stderr);record.update(run_exit=v.returncode,literal_output=v.stdout,inputs_unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items()));(out/'verification.json').write_text(json.dumps(record,indent=2));self.assertEqual(v.returncode,0,v.stdout+v.stderr);self.assertTrue(record['inputs_unchanged']);self.assertIn('INPUT_STATE_MOCK once=1 transparent=1 BE16=1 failure_no_read=1 guard=1 cap=1 freeze=1 concurrent=1 pending=1 throw=1',v.stdout)
WEAK=r'''
#include "mc2_probe_pch.h"
extern "C" void InputOriginal(PPCContext&,uint8_t*);
DEFINE_REX_FUNC(sub_82868178){REX_FUNC_PROLOGUE();InputOriginal(ctx,base);}
'''
MOCK=r'''
#include "input_state_trace.h"
#include <cassert>
#include <thread>
#include <vector>
#include <cstring>
using namespace mc2::host;
using namespace mc2::host::input_state_trace;
std::atomic<unsigned> invoked{0};std::atomic<bool> throwing{false},blocking{false},entered{false},released{false};
void Reset(){active=false;configured=false;reserved=0;calls=0;posts=0;dropped=0;suppressed=0;sequences=0;for(auto& e:entries)e.ready=false;throwing=false;blocking=false;entered=false;released=false;status="fixture";}
extern "C" void InputOriginal(PPCContext& ctx,uint8_t*){assert(errno==EAGAIN&&GetLastError()==0x1234);++invoked;ctx.r3.u64=ctx.r6.u64;ctx.r4.u64=0xABCD;ctx.r11.u64^=0x12345678;ctx.lr^=0x22;if(blocking){entered=true;while(!released)std::this_thread::yield();}errno=ERANGE;SetLastError(0x5678);if(throwing)throw 42;}
PPCContext Context(uint64_t address,uint64_t code=0){PPCContext ctx{};ctx.r3.u64=3;ctx.r4.u64=address;ctx.r6.u64=code;ctx.r1.u64=0x7018F000;ctx.lr=0x82345678;ctx.r11.u64=0xBAD;return ctx;}
void Call(uint8_t* base,uint64_t address=0x10000,uint64_t code=0){auto c=Context(address,code);errno=EAGAIN;SetLastError(0x1234);sub_82868178(c,base);assert(errno==ERANGE&&GetLastError()==0x5678);}
int main(){auto* memory=static_cast<uint8_t*>(VirtualAlloc(nullptr,0x4000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));assert(memory);auto* base=reinterpret_cast<uint8_t*>(uintptr_t(memory)-0x10000);for(unsigned i=0;i<16;++i)memory[i]=uint8_t(i);memory[4]=0;memory[5]=0x10;const auto expected=std::array<uint8_t,16>{0,1,2,3,0,16,6,7,8,9,10,11,12,13,14,15};
assert(&sub_82868178!=&__imp__sub_82868178);
for(bool enabled:{false,true}){Reset();assert(ConfigureInputStateTrace(enabled,enabled));auto a=Context(0x10000),b=a;auto before=invoked.load();errno=EAGAIN;SetLastError(0x1234);__imp__sub_82868178(a,base);errno=EAGAIN;SetLastError(0x1234);sub_82868178(b,base);assert(invoked==before+2&&std::memcmp(&a,&b,sizeof(a))==0);assert(errno==ERANGE&&GetLastError()==0x5678);assert(calls==unsigned(enabled)&&posts==unsigned(enabled));if(enabled){assert(reserved==1&&entries[0].ready&&entries[0].captured==16&&entries[0].bytes==expected&&entries[0].user==3&&entries[0].state_address==0x10000&&entries[0].lr==0x82345678&&entries[0].sp==0x7018F000);}}
Reset();assert(!ConfigureInputStateTrace(false,true));Call(base);assert(calls==0);assert(!ConfigureInputStateTrace(true,true));
Reset();assert(ConfigureInputStateTrace(true,true));Call(reinterpret_cast<uint8_t*>(1),0x7FC80000,0x48F);assert(entries[0].captured==0&&std::strcmp(entries[0].read_status,"not-read-status")==0);Call(base,0x7FC80000);assert(entries[1].captured==0&&std::strcmp(entries[1].read_status,"outside-ordinary-ram")==0);Call(base,0x100010000ULL);assert(entries[2].captured==0);
DWORD old=0;assert(VirtualProtect(memory,0x1000,PAGE_NOACCESS,&old));Call(base);assert(entries[3].captured==0&&std::strcmp(entries[3].read_status,"unreadable")==0);assert(VirtualProtect(memory,0x1000,PAGE_READWRITE|PAGE_GUARD,&old));Call(base,0x10000,0x48F);MEMORY_BASIC_INFORMATION mbi{};assert(VirtualQuery(memory,&mbi,sizeof(mbi))&&bool(mbi.Protect&PAGE_GUARD));assert(entries[4].captured==0&&std::strcmp(entries[4].read_status,"not-read-status")==0);Call(base);assert(VirtualQuery(memory,&mbi,sizeof(mbi))&&bool(mbi.Protect&PAGE_GUARD));assert(entries[5].captured==0);assert(VirtualProtect(memory,0x1000,PAGE_READWRITE,&old));assert(std::memcmp(memory,expected.data(),16)==0);Call(reinterpret_cast<uint8_t*>(1),0x82000000);assert(entries[6].captured==0&&std::strcmp(entries[6].read_status,"outside-ordinary-ram")==0);
Reset();assert(ConfigureInputStateTrace(true,true));throwing=true;auto c=Context(0x10000);errno=EAGAIN;SetLastError(0x1234);try{sub_82868178(c,base);assert(false);}catch(int x){assert(x==42);}assert(errno==ERANGE&&GetLastError()==0x5678&&calls==1&&posts==0&&reserved==0);throwing=false;
Reset();assert(ConfigureInputStateTrace(true,true));std::vector<std::thread> ts;for(int t=0;t<4;++t)ts.emplace_back([&]{for(int n=0;n<40;++n)Call(base);});for(auto& t:ts)t.join();assert(calls==160&&posts==160&&reserved==160);for(unsigned n=0;n<160;++n)assert(entries[n].ready&&entries[n].captured==16);
Reset();assert(ConfigureInputStateTrace(true,true));reserved=kCapacity-1;Call(base);Call(base);assert(reserved==kCapacity+1&&dropped==1);
Reset();assert(ConfigureInputStateTrace(true,true));blocking=true;std::thread pending([&]{Call(base);});while(!entered)std::this_thread::yield();FreezeInputStateTrace();released=true;pending.join();assert(calls==1&&posts==1&&suppressed==1&&(reserved.load()&~kFrozen)==0);const auto before=calls.load();Call(base);assert(calls==before);blocking=false;
Reset();assert(ConfigureInputStateTrace(true,true));Call(base);reserved=2;FreezeInputStateTrace();FILE* f=std::fopen("synthetic-input-trace.txt","wb+");assert(f);DumpInputStateTrace(f);std::rewind(f);char buf[2048]{};auto count=std::fread(buf,1,sizeof(buf)-1,f);buf[count]=0;assert(std::strstr(buf,"INPUT_STATE_TRACE status=frozen")&&std::strstr(buf,"INPUT_STATE_PENDING slot=1")&&std::strstr(buf,"000102030010060708090A0B0C0D0E0F"));std::fclose(f);DumpInputStateTrace(nullptr);const auto immutable=entries[0].bytes;memory[0]^=0xFF;Call(base);assert(entries[0].bytes==immutable);VirtualFree(memory,0,MEM_RELEASE);std::puts("INPUT_STATE_MOCK once=1 transparent=1 BE16=1 failure_no_read=1 guard=1 cap=1 freeze=1 concurrent=1 pending=1 throw=1");}
'''
