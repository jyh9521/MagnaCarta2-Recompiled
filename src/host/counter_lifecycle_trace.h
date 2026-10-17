#pragma once
// Default-off observation through the SDK's supported strong RAW hook surface.
// Every path delegates exactly once to the generated always-original __imp__ body.
#include <Windows.h>
#include <rex/hook.h>
#include <rex/ppc/func.h>
#include <array>
#include <atomic>
#include <cerrno>
#include <cstdint>
#include <cstdio>

namespace mc2::host {
inline constexpr char kCounterLifecycleRuntimeSha256[]="e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a";
inline constexpr size_t kExtraWords=20;
struct CounterExtra {std::array<uint64_t,kExtraWords> values{};uint32_t flags=0,selection=0;};
using CounterExtraHook=CounterExtra(*)(uint32_t,uint32_t,const PPCContext&,uint8_t*,const std::array<uint64_t,8>&,uint64_t,const CounterExtra&);
namespace counter_trace {
inline constexpr size_t kCount=3,kCapacity=8192;
inline constexpr uint64_t kFrozen=uint64_t(1)<<63;
inline constexpr std::array<uint32_t,kCount> kTargets={0x82399650,0x82399738,0x822D0A68};
static_assert(std::atomic<uint64_t>::is_always_lock_free);
struct Entry {
 std::atomic<bool> ready{false};uint64_t seq=0,call=0,parent=0,context=0,lr=0,sp=0,result=0;
 std::array<uint64_t,8> args{};CounterExtra extra{};uint32_t thread=0,target=0,phase=0;
};
struct Partition {
 std::atomic<uint64_t> reserved{0},pre{0},post{0},selected{0},selected_post{0},unknown{0},unknown_post{0},dropped{0},suppressed{0};
 std::array<Entry,kCapacity> entries;
};
inline std::array<Partition,kCount> partitions;
inline std::atomic<uint64_t> calls{0},posts{0},sequences{0};
inline std::atomic<bool> active{false},configured{false};
inline std::atomic<const char*> status{"not-configured"};
inline CounterExtraHook hook=nullptr; // Set before Configure/guest launch; immutable thereafter.
inline thread_local uint64_t parent_call=0;
struct ParentScope {uint64_t previous;explicit ParentScope(uint64_t call,bool selected):previous(parent_call){if(selected)parent_call=call;}~ParentScope(){parent_call=previous;}};
inline CounterExtra Probe(uint32_t target,uint32_t phase,const PPCContext& ctx,uint8_t* base,const std::array<uint64_t,8>& args,uint64_t call,const CounterExtra& pre) {
 try {auto x=hook(target,phase,ctx,base,args,call,pre);if(x.selection>2){x.selection=2;x.flags|=0x80000000u;}return x;}
 catch(...) {CounterExtra x;x.selection=2;x.flags=0x80000000u;return x;}
}
inline void Record(size_t kind,uint32_t phase,uint64_t call,uint64_t parent,PPCContext& ctx,const std::array<uint64_t,8>& args,const CounterExtra& extra) {
 auto& p=partitions[kind];uint64_t index=p.reserved.load(std::memory_order_relaxed);
 do {if(index&kFrozen){p.suppressed.fetch_add(1,std::memory_order_relaxed);return;}}while(!p.reserved.compare_exchange_weak(index,index+1,std::memory_order_acq_rel));
 if(index>=kCapacity){p.dropped.fetch_add(1,std::memory_order_relaxed);return;}
 auto& e=p.entries[size_t(index)];e.seq=sequences.fetch_add(1,std::memory_order_relaxed)+1;e.call=call;e.parent=parent;e.target=kTargets[kind];e.phase=phase;e.thread=GetCurrentThreadId();e.context=uintptr_t(&ctx);e.lr=ctx.lr;e.sp=ctx.r1.u64;e.result=ctx.r3.u64;e.args=args;e.extra=extra;e.ready.store(true,std::memory_order_release);
}
template<size_t Kind> inline void Invoke(PPCContext& ctx,uint8_t* base,PPCFunc* original) {
 if(!active.load(std::memory_order_acquire)){original(ctx,base);return;}
 const DWORD error=GetLastError();const int saved_errno=errno;
 const std::array<uint64_t,8> args={ctx.r3.u64,ctx.r4.u64,ctx.r5.u64,ctx.r6.u64,ctx.r7.u64,ctx.r8.u64,ctx.r9.u64,ctx.r10.u64};
 const uint64_t call=calls.fetch_add(1,std::memory_order_relaxed)+1,parent=parent_call;
 auto& p=partitions[Kind];p.pre.fetch_add(1,std::memory_order_relaxed);
 const CounterExtra empty{},pre=Probe(kTargets[Kind],0,ctx,base,args,call,empty);
 if(pre.selection==1){p.selected.fetch_add(1,std::memory_order_relaxed);Record(Kind,0,call,parent,ctx,args,pre);}
 else if(pre.selection==2)p.unknown.fetch_add(1,std::memory_order_relaxed);
 errno=saved_errno;SetLastError(error);
 {ParentScope scope(call,pre.selection==1);original(ctx,base);} // Exceptions propagate; TLS alone is restored.
 const DWORD result_error=GetLastError();const int result_errno=errno;
 posts.fetch_add(1,std::memory_order_relaxed);p.post.fetch_add(1,std::memory_order_relaxed);
 if(pre.selection==1){p.selected_post.fetch_add(1,std::memory_order_relaxed);auto post=Probe(kTargets[Kind],1,ctx,base,args,call,pre);if(post.selection==2)p.unknown_post.fetch_add(1,std::memory_order_relaxed);Record(Kind,1,call,parent,ctx,args,post);}
 errno=result_errno;SetLastError(result_error);
}
} // namespace counter_trace
inline uint64_t CurrentCounterParentCall(){return counter_trace::parent_call;}
inline bool SetCounterLifecycleHook(CounterExtraHook hook){using namespace counter_trace;if(configured.load()||active.load())return false;counter_trace::hook=hook;return true;}
// codeverified is a parent attestation of exact original bodies and fixed SDK;
// no independent process self-hash or guest-data ownership is implied.
inline bool ConfigureCounterLifecycleTrace(bool codeverified,bool enabled){using namespace counter_trace;if(configured.exchange(true))return false;if(enabled&&(!codeverified||!hook)){status="guard-failed";return false;}status=enabled?"enabled":"disabled";active.store(enabled,std::memory_order_release);return true;}
inline void FreezeCounterLifecycleTrace(){using namespace counter_trace;active.store(false,std::memory_order_release);for(auto& p:partitions)p.reserved.fetch_or(kFrozen,std::memory_order_acq_rel);status="frozen";}
// No quiescence: already-observing delegates can still change aggregate counters.
// Acquire-ready entries are immutable; an unmatched pre is not a deadlock proof.
inline void DumpCounterLifecycleTrace(FILE* output=stdout){using namespace counter_trace;if(!output)return;uint64_t reserved=0,dropped=0,suppressed=0;bool frozen=true;for(auto& p:partitions){const auto n=p.reserved.load();reserved+=n&~kFrozen;dropped+=p.dropped.load();suppressed+=p.suppressed.load();frozen=frozen&&bool(n&kFrozen);}std::fprintf(output,"COUNTER_TRACE status=%s capacity=%zu targets=%zu total_capacity=%zu reserved=%llu calls=%llu posts=%llu dropped=%llu suppressed=%llu frozen=%u weak_snapshot=1\n",status.load(),kCapacity,kCount,kCapacity*kCount,(unsigned long long)reserved,(unsigned long long)calls.load(),(unsigned long long)posts.load(),(unsigned long long)dropped,(unsigned long long)suppressed,unsigned(frozen));
 for(size_t kind=0;kind<kCount;++kind){auto& p=partitions[kind];const auto snapshot=p.reserved.load(std::memory_order_acquire),count=snapshot&~kFrozen;std::fprintf(output,"COUNTER_TARGET kind=%zu target=%08X reserved=%llu pre=%llu post=%llu selected=%llu selected_post=%llu unknown=%llu unknown_post=%llu dropped=%llu suppressed=%llu frozen=%u\n",kind,kTargets[kind],(unsigned long long)count,(unsigned long long)p.pre.load(),(unsigned long long)p.post.load(),(unsigned long long)p.selected.load(),(unsigned long long)p.selected_post.load(),(unsigned long long)p.unknown.load(),(unsigned long long)p.unknown_post.load(),(unsigned long long)p.dropped.load(),(unsigned long long)p.suppressed.load(),unsigned(bool(snapshot&kFrozen)));
 for(size_t i=0;i<count&&i<kCapacity;++i){const auto& e=p.entries[i];const auto slot=kind*kCapacity+i;if(!e.ready.load(std::memory_order_acquire)){std::fprintf(output,"COUNTER_PENDING slot=%zu\n",slot);continue;}std::fprintf(output,"COUNTER_ENTRY slot=%zu seq=%llu call=%llu parent=%llu target=%08X phase=%s thread=%u context=%llX lr=%llX sp=%llX r3=%llX r4=%llX r5=%llX r6=%llX r7=%llX r8=%llX r9=%llX r10=%llX result=%llX selection=%u flags=%08X",slot,(unsigned long long)e.seq,(unsigned long long)e.call,(unsigned long long)e.parent,e.target,e.phase?"post":"pre",e.thread,(unsigned long long)e.context,(unsigned long long)e.lr,(unsigned long long)e.sp,(unsigned long long)e.args[0],(unsigned long long)e.args[1],(unsigned long long)e.args[2],(unsigned long long)e.args[3],(unsigned long long)e.args[4],(unsigned long long)e.args[5],(unsigned long long)e.args[6],(unsigned long long)e.args[7],(unsigned long long)e.result,e.extra.selection,e.extra.flags);for(size_t x=0;x<kExtraWords;++x)std::fprintf(output," x%zu=%llX",x,(unsigned long long)e.extra.values[x]);std::fprintf(output,"\n");}}
}
} // namespace mc2::host
REX_EXTERN(__imp__sub_82399650);
REX_EXTERN(__imp__sub_82399738);
REX_EXTERN(__imp__sub_822D0A68);
REX_HOOK_RAW(sub_82399650){mc2::host::counter_trace::Invoke<0>(ctx,base,&__imp__sub_82399650);}
REX_HOOK_RAW(sub_82399738){mc2::host::counter_trace::Invoke<1>(ctx,base,&__imp__sub_82399738);}
REX_HOOK_RAW(sub_822D0A68){mc2::host::counter_trace::Invoke<2>(ctx,base,&__imp__sub_822D0A68);}
