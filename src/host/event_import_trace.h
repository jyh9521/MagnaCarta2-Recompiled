#pragma once
// Scoped host import observation only. SDK/game bytes are never patched.
#include <Windows.h>
#include <rex/ppc/context.h>
#include <array>
#include <atomic>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstring>

namespace mc2::host {
inline constexpr char kEventImportRuntimeSha256[] =
    "e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a";
namespace event_trace {
inline constexpr size_t kCount = 4, kCapacity = 8192;
inline constexpr uint64_t kFrozen=uint64_t(1)<<63;
// Exact exports independently read from the supported DLL and host PE imports.
// NtResetEvent is absent, and is NOT replaced with the distinct KeResetEvent.
inline constexpr std::array<const char*, kCount> kNames = {
    "__imp__NtCreateEvent", "__imp__NtSetEvent", "__imp__NtClearEvent",
    "__imp__NtWaitForSingleObjectEx"};
struct Entry {
  std::atomic<bool> ready{false};
  uint64_t call=0, context=0, lr=0, sp=0, result=0;
  std::array<uint64_t, 8> args{};
  uint32_t thread=0, api=0, phase=0, out_handle=0;
  std::array<void*,16> frames{};
  uint16_t frame_count=0;
  bool out_read=false;
};
static_assert(std::atomic<uint64_t>::is_always_lock_free);
static_assert(std::atomic<bool>::is_always_lock_free);
inline std::array<Entry, kCapacity> ring;
inline std::atomic<uint64_t> reserved{0}, calls{0}, dropped{0};
inline std::array<PPCFunc*, kCount> original{};
inline std::array<void**, kCount> slots{};
inline std::array<DWORD,kCount> slot_protection{};
inline bool installed=false;
inline std::atomic<const char*> status{"not-installed"};
inline thread_local bool memory_read_active=false;
inline uintptr_t module_base=0;
inline size_t module_size=0;

inline bool ReadOutHandle(uint8_t* base, uint32_t address, uint32_t& out) {
  if (!base || !address || address>0xFFFFFFFCu ||
      uintptr_t(base)>UINTPTR_MAX-address-3) return false;
  const uintptr_t target=uintptr_t(base)+address;
  MEMORY_BASIC_INFORMATION info{};
  if (VirtualQuery(reinterpret_cast<void*>(target),&info,sizeof(info))!=sizeof(info) ||
      info.State!=MEM_COMMIT || (info.Protect&(PAGE_GUARD|PAGE_NOACCESS)) ||
      !(info.Protect&(PAGE_READONLY|PAGE_READWRITE|PAGE_WRITECOPY|PAGE_EXECUTE_READ|
                      PAGE_EXECUTE_READWRITE|PAGE_EXECUTE_WRITECOPY)) ||
      target<uintptr_t(info.BaseAddress) || info.RegionSize<4 ||
      target-uintptr_t(info.BaseAddress)>info.RegionSize-4) return false;
  const bool previous=memory_read_active;memory_read_active=true;
  __try {
    const volatile uint8_t* p=reinterpret_cast<const volatile uint8_t*>(target);
    out=(uint32_t(p[0])<<24)|(uint32_t(p[1])<<16)|(uint32_t(p[2])<<8)|p[3];
  } __except(EXCEPTION_EXECUTE_HANDLER) { memory_read_active=previous;return false; }
  memory_read_active=previous;return true;
}

inline void Record(uint32_t api, uint32_t phase, uint64_t call, PPCContext& ctx,
                   const std::array<uint64_t,8>& args, uint8_t* base) {
  uint64_t index=reserved.load(std::memory_order_relaxed);
  do {
    if (index&kFrozen) return;
  } while (!reserved.compare_exchange_weak(index,index+1,std::memory_order_acq_rel));
  if (index>=kCapacity) { dropped.fetch_add(1,std::memory_order_relaxed); return; }
  Entry& e=ring[size_t(index)];
  e.call=call; e.context=uintptr_t(&ctx); e.lr=ctx.lr; e.sp=ctx.r1.u64;
  e.thread=GetCurrentThreadId(); e.api=api; e.phase=phase; e.args=args;
  e.result=ctx.r3.u64;
  if (phase==0) e.frame_count=CaptureStackBackTrace(0,ULONG(e.frames.size()),e.frames.data(),nullptr);
  if (api==0 && phase==1 && ctx.r3.u32==0)
    e.out_read=ReadOutHandle(base,uint32_t(args[0]),e.out_handle);
  e.ready.store(true,std::memory_order_release);
}

template<size_t Api> inline void Invoke(PPCContext& ctx, uint8_t* base) {
  const DWORD saved_error=GetLastError(); const int saved_errno=errno;
  const std::array<uint64_t,8> args={ctx.r3.u64,ctx.r4.u64,ctx.r5.u64,ctx.r6.u64,
                                   ctx.r7.u64,ctx.r8.u64,ctx.r9.u64,ctx.r10.u64};
  const uint64_t call=calls.fetch_add(1,std::memory_order_relaxed);
  Record(uint32_t(Api),0,call,ctx,args,base);
  errno=saved_errno; SetLastError(saved_error);
  original[Api](ctx,base);  // Exactly one unmodified PPCFunc delegation.
  const DWORD result_error=GetLastError(); const int result_errno=errno;
  Record(uint32_t(Api),1,call,ctx,args,base);
  errno=result_errno; SetLastError(result_error);
}
inline const std::array<PPCFunc*,kCount> wrappers={&Invoke<0>,&Invoke<1>,&Invoke<2>,&Invoke<3>};

// Parser is independently mockable: bytes are a mapped AMD64 PE image, not raw
// file offsets. Every selected IAT slot is checked before any page write.
inline bool Plan(uint8_t* image, size_t extent, const std::array<PPCFunc*,kCount>& expected,
                 std::array<void**,kCount>& selected) {
  auto fits=[extent](uint64_t at,uint64_t size){return at<=extent && size<=extent-at;};
  if (!image || !fits(0,sizeof(IMAGE_DOS_HEADER))) return false;
  auto* dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);
  if (dos->e_magic!=IMAGE_DOS_SIGNATURE || dos->e_lfanew<0 ||
      !fits(uint32_t(dos->e_lfanew),sizeof(IMAGE_NT_HEADERS64))) return false;
  auto* nt=reinterpret_cast<IMAGE_NT_HEADERS64*>(image+dos->e_lfanew);
  if (nt->Signature!=IMAGE_NT_SIGNATURE || nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_AMD64 ||
      nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR64_MAGIC ||
      nt->FileHeader.SizeOfOptionalHeader!=sizeof(IMAGE_OPTIONAL_HEADER64) ||
      nt->OptionalHeader.SizeOfImage!=extent ||
      nt->OptionalHeader.NumberOfRvaAndSizes<=IMAGE_DIRECTORY_ENTRY_IMPORT) return false;
  const auto dir=nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
  if (!dir.VirtualAddress || !fits(dir.VirtualAddress,dir.Size)) return false;
  auto string_at=[&](uint32_t at)->const char* {
    if (!fits(at,1)) return nullptr;
    const auto* p=reinterpret_cast<const char*>(image+at);
    return std::memchr(p,0,extent-at)?p:nullptr;
  };
  std::array<size_t,kCount> counts{}; selected.fill(nullptr);
  size_t matching_dlls=0; bool terminated=false;
  for (uint64_t at=dir.VirtualAddress; fits(at,sizeof(IMAGE_IMPORT_DESCRIPTOR)) &&
       at+sizeof(IMAGE_IMPORT_DESCRIPTOR)<=uint64_t(dir.VirtualAddress)+dir.Size;
       at+=sizeof(IMAGE_IMPORT_DESCRIPTOR)) {
    auto* d=reinterpret_cast<IMAGE_IMPORT_DESCRIPTOR*>(image+at);
    if (!d->Name && !d->FirstThunk && !d->OriginalFirstThunk) {terminated=true;break;}
    const char* dll=string_at(d->Name); if (!dll) return false;
    if (_stricmp(dll,"rexruntime.dll")) continue;
    if (++matching_dlls!=1 || !d->OriginalFirstThunk || !d->FirstThunk) return false;
    bool thunk_end=false;
    for (uint64_t i=0; i<extent/sizeof(IMAGE_THUNK_DATA64);++i) {
      const uint64_t oa=uint64_t(d->OriginalFirstThunk)+i*8, ia=uint64_t(d->FirstThunk)+i*8;
      if (!fits(oa,8) || !fits(ia,8) || (ia&7)) return false;
      const uint64_t name=reinterpret_cast<IMAGE_THUNK_DATA64*>(image+oa)->u1.AddressOfData;
      if (!name) {thunk_end=true;break;}
      if (IMAGE_SNAP_BY_ORDINAL64(name)) continue;
      if (name>UINT32_MAX-2 || !fits(name,3)) return false;
      const char* symbol=string_at(uint32_t(name)+2); if (!symbol) return false;
      for (size_t n=0;n<kCount;++n) if (!std::strcmp(symbol,kNames[n])) {
        if (++counts[n]!=1 || !expected[n]) return false;
        void** slot=reinterpret_cast<void**>(image+ia);
        if (*slot!=reinterpret_cast<void*>(expected[n])) return false;
        selected[n]=slot;
      }
    }
    if (!thunk_end) return false;
  }
  if (!terminated || matching_dlls!=1) return false;
  for (size_t n=0;n<kCount;++n) if (counts[n]!=1) return false;
  return true;
}

inline bool Exchange(void** slot, void* before, void* after) {
  DWORD protect=0;
  if (!VirtualProtect(slot,sizeof(void*),PAGE_READWRITE,&protect)) return false;
  void* observed=InterlockedCompareExchangePointer(slot,after,before);
  DWORD ignored=0; const bool protection_restored=VirtualProtect(slot,sizeof(void*),protect,&ignored)!=FALSE;
  return observed==before && *slot==after && protection_restored;
}
}  // namespace event_trace

