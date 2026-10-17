#pragma once
// Default-off RAW observation of the original START consumer. Delegates unchanged.
#include <Windows.h>
#include <rex/hook.h>
#include <rex/ppc/func.h>
#include "panic_observation.h"
#include "confirm_event_trace.h"
#include <array>
#include <atomic>
#include <cerrno>
#include <cstdint>
#include <cstdio>
namespace mc2::host::start_event_trace {
inline constexpr size_t kCapacity=16384;
inline constexpr uint64_t kFrozen=uint64_t(1)<<63;
static_assert(std::atomic<uint64_t>::is_always_lock_free);
struct Entry {
 std::atomic<bool> ready{false};
 uint64_t seq=0,call=0,tick=0,context=0,lr=0,sp=0,result=0;
 std::array<uint64_t,5> args{};
 uint32_t thread=0,old_word=0;bool post=false,old_known=false;
 const char* old_status="not-read";
};
inline std::array<Entry,kCapacity> entries;
inline std::atomic<uint64_t> reserved{0},calls{0},posts{0},selected{0},selected_posts{0},invalid_user{0},unknown{0},unwound{0},inflight{0},dropped{0},suppressed{0},sequences{0};
inline std::atomic<bool> active{false},configured{false};
inline std::atomic<const char*> status{"not-configured"};
struct Word {bool known=false;uint32_t value=0;const char* status="not-read";};
inline Word ReadOld(uint8_t* base,uint32_t object,uint32_t user) {
 const uint64_t address=uint64_t(object)+0x4AC+uint64_t(user)*0xC0;
 if(address>0xFFFFFFFCULL)return {false,0,"address-overflow"};
 if(address<0x10000 || address+4>0x7F000000ULL)return {false,0,"outside-ram"};
 const auto value=panic_observation::ReadWord({base,0x100001000ULL},uint32_t(address));
 if(value.status!=panic_observation::Status::ok)return {false,0,panic_observation::StatusName(value.status)};
 return {true,value.word,"ok"};
}
inline void Record(uint64_t call,bool post,PPCContext& ctx,uint8_t* base,const std::array<uint64_t,5>& args) {
 uint64_t index=reserved.load(std::memory_order_relaxed);
 do{if(index&kFrozen){suppressed.fetch_add(1,std::memory_order_relaxed);return;}}
 while(!reserved.compare_exchange_weak(index,index+1,std::memory_order_acq_rel));
 if(index>=kCapacity){dropped.fetch_add(1,std::memory_order_relaxed);return;}
 const auto word=ReadOld(base,uint32_t(args[0]),uint32_t(args[2]));
 if(!word.known)unknown.fetch_add(1,std::memory_order_relaxed);
 auto& e=entries[size_t(index)];e.call=call;e.post=post;e.args=args;e.seq=sequences.fetch_add(1,std::memory_order_relaxed)+1;
 e.thread=GetCurrentThreadId();e.context=uintptr_t(&ctx);e.lr=ctx.lr;e.sp=ctx.r1.u64;e.result=ctx.r3.u64;e.tick=GetTickCount64();
 e.old_known=word.known;e.old_word=word.value;e.old_status=word.status;e.ready.store(true,std::memory_order_release);
}
struct Scope {bool returned=false;Scope(){inflight.fetch_add(1,std::memory_order_relaxed);}~Scope(){if(!returned)unwound.fetch_add(1,std::memory_order_relaxed);inflight.fetch_sub(1,std::memory_order_relaxed);}};
inline void Invoke(PPCContext& ctx,uint8_t* base,PPCFunc* original) {
 if(!active.load(std::memory_order_acquire)){original(ctx,base);return;}
 // Other helper invocations bypass all memory reads and observer Win32 calls.
 if(ctx.r4.u32!=5 || ctx.lr!=0x827B4D10){original(ctx,base);return;}
 if(ctx.r5.u64>3){invalid_user.fetch_add(1,std::memory_order_relaxed);original(ctx,base);return;}
 const DWORD before_error=GetLastError();const int before_errno=errno;
 const std::array<uint64_t,5> args={ctx.r3.u64,ctx.r4.u64,ctx.r5.u64,ctx.r6.u64,ctx.r7.u64};
 const uint64_t call=calls.fetch_add(1,std::memory_order_relaxed)+1;
 selected.fetch_add(1,std::memory_order_relaxed);Record(call,false,ctx,base,args);
 errno=before_errno;SetLastError(before_error);
 {Scope scope;original(ctx,base);scope.returned=true;} // Original exceptions/fatal behavior propagate.
 const DWORD result_error=GetLastError();const int result_errno=errno;
 posts.fetch_add(1,std::memory_order_relaxed);selected_posts.fetch_add(1,std::memory_order_relaxed);Record(call,true,ctx,base,args);
 errno=result_errno;SetLastError(result_error);
}
} // namespace mc2::host::start_event_trace
namespace mc2::host {
// Caller attests complete original ranges/SDK before launch. Not a process self-hash.
inline bool ConfigureStartEventTrace(bool codeverified,bool enabled){using namespace start_event_trace;if(configured.exchange(true))return false;if(enabled&&!codeverified){status="guard-failed";return false;}status=enabled?"enabled":"disabled";active.store(enabled,std::memory_order_release);return true;}
inline void FreezeStartEventTrace(){using namespace start_event_trace;active.store(false,std::memory_order_release);reserved.fetch_or(kFrozen,std::memory_order_acq_rel);status="frozen";}
inline void DumpStartEventTrace(FILE* output=stdout){using namespace start_event_trace;if(!output)return;const uint64_t snapshot=reserved.load(std::memory_order_acquire),count=snapshot&~kFrozen;
 std::fprintf(output,"START_EVENT_TRACE status=%s capacity=%zu reserved=%llu calls=%llu posts=%llu selected=%llu selected_posts=%llu invalid_user=%llu unknown=%llu unwound=%llu inflight=%llu dropped=%llu suppressed=%llu frozen=%u weak_snapshot=1\n",status.load(),kCapacity,(unsigned long long)count,(unsigned long long)calls.load(),(unsigned long long)posts.load(),(unsigned long long)selected.load(),(unsigned long long)selected_posts.load(),(unsigned long long)invalid_user.load(),(unsigned long long)unknown.load(),(unsigned long long)unwound.load(),(unsigned long long)inflight.load(),(unsigned long long)dropped.load(),(unsigned long long)suppressed.load(),unsigned(bool(snapshot&kFrozen)));
 for(size_t i=0;i<count&&i<kCapacity;++i){const auto& e=entries[i];if(!e.ready.load(std::memory_order_acquire)){std::fprintf(output,"START_EVENT_PENDING slot=%zu\n",i);continue;}
 std::fprintf(output,"START_EVENT_ENTRY slot=%zu seq=%llu call=%llu phase=%s thread=%u context=%llX lr=%llX sp=%llX obj=%llX key=%llX user=%llX opaque=%llX new_value=%llX old_known=%u old_word=%08X old_status=%s tick_ms=%llu result=%llX\n",i,(unsigned long long)e.seq,(unsigned long long)e.call,e.post?"post":"pre",e.thread,(unsigned long long)e.context,(unsigned long long)e.lr,(unsigned long long)e.sp,(unsigned long long)e.args[0],(unsigned long long)e.args[1],(unsigned long long)e.args[2],(unsigned long long)e.args[3],(unsigned long long)e.args[4],unsigned(e.old_known),e.old_word,e.old_status,(unsigned long long)e.tick,(unsigned long long)e.result);}}
} // namespace mc2::host
REX_EXTERN(__imp__sub_827B4938);
namespace mc2::host {inline void ConfirmThenOriginal(PPCContext& ctx,uint8_t* base){confirm_event_trace::Invoke(ctx,base,&__imp__sub_827B4938);}}
REX_HOOK_RAW(sub_827B4938){mc2::host::start_event_trace::Invoke(ctx,base,&mc2::host::ConfirmThenOriginal);}
