"""RAW strong/weak delegation fixture, never game/title execution."""
import hashlib,json,os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HEADER=ROOT/'src/host/counter_lifecycle_trace.h'
class CounterTraceTests(unittest.TestCase):
 def test_twenty_extra_words(self):self.assertIn('kExtraWords=20',HEADER.read_text())
 def test_default_off_guard_and_once_delegation(self):
  s=HEADER.read_text();self.assertIn('active{false}',s);self.assertIn('enabled&&(!codeverified||!hook)',s);self.assertIn('original(ctx,base);return;',s);self.assertIn('ParentScope scope(call,pre.selection==1);original(ctx,base);',s)
 def test_three_exact_raw_targets(self):
  s=HEADER.read_text()
  for target in ['82399650','82399738','822D0A68']:
   self.assertIn('REX_HOOK_RAW(sub_'+target+')',s);self.assertIn('&__imp__sub_'+target,s)
 def test_readonly_callbacks_and_no_guest_operation(self):
  s=HEADER.read_text();self.assertIn('const PPCContext&',s);self.assertIn('const CounterExtra&',s)
  for bad in ['ReadProcessMemory','WriteProcessMemory','VirtualProtect','KernelState','ctx.r3.u64=','#undef']:self.assertNotIn(bad,s)
 def test_bounded_ready_freeze_and_selection_counters(self):
  s=HEADER.read_text()
  for text in ['kCapacity=8192','memory_order_release','memory_order_acquire','fetch_or(kFrozen','unknown_post','selected_post','COUNTER_PENDING','weak_snapshot=1']:self.assertIn(text,s)
 def test_real_sdk_macro_definition(self):
  sdk=ROOT/'local/upstream/rexglue/sdk/win-amd64/include/rex/hook.h'
  if not sdk.exists():self.skipTest('optional pinned SDK absent')
  self.assertIn('#define REX_HOOK_RAW(name) extern "C" REX_FUNC(name)',sdk.read_text())
 @unittest.skipUnless(os.name=='nt','Windows actual SDK macro/COFF fixture')
 def test_native_strong_weak_transparency(self):
  from tools.research.compile_module import vc_environment
  from tools.research.probe_route_a import CLANG_CL_SHA256
  cc=ROOT/'local/upstream/llvm/unpacked/bin/clang-cl.exe';sdk=ROOT/'local/upstream/rexglue/sdk/win-amd64';pch=ROOT/'local/analysis/phase20/strict-codegen/project/generated/default-disc1'
  if not cc.exists() or not sdk.exists() or not pch.exists():self.skipTest('optional pinned compiler/SDK/generated PCH absent')
  self.assertEqual(hashlib.sha256(cc.read_bytes()).hexdigest(),CLANG_CL_SHA256)
  outroot=ROOT/'local/analysis/phase24';outroot.mkdir(parents=True,exist_ok=True);out=Path(tempfile.mkdtemp(prefix='counter-mock-',dir=outroot));source=out/'main.cpp';weak=out/'weak.cpp';source.write_text(MOCK);weak.write_text(WEAK)
  hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [HEADER,sdk/'include/rex/hook.h',pch/'mc2_probe_pch.h']}
  cmd=[str(cc),'/nologo','/std:c++latest','/EHa','/MD','/O2','/fp:strict','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/DSPDLOG_FMT_EXTERNAL','/DSPDLOG_COMPILED_LIB','/I'+str(sdk/'include'),'/I'+str(HEADER.parent),'/I'+str(pch),str(source),str(weak),'/Fe'+str(out/'mock.exe'),'/Fo'+str(out)+'\\','/link','/MAP:'+str(out/'mock.map')]
  env=vc_environment(Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat'));v=subprocess.run(cmd,cwd=out,env=env,capture_output=True,text=True,timeout=120);(out/'compile.txt').write_text(v.stdout+v.stderr);r={'compile_command':cmd,'compile_exit':v.returncode,'inputs':hashes};(out/'verification.json').write_text(json.dumps(r,indent=2));self.assertEqual(v.returncode,0,v.stdout+v.stderr)
  v=subprocess.run([str(out/'mock.exe')],cwd=out,capture_output=True,text=True,timeout=30);(out/'run.txt').write_text(v.stdout+v.stderr);r.update(run_command=[str(out/'mock.exe')],run_exit=v.returncode,literal_output=v.stdout,inputs_unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items()));(out/'verification.json').write_text(json.dumps(r,indent=2));self.assertEqual(v.returncode,0,v.stdout+v.stderr);self.assertTrue(r['inputs_unchanged']);self.assertIn('COUNTER_MOCK equivalence=3 raw_strong_weak=1 tls=1 selection=1 throw=1 concurrent=1 drop=1 pending=1',v.stdout)

