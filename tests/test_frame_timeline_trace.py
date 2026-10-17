"""SDK RAW hook transparency and bounded timeline fixtures; no title execution."""
import hashlib,json,os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HEADER=ROOT/'src/host/frame_timeline_trace.h'
TARGETS=['8277B6D8','8244A360','8286E618','82E20568','82399778']
class FrameTimelineTests(unittest.TestCase):
 def test_default_off_and_attestation(self):
  s=HEADER.read_text();self.assertIn('active{false}',s);self.assertIn('enabled&&!codeverified',s);self.assertIn('configured.exchange(true)',s)
 def test_exact_targets_and_original_delegates(self):
  s=HEADER.read_text()
  for target in TARGETS:self.assertIn('REX_HOOK_RAW(sub_'+target+')',s);self.assertIn('&__imp__sub_'+target,s)
  for target in ['82399650','82399738','822D0A68']:self.assertNotIn('REX_HOOK_RAW(sub_'+target+')',s)
 def test_no_guest_reads_writes_or_inline_logging(self):
  s=HEADER.read_text();wrapper=s.split('template<size_t Kind>')[1].split('} // namespace frame_timeline')[0]
  for text in ['ReadProcessMemory','WriteProcessMemory','VirtualProtect','printf','SetThreadContext','CaptureStackBackTrace']:self.assertNotIn(text,wrapper)
  self.assertIn('errno=result_errno;SetLastError(result_error)',wrapper)
 def test_bounded_publication_and_freeze(self):
  s=HEADER.read_text()
  for text in ['kCapacity=8192','memory_order_acquire','memory_order_release','fetch_or(kFrozen','suppressed.fetch_add','TIMELINE_PENDING','weak_snapshot=1']:self.assertIn(text,s)
 def test_parent_depth_and_exception_scope(self):
  s=HEADER.read_text()
  for text in ['current_depth=0','previous_depth','scope.returned=true','part.unwound.fetch_add','part.inflight.fetch_sub']:self.assertIn(text,s)
 def test_raw_macro_actual_sdk(self):
  p=ROOT/'local/upstream/rexglue/sdk/win-amd64/include/rex/hook.h'
  if not p.exists():self.skipTest('optional pinned SDK absent')
  self.assertIn('#define REX_HOOK_RAW(name) extern "C" REX_FUNC(name)',p.read_text())
 @unittest.skipUnless(os.name=='nt','Windows SDK/COFF macro fixture')
 def test_native_actual_header_strong_weak_transparency(self):
  from tools.research.compile_module import vc_environment
  from tools.research.probe_route_a import CLANG_CL_SHA256
  cc=ROOT/'local/upstream/llvm/unpacked/bin/clang-cl.exe';sdk=ROOT/'local/upstream/rexglue/sdk/win-amd64';pch=ROOT/'local/analysis/phase20/strict-codegen/project/generated/default-disc1'
  if not cc.exists() or not sdk.exists() or not pch.exists():self.skipTest('optional compiler/SDK/generated PCH absent')
  self.assertEqual(hashlib.sha256(cc.read_bytes()).hexdigest(),CLANG_CL_SHA256)
  out=Path(tempfile.mkdtemp(prefix='timeline-mock-',dir=ROOT/'local/analysis/phase25'));source=out/'main.cpp';weak=out/'weak.cpp';source.write_text(MOCK);weak.write_text(WEAK)
  hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [HEADER,sdk/'include/rex/hook.h',pch/'mc2_probe_pch.h']}
  command=[str(cc),'/nologo','/std:c++latest','/EHa','/MD','/O2','/fp:strict','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/DSPDLOG_FMT_EXTERNAL','/DSPDLOG_COMPILED_LIB','/I'+str(sdk/'include'),'/I'+str(HEADER.parent),'/I'+str(pch),str(source),str(weak),'/Fe'+str(out/'mock.exe'),'/Fo'+str(out)+'\\','/link','/MAP:'+str(out/'mock.map')];env=vc_environment(Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat'));v=subprocess.run(command,cwd=out,env=env,capture_output=True,text=True,timeout=120);r={'compile_command':command,'compile_exit':v.returncode,'inputs':hashes};(out/'compile.txt').write_text(v.stdout+v.stderr);(out/'verification.json').write_text(json.dumps(r,indent=2));self.assertEqual(v.returncode,0,v.stdout+v.stderr)
  v=subprocess.run([str(out/'mock.exe')],cwd=out,capture_output=True,text=True,timeout=30);(out/'run.txt').write_text(v.stdout+v.stderr);r.update(run_command=[str(out/'mock.exe')],run_exit=v.returncode,literal_output=v.stdout,inputs_unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items()));(out/'verification.json').write_text(json.dumps(r,indent=2));self.assertEqual(v.returncode,0,v.stdout+v.stderr);self.assertTrue(r['inputs_unchanged']);self.assertIn('TIMELINE_MOCK equivalence=5 nested=5 tls=1 mxcsr=1 throw=1 concurrent=1 drop=1 suppressed=1 pending=1',v.stdout)