inline bool EventTraceMemoryReadActive() { return event_trace::memory_read_active; }

inline bool RestoreEventImportTrace() {
  using namespace event_trace;
  // Freeze reservation and its cutoff in ONE atomic operation. Inflight
  // publishers may finish their existing slot; no later pre/post can reserve.
  reserved.fetch_or(kFrozen,std::memory_order_acq_rel);
  bool okay=true;
  for (size_t n=0;n<kCount;++n) if (slots[n]) {
    const bool owned=*slots[n]==reinterpret_cast<void*>(wrappers[n]) ||
                     *slots[n]==reinterpret_cast<void*>(original[n]);
    if (*slots[n]==reinterpret_cast<void*>(wrappers[n]))
      okay=Exchange(slots[n],reinterpret_cast<void*>(wrappers[n]),reinterpret_cast<void*>(original[n]))&&okay;
    else okay=(*slots[n]==reinterpret_cast<void*>(original[n]))&&okay;
    // Preserve the preflight protection even if an earlier write succeeded but
    // its first protection-restoration call failed. Never claim that as clean.
    if (owned && slot_protection[n]) {
      DWORD ignored=0;MEMORY_BASIC_INFORMATION info{};
      const bool changed=VirtualProtect(slots[n],sizeof(void*),slot_protection[n],&ignored)!=FALSE;
      const bool queried=VirtualQuery(slots[n],&info,sizeof(info))==sizeof(info);
      okay=changed && queried && info.Protect==slot_protection[n] && okay;
    }
  }
  installed=false; status=okay?"restored":"restore-failed";
  return okay;
}

