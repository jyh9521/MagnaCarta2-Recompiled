#pragma once
// Default-off, post-return observation. Include this RAW hook in one host TU.
// Same-context original delegation; no input fabrication or guest/context writes.
#include "schedule_observation.h"
#include <rex/hook.h>
#include <rex/ppc/func.h>
#include <array>
#include <atomic>
#include <cerrno>
#include <cstdint>
#include <cstdio>

namespace mc2::host::input_state_trace {
inline constexpr size_t kCapacity=8192;
inline constexpr uint64_t kFrozen=uint64_t(1)<<63;
static_assert(std::atomic<uint64_t>::is_always_lock_free);
struct Entry {
 std::atomic<bool> ready{false};
 uint64_t seq=0,call=0,context=0,lr=0,sp=0,user=0,state_address=0,status=0,tick_ms=0;
 uint32_t thread=0,captured=0;
 const char* read_status="not-read-status";
 std::array<uint8_t,16> bytes{};
};
inline std::array<Entry,kCapacity> entries;
inline std::atomic<uint64_t> reserved{0},calls{0},posts{0},dropped{0},suppressed{0},sequences{0};
inline std::atomic<bool> active{false},configured{false};
inline std::atomic<const char*> status{"not-configured"};
struct Arguments {uint64_t call,context,lr,sp,user,address;uint32_t thread;};
inline void Record(const Arguments& args,const PPCContext& ctx,uint8_t* base) noexcept {
 uint64_t index=reserved.load(std::memory_order_relaxed);
 do {if(index&kFrozen){suppressed.fetch_add(1,std::memory_order_relaxed);return;}}
 while(!reserved.compare_exchange_weak(index,index+1,std::memory_order_acq_rel));
 if(index>=kCapacity){dropped.fetch_add(1,std::memory_order_relaxed);return;}
 auto& e=entries[size_t(index)];
 e.seq=sequences.fetch_add(1,std::memory_order_relaxed)+1;e.call=args.call;e.context=args.context;
 e.lr=args.lr;e.sp=args.sp;e.user=args.user;e.state_address=args.address;e.thread=args.thread;
 e.status=ctx.r3.u64;e.tick_ms=GetTickCount64();e.captured=0;e.bytes.fill(0);e.read_status="not-read-status";
 if(e.status!=0){e.ready.store(true,std::memory_order_release);return;}
 const uint64_t address=args.address;
 if(address>UINT32_MAX || address<0x10000 || address+16>0x7F000000ULL || !schedule_observation::DataRange(address,16))e.read_status="outside-ordinary-ram";
 else {
  namespace po=panic_observation;
  const auto value=po::ReadBytes({base,0x100001000ULL},uint32_t(address),16);
  e.read_status=po::StatusName(value.status);
  if(value.status==po::Status::ok && value.captured==16){e.captured=16;for(size_t i=0;i<16;++i)e.bytes[i]=value.bytes[i];}
  else if(value.status==po::Status::ok)e.read_status="unexpected-length";
 }
 e.ready.store(true,std::memory_order_release);
}
inline void Invoke(PPCContext& ctx,uint8_t* base,PPCFunc* original) {
 if(!active.load(std::memory_order_acquire)){original(ctx,base);return;}
 const DWORD error=GetLastError();const int saved_errno=errno;
 const Arguments args{calls.fetch_add(1,std::memory_order_relaxed)+1,uintptr_t(&ctx),ctx.lr,ctx.r1.u64,ctx.r3.u64,ctx.r4.u64,GetCurrentThreadId()};
 errno=saved_errno;SetLastError(error);
 original(ctx,base); // Original exceptions/faults propagate unchanged; no invented post.
 const DWORD result_error=GetLastError();const int result_errno=errno;
 posts.fetch_add(1,std::memory_order_relaxed);Record(args,ctx,base);
 errno=result_errno;SetLastError(result_error);
}
} // namespace mc2::host::input_state_trace
namespace mc2::host {
// Caller attests the exact original adapter, generated binding and SDK before launch.
inline bool ConfigureInputStateTrace(bool codeverified,bool enabled) {
 using namespace input_state_trace;if(configured.exchange(true))return false;
 if(enabled&&!codeverified){status="guard-failed";return false;}
 status=enabled?"enabled":"disabled";active.store(enabled,std::memory_order_release);return true;
}
inline void FreezeInputStateTrace() {
 using namespace input_state_trace;active.store(false,std::memory_order_release);
 reserved.fetch_or(kFrozen,std::memory_order_acq_rel);status="frozen";
}
// Not a quiescence barrier: in-flight originals can return after this snapshot.
// Ready entries never mutate. All 16 bytes are separate post-call, non-atomic data.
inline void DumpInputStateTrace(FILE* output=stdout) {
 using namespace input_state_trace;if(!output)return;
 const auto snapshot=reserved.load(std::memory_order_acquire),count=snapshot&~kFrozen;
 std::fprintf(output,"INPUT_STATE_TRACE status=%s capacity=%zu reserved=%llu calls=%llu posts=%llu dropped=%llu suppressed=%llu frozen=%u weak_snapshot=1\n",status.load(),kCapacity,(unsigned long long)count,(unsigned long long)calls.load(),(unsigned long long)posts.load(),(unsigned long long)dropped.load(),(unsigned long long)suppressed.load(),unsigned(bool(snapshot&kFrozen)));
 for(size_t i=0;i<count&&i<kCapacity;++i){const auto& e=entries[i];
  if(!e.ready.load(std::memory_order_acquire)){std::fprintf(output,"INPUT_STATE_PENDING slot=%zu\n",i);continue;}
  std::fprintf(output,"INPUT_STATE_ENTRY slot=%zu seq=%llu call=%llu thread=%u context=%llX lr=%llX sp=%llX user=%llX state_address=%llX status=%llX tick_ms=%llu captured=%u read_status=%s hex=",i,(unsigned long long)e.seq,(unsigned long long)e.call,e.thread,(unsigned long long)e.context,(unsigned long long)e.lr,(unsigned long long)e.sp,(unsigned long long)e.user,(unsigned long long)e.state_address,(unsigned long long)e.status,(unsigned long long)e.tick_ms,e.captured,e.read_status);
  if(e.captured==16)for(auto byte:e.bytes)std::fprintf(output,"%02X",unsigned(byte));else std::fputc('-',output);
  std::fputc('\n',output);
 }
}
} // namespace mc2::host
REX_EXTERN(__imp__sub_82868178);
REX_HOOK_RAW(sub_82868178){mc2::host::input_state_trace::Invoke(ctx,base,&__imp__sub_82868178);}