WEAK=r'''
#include "mc2_probe_pch.h"
extern "C" void TestOriginal0(PPCContext&,uint8_t*);
extern "C" void TestOriginal1(PPCContext&,uint8_t*);
extern "C" void TestOriginal2(PPCContext&,uint8_t*);
DEFINE_REX_FUNC(sub_82399650){REX_FUNC_PROLOGUE();TestOriginal0(ctx,base);}
DEFINE_REX_FUNC(sub_82399738){REX_FUNC_PROLOGUE();TestOriginal1(ctx,base);}
DEFINE_REX_FUNC(sub_822D0A68){REX_FUNC_PROLOGUE();TestOriginal2(ctx,base);}
'''
MOCK=r'''
#include "counter_lifecycle_trace.h"
#include <cassert>
#include <thread>
#include <vector>
using namespace mc2::host;
using namespace mc2::host::counter_trace;
std::atomic<unsigned> delegates{0},hooks{0};
std::atomic<unsigned> selection{1};
std::atomic<bool> throwing{false},nested{false},blocking{false},release{false},entered{false},hook_failure{false};
void Fixture(PPCContext& ctx,std::array<uint8_t,128>& mem){for(size_t i=0;i<sizeof(ctx);++i)((uint8_t*)&ctx)[i]=uint8_t(i*7+13);ctx.r3.u64=0x1234567800000020;for(size_t i=0;i<mem.size();++i)mem[i]=uint8_t(i*17);}
void Common(unsigned kind,PPCContext& ctx,uint8_t* base){assert(errno==EAGAIN&&GetLastError()==0x1234);++delegates;if(kind==0&&nested.load())sub_822D0A68(ctx,base);if(blocking.load()){entered=true;while(!release.load())std::this_thread::yield();}for(size_t i=0;i<sizeof(ctx);++i)((uint8_t*)&ctx)[i]^=uint8_t(i*3+kind+5);base[11]^=0x5A;errno=ERANGE;SetLastError(0x5678);if(throwing.load())throw 42;}
extern "C" void TestOriginal0(PPCContext& ctx,uint8_t* base){Common(0,ctx,base);}
extern "C" void TestOriginal1(PPCContext& ctx,uint8_t* base){Common(1,ctx,base);}
extern "C" void TestOriginal2(PPCContext& ctx,uint8_t* base){Common(2,ctx,base);}
CounterExtra Hook(uint32_t target,uint32_t phase,const PPCContext& ctx,uint8_t*,const std::array<uint64_t,8>& args,uint64_t,const CounterExtra& pre){++hooks;if(hook_failure.load())throw 99;CounterExtra e;e.selection=selection.load();e.flags=7;e.values[0]=args[0];e.values[1]=ctx.r3.u64;e.values[19]=CurrentCounterParentCall();if(phase==0)assert(args[0]==ctx.r3.u64);else{assert(pre.values[0]==args[0]);assert(ctx.r3.u64!=args[0]);}errno=EDOM;SetLastError(999);return e;}
void Reset(){active=false;configured=false;calls=0;posts=0;sequences=0;parent_call=0;for(auto& p:partitions){p.reserved=0;p.pre=0;p.post=0;p.selected=0;p.selected_post=0;p.unknown=0;p.unknown_post=0;p.dropped=0;p.suppressed=0;for(auto& e:p.entries)e.ready=false;}selection=1;throwing=false;nested=false;blocking=false;release=false;entered=false;hook_failure=false;status="test-reset";assert(SetCounterLifecycleHook(Hook));}
PPCFunc* originals[]={&__imp__sub_82399650,&__imp__sub_82399738,&__imp__sub_822D0A68};
PPCFunc* wrappers[]={&sub_82399650,&sub_82399738,&sub_822D0A68};
void Call(size_t kind){PPCContext c;std::array<uint8_t,128> m;Fixture(c,m);errno=EAGAIN;SetLastError(0x1234);wrappers[kind](c,m.data());assert(errno==ERANGE&&GetLastError()==0x5678);}
int main(){
for(unsigned mode=0;mode<2;++mode)for(size_t kind=0;kind<3;++kind){Reset();assert(ConfigureCounterLifecycleTrace(mode,mode));PPCContext a,b;std::array<uint8_t,128> ma,mb;Fixture(a,ma);std::memcpy(&b,&a,sizeof(a));mb=ma;auto start=delegates.load();errno=EAGAIN;SetLastError(0x1234);originals[kind](a,ma.data());errno=EAGAIN;SetLastError(0x1234);wrappers[kind](b,mb.data());assert(delegates==start+2);assert(std::memcmp(&a,&b,sizeof(a))==0&&ma==mb);assert(errno==ERANGE&&GetLastError()==0x5678);assert(calls==mode&&posts==mode);if(mode){auto& p=partitions[kind];assert(p.reserved==2&&p.entries[0].ready&&p.entries[1].ready);assert(p.entries[0].args==p.entries[1].args);assert(p.entries[1].extra.values[0]==p.entries[0].args[0]);}}
Reset();assert(!ConfigureCounterLifecycleTrace(false,true));Call(0);assert(calls==0);
Reset();assert(ConfigureCounterLifecycleTrace(true,true));hook_failure=true;Call(0);assert(partitions[0].unknown==1&&partitions[0].reserved==0&&posts==1);
Reset();assert(ConfigureCounterLifecycleTrace(true,true));selection=0;Call(0);assert(partitions[0].selected==0&&partitions[0].reserved==0);selection=2;Call(0);assert(partitions[0].unknown==1&&partitions[0].reserved==0);
Reset();assert(ConfigureCounterLifecycleTrace(true,true));nested=true;Call(0);assert(CurrentCounterParentCall()==0&&partitions[2].entries[0].parent==1&&partitions[2].entries[0].call==2&&partitions[0].entries[1].parent==0);nested=false;
Reset();assert(ConfigureCounterLifecycleTrace(true,true));throwing=true;PPCContext c;std::array<uint8_t,128> m;Fixture(c,m);errno=EAGAIN;SetLastError(0x1234);try{wrappers[0](c,m.data());assert(false);}catch(int x){assert(x==42);}assert(errno==ERANGE&&GetLastError()==0x5678&&CurrentCounterParentCall()==0&&partitions[0].pre==1&&partitions[0].post==0&&partitions[0].reserved==1);throwing=false;
Reset();assert(ConfigureCounterLifecycleTrace(true,true));std::vector<std::thread> threads;for(int t=0;t<4;++t)threads.emplace_back([]{for(int n=0;n<50;++n)Call(1);});for(auto& t:threads)t.join();assert(partitions[1].pre==200&&partitions[1].post==200&&partitions[1].reserved==400);for(size_t n=0;n<400;++n)assert(partitions[1].entries[n].ready);
Reset();assert(ConfigureCounterLifecycleTrace(true,true));partitions[0].reserved=kCapacity-1;Call(0);assert(partitions[0].reserved==kCapacity+1&&partitions[0].dropped==1);Call(2);assert(partitions[2].reserved==2&&partitions[2].dropped==0);
Reset();assert(ConfigureCounterLifecycleTrace(true,true));blocking=true;std::thread wait([]{Call(0);});while(!entered.load())std::this_thread::yield();assert(partitions[0].entries[0].ready&&partitions[0].post==0);FreezeCounterLifecycleTrace();release=true;wait.join();assert(partitions[0].post==1&&partitions[0].suppressed==1&&partitions[0].dropped==0&&(partitions[0].reserved.load()&~kFrozen)==1&&CurrentCounterParentCall()==0);auto snapshot=calls.load();Call(1);assert(calls==snapshot);FILE* f=std::fopen("synthetic-counter-trace.txt","wb+");assert(f);DumpCounterLifecycleTrace(f);assert(std::ftell(f)>0);std::rewind(f);char line[512]{};assert(std::fgets(line,sizeof(line),f));assert(std::strstr(line,"COUNTER_TRACE status=frozen"));std::fclose(f);DumpCounterLifecycleTrace(nullptr);
Reset();partitions[0].reserved=1;FreezeCounterLifecycleTrace();f=std::tmpfile();assert(f);DumpCounterLifecycleTrace(f);std::rewind(f);char pending[4096]{};auto length=std::fread(pending,1,sizeof(pending)-1,f);pending[length]=0;assert(std::strstr(pending,"COUNTER_PENDING slot=0"));std::fclose(f);
std::puts("COUNTER_MOCK equivalence=3 raw_strong_weak=1 tls=1 selection=1 throw=1 concurrent=1 drop=1 pending=1");}
'''
