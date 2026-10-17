#pragma once
// Transparent SDK RAW hooks only. Bounded read-only guest snapshots; no replacement body or context writes.
#include <Windows.h>
#include <rex/hook.h>
#include "panic_observation.h"
#include <rex/ppc/func.h>
#include <array>
#include <atomic>
#include <cerrno>
#include <cstdint>
#include <cstdio>
namespace mc2::host {
inline constexpr char kMovieTraceRuntimeSha256[]="e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a";
namespace movie_trace {
inline constexpr size_t kCount=9,kCapacity=4096;
inline constexpr uint64_t kFrozen=uint64_t(1)<<63;
inline constexpr std::array<uint32_t,kCount> kTargets={0x8248FED8,0x82490CF0,0x827B6148,0x82490708,0x824909B8,0x82490C78,0x82491630,0x82491930,0x82491BD8};
static_assert(std::atomic<uint64_t>::is_always_lock_free);
struct Entry {std::atomic<bool> ready{false};uint64_t seq=0,call=0,parent=0,depth=0,tick_ms=0,context=0,lr=0,sp=0,result=0;std::array<uint64_t,8> args{};uint32_t target=0,phase=0,thread=0,obj=0,known=0;std::array<uint32_t,4> words{};uint32_t text_known=0,text_count=0;const char* name_status="not-read";std::array<char,385> name_hex{'-',0};};
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
inline void Record(size_t kind,uint32_t phase,uint64_t call,uint64_t parent,uint64_t depth,PPCContext& ctx,uint8_t* base,const std::array<uint64_t,8>& args){auto& p=partitions[kind];uint64_t index=p.reserved.load(std::memory_order_relaxed);do{if(index&kFrozen){p.suppressed.fetch_add(1,std::memory_order_relaxed);return;}}while(!p.reserved.compare_exchange_weak(index,index+1,std::memory_order_acq_rel));if(index>=kCapacity){p.dropped.fetch_add(1,std::memory_order_relaxed);return;}auto& e=p.entries[size_t(index)];e.seq=sequences.fetch_add(1,std::memory_order_relaxed)+1;e.call=call;e.parent=parent;e.depth=depth;e.tick_ms=GetTickCount64();e.target=kTargets[kind];e.phase=phase;e.thread=GetCurrentThreadId();e.context=uintptr_t(&ctx);e.lr=ctx.lr;e.sp=ctx.r1.u64;e.result=ctx.r3.u64;e.args=args;
 if(kind!=0 && kind!=2){const auto obj=uint32_t(args[0]);if(obj>=0x10000 && obj<=0x7EFFFF44){e.obj=obj;const uint32_t offsets[]={0x38,0x50,0x58,0xB8};for(unsigned j=0;j<4;++j){const auto read=panic_observation::ReadWord({base,0x100001000ULL},obj+offsets[j]);if(read.word_known){e.known|=1u<<j;e.words[j]=read.word;}}}}
 uint32_t container=kind==2?uint32_t(args[0]):(e.known&8)?e.words[3]:0;
 if(container>=0x10000&&container<=0x7EFFFFF8){const auto count=panic_observation::ReadWord({base,0x100001000ULL},container+4);if(count.word_known){e.text_known=1;e.text_count=count.word;}}
 uint32_t name=kind==1?uint32_t(args[2]):(kind==2||kind==3||kind==4)?uint32_t(args[1]):0;
 if(kind==2&&name){if(name>=0x10000&&name<=0x7EFFFFFC){const auto ptr=panic_observation::ReadWord({base,0x100001000ULL},name);if(ptr.word_known)name=ptr.word;else {name=0;e.name_status=panic_observation::StatusName(ptr.status);}}else {name=0;e.name_status="outside-ram";}}
 if(name){if(name>=0x10000 && name<=0x7EFFFF40){const auto read=panic_observation::ReadUtf16({base,0x100001000ULL},name,96);e.name_status=read.truncated?"truncated":panic_observation::StatusName(read.status);if(read.status==panic_observation::Status::ok&&read.terminated){static constexpr char hex[]="0123456789ABCDEF";for(size_t j=0;j<read.captured;++j){e.name_hex[j*2]=hex[read.bytes[j]>>4];e.name_hex[j*2+1]=hex[read.bytes[j]&15];}e.name_hex[read.captured*2]=0;}}else e.name_status="outside-ram";}
 e.ready.store(true,std::memory_order_release);}
template<size_t Kind> inline void Invoke(PPCContext& ctx,uint8_t* base,PPCFunc* original){if(!active.load(std::memory_order_acquire)){original(ctx,base);return;}const DWORD error=GetLastError();const int saved_errno=errno;const std::array<uint64_t,8> args={ctx.r3.u64,ctx.r4.u64,ctx.r5.u64,ctx.r6.u64,ctx.r7.u64,ctx.r8.u64,ctx.r9.u64,ctx.r10.u64};const uint64_t call=calls.fetch_add(1,std::memory_order_relaxed)+1,parent=current_call,depth=current_depth+1;auto& p=partitions[Kind];p.pre.fetch_add(1,std::memory_order_relaxed);Record(Kind,0,call,parent,depth,ctx,base,args);errno=saved_errno;SetLastError(error);{DelegateScope scope(p,call,depth);original(ctx,base);scope.returned=true;}const DWORD result_error=GetLastError();const int result_errno=errno;posts.fetch_add(1,std::memory_order_relaxed);p.post.fetch_add(1,std::memory_order_relaxed);Record(Kind,1,call,parent,depth,ctx,base,args);errno=result_errno;SetLastError(result_error);}
} // namespace movie_trace
// Parent attestation covers pinned SDK and exact generated/original boundaries;
// this boolean is not a process self-hash. Configure only before guest launch.
inline bool ConfigureMovieTrace(bool codeverified,bool enabled){using namespace movie_trace;if(configured.exchange(true))return false;if(enabled&&!codeverified){status="guard-failed";return false;}status=enabled?"enabled":"disabled";active.store(enabled,std::memory_order_release);return true;}
inline void FreezeMovieTrace(){using namespace movie_trace;active.store(false,std::memory_order_release);for(auto& p:partitions)p.reserved.fetch_or(kFrozen,std::memory_order_acq_rel);status="frozen";}
// No quiescence. Inflight/counters may change after freeze; unmatched pre and
// weak snapshots never establish deadlock, complete execution or first-frame proof.
inline void DumpMovieTrace(FILE* output=stdout){using namespace movie_trace;if(!output)return;uint64_t reserved=0,dropped=0,suppressed=0;bool frozen=true;for(auto& p:partitions){const auto n=p.reserved.load();reserved+=n&~kFrozen;dropped+=p.dropped.load();suppressed+=p.suppressed.load();frozen=frozen&&bool(n&kFrozen);}std::fprintf(output,"MOVIE_TRACE status=%s capacity=%zu targets=%zu total_capacity=%zu reserved=%llu calls=%llu posts=%llu unwound=%llu inflight=%llu dropped=%llu suppressed=%llu frozen=%u weak_snapshot=1\n",status.load(),kCapacity,kCount,kCapacity*kCount,(unsigned long long)reserved,(unsigned long long)calls.load(),(unsigned long long)posts.load(),(unsigned long long)unwound.load(),(unsigned long long)inflight.load(),(unsigned long long)dropped,(unsigned long long)suppressed,unsigned(frozen));for(size_t kind=0;kind<kCount;++kind){const auto& p=partitions[kind];const auto snapshot=p.reserved.load(std::memory_order_acquire),count=snapshot&~kFrozen;std::fprintf(output,"MOVIE_TARGET kind=%zu target=%08X reserved=%llu pre=%llu post=%llu unwound=%llu inflight=%llu dropped=%llu suppressed=%llu frozen=%u\n",kind,kTargets[kind],(unsigned long long)count,(unsigned long long)p.pre.load(),(unsigned long long)p.post.load(),(unsigned long long)p.unwound.load(),(unsigned long long)p.inflight.load(),(unsigned long long)p.dropped.load(),(unsigned long long)p.suppressed.load(),unsigned(bool(snapshot&kFrozen)));for(size_t i=0;i<count&&i<kCapacity;++i){const auto& e=p.entries[i];const auto slot=kind*kCapacity+i;if(!e.ready.load(std::memory_order_acquire)){std::fprintf(output,"MOVIE_PENDING slot=%zu\n",slot);continue;}std::fprintf(output,"MOVIE_ENTRY slot=%zu seq=%llu call=%llu parent=%llu depth=%llu target=%08X phase=%s thread=%u context=%llX lr=%llX sp=%llX tick_ms=%llu r3=%llX r4=%llX r5=%llX r6=%llX r7=%llX r8=%llX r9=%llX r10=%llX result=%llX obj=%X known=%X w38=%X w50=%X w58=%X wB8=%X text_known=%u text_count=%X name_status=%s name_hex=%s\n",slot,(unsigned long long)e.seq,(unsigned long long)e.call,(unsigned long long)e.parent,(unsigned long long)e.depth,e.target,e.phase?"post":"pre",e.thread,(unsigned long long)e.context,(unsigned long long)e.lr,(unsigned long long)e.sp,(unsigned long long)e.tick_ms,(unsigned long long)e.args[0],(unsigned long long)e.args[1],(unsigned long long)e.args[2],(unsigned long long)e.args[3],(unsigned long long)e.args[4],(unsigned long long)e.args[5],(unsigned long long)e.args[6],(unsigned long long)e.args[7],(unsigned long long)e.result,e.obj,e.known,e.words[0],e.words[1],e.words[2],e.words[3],e.text_known,e.text_count,e.name_status,e.name_hex.data());}}}
} // namespace mc2::host
REX_EXTERN(__imp__sub_8248FED8);
REX_EXTERN(__imp__sub_82490CF0);
REX_EXTERN(__imp__sub_827B6148);
REX_EXTERN(__imp__sub_82490708);
REX_EXTERN(__imp__sub_824909B8);
REX_EXTERN(__imp__sub_82490C78);
REX_EXTERN(__imp__sub_82491630);
REX_EXTERN(__imp__sub_82491930);
REX_EXTERN(__imp__sub_82491BD8);
REX_HOOK_RAW(sub_8248FED8){mc2::host::movie_trace::Invoke<0>(ctx,base,&__imp__sub_8248FED8);}
REX_HOOK_RAW(sub_82490CF0){mc2::host::movie_trace::Invoke<1>(ctx,base,&__imp__sub_82490CF0);}
REX_HOOK_RAW(sub_827B6148){mc2::host::movie_trace::Invoke<2>(ctx,base,&__imp__sub_827B6148);}
REX_HOOK_RAW(sub_82490708){mc2::host::movie_trace::Invoke<3>(ctx,base,&__imp__sub_82490708);}
REX_HOOK_RAW(sub_824909B8){mc2::host::movie_trace::Invoke<4>(ctx,base,&__imp__sub_824909B8);}
REX_HOOK_RAW(sub_82490C78){mc2::host::movie_trace::Invoke<5>(ctx,base,&__imp__sub_82490C78);}
REX_HOOK_RAW(sub_82491630){mc2::host::movie_trace::Invoke<6>(ctx,base,&__imp__sub_82491630);}
REX_HOOK_RAW(sub_82491930){mc2::host::movie_trace::Invoke<7>(ctx,base,&__imp__sub_82491930);}
REX_HOOK_RAW(sub_82491BD8){mc2::host::movie_trace::Invoke<8>(ctx,base,&__imp__sub_82491BD8);}