// Caller attests the loaded runtime's complete SHA above. Install before guest
// threads start, never on a running module. Only the current EXE's IAT is owned.
inline bool InstallEventImportTrace(HMODULE exe, HMODULE runtime, bool verified) {
  using namespace event_trace;
  if (!verified) {status="unsupported-sdk";return false;}
  if (installed || reserved.load()!=0) {status="already-used";return false;}
  if (!exe || exe!=GetModuleHandleW(nullptr) || !runtime ||
      runtime!=GetModuleHandleW(L"rexruntime.dll")) {status="module-mismatch";return false;}
  for (size_t n=0;n<kCount;++n) {
    original[n]=reinterpret_cast<PPCFunc*>(GetProcAddress(runtime,kNames[n]));
    if (!original[n]) {status="missing-export";return false;}
  }
  auto* base=reinterpret_cast<uint8_t*>(exe);
  auto* dos=reinterpret_cast<IMAGE_DOS_HEADER*>(base);
  auto* nt=reinterpret_cast<IMAGE_NT_HEADERS64*>(base+dos->e_lfanew);
  if (!Plan(base,nt->OptionalHeader.SizeOfImage,original,slots)) {status="import-guard-failed";return false;}
  for (size_t n=0;n<kCount;++n) {
    MEMORY_BASIC_INFORMATION info{};
    if (VirtualQuery(slots[n],&info,sizeof(info))!=sizeof(info) || info.State!=MEM_COMMIT ||
        (info.Protect&(PAGE_GUARD|PAGE_NOACCESS))) {status="iat-page-guard-failed";return false;}
    slot_protection[n]=info.Protect;
  }
  module_base=uintptr_t(base);module_size=nt->OptionalHeader.SizeOfImage;
  for (size_t n=0;n<kCount;++n) {
    if (!Exchange(slots[n],reinterpret_cast<void*>(original[n]),reinterpret_cast<void*>(wrappers[n]))) {
      RestoreEventImportTrace();status="install-failed-rollback-attempted";return false;
    }
  }
  installed=true;status="installed";return true;
}

