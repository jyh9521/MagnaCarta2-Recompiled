#pragma once
// Diagnostic-only, bounded per-worker append log. No SDK/private memory reads.
#include <Windows.h>
#include <cstdint>
namespace mc2::input_probe {
struct Event { uint64_t sequence, object, argument; uint32_t thread, api, iteration, kind, gated, depth; };
inline constexpr unsigned capacity=65536, workers=2;
struct Stream { uint64_t count, dropped; Event events[capacity]; };
struct Trace { uint64_t magic, version, bytes; Stream streams[workers]; };
inline Trace* trace=nullptr;
inline HANDLE file=INVALID_HANDLE_VALUE,mapping=nullptr;
inline volatile LONG64 sequence=0;
inline thread_local unsigned worker=0,api=0,iteration=0,depth=0;
inline thread_local bool gated=false;
inline void* object=nullptr;
inline bool Open(const wchar_t* path) {
 file=CreateFileW(path,GENERIC_READ|GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
 if(file==INVALID_HANDLE_VALUE)return false;
 mapping=CreateFileMappingW(file,nullptr,PAGE_READWRITE,0,sizeof(Trace),nullptr);
 if(!mapping)return false;
 trace=static_cast<Trace*>(MapViewOfFile(mapping,FILE_MAP_WRITE,0,0,sizeof(Trace)));
 if(!trace)return false;
 trace->magic=0x373343415254324dULL;trace->version=1;trace->bytes=sizeof(Trace);return true;
}
inline void Record(unsigned kind, const void* arg=nullptr) {
 if(!trace)return;
 const auto saved_error=GetLastError();
 auto& s=trace->streams[worker];
 if(s.count<capacity) {
  auto& e=s.events[s.count];
  e={static_cast<uint64_t>(InterlockedIncrement64(&sequence)),reinterpret_cast<uint64_t>(object),reinterpret_cast<uint64_t>(arg),GetCurrentThreadId(),api,iteration,kind,unsigned(gated),depth};
  // Single writer per stream. Reader opens only after the process has exited.
  MemoryBarrier();++s.count;
 }else ++s.dropped;
 SetLastError(saved_error);
}
inline void Close() {if(trace){FlushViewOfFile(trace,0);UnmapViewOfFile(trace);trace=nullptr;}if(mapping)CloseHandle(mapping);if(file!=INVALID_HANDLE_VALUE)CloseHandle(file);}
}
