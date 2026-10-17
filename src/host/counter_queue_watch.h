#pragma once
// Bounded read-only queue prefixes. Caller supplies verified code/SDK attestation
// and runs the optional sampling thread; this header creates no threads.
#include "schedule_observation.h"
#include <array>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstring>
namespace mc2::host {
struct QueueWatchSample {
 uint64_t tick_ms=0;std::array<uint64_t,20> fields{};uint32_t flags=0;
 std::array<uint8_t,32> head_bytes{};size_t head_captured=0;const char* head_status="not-read";
 std::array<uint8_t,12> table_bytes{};size_t table_captured=0;const char* table_status="not-read";
 const char* status="disabled";
};
namespace queue_watch {
namespace so=schedule_observation;namespace po=panic_observation;
inline constexpr uint32_t kCounter=0x83265218,kGlobal=0x83263ACC,kManager=0x83276B18;
inline constexpr size_t kCapacity=128;
inline constexpr uint64_t kFrozen=uint64_t(1)<<63;
struct Entry{std::atomic<bool> ready{false};QueueWatchSample sample;};
inline std::array<Entry,kCapacity> entries;
inline std::atomic<bool> active{false},configured{false};
inline std::atomic<uint64_t> reserved{0},dropped{0};
inline std::atomic<const char*> status{"not-configured"};
inline uint32_t Word(const uint8_t* p){return (uint32_t(p[0])<<24)|(uint32_t(p[1])<<16)|(uint32_t(p[2])<<8)|p[3];}
}
inline bool ConfigureQueueWatch(bool codeverified,bool enabled){using namespace queue_watch;if(configured.exchange(true))return false;if(enabled&&!codeverified){status="guard-failed";return false;}status=enabled?"enabled":"disabled";active.store(enabled,std::memory_order_release);return true;}
inline QueueWatchSample CaptureQueueWatch(uint8_t* base){using namespace queue_watch;QueueWatchSample s;if(!active.load(std::memory_order_acquire))return s;s.tick_ms=GetTickCount64();s.status="fixed-unreadable";po::GuestView view{base,0x100001000ULL};auto field=[&](size_t slot,uint64_t address){if(so::Read(view,address,4,s.fields[slot]))s.flags|=uint32_t(1)<<slot;};field(0,kCounter);field(1,kGlobal);for(size_t i=0;i<7;++i)field(2+i,uint64_t(kManager)+4*i);
 // x0 counter word; x1 global raw word; x2..8 manager begin/end/write/wrap/reserved/read/alignment.
 constexpr uint32_t critical=(1u<<2)|(1u<<3)|(1u<<4)|(1u<<7);
 if((s.flags&critical)!=critical)return s;
 const uint64_t begin=s.fields[2],end=s.fields[3],write=s.fields[4],head=s.fields[7];
 if(head==write){s.status="empty";return s;}
 if(begin>head||head>=end||write<begin||write>end||end-head<4){s.status="bounds-invalid";return s;}
 const size_t bytes=size_t(end-head<32?end-head:32);
 if(!so::DataRange(head,bytes)){s.status="bounds-invalid";return s;}
 const auto prefix=po::ReadBytes(view,uint32_t(head),bytes);s.head_status=po::StatusName(prefix.status);
 if(prefix.status!=po::Status::ok||prefix.captured!=bytes){s.status="head-unreadable";return s;}
 s.head_captured=bytes;std::memcpy(s.head_bytes.data(),prefix.bytes.data(),bytes);
 // x9 raw first head word. x13..19 remaining prefix words, only complete BE32s.
 for(size_t i=0;i<bytes/4;++i){const size_t slot=i?12+i:9;s.fields[slot]=Word(s.head_bytes.data()+i*4);s.flags|=uint32_t(1)<<slot;}
 const uint64_t table=s.fields[9];s.status="head-only";
 // Follow only a 12-byte original-image table prefix; do not execute slot4.
 if(table<0x82000000ULL||table+12>0x83330000ULL){s.table_status="outside-image";return s;}
 const auto vtable=po::ReadBytes(view,uint32_t(table),12);s.table_status=po::StatusName(vtable.status);
 if(vtable.status!=po::Status::ok||vtable.captured!=12)return s;
 s.table_captured=12;std::memcpy(s.table_bytes.data(),vtable.bytes.data(),12);
 for(size_t i=0;i<3;++i){s.fields[10+i]=Word(s.table_bytes.data()+i*4);s.flags|=uint32_t(1)<<(10+i);}
 s.status="captured";return s;
}
inline bool StoreQueueWatch(const QueueWatchSample& sample){using namespace queue_watch;if(!active.load(std::memory_order_acquire))return false;if(sample.head_captured>sample.head_bytes.size()||sample.table_captured>sample.table_bytes.size()||!sample.status||!sample.head_status||!sample.table_status)return false;uint64_t index=reserved.load(std::memory_order_relaxed);do{if(index&kFrozen)return false;}while(!reserved.compare_exchange_weak(index,index+1,std::memory_order_acq_rel));if(index>=kCapacity){dropped.fetch_add(1,std::memory_order_relaxed);return false;}entries[size_t(index)].sample=sample;entries[size_t(index)].ready.store(true,std::memory_order_release);return true;}
inline void FreezeQueueWatch(){using namespace queue_watch;active.store(false,std::memory_order_release);reserved.fetch_or(kFrozen,std::memory_order_acq_rel);status="frozen";}
// Weak snapshot: no queue consistency/ownership, instruction execution or
// deadlock conclusion follows. Caller should stop/join its monitor before dump.
inline void DumpQueueWatch(FILE* output=stdout){using namespace queue_watch;if(!output)return;const uint64_t snapshot=reserved.load(std::memory_order_acquire),count=snapshot&~kFrozen;std::fprintf(output,"QUEUE_WATCH_TRACE status=%s capacity=%zu reserved=%llu dropped=%llu frozen=%u weak_snapshot=1 counter=%08X global=%08X manager=%08X\n",status.load(),kCapacity,(unsigned long long)count,(unsigned long long)dropped.load(),unsigned(bool(snapshot&kFrozen)),kCounter,kGlobal,kManager);for(size_t i=0;i<count&&i<kCapacity;++i){const auto& e=entries[i];if(!e.ready.load(std::memory_order_acquire)){std::fprintf(output,"QUEUE_WATCH_PENDING slot=%zu\n",i);continue;}const auto& s=e.sample;std::fprintf(output,"QUEUE_WATCH_ENTRY slot=%zu tick_ms=%llu status=%s flags=%08X",i,(unsigned long long)s.tick_ms,s.status,s.flags);for(size_t x=0;x<s.fields.size();++x)std::fprintf(output," x%zu=%llX",x,(unsigned long long)s.fields[x]);std::fprintf(output," head_captured=%zu head_status=%s head_hex=",s.head_captured,s.head_status);for(size_t b=0;b<s.head_captured;++b)std::fprintf(output,"%02X",s.head_bytes[b]);std::fprintf(output," table_captured=%zu table_status=%s table_hex=",s.table_captured,s.table_status);for(size_t b=0;b<s.table_captured;++b)std::fprintf(output,"%02X",s.table_bytes[b]);std::fprintf(output,"\n");}}
} // namespace mc2::host
