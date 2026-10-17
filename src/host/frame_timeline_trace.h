#pragma once
// Transparent SDK RAW hooks only. No guest reads/writes and no replacement body.
#include <Windows.h>
#include <rex/hook.h>
#include <rex/ppc/func.h>
#include <array>
#include <atomic>
#include <cerrno>
#include <cstdint>
#include <cstdio>
namespace mc2::host {
inline constexpr char kFrameTimelineRuntimeSha256[]="e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a";
namespace frame_timeline {
inline constexpr size_t kCount=5,kCapacity=8192;
inline constexpr uint64_t kFrozen=uint64_t(1)<<63;
inline constexpr std::array<uint32_t,kCount> kTargets={0x8277B6D8,0x8244A360,0x8286E618,0x82E20568,0x82399778};
static_assert(std::atomic<uint64_t>::is_always_lock_free);
struct Entry {std::atomic<bool> ready{false};uint64_t seq=0,call=0,parent=0,depth=0,tick_ms=0,context=0,lr=0,sp=0,result=0;std::array<uint64_t,8> args{};uint32_t target=0,phase=0,thread=0;};
struct Partition {std::atomic<uint64_t> reserved{0},pre{0},post{0},unwound{0},inflight{0},dropped{0},suppressed{0};std::array<Entry,kCapacity> entries;};
inline std::array<Partition,kCount> partitions;
inline std::atomic<uint64_t> calls{0},posts{0},unwound{0},inflight{0},sequences{0};
inline std::atomic<bool> active{false},configured{false};
inline std::atomic<const char*> status{"not-configured"};
inline thread_local uint64_t current_call=0,current_depth=0;
struct DelegateScope {
 Partition& part;uint64_t previous_call,previous_depth;bool returned=false;
 DelegateScope(Partition& p,uint64_t call,uint64_t depth):part(p),previous_call(current_call),previous_depth(current_depth){current_call=call;current_depth=depth;part.inflight.fetch_add(1,std::memory_order_relaxed);inflight.fetch_add(1,std::memory_order_relaxed);}
 ~DelegateScope(){current_call=previous_call;current_depth=previous_depth;if(!returned){part.unwound.fetch_add(1,std::memory_order_relaxed);unwound.fetch_add(1,std::memory_order_relaxed);}part.inflight.fetch_sub(1,std::memory_order_relaxed);inflight.fetch_sub(1,std::memory_order_relaxed);}
};
inline void Record(size_t kind,uint32_t phase,uint64_t call,uint64_t parent,uint64_t depth,PPCContext& ctx,const std::array<uint64_t,8>& args){auto& p=partitions[kind];uint64_t index=p.reserved.load(std::memory_order_relaxed);do{if(index&kFrozen){p.suppressed.fetch_add(1,std::memory_order_relaxed);return;}}while(!p.reserved.compare_exchange_weak(index,index+1,std::memory_order_acq_rel));if(index>=kCapacity){p.dropped.fetch_add(1,std::memory_order_relaxed);return;}auto& e=p.entries[size_t(index)];e.seq=sequences.fetch_add(1,std::memory_order_relaxed)+1;e.call=call;e.parent=parent;e.depth=depth;e.tick_ms=GetTickCount64();e.target=kTargets[kind];e.phase=phase;e.thread=GetCurrentThreadId();e.context=uintptr_t(&ctx);e.lr=ctx.lr;e.sp=ctx.r1.u64;e.result=ctx.r3.u64;e.args=args;e.ready.store(true,std::memory_order_release);}
template<size_t Kind> inline void Invoke(PPCContext& ctx,uint8_t* base,PPCFunc* original){if(!active.load(std::memory_order_acquire)){original(ctx,base);return;}const DWORD error=GetLastError();const int saved_errno=errno;const std::array<uint64_t,8> args={ctx.r3.u64,ctx.r4.u64,ctx.r5.u64,ctx.r6.u64,ctx.r7.u64,ctx.r8.u64,ctx.r9.u64,ctx.r10.u64};const uint64_t call=calls.fetch_add(1,std::memory_order_relaxed)+1,parent=current_call,depth=current_depth+1;auto& p=partitions[Kind];p.pre.fetch_add(1,std::memory_order_relaxed);Record(Kind,0,call,parent,depth,ctx,args);errno=saved_errno;SetLastError(error);{DelegateScope scope(p,call,depth);original(ctx,base);scope.returned=true;}const DWORD result_error=GetLastError();const int result_errno=errno;posts.fetch_add(1,std::memory_order_relaxed);p.post.fetch_add(1,std::memory_order_relaxed);Record(Kind,1,call,parent,depth,ctx,args);errno=result_errno;SetLastError(result_error);}
} // namespace frame_timeline
// Parent attestation covers pinned SDK and exact generated/original boundaries;
// this boolean is not a process self-hash. Configure only before guest launch.
inline bool ConfigureFrameTimeline(bool codeverified,bool enabled){using namespace frame_timeline;if(configured.exchange(true))return false;if(enabled&&!codeverified){status="guard-failed";return false;}status=enabled?"enabled":"disabled";active.store(enabled,std::memory_order_release);return true;}
inline void FreezeFrameTimeline(){using namespace frame_timeline;active.store(false,std::memory_order_release);for(auto& p:partitions)p.reserved.fetch_or(kFrozen,std::memory_order_acq_rel);status="frozen";}
// No quiescence. Inflight/counters may change after freeze; unmatched pre and
// weak snapshots never establish deadlock, complete execution or first-frame proof.
inline void DumpFrameTimeline(FILE* output=stdout){using namespace frame_timeline;if(!output)return;uint64_t reserved=0,dropped=0,suppressed=0;bool frozen=true;for(auto& p:partitions){const auto n=p.reserved.load();reserved+=n&~kFrozen;dropped+=p.dropped.load();suppressed+=p.suppressed.load();frozen=frozen&&bool(n&kFrozen);}std::fprintf(output,"TIMELINE_TRACE status=%s capacity=%zu targets=%zu total_capacity=%zu reserved=%llu calls=%llu posts=%llu unwound=%llu inflight=%llu dropped=%llu suppressed=%llu frozen=%u weak_snapshot=1\n",status.load(),kCapacity,kCount,kCapacity*kCount,(unsigned long long)reserved,(unsigned long long)calls.load(),(unsigned long long)posts.load(),(unsigned long long)unwound.load(),(unsigned long long)inflight.load(),(unsigned long long)dropped,(unsigned long long)suppressed,unsigned(frozen));for(size_t kind=0;kind<kCount;++kind){const auto& p=partitions[kind];const auto snapshot=p.reserved.load(std::memory_order_acquire),count=snapshot&~kFrozen;std::fprintf(output,"TIMELINE_TARGET kind=%zu target=%08X reserved=%llu pre=%llu post=%llu unwound=%llu inflight=%llu dropped=%llu suppressed=%llu frozen=%u\n",kind,kTargets[kind],(unsigned long long)count,(unsigned long long)p.pre.load(),(unsigned long long)p.post.load(),(unsigned long long)p.unwound.load(),(unsigned long long)p.inflight.load(),(unsigned long long)p.dropped.load(),(unsigned long long)p.suppressed.load(),unsigned(bool(snapshot&kFrozen)));for(size_t i=0;i<count&&i<kCapacity;++i){const auto& e=p.entries[i];const auto slot=kind*kCapacity+i;if(!e.ready.load(std::memory_order_acquire)){std::fprintf(output,"TIMELINE_PENDING slot=%zu\n",slot);continue;}std::fprintf(output,"TIMELINE_ENTRY slot=%zu seq=%llu call=%llu parent=%llu depth=%llu target=%08X phase=%s thread=%u context=%llX lr=%llX sp=%llX tick_ms=%llu r3=%llX r4=%llX r5=%llX r6=%llX r7=%llX r8=%llX r9=%llX r10=%llX result=%llX\n",slot,(unsigned long long)e.seq,(unsigned long long)e.call,(unsigned long long)e.parent,(unsigned long long)e.depth,e.target,e.phase?"post":"pre",e.thread,(unsigned long long)e.context,(unsigned long long)e.lr,(unsigned long long)e.sp,(unsigned long long)e.tick_ms,(unsigned long long)e.args[0],(unsigned long long)e.args[1],(unsigned long long)e.args[2],(unsigned long long)e.args[3],(unsigned long long)e.args[4],(unsigned long long)e.args[5],(unsigned long long)e.args[6],(unsigned long long)e.args[7],(unsigned long long)e.result);}}}
} // namespace mc2::host
REX_EXTERN(__imp__sub_8277B6D8);
REX_EXTERN(__imp__sub_8244A360);
REX_EXTERN(__imp__sub_8286E618);
REX_EXTERN(__imp__sub_82E20568);
REX_EXTERN(__imp__sub_82399778);
REX_HOOK_RAW(sub_8277B6D8){mc2::host::frame_timeline::Invoke<0>(ctx,base,&__imp__sub_8277B6D8);}
REX_HOOK_RAW(sub_8244A360){mc2::host::frame_timeline::Invoke<1>(ctx,base,&__imp__sub_8244A360);}
REX_HOOK_RAW(sub_8286E618){mc2::host::frame_timeline::Invoke<2>(ctx,base,&__imp__sub_8286E618);}
REX_HOOK_RAW(sub_82E20568){mc2::host::frame_timeline::Invoke<3>(ctx,base,&__imp__sub_82E20568);}
REX_HOOK_RAW(sub_82399778){mc2::host::frame_timeline::Invoke<4>(ctx,base,&__imp__sub_82399778);}