WEAK='#include "mc2_probe_pch.h"\n'+''.join(f'extern "C" void TestOriginal{i}(PPCContext&,uint8_t*);\nDEFINE_REX_FUNC(sub_{target}){{REX_FUNC_PROLOGUE();TestOriginal{i}(ctx,base);}}\n' for i,target in enumerate(TARGETS))
MOCK=r'''
#include "frame_timeline_trace.h"
#include <cassert>
#include <thread>
#include <vector>
#include <set>
using namespace mc2::host;
using namespace mc2::host::frame_timeline;
std::atomic<unsigned> delegates{0};std::atomic<bool> nested{false},throwing{false},blocking{false},release{false},entered{false};
void Fixture(PPCContext& ctx,std::array<uint8_t,128>& mem){for(size_t i=0;i<sizeof(ctx);++i)((uint8_t*)&ctx)[i]=uint8_t(i*7+11);ctx.r3.u64=0x1234567800000020;for(size_t i=0;i<mem.size();++i)mem[i]=uint8_t(i*17);}
PPCFunc* originals[]={&__imp__sub_8277B6D8,&__imp__sub_8244A360,&__imp__sub_8286E618,&__imp__sub_82E20568,&__imp__sub_82399778};
PPCFunc* wrappers[]={&sub_8277B6D8,&sub_8244A360,&sub_8286E618,&sub_82E20568,&sub_82399778};
void Common(unsigned kind,PPCContext& ctx,uint8_t* base){assert(errno==EAGAIN&&GetLastError()==0x1234);++delegates;if(nested.load()&&kind<4)wrappers[kind+1](ctx,base);if(blocking.load()){entered=true;while(!release.load())std::this_thread::yield();}for(size_t i=0;i<sizeof(ctx);++i)((uint8_t*)&ctx)[i]^=uint8_t(i*3+kind+5);base[11]^=0x5A;errno=ERANGE;SetLastError(0x5678);if(throwing.load())throw 42;}
extern "C" void TestOriginal0(PPCContext& c,uint8_t*b){Common(0,c,b);}extern "C" void TestOriginal1(PPCContext& c,uint8_t*b){Common(1,c,b);}extern "C" void TestOriginal2(PPCContext& c,uint8_t*b){Common(2,c,b);}extern "C" void TestOriginal3(PPCContext& c,uint8_t*b){Common(3,c,b);}extern "C" void TestOriginal4(PPCContext& c,uint8_t*b){Common(4,c,b);}
void Reset(){active=false;configured=false;calls=0;posts=0;unwound=0;inflight=0;sequences=0;current_call=0;current_depth=0;for(auto& p:partitions){p.reserved=0;p.pre=0;p.post=0;p.unwound=0;p.inflight=0;p.dropped=0;p.suppressed=0;for(auto& e:p.entries)e.ready=false;}nested=false;throwing=false;blocking=false;release=false;entered=false;}
void Call(size_t kind){PPCContext c;std::array<uint8_t,128> m;Fixture(c,m);errno=EAGAIN;SetLastError(0x1234);wrappers[kind](c,m.data());assert(errno==ERANGE&&GetLastError()==0x5678);}
int main(){const auto original_csr=PPCFPSCRRegister::Platform::getcsr();
for(unsigned mode=0;mode<2;++mode)for(size_t kind=0;kind<5;++kind){Reset();assert(ConfigureFrameTimeline(mode,mode));assert(!ConfigureFrameTimeline(true,true));PPCContext a,b;std::array<uint8_t,128> ma,mb;Fixture(a,ma);std::memcpy(&b,&a,sizeof(a));mb=ma;auto initial=delegates.load();const unsigned csr=0x1F80u|((kind%4)<<13)|0x8040u|(kind&0x3Fu);PPCFPSCRRegister::Platform::setcsr(csr);errno=EAGAIN;SetLastError(0x1234);originals[kind](a,ma.data());assert(PPCFPSCRRegister::Platform::getcsr()==csr);errno=EAGAIN;SetLastError(0x1234);wrappers[kind](b,mb.data());assert(PPCFPSCRRegister::Platform::getcsr()==csr&&errno==ERANGE&&GetLastError()==0x5678);assert(delegates==initial+2&&std::memcmp(&a,&b,sizeof(a))==0&&ma==mb);assert(calls==mode&&posts==mode&&inflight==0&&unwound==0);if(mode){auto& p=partitions[kind];auto& pre=p.entries[0];auto& post=p.entries[1];assert(p.reserved==2&&pre.ready&&post.ready&&pre.args==post.args&&pre.depth==1&&post.depth==1&&pre.parent==0&&pre.tick_ms<=post.tick_ms&&pre.seq<post.seq);assert(pre.result==pre.args[0]&&post.result==b.r3.u64);}}
for(unsigned mode=0;mode<2;++mode){Reset();assert(ConfigureFrameTimeline(mode,mode));throwing=true;PPCContext a,b;std::array<uint8_t,128> ma,mb;Fixture(a,ma);std::memcpy(&b,&a,sizeof(a));mb=ma;errno=EAGAIN;SetLastError(0x1234);try{originals[2](a,ma.data());assert(false);}catch(int e){assert(e==42);}const DWORD error=GetLastError();const int err=errno;errno=EAGAIN;SetLastError(0x1234);try{wrappers[2](b,mb.data());assert(false);}catch(int e){assert(e==42);}assert(std::memcmp(&a,&b,sizeof(a))==0&&ma==mb&&GetLastError()==error&&errno==err&&inflight==0&&current_call==0&&current_depth==0&&unwound==mode);}
Reset();assert(!ConfigureFrameTimeline(false,true));Call(0);assert(calls==0);Reset();assert(ConfigureFrameTimeline(true,true));nested=true;Call(0);assert(calls==5&&posts==5&&current_call==0&&current_depth==0);for(size_t kind=0;kind<5;++kind){auto& p=partitions[kind];assert(p.entries[0].depth==kind+1&&p.entries[1].depth==kind+1&&p.entries[0].parent==kind&&p.entries[1].parent==kind);}
Reset();assert(ConfigureFrameTimeline(true,true));nested=true;throwing=true;PPCContext c;std::array<uint8_t,128> m;Fixture(c,m);errno=EAGAIN;SetLastError(0x1234);try{wrappers[0](c,m.data());assert(false);}catch(int x){assert(x==42);}assert(errno==ERANGE&&GetLastError()==0x5678&&current_call==0&&current_depth==0&&calls==5&&posts==0&&unwound==5&&inflight==0);for(auto& p:partitions)assert(p.pre==1&&p.post==0&&p.unwound==1&&p.inflight==0);
Reset();assert(ConfigureFrameTimeline(true,true));std::vector<std::thread> threads;for(int t=0;t<4;++t)threads.emplace_back([t]{for(int n=0;n<100;++n)Call((n+t)%5);});for(auto& t:threads)t.join();assert(calls==400&&posts==400&&inflight==0);std::set<uint64_t> seq;for(auto& p:partitions)for(size_t i=0;i<p.reserved.load();++i){assert(p.entries[i].ready);assert(seq.insert(p.entries[i].seq).second);}assert(seq.size()==800);
Reset();assert(ConfigureFrameTimeline(true,true));partitions[0].reserved=kCapacity-1;Call(0);assert(partitions[0].dropped==1&&partitions[0].reserved==kCapacity+1);Call(4);assert(partitions[4].reserved==2&&partitions[4].dropped==0);
Reset();assert(ConfigureFrameTimeline(true,true));blocking=true;std::thread wait([]{Call(0);});while(!entered.load())std::this_thread::yield();assert(inflight==1&&partitions[0].pre==1&&partitions[0].post==0&&partitions[0].entries[0].ready);FreezeFrameTimeline();release=true;wait.join();assert(inflight==0&&posts==1&&partitions[0].suppressed==1&&partitions[0].dropped==0&&(partitions[0].reserved.load()&~kFrozen)==1);auto count=calls.load();Call(1);assert(calls==count);FILE*f=std::fopen("synthetic-timeline.txt","wb");assert(f);DumpFrameTimeline(f);assert(std::ftell(f)>0);std::fclose(f);DumpFrameTimeline(nullptr);
Reset();partitions[0].reserved=1;FreezeFrameTimeline();f=std::tmpfile();assert(f);DumpFrameTimeline(f);std::rewind(f);char text[8192]{};auto bytes=std::fread(text,1,sizeof(text)-1,f);text[bytes]=0;assert(std::strstr(text,"TIMELINE_PENDING slot=0"));std::fclose(f);PPCFPSCRRegister::Platform::setcsr(original_csr);std::puts("TIMELINE_MOCK equivalence=5 nested=5 tls=1 mxcsr=1 throw=1 concurrent=1 drop=1 suppressed=1 pending=1");}
'''
