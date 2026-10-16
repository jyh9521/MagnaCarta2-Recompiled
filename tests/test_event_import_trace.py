"""IAT/observer contracts and real-header synthetic delegates (no SDK execution)."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
HEADER=ROOT/'src/host/event_import_trace.h'


class EventTraceContractTests(unittest.TestCase):
    def setUp(self): self.source=HEADER.read_text(encoding='utf8')
    def test_supported_identity(self):
        self.assertIn('e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a',self.source)
        self.assertLess(self.source.index('if (!verified)'),self.source.index('GetProcAddress(runtime'))
    def test_exact_exports(self):
        for name in ('NtCreateEvent','NtSetEvent','NtClearEvent','NtWaitForSingleObjectEx'):
            self.assertIn('"__imp__'+name+'"',self.source)
        self.assertNotIn('"__imp__NtResetEvent"',self.source)
        self.assertIn('reset_export=absent',self.source)
    def test_complete_preflight(self):
        for guard in ('IMAGE_FILE_MACHINE_AMD64','IMAGE_NT_OPTIONAL_HDR64_MAGIC',
                      'matching_dlls!=1','counts[n]!=1','reinterpret_cast<void*>(expected[n])',
                      '_stricmp(dll,"rexruntime.dll")','GetModuleHandleW(nullptr)'):
            self.assertIn(guard,self.source)
        install=self.source[self.source.index('inline bool InstallEventImportTrace'):]
        self.assertLess(install.index('if (!Plan('),install.index('if (!Exchange('))
    def test_atomic_bounded_append_only(self):
        self.assertIn('kCapacity = 8192',self.source)
        self.assertIn('is_always_lock_free',self.source)
        self.assertIn('if (index>=kCapacity)',self.source)
        self.assertNotIn('%kCapacity',self.source)
        self.assertIn('memory_order_release',self.source)
        self.assertIn('memory_order_acquire',self.source)
        self.assertIn('reserved.fetch_or(kFrozen',self.source)
        self.assertIn('compare_exchange_weak(index,index+1',self.source)
        self.assertIn('EVENT_TRACE_PENDING slot=',self.source)
    def test_wrapper_one_delegate_and_no_logging_or_object_operations(self):
        wrapper=self.source.split('template<size_t Api>')[1].split('inline const std::array')[0]
        self.assertEqual(wrapper.count('original[Api](ctx,base)'),1)
        for forbidden in ('printf','new ','KernelState','WaitFor','SetEvent(', 'Signal', 'Query('):
            self.assertNotIn(forbidden,wrapper)
        self.assertLess(wrapper.index('Record(uint32_t(Api),0'),wrapper.index('original[Api]'))
        self.assertIn('errno=result_errno; SetLastError(result_error)',wrapper)
    def test_read_guard_tls_and_no_sdk_patch(self):
        self.assertIn('EventTraceMemoryReadActive()',self.source)
        self.assertIn('thread_local bool memory_read_active=false',self.source)
        self.assertIn('VirtualQuery(',self.source)
        self.assertIn('__except(EXCEPTION_EXECUTE_HANDLER)',self.source)
        self.assertNotIn('WriteProcessMemory',self.source)
        self.assertNotIn('VirtualProtect(runtime',self.source)
    def test_restore_compares_owned_pointer(self):
        self.assertIn('InterlockedCompareExchangePointer(slot,after,before)',self.source)
        self.assertIn('*slots[n]==reinterpret_cast<void*>(wrappers[n])',self.source)
        self.assertIn('protection_restored',self.source)
    def test_bounded_native_stack_without_symbol_calls(self):
        self.assertIn('std::array<void*,16> frames',self.source)
        self.assertIn('if (phase==0) e.frame_count=CaptureStackBackTrace',self.source)
        self.assertIn('EVENT_TRACE_MODULE base=',self.source)
        self.assertIn('EVENT_TRACE_FRAME slot=',self.source)
        self.assertNotIn('SymFromAddr',self.source)
        self.assertIn('DumpEventImportTrace(FILE* output=stdout)',self.source)
        self.assertIn('status.load(std::memory_order_acquire)',self.source)
        self.assertNotIn('std::printf(',self.source)

    @unittest.skipUnless(os.name=='nt','actual Windows header mock requires Windows')
    def test_actual_header_synthetic_delegation_pe_guards_and_restore(self):
        from tools.research.compile_module import vc_environment
        compiler=ROOT/'local/upstream/llvm/unpacked/bin/clang-cl.exe'
        sdk=ROOT/'local/upstream/rexglue/sdk/win-amd64'
        if not compiler.exists() or not sdk.exists():self.skipTest('local pinned SDK/compiler absent')
        evidence=ROOT/'local/analysis/phase12';evidence.mkdir(parents=True,exist_ok=True)
        output=Path(tempfile.mkdtemp(prefix='event-mock-',dir=evidence))
        source=output/'mock.cpp';source.write_text(MOCK,encoding='utf8')
        command=[str(compiler),'/nologo','/std:c++latest','/EHa','/MD','/O2','/DNOMINMAX',
                 '/DWIN32_LEAN_AND_MEAN','/I'+str(sdk/'include'),'/I'+str(HEADER.parent),
                 str(source),'/Fe'+str(output/'mock.exe'),'/Fo'+str(output/'mock.obj')]
        env=vc_environment(Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat'))
        build=subprocess.run(command,env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
        (output/'build.txt').write_text(build.stdout+build.stderr,encoding='utf8')
        (output/'build.json').write_text(json.dumps({'command':command,'exit_status':build.returncode},indent=2),encoding='utf8')
        self.assertEqual(build.returncode,0,build.stdout+build.stderr)
        run=subprocess.run([str(output/'mock.exe')],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
        (output/'run.txt').write_text(run.stdout+run.stderr,encoding='utf8')
        (output/'run.json').write_text(json.dumps({'command':[str(output/'mock.exe')],'exit_status':run.returncode},indent=2),encoding='utf8')
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        self.assertIn('EVENT_MOCK equivalence=4 guards=9 overflow=2 blocked_pre=1 restore=1',run.stdout)


MOCK=r'''
#include "event_import_trace.h"
#include <cassert>
#include <thread>
#include <vector>
using namespace mc2::host;
using namespace mc2::host::event_trace;
PPCContext expected_context;
std::array<uint8_t,128> expected_memory;
int delegates=0;
std::atomic<bool> block_wait=false, release_wait=false;
template<int Api> void Delegate(PPCContext& ctx,uint8_t* base) {
  assert(std::memcmp(&ctx,&expected_context,sizeof(ctx))==0);
  assert(std::memcmp(base,expected_memory.data(),expected_memory.size())==0);
  assert(GetLastError()==0x1234 && errno==EAGAIN);
  assert(!EventTraceMemoryReadActive());
  ++delegates;
  if constexpr(Api==3) while(block_wait.load() && !release_wait.load()) std::this_thread::yield();
  auto* raw=reinterpret_cast<uint8_t*>(&ctx);
  for(size_t i=0;i<sizeof(ctx);++i) raw[i]^=uint8_t(i*7+13);
  ctx.r3.u64=Api==0?0:0xABCDEF0012345678ull;
  base[32]=0xF8;base[33]=0x00;base[34]=0x00;base[35]=0xAC;base[80]^=0x5A;
  errno=ERANGE;SetLastError(0x5678);
}
void ThrowDelegate(PPCContext& ctx,uint8_t* base) {Delegate<1>(ctx,base);throw 42;}
void ResetRing() {
  for(auto& e:ring)e.ready.store(false);
  reserved=0;calls=0;dropped=0;
}
void Fixture(PPCContext& ctx,std::array<uint8_t,128>& memory) {
  auto* bytes=reinterpret_cast<uint8_t*>(&ctx);
  for(size_t i=0;i<sizeof(ctx);++i)bytes[i]=uint8_t(i*17+3);
  ctx.r3.u64=0x100000020ull;
  for(size_t i=0;i<memory.size();++i)memory[i]=uint8_t(i*11+7);
  std::memcpy(&expected_context,&ctx,sizeof(ctx));expected_memory=memory;
}
std::vector<uint8_t> Image() {
  std::vector<uint8_t> v(0x4000);
  auto* d=reinterpret_cast<IMAGE_DOS_HEADER*>(v.data());d->e_magic=IMAGE_DOS_SIGNATURE;d->e_lfanew=0x100;
  auto* n=reinterpret_cast<IMAGE_NT_HEADERS64*>(v.data()+0x100);
  n->Signature=IMAGE_NT_SIGNATURE;n->FileHeader.Machine=IMAGE_FILE_MACHINE_AMD64;
  n->FileHeader.SizeOfOptionalHeader=sizeof(IMAGE_OPTIONAL_HEADER64);
  n->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR64_MAGIC;n->OptionalHeader.SizeOfImage=uint32_t(v.size());
  n->OptionalHeader.NumberOfRvaAndSizes=IMAGE_NUMBEROF_DIRECTORY_ENTRIES;
  n->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT]={0x300,2*sizeof(IMAGE_IMPORT_DESCRIPTOR)};
  auto* imp=reinterpret_cast<IMAGE_IMPORT_DESCRIPTOR*>(v.data()+0x300);
  imp->Name=0x500;imp->OriginalFirstThunk=0x1000;imp->FirstThunk=0x1100;
  std::strcpy(reinterpret_cast<char*>(v.data()+0x500),"rexruntime.dll");
  for(size_t i=0;i<kCount;++i) {
    auto at=0x700+i*0x80;
    std::strcpy(reinterpret_cast<char*>(v.data()+at+2),kNames[i]);
    reinterpret_cast<uint64_t*>(v.data()+0x1000)[i]=at;
    reinterpret_cast<void**>(v.data()+0x1100)[i]=reinterpret_cast<void*>(original[i]);
  }
  return v;
}
int main(){
  original={&Delegate<0>,&Delegate<1>,&Delegate<2>,&Delegate<3>};
  assert(!InstallEventImportTrace(nullptr,nullptr,false));
  for(size_t api=0;api<kCount;++api) {
    ResetRing();PPCContext a,b;std::array<uint8_t,128> ma,mb;Fixture(a,ma);
    std::memcpy(&b,&a,sizeof(a));mb=ma;
    errno=EAGAIN;SetLastError(0x1234);original[api](a,ma.data());
    const int direct_errno=errno;const DWORD direct_error=GetLastError();
    errno=EAGAIN;SetLastError(0x1234);wrappers[api](b,mb.data());
    assert(errno==direct_errno && GetLastError()==direct_error);
    assert(std::memcmp(&a,&b,sizeof(a))==0 && ma==mb);
    assert(reserved==2 && ring[0].ready && ring[1].ready);
    assert(ring[0].args[0]==0x100000020ull && ring[0].phase==0 && ring[1].phase==1);
    assert(ring[0].thread==GetCurrentThreadId());
    assert(ring[0].frame_count>0 && ring[0].frame_count<=16 && ring[1].frame_count==0);
    if(api==0)assert(ring[1].out_read && ring[1].out_handle==0xF80000AC);
  }
  assert(delegates==8);
  {
    ResetRing();PPCContext a,b;std::array<uint8_t,128> ma,mb;Fixture(a,ma);
    std::memcpy(&b,&a,sizeof(a));mb=ma;original[1]=ThrowDelegate;
    errno=EAGAIN;SetLastError(0x1234);
    try{original[1](a,ma.data());assert(false);}catch(int value){assert(value==42);}
    const int direct_errno=errno;const DWORD direct_error=GetLastError();
    errno=EAGAIN;SetLastError(0x1234);
    try{wrappers[1](b,mb.data());assert(false);}catch(int value){assert(value==42);}
    assert(errno==direct_errno && GetLastError()==direct_error);
    assert(std::memcmp(&a,&b,sizeof(a))==0 && ma==mb);
    assert(reserved==1 && ring[0].ready && !ring[1].ready);
    original[1]=Delegate<1>;
  }
  auto good=Image();std::array<void**,kCount> found{};
  assert(Plan(good.data(),good.size(),original,found));
  for(int bad=0;bad<9;++bad) {
    auto bytes=good;
    auto* n=reinterpret_cast<IMAGE_NT_HEADERS64*>(bytes.data()+0x100);
    auto* imp=reinterpret_cast<IMAGE_IMPORT_DESCRIPTOR*>(bytes.data()+0x300);
    if(bad==0)n->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;
    if(bad==1)n->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;
    if(bad==2)std::strcpy(reinterpret_cast<char*>(bytes.data()+0x500),"wrong.dll");
    if(bad==3)reinterpret_cast<uint64_t*>(bytes.data()+0x1000)[0]=0x780; // duplicate/missing
    if(bad==4)reinterpret_cast<void**>(bytes.data()+0x1100)[0]=nullptr;
    if(bad==5)imp->OriginalFirstThunk=0;
    if(bad==6)imp->FirstThunk=0x3FFC;
    if(bad==7)n->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].Size=sizeof(IMAGE_IMPORT_DESCRIPTOR);
    if(bad==8)n->OptionalHeader.SizeOfImage=0x5000;
    const auto before=bytes;
    assert(!Plan(bytes.data(),bytes.size(),original,found));assert(bytes==before);
  }
  for(int overflow=0;overflow<2;++overflow) {
    ResetRing();reserved=kCapacity-1+overflow;
    PPCContext a;std::array<uint8_t,128> m;Fixture(a,m);
    errno=EAGAIN;SetLastError(0x1234);wrappers[1](a,m.data());
    assert(dropped==uint64_t(1+overflow));assert(errno==ERANGE && GetLastError()==0x5678);
  }
  ResetRing();PPCContext wait;std::array<uint8_t,128> wm;Fixture(wait,wm);
  block_wait=true;std::thread t([&]{errno=EAGAIN;SetLastError(0x1234);wrappers[3](wait,wm.data());});
  while(!ring[0].ready.load(std::memory_order_acquire))std::this_thread::yield();
  assert(ring[0].phase==0 && !ring[1].ready.load());release_wait=true;t.join();assert(ring[1].ready);
  uint32_t out=0;assert(!ReadOutHandle(nullptr,32,out));assert(!EventTraceMemoryReadActive());
  auto* page=static_cast<void**>(VirtualAlloc(nullptr,4096,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));assert(page);
  page[0]=reinterpret_cast<void*>(original[0]);DWORD old;
  assert(VirtualProtect(page,4096,PAGE_READONLY,&old));
  assert(Exchange(page,reinterpret_cast<void*>(original[0]),reinterpret_cast<void*>(wrappers[0])));
  MEMORY_BASIC_INFORMATION info{};VirtualQuery(page,&info,sizeof(info));assert(info.Protect==PAGE_READONLY);
  slots.fill(nullptr);slots[0]=page;slot_protection[0]=PAGE_READONLY;assert(RestoreEventImportTrace());
  assert(page[0]==reinterpret_cast<void*>(original[0]));
  VirtualQuery(page,&info,sizeof(info));assert(info.Protect==PAGE_READONLY);
  assert(VirtualProtect(page,4096,PAGE_READWRITE,&old));page[0]=reinterpret_cast<void*>(uintptr_t(123));
  assert(!RestoreEventImportTrace());assert(page[0]==reinterpret_cast<void*>(uintptr_t(123)));
  slots.fill(nullptr);VirtualFree(page,0,MEM_RELEASE);
  const auto frozen=reserved.load();assert(frozen&kFrozen);
  PPCContext last;std::array<uint8_t,128> lm;Fixture(last,lm);
  errno=EAGAIN;SetLastError(0x1234);wrappers[1](last,lm.data());
  assert(reserved.load()==frozen && errno==ERANGE && GetLastError()==0x5678);
  FILE* trace=std::tmpfile();assert(trace);char buffer[65536];
  assert(std::setvbuf(trace,buffer,_IOFBF,sizeof(buffer))==0);
  DumpEventImportTrace(trace);assert(std::fflush(trace)==0);assert(std::ftell(trace)>0);
  std::rewind(trace);char first[256]{};assert(std::fgets(first,sizeof(first),trace));
  assert(std::strstr(first,"EVENT_TRACE status="));std::fclose(trace);
  DumpEventImportTrace(nullptr);
  std::puts("EVENT_MOCK equivalence=4 guards=9 overflow=2 blocked_pre=1 restore=1");
}
'''

if __name__=='__main__':unittest.main()