// Call at the observation bound, outside hooks. Only acquire-ready immutable
// entries are read. Inflight wait pre entries need no matching post to be valid.
inline void DumpEventImportTrace(FILE* output=stdout) {
  using namespace event_trace;
  if (!output) return;
  const uint64_t snapshot=reserved.load(std::memory_order_acquire);
  const uint64_t count=snapshot&~kFrozen;
  const size_t cutoff=count<kCapacity?size_t(count):kCapacity;
  std::fprintf(output,"EVENT_TRACE status=%s capacity=%zu reserved=%llu dropped=%llu reset_export=absent frozen=%u weak_snapshot=1 cutoff=%zu\n",
              status.load(std::memory_order_acquire),kCapacity,(unsigned long long)count,(unsigned long long)dropped.load(),
              unsigned((snapshot&kFrozen)!=0),cutoff);
  std::fprintf(output,"EVENT_TRACE_MODULE base=%llX size=%zX\n",(unsigned long long)module_base,module_size);
  for (size_t i=0;i<cutoff;++i) {
    const Entry& e=ring[i];if (!e.ready.load(std::memory_order_acquire)) {
      std::fprintf(output,"EVENT_TRACE_PENDING slot=%zu\n",i);continue;
    }
    std::fprintf(output,"EVENT_TRACE_ENTRY slot=%zu call=%llu phase=%s api=%s thread=%u context=%llX lr=%llX sp=%llX r3=%llX r4=%llX r5=%llX r6=%llX r7=%llX r8=%llX r9=%llX r10=%llX result=%llX out_read=%u out_handle=%08X\n",
      i,(unsigned long long)e.call,e.phase?"post":"pre",kNames[e.api],e.thread,
      (unsigned long long)e.context,(unsigned long long)e.lr,(unsigned long long)e.sp,
      (unsigned long long)e.args[0],(unsigned long long)e.args[1],(unsigned long long)e.args[2],
      (unsigned long long)e.args[3],(unsigned long long)e.args[4],(unsigned long long)e.args[5],
      (unsigned long long)e.args[6],(unsigned long long)e.args[7],(unsigned long long)e.result,
      unsigned(e.out_read),e.out_handle);
    for (size_t f=0;f<e.frame_count;++f) {
      const uintptr_t pc=uintptr_t(e.frames[f]);
      if (module_base && pc>=module_base && pc-module_base<module_size)
        std::fprintf(output,"EVENT_TRACE_FRAME slot=%zu index=%zu address=%llX module=own rva=%llX\n",
                    i,f,(unsigned long long)pc,(unsigned long long)(pc-module_base));
      else std::fprintf(output,"EVENT_TRACE_FRAME slot=%zu index=%zu address=%llX module=other\n",
                       i,f,(unsigned long long)pc);
    }
  }
}
}  // namespace mc2::host
