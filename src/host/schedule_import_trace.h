#pragma once
// Default-off scoped host-IAT observation. Delegates unchanged; no guest reads/writes.
// PE planner/exchange guards derived from event_import_trace.h, retained separately
// to avoid changing the established event observer contract.
#include <Windows.h>
#include <rex/ppc/context.h>
#include <array>
#include <atomic>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstring>
namespace mc2::host {
inline constexpr char kScheduleImportRuntimeSha256[]="e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a";
struct ScheduleExtra {std::array<uint64_t,8> values{};uint32_t flags=0;};
using ScheduleSampleHook=ScheduleExtra(*)(uint32_t,const PPCContext&,uint8_t*);
namespace schedule_trace {
inline constexpr size_t kCount=3,kKeysPerApi=64,kKeys=kCount*kKeysPerApi,kBins=128;
inline constexpr uint64_t kBucketMs=500;
inline constexpr std::array<const char*,kCount> kNames={"__imp__KeDelayExecutionThread","__imp__RtlEnterCriticalSection","__imp__RtlLeaveCriticalSection"};
static_assert(std::atomic<uint64_t>::is_always_lock_free);
struct Entry {
  std::atomic<bool> ready{false};
  uint64_t call=0,tick=0,context=0,lr=0,sp=0,result=0,r29=0,r30=0,r31=0;
  std::array<uint64_t,8> args{};
  uint32_t thread=0;
  ScheduleExtra extra{};
};
struct Sample {std::atomic<bool> claimed{false};Entry pre,post;};
struct Key {
  std::atomic<unsigned> state{0}; // 0 empty; 1 publishing; 2 immutable identity ready
  uint32_t api=0,thread=0;uint64_t lr=0;
  std::array<uint64_t,3> args{}; // delay r3/r4/r5; CS only r3, other slots zero
  std::atomic<uint64_t> pre{0},post{0},sampled{0};
  std::array<Sample,kBins> samples;
};
inline std::array<Key,kKeys> keys;
inline std::array<PPCFunc*,kCount> original{};
inline std::array<void**,kCount> slots{};
inline std::array<DWORD,kCount> slot_protection{};
inline std::atomic<uint64_t> calls{0},posts{0},key_overflow{0},late{0};
inline std::array<std::atomic<uint64_t>,kCount> api_pre{},api_post{},api_overflow{};
inline std::atomic<bool> active{false},frozen{false};
inline uint64_t epoch=0; // Set before guest launch; never changed while hooks run.
inline bool installed=false;
inline ScheduleSampleHook sample_hook=nullptr;
inline std::atomic<const char*> status{"not-installed"};

inline Key* FindKey(uint32_t api,uint32_t thread,uint64_t lr,const std::array<uint64_t,8>& args) {
  const std::array<uint64_t,3> identity={args[0],api==0?args[1]:0,api==0?args[2]:0};
  // Non-blocking bounded scan of this API's reserved partition. A publishing slot is skipped; rare
  // duplicate identities remain separate groups, not merged or silently lost.
  for(size_t index=api*kKeysPerApi;index<(api+1)*kKeysPerApi;++index) {
    auto& k=keys[index];
    unsigned state=k.state.load(std::memory_order_acquire);
    if(state==2 && k.api==api && k.thread==thread && k.lr==lr && k.args==identity)return &k;
    if(state==0 && k.state.compare_exchange_strong(state,1,std::memory_order_acq_rel)) {
      k.api=api;k.thread=thread;k.lr=lr;k.args=identity;k.state.store(2,std::memory_order_release);return &k;
    }
  }
  key_overflow.fetch_add(1,std::memory_order_relaxed);api_overflow[api].fetch_add(1,std::memory_order_relaxed);return nullptr;
}
inline void Record(Entry& e,uint64_t call,uint64_t tick,PPCContext& ctx,const std::array<uint64_t,8>& args) {
  e.call=call;e.tick=tick;e.context=uintptr_t(&ctx);e.lr=ctx.lr;e.sp=ctx.r1.u64;
  e.result=ctx.r3.u64;e.r29=ctx.r29.u64;e.r30=ctx.r30.u64;e.r31=ctx.r31.u64;
  e.args=args;e.thread=GetCurrentThreadId();e.ready.store(true,std::memory_order_release);
}
template<size_t Api> inline void Invoke(PPCContext& ctx,uint8_t* base) {
  if(!active.load(std::memory_order_acquire)){original[Api](ctx,base);return;}
  const DWORD saved_error=GetLastError();const int saved_errno=errno;
  const std::array<uint64_t,8> args={ctx.r3.u64,ctx.r4.u64,ctx.r5.u64,ctx.r6.u64,ctx.r7.u64,ctx.r8.u64,ctx.r9.u64,ctx.r10.u64};
  const uint64_t call=calls.fetch_add(1,std::memory_order_relaxed),tick=GetTickCount64()-epoch;
  api_pre[Api].fetch_add(1,std::memory_order_relaxed);
  Key* key=FindKey(uint32_t(Api),GetCurrentThreadId(),ctx.lr,args);Sample* sample=nullptr;
  if(key) {
    key->pre.fetch_add(1,std::memory_order_relaxed);
    const uint64_t bin=tick/kBucketMs;
    if(bin<kBins) {
      auto& candidate=key->samples[size_t(bin)];bool empty=false;
      if(candidate.claimed.compare_exchange_strong(empty,true,std::memory_order_acq_rel)) {
        sample=&candidate;key->sampled.fetch_add(1,std::memory_order_relaxed);
        if(sample_hook) {try {sample->pre.extra=sample_hook(uint32_t(Api),ctx,base);} catch(...) {sample->pre.extra.flags=0x80000000u;}}
        Record(sample->pre,call,tick,ctx,args);
      }
    } else late.fetch_add(1,std::memory_order_relaxed);
  }
  errno=saved_errno;SetLastError(saved_error);
  original[Api](ctx,base); // Exactly once; exceptions propagate without repair.
  const DWORD result_error=GetLastError();const int result_errno=errno;
  posts.fetch_add(1,std::memory_order_relaxed);api_post[Api].fetch_add(1,std::memory_order_relaxed);
  if(key)key->post.fetch_add(1,std::memory_order_relaxed);
  if(sample)Record(sample->post,call,GetTickCount64()-epoch,ctx,args);
  errno=result_errno;SetLastError(result_error);
}
inline const std::array<PPCFunc*,kCount> wrappers={&Invoke<0>,&Invoke<1>,&Invoke<2>};
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
} // namespace schedule_trace
inline bool SetScheduleSampleHook(ScheduleSampleHook hook) {
  using namespace schedule_trace;
  if(installed || active.load() || calls.load()!=0 || frozen.load())return false;
  sample_hook=hook;return true;
}

inline bool RestoreScheduleImportTrace() {
  using namespace schedule_trace;
  // Disable new observations before restoring owned slots. Already-observing
  // delegates may publish their post or counters; dumps explicitly remain weak.
  active.store(false,std::memory_order_release); frozen.store(true,std::memory_order_release);
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
inline bool InstallScheduleImportTrace(HMODULE exe, HMODULE runtime, bool verified) {
  using namespace schedule_trace;
  if (!verified) {status="unsupported-sdk";return false;}
  if (installed || calls.load()!=0 || frozen.load()) {status="already-used";return false;}
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
  epoch=GetTickCount64();
  for (size_t n=0;n<kCount;++n) {
    if (!Exchange(slots[n],reinterpret_cast<void*>(original[n]),reinterpret_cast<void*>(wrappers[n]))) {
      RestoreScheduleImportTrace();status="install-failed-rollback-attempted";return false;
    }
  }
  installed=true;status="installed";active.store(true,std::memory_order_release);return true;
}


// Weak snapshot of atomic counters plus acquire-ready immutable samples. A
// blocked/throwing sampled call has pre but no post; that alone is not deadlock.
inline void DumpScheduleImportTrace(FILE* output=stdout) {
  using namespace schedule_trace;if(!output)return;
  std::fprintf(output,"SCHEDULE_TRACE status=%s keys=%zu bins=%zu bucket_ms=%llu calls=%llu posts=%llu key_overflow=%llu late=%llu frozen=%u weak_snapshot=1 elapsed_ms=%llu\n",status.load(),kKeys,kBins,(unsigned long long)kBucketMs,(unsigned long long)calls.load(),(unsigned long long)posts.load(),(unsigned long long)key_overflow.load(),(unsigned long long)late.load(),unsigned(frozen.load()),(unsigned long long)(GetTickCount64()-epoch));
  for(size_t api=0;api<kCount;++api)std::fprintf(output,"SCHEDULE_API api=%s pre=%llu post=%llu key_overflow=%llu\n",kNames[api],(unsigned long long)api_pre[api].load(),(unsigned long long)api_post[api].load(),(unsigned long long)api_overflow[api].load());
  for(size_t i=0;i<kKeys;++i) {
    const auto& k=keys[i];if(k.state.load(std::memory_order_acquire)!=2)continue;
    std::fprintf(output,"SCHEDULE_KEY key=%zu api=%s thread=%u lr=%llX a0=%llX a1=%llX a2=%llX pre=%llu post=%llu sampled=%llu\n",i,kNames[k.api],k.thread,(unsigned long long)k.lr,(unsigned long long)k.args[0],(unsigned long long)k.args[1],(unsigned long long)k.args[2],(unsigned long long)k.pre.load(),(unsigned long long)k.post.load(),(unsigned long long)k.sampled.load());
    for(size_t bin=0;bin<kBins;++bin) {
      const auto& s=k.samples[bin];if(!s.claimed.load(std::memory_order_acquire))continue;
      for(unsigned phase=0;phase<2;++phase) {
        const auto& e=phase?s.post:s.pre;
        if(!e.ready.load(std::memory_order_acquire)){std::fprintf(output,"SCHEDULE_PENDING key=%zu bin=%zu phase=%s\n",i,bin,phase?"post":"pre");continue;}
        std::fprintf(output,"SCHEDULE_ENTRY key=%zu bin=%zu phase=%s call=%llu tick_ms=%llu thread=%u context=%llX lr=%llX sp=%llX r3=%llX r4=%llX r5=%llX r6=%llX r7=%llX r8=%llX r9=%llX r10=%llX result=%llX r29=%llX r30=%llX r31=%llX flags=%08X x0=%llX x1=%llX x2=%llX x3=%llX x4=%llX x5=%llX x6=%llX x7=%llX\n",i,bin,phase?"post":"pre",(unsigned long long)e.call,(unsigned long long)e.tick,e.thread,(unsigned long long)e.context,(unsigned long long)e.lr,(unsigned long long)e.sp,(unsigned long long)e.args[0],(unsigned long long)e.args[1],(unsigned long long)e.args[2],(unsigned long long)e.args[3],(unsigned long long)e.args[4],(unsigned long long)e.args[5],(unsigned long long)e.args[6],(unsigned long long)e.args[7],(unsigned long long)e.result,(unsigned long long)e.r29,(unsigned long long)e.r30,(unsigned long long)e.r31,e.extra.flags,(unsigned long long)e.extra.values[0],(unsigned long long)e.extra.values[1],(unsigned long long)e.extra.values[2],(unsigned long long)e.extra.values[3],(unsigned long long)e.extra.values[4],(unsigned long long)e.extra.values[5],(unsigned long long)e.extra.values[6],(unsigned long long)e.extra.values[7]);
      }
    }
  }
}
} // namespace mc2::host
