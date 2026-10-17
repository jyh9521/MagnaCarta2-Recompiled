"""Scoped schedule observer contracts and native Windows synthetic delegates."""
import hashlib,json,os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HEADER=ROOT/'src/host/schedule_import_trace.h'

class ScheduleTraceTests(unittest.TestCase):
    def setUp(self):self.source=HEADER.read_text()
    def test_default_off_and_parent_attestation(self):
        self.assertIn('active{false}',self.source);self.assertIn('if (!verified)',self.source)
        self.assertLess(self.source.index('if (!verified)'),self.source.index('GetProcAddress(runtime'))
        self.assertIn('e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a',self.source)
    def test_overflow_accounting_per_api(self):
        self.assertIn('SCHEDULE_API api=',self.source)
        self.assertIn('api_pre[Api].fetch_add',self.source)
        self.assertIn('api_post[Api].fetch_add',self.source)
        self.assertIn('api_overflow[api].fetch_add',self.source)
    def test_exact_three_exports(self):
        for n in ['KeDelayExecutionThread','RtlEnterCriticalSection','RtlLeaveCriticalSection']:self.assertIn('"__imp__'+n+'"',self.source)
        self.assertIn('kCount=3',self.source)
    def test_time_bounded_partitioned_sampling(self):
        for text in ['kKeysPerApi=64','kBins=128','kBucketMs=500','api*kKeysPerApi','key->pre.fetch_add','key->post.fetch_add','bin<kBins','candidate.claimed.compare_exchange_strong','memory_order_acquire','memory_order_release']:self.assertIn(text,self.source)
        self.assertNotIn('CaptureStackBackTrace',self.source)
    def test_no_guest_memory_or_logging_in_wrapper(self):
        wrapper=self.source.split('template<size_t Api>')[1].split('inline const std::array')[0]
        self.assertEqual(wrapper.count('original[Api](ctx,base)'),2) # exclusive disabled and observed paths
        for forbidden in ['printf','VirtualQuery','ReadProcessMemory','WriteProcessMemory','KernelState','WaitFor']:self.assertNotIn(forbidden,wrapper)
        self.assertIn('errno=result_errno;SetLastError(result_error)',wrapper)
        self.assertIn('const PPCContext&',self.source)
    def test_iat_plan_and_owned_restore(self):
        for text in ['IMAGE_FILE_MACHINE_AMD64','IMAGE_NT_OPTIONAL_HDR64_MAGIC','matching_dlls!=1','counts[n]!=1','InterlockedCompareExchangePointer(slot,after,before)','slot_protection[n]','GetModuleHandleW(nullptr)']:self.assertIn(text,self.source)
    def test_dump_protocol_and_hook(self):
        for text in ['SCHEDULE_TRACE','SCHEDULE_KEY','SCHEDULE_ENTRY','SCHEDULE_PENDING','weak_snapshot=1','flags=%08X x0=%llX','SetScheduleSampleHook','sample_hook(uint32_t(Api),ctx,base)']:self.assertIn(text,self.source)
    @unittest.skipUnless(os.name=='nt','Windows native mock')
    def test_native_transparency_guards_sampling_blocked_and_restore(self):
        from tools.research.compile_module import vc_environment
        from tools.research.probe_route_a import CLANG_CL_SHA256
        cc=ROOT/'local/upstream/llvm/unpacked/bin/clang-cl.exe';sdk=ROOT/'local/upstream/rexglue/sdk/win-amd64'
        if not cc.exists() or not sdk.exists():self.skipTest('optional pinned compiler/SDK absent')
        self.assertEqual(hashlib.sha256(cc.read_bytes()).hexdigest(),CLANG_CL_SHA256)
        evidence=ROOT/'local/analysis/phase23';evidence.mkdir(parents=True,exist_ok=True);out=Path(tempfile.mkdtemp(prefix='schedule-mock-',dir=evidence));source=out/'mock.cpp';source.write_text(MOCK)
        before=hashlib.sha256(HEADER.read_bytes()).hexdigest()
        command=[str(cc),'/nologo','/std:c++latest','/EHa','/MD','/O2','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/I'+str(sdk/'include'),'/I'+str(HEADER.parent),str(source),'/Fe'+str(out/'mock.exe'),'/Fo'+str(out/'mock.obj')]
        env=vc_environment(Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat'))
        build=subprocess.run(command,env=env,capture_output=True,text=True,timeout=120);(out/'build.txt').write_text(build.stdout+build.stderr);(out/'build.json').write_text(json.dumps({'command':command,'exit_status':build.returncode},indent=2));self.assertEqual(build.returncode,0,build.stdout+build.stderr)
        run=subprocess.run([str(out/'mock.exe')],capture_output=True,text=True,timeout=30);(out/'run.txt').write_text(run.stdout+run.stderr);(out/'run.json').write_text(json.dumps({'command':[str(out/'mock.exe')],'exit_status':run.returncode,'header_sha256':before},indent=2));self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertIn('SCHEDULE_MOCK transparency=3 guards=9 sampled45s=1 blocked=1 restore=1',run.stdout);self.assertEqual(hashlib.sha256(HEADER.read_bytes()).hexdigest(),before)

MOCK=r'''
#include "schedule_import_trace.h"
#include <cassert>
#include <thread>
#include <vector>
using namespace mc2::host;
using namespace mc2::host::schedule_trace;
PPCContext input_context;
std::array<uint8_t,128> input_memory;
std::atomic<unsigned> delegates{0},hooks{0};
std::atomic<bool> block{false},release{false};
void Fixture(PPCContext& ctx,std::array<uint8_t,128>& mem){for(size_t i=0;i<sizeof(ctx);++i)((uint8_t*)&ctx)[i]=uint8_t(i*13+7);ctx.lr=0x82869854;for(size_t i=0;i<mem.size();++i)mem[i]=uint8_t(i*17);std::memcpy(&input_context,&ctx,sizeof(ctx));input_memory=mem;}
template<int Api> void Delegate(PPCContext& ctx,uint8_t* base){assert(std::memcmp(&ctx,&input_context,sizeof(ctx))==0);assert(std::memcmp(base,input_memory.data(),128)==0);assert(errno==EAGAIN && GetLastError()==0x1234);++delegates;if(Api==1)while(block.load()&&!release.load())std::this_thread::yield();for(size_t i=0;i<sizeof(ctx);++i)((uint8_t*)&ctx)[i]^=uint8_t(i*7+3);base[10]^=0xA5;errno=ERANGE;SetLastError(0x5678);}
ScheduleExtra ThrowHook(uint32_t,const PPCContext&,uint8_t*){throw 99;}
ScheduleExtra Hook(uint32_t api,const PPCContext& ctx,uint8_t* base){assert(std::memcmp(&ctx,&input_context,sizeof(ctx))==0);assert(std::memcmp(base,input_memory.data(),128)==0);++hooks;errno=EDOM;SetLastError(99);ScheduleExtra e;e.flags=7;e.values[0]=api;e.values[7]=0xABCDEF0123456789ull;return e;}
void ThrowDelegate(PPCContext& ctx,uint8_t* base){Delegate<2>(ctx,base);throw 42;}
void Reset(){active=false;for(auto& k:keys){k.state=0;k.pre=0;k.post=0;k.sampled=0;for(auto& s:k.samples){s.claimed=false;s.pre.ready=false;s.post.ready=false;s.pre.extra={};s.post.extra={};}}calls=0;posts=0;key_overflow=0;late=0;for(size_t api=0;api<kCount;++api){api_pre[api]=0;api_post[api]=0;api_overflow[api]=0;}frozen=false;epoch=GetTickCount64();active=true;}
void Call(size_t api){PPCContext c;std::array<uint8_t,128> m;Fixture(c,m);errno=EAGAIN;SetLastError(0x1234);wrappers[api](c,m.data());assert(errno==ERANGE && GetLastError()==0x5678);}
std::vector<uint8_t> Image(){std::vector<uint8_t> v(0x4000);auto*d=(IMAGE_DOS_HEADER*)v.data();d->e_magic=IMAGE_DOS_SIGNATURE;d->e_lfanew=0x100;auto*n=(IMAGE_NT_HEADERS64*)(v.data()+0x100);n->Signature=IMAGE_NT_SIGNATURE;n->FileHeader.Machine=IMAGE_FILE_MACHINE_AMD64;n->FileHeader.SizeOfOptionalHeader=sizeof(IMAGE_OPTIONAL_HEADER64);n->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR64_MAGIC;n->OptionalHeader.SizeOfImage=uint32_t(v.size());n->OptionalHeader.NumberOfRvaAndSizes=IMAGE_NUMBEROF_DIRECTORY_ENTRIES;n->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT]={0x300,2*sizeof(IMAGE_IMPORT_DESCRIPTOR)};auto*i=(IMAGE_IMPORT_DESCRIPTOR*)(v.data()+0x300);i->Name=0x500;i->OriginalFirstThunk=0x1000;i->FirstThunk=0x1100;std::strcpy((char*)v.data()+0x500,"rexruntime.dll");for(size_t a=0;a<kCount;++a){auto at=0x700+a*0x80;std::strcpy((char*)v.data()+at+2,kNames[a]);((uint64_t*)(v.data()+0x1000))[a]=at;((void**)(v.data()+0x1100))[a]=(void*)original[a];}return v;}
int main(){original={&Delegate<0>,&Delegate<1>,&Delegate<2>};assert(!InstallScheduleImportTrace(nullptr,nullptr,false));assert(SetScheduleSampleHook(Hook));
for(size_t api=0;api<3;++api){Reset();PPCContext a,b;std::array<uint8_t,128> ma,mb;Fixture(a,ma);std::memcpy(&b,&a,sizeof(a));mb=ma;errno=EAGAIN;SetLastError(0x1234);original[api](a,ma.data());errno=EAGAIN;SetLastError(0x1234);wrappers[api](b,mb.data());assert(std::memcmp(&a,&b,sizeof(a))==0&&ma==mb);assert(errno==ERANGE&&GetLastError()==0x5678);auto& k=keys[api*kKeysPerApi];assert(k.pre==1&&k.post==1&&k.samples[0].pre.ready&&k.samples[0].post.ready);assert(k.samples[0].pre.extra.flags==7&&k.samples[0].pre.extra.values[7]==0xABCDEF0123456789ull);assert(k.samples[0].post.extra.flags==0);}
assert(delegates==6);
Reset();sample_hook=ThrowHook;Call(0);assert(keys[0].samples[0].pre.extra.flags==0x80000000u&&api_pre[0]==1&&api_post[0]==1);sample_hook=Hook;
Reset();active=false;Call(2);assert(calls==0&&posts==0);active=true;
Reset();std::array<uint64_t,8> args{};for(size_t n=0;n<kKeysPerApi;++n){args[0]=n+1;assert(FindKey(1,1,123,args));}args[0]=999;assert(!FindKey(1,1,123,args));assert(api_overflow[1]==1&&key_overflow==1);Call(0);assert(keys[0].state==2&&api_pre[0]==1&&api_post[0]==1);
Reset();original[2]=ThrowDelegate;PPCContext c;std::array<uint8_t,128> mem;Fixture(c,mem);errno=EAGAIN;SetLastError(0x1234);try{wrappers[2](c,mem.data());assert(false);}catch(int x){assert(x==42);}assert(errno==ERANGE&&GetLastError()==0x5678);assert(keys[2*kKeysPerApi].pre==1&&keys[2*kKeysPerApi].post==0);original[2]=Delegate<2>;
auto good=Image();std::array<void**,kCount> found{};assert(Plan(good.data(),good.size(),original,found));for(int bad=0;bad<9;++bad){auto v=good;auto*n=(IMAGE_NT_HEADERS64*)(v.data()+0x100);auto*i=(IMAGE_IMPORT_DESCRIPTOR*)(v.data()+0x300);if(bad==0)n->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;if(bad==1)n->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;if(bad==2)std::strcpy((char*)v.data()+0x500,"wrong.dll");if(bad==3)((uint64_t*)(v.data()+0x1000))[0]=0x780;if(bad==4)((void**)(v.data()+0x1100))[0]=nullptr;if(bad==5)i->OriginalFirstThunk=0;if(bad==6)i->FirstThunk=0x3FFC;if(bad==7)n->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].Size=sizeof(IMAGE_IMPORT_DESCRIPTOR);if(bad==8)n->OptionalHeader.SizeOfImage=0x5000;const auto before=v;assert(!Plan(v.data(),v.size(),original,found));assert(v==before);}
Reset();for(int n=0;n<10000;++n)Call(0);assert(keys[0].pre==10000&&keys[0].post==10000&&keys[0].sampled==1);epoch=GetTickCount64()-45000;Call(0);assert(keys[0].samples[90].pre.ready&&keys[0].samples[90].post.ready&&keys[0].sampled==2);epoch=GetTickCount64()-65000;Call(0);assert(late==1&&keys[0].pre==10002&&keys[0].post==10002);
Reset();block=true;std::thread t([]{Call(1);});auto& wait=keys[kKeysPerApi];while(!wait.samples[0].pre.ready.load(std::memory_order_acquire))std::this_thread::yield();assert(wait.pre==1&&wait.post==0&&!wait.samples[0].post.ready.load());release=true;t.join();assert(wait.post==1&&wait.samples[0].post.ready);
auto* page=(void**)VirtualAlloc(nullptr,4096,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);assert(page);page[0]=(void*)original[0];DWORD old;assert(VirtualProtect(page,4096,PAGE_READONLY,&old));assert(Exchange(page,(void*)original[0],(void*)wrappers[0]));slots.fill(nullptr);slots[0]=page;slot_protection[0]=PAGE_READONLY;assert(RestoreScheduleImportTrace());assert(page[0]==(void*)original[0]);MEMORY_BASIC_INFORMATION info{};VirtualQuery(page,&info,sizeof(info));assert(info.Protect==PAGE_READONLY);assert(VirtualProtect(page,4096,PAGE_READWRITE,&old));page[0]=(void*)uintptr_t(123);assert(!RestoreScheduleImportTrace());assert(page[0]==(void*)uintptr_t(123));slots.fill(nullptr);VirtualFree(page,0,MEM_RELEASE);
FILE* out=std::tmpfile();assert(out);DumpScheduleImportTrace(out);assert(std::ftell(out)>0);std::rewind(out);char first[512]{};assert(std::fgets(first,sizeof(first),out));assert(std::strstr(first,"SCHEDULE_TRACE status="));std::fclose(out);DumpScheduleImportTrace(nullptr);std::puts("SCHEDULE_MOCK transparency=3 guards=9 sampled45s=1 blocked=1 restore=1");}
'''
