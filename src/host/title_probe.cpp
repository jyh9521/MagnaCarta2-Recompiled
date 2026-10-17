// Unmodified generated-module / SDK title-launch probe. No guest data fixtures.
#include "mc2_probe_init.h"
#include "presentation_probe.h"
#include "wait_observation.h"
#include "event_import_trace.h"
#include "schedule_observation.h"
#include "counter_observation.h"
#include "counter_queue_watch.h"
#include "counter_worker_sample.h"
#include "frame_timeline_observation.h"
#include "guest_output_capture.h"
#include "scripted_controller_probe.h"
#include "start_input_observation.h"
#include <rex/input/input_system.h>
#include "panic_observation.h"
#include <thread>
#include <rex/cvar.h>
#include <rex/runtime.h>
#include <rex/system/function_dispatcher.h>
#include <rex/system/xthread.h>
#include <rex/logging.h>
#include <rex/kernel/init.h>
#include <rex/system/gpu_plugin.h>
#include <rex/audio/sdl/sdl_audio_system.h>
#include <rex/input/input_system.h>
#include <Windows.h>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <filesystem>
#include <exception>
#include <spdlog/sinks/base_sink.h>

extern void mc2_probe_RegisterFunctions(rex::runtime::IModuleRegistrar*);
namespace {
uint8_t* guest_base = nullptr;
volatile LONG launch_phase = 0;
rex::system::KernelState* kernel_state = nullptr;
bool wait_sdk_verified = false;
bool event_trace_requested = false;
bool schedule_trace_requested = false;
bool counter_trace_requested = false;
bool timeline_requested = false;
bool capture_guest_output_requested = false;
bool input_trace_requested=false;
bool scripted_start_requested=false;
bool scripted_neutral_requested=false;
std::atomic<unsigned> input_dump_index{0};
void WriteInputTrace(const char* reason){
 const auto index=input_dump_index.fetch_add(1);if(index>=4)return;
 mc2::host::FreezeInputStateTrace();mc2::host::FreezeStartEventTrace();
 char name[64]{};std::snprintf(name,sizeof(name),"input-state-%u.txt",index);auto* file=std::fopen(name,"wb");bool okay=file&&std::setvbuf(file,nullptr,_IOFBF,64*1024)==0;
 if(file){mc2::host::DumpInputStateTrace(file);okay=std::ferror(file)==0&&okay;okay=std::fclose(file)==0&&okay;}
 std::printf("INPUT_STATE_FILE reason=%s path=%s success=%u\n",reason,name,unsigned(okay));
 std::snprintf(name,sizeof(name),"start-event-%u.txt",index);file=std::fopen(name,"wb");okay=file&&std::setvbuf(file,nullptr,_IOFBF,64*1024)==0;
 if(file){mc2::host::DumpStartEventTrace(file);okay=std::ferror(file)==0&&okay;okay=std::fclose(file)==0&&okay;}
 std::printf("START_EVENT_FILE reason=%s path=%s success=%u\n",reason,name,unsigned(okay));
 if(scripted_start_requested)mc2::host::DumpScriptedController();
}

std::atomic<unsigned> timeline_dump_index{0};
void WriteFrameTimeline(const char* reason) {
 const auto index=timeline_dump_index.fetch_add(1);if(index>=4)return;
 mc2::host::FreezeFrameTimeline();char name[64]{};std::snprintf(name,sizeof(name),"frame-timeline-%u.txt",index);
 auto* file=std::fopen(name,"wb");bool okay=file && std::setvbuf(file,nullptr,_IOFBF,64*1024)==0;
 if(file){mc2::host::DumpFrameTimeline(file);okay=std::ferror(file)==0&&okay;okay=std::fclose(file)==0&&okay;}
 std::printf("FRAME_TIMELINE_FILE reason=%s path=%s success=%u\n",reason,name,unsigned(okay));
}

std::atomic<unsigned> queue_dump_index{0};
void WriteQueueWatch(const char* reason) {
 const auto index=queue_dump_index.fetch_add(1);if(index>=4)return;mc2::host::FreezeQueueWatch();
 char name[64]{};std::snprintf(name,sizeof(name),"queue-watch-%u.txt",index);auto* file=std::fopen(name,"wb");bool okay=file && std::setvbuf(file,nullptr,_IOFBF,64*1024)==0;
 if(file){mc2::host::DumpQueueWatch(file);okay=std::ferror(file)==0&&okay;okay=std::fclose(file)==0&&okay;}
 std::printf("QUEUE_WATCH_FILE reason=%s path=%s success=%u\n",reason,name,unsigned(okay));
}
std::atomic<unsigned> counter_dump_index{0};
void WriteCounterTrace(const char* reason) {
 const auto index=counter_dump_index.fetch_add(1);if(index>=4)return;
 mc2::host::FreezeCounterLifecycleTrace();
 char name[64]{};std::snprintf(name,sizeof(name),"counter-trace-%u.txt",index);
 auto* file=std::fopen(name,"wb");bool okay=file && std::setvbuf(file,nullptr,_IOFBF,64*1024)==0;
 if(file){mc2::host::DumpCounterLifecycleTrace(file);okay=std::ferror(file)==0&&okay;okay=std::fclose(file)==0&&okay;}
 std::printf("COUNTER_TRACE_FILE reason=%s path=%s success=%u\n",reason,name,unsigned(okay));
}
std::atomic<unsigned> schedule_dump_index{0};
void WriteScheduleTrace(const char* reason) {
  const auto index=schedule_dump_index.fetch_add(1);if(index>=4)return;
  char name[64]{};std::snprintf(name,sizeof(name),"schedule-trace-%u.txt",index);
  auto* file=std::fopen(name,"wb");bool okay=file && std::setvbuf(file,nullptr,_IOFBF,64*1024)==0;
  if(file){mc2::host::DumpScheduleImportTrace(file);okay=std::ferror(file)==0 && okay;okay=std::fclose(file)==0 && okay;}
  std::printf("SCHEDULE_TRACE_FILE reason=%s path=%s success=%u\n",reason,name,unsigned(okay));
}
thread_local bool critical_capture_active = false;
std::atomic<unsigned> critical_capture_count{0};
std::atomic<unsigned> event_dump_index{0};
void WriteEventTrace(const char* reason) {
  const auto index=event_dump_index.fetch_add(1);
  if(index>=4){std::printf("EVENT_TRACE_FILE reason=%s path=- success=0 limit=1\n",reason);return;}
  char name[64]{};std::snprintf(name,sizeof(name),"event-trace-%u.txt",index);
  auto* file=std::fopen(name,"wb");
  bool okay=file && std::setvbuf(file,nullptr,_IOFBF,64*1024)==0;
  if(file){mc2::host::DumpEventImportTrace(file);okay=std::ferror(file)==0 && okay;okay=std::fclose(file)==0 && okay;}
  std::printf("EVENT_TRACE_FILE reason=%s path=%s success=%u\n",reason,name,unsigned(okay));
}
uint32_t Read32(uint32_t address) {
  uint32_t value; std::memcpy(&value,guest_base+address,sizeof(value));return __builtin_bswap32(value);
}
bool Readable(uint32_t address,uint32_t size) {
  MEMORY_BASIC_INFORMATION memory{};
  auto host=reinterpret_cast<uintptr_t>(guest_base)+address;
  return size && address<=UINT32_MAX-size && VirtualQuery(reinterpret_cast<void*>(host),&memory,sizeof(memory)) &&
    memory.State==MEM_COMMIT && !(memory.Protect&(PAGE_NOACCESS|PAGE_GUARD)) &&
    host+size<=reinterpret_cast<uintptr_t>(memory.BaseAddress)+memory.RegionSize;
}
void NativeState() {
  uint32_t bound=0,fallback=0;
  for(uint32_t i=0;i<4096;++i) {auto value=Read32(0x83250D80+i*4);bound+=value!=0;fallback+=value==0x82505980;}
  std::printf("TITLE_NATIVES guard=%u bound=%u fallback=%u int_const=%08X add=%08X\n",
    Read32(0x8327B660),bound,fallback,Read32(0x83250D80+29*4),Read32(0x83250D80+146*4));
  if(auto* table=std::fopen("title-natives.bin","wb")){std::fwrite(guest_base+0x83250D80,4,4096,table);std::fclose(table);}
}
void PrintFrame(const char* kind, unsigned sample, unsigned index, uintptr_t address) {
  HMODULE module=nullptr;char name[MAX_PATH]{};
  GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
    reinterpret_cast<LPCSTR>(address),&module);
  if(module)GetModuleFileNameA(module,name,MAX_PATH);
  std::printf("%s sample=%u index=%u address=%016llX rva=%llX module=%s\n",kind,sample,index,
    static_cast<unsigned long long>(address),address-reinterpret_cast<uintptr_t>(module),name);
}
class FatalDiagnosticSink final : public spdlog::sinks::base_sink<std::mutex> {
  void sink_it_(const spdlog::details::log_msg& message) override {
    const std::string_view payload(message.payload.data(),message.payload.size());
    if(!launch_phase || payload.find("Call to invalid or unregistered function at guest address")==std::string_view::npos)return;
    std::printf("TITLE_FATAL %.*s\n",int(payload.size()),payload.data());
    void* frames[48]{};const auto count=CaptureStackBackTrace(0,48,frames,nullptr);
    for(USHORT i=0;i<count;++i)PrintFrame("TITLE_FATAL_STACK",0,i,reinterpret_cast<uintptr_t>(frames[i]));
    if(auto* state=rex::runtime::ThreadState::Get()) {
      auto* c=state->context();
      std::printf("TITLE_FATAL_PPC r1=%08X r3=%08X r4=%08X lr=%08X ctr=%08X\n",
        c->r1.u32,c->r3.u32,c->r4.u32,unsigned(c->lr),c->ctr.u32);
    }
    NativeState();
    if(event_trace_requested)WriteEventTrace("fault");
    if(schedule_trace_requested)WriteScheduleTrace("fault");
    if(counter_trace_requested){WriteCounterTrace("fault");WriteQueueWatch("fault");}
    if(timeline_requested)WriteFrameTimeline("fault");
    if(input_trace_requested)WriteInputTrace("fault");
  }
  void flush_() override {std::fflush(stdout);}
};
void SampleThread(rex::system::XThread* thread) {
  auto handle=static_cast<HANDLE>(thread->thread()->native_handle());
  for(unsigned sample=0;sample<3;++sample) {
    if(SuspendThread(handle)==DWORD(-1)){std::printf("TITLE_SAMPLE_FAILED error=%lu\n",GetLastError());return;}
    uint32_t wait_handle=0; bool sampled_wait=false;
    CONTEXT context{};context.ContextFlags=CONTEXT_FULL;
    if(GetThreadContext(handle,&context)) {
      auto* c=thread->thread_state()->context();
      std::printf("TITLE_SAMPLE sample=%u pc=%016llX r1=%08X r3=%08X r4=%08X r11=%08X lr=%08X ctr=%08X\n",
        sample,context.Rip,c->r1.u32,c->r3.u32,c->r4.u32,c->r11.u32,unsigned(c->lr),c->ctr.u32);
      std::printf("TITLE_NONVOL sample=%u r13=%08X r29=%08X r30=%08X r31=%08X\n",
        sample,c->r13.u32,c->r29.u32,c->r30.u32,c->r31.u32);
      sampled_wait=c->lr==0x82869BC0 && c->ctr.u32==0x8248B100;
      wait_handle=c->r3.u32;
      const auto object=c->r29.u32;
      if(Readable(object,11016)) {
        auto read_address=Read32(object+10896);
        if(Readable(read_address,4))std::printf("TITLE_RING sample=%u object=%08X field_10888=%08X read_address=%08X read=%08X write=%08X flags=%02X field_11008=%08X field_11012=%08X\n",
          sample,object,Read32(object+10888),read_address,Read32(read_address),Read32(object+10908),
          unsigned(guest_base[object+10941]),Read32(object+11008),Read32(object+11012));
      }
      for(unsigned i=0;i<40 && context.Rip;++i) {
        PrintFrame("TITLE_SAMPLE_STACK",sample,i,context.Rip);
        DWORD64 image_base=0;auto* entry=RtlLookupFunctionEntry(context.Rip,&image_base,nullptr);
        if(entry) {
          PVOID handler=nullptr;DWORD64 establisher=0;
          RtlVirtualUnwind(UNW_FLAG_NHANDLER,image_base,context.Rip,entry,&context,&handler,&establisher,nullptr);
        } else {
          MEMORY_BASIC_INFORMATION memory{};
          if(!VirtualQuery(reinterpret_cast<void*>(context.Rsp),&memory,sizeof(memory)) || memory.State!=MEM_COMMIT ||
              (memory.Protect&(PAGE_NOACCESS|PAGE_GUARD)))break;
          context.Rip=*reinterpret_cast<DWORD64*>(context.Rsp);context.Rsp+=8;
        }
      }
    } else std::printf("TITLE_SAMPLE_FAILED error=%lu\n",GetLastError());
    ResumeThread(handle);
    if(sampled_wait)mc2::host::ObserveWaitObject(kernel_state,sample,wait_handle,wait_sdk_verified);
    Sleep(250);
  }
  NativeState();
}
namespace po = mc2::host::panic_observation;
void PrintPanicRead(const char* tag,const po::Result& value) {
  std::printf("PANIC_READ tag=%s guest=%08X status=%s captured=%zu terminated=%u truncated=%u word_known=%u word=%08X hex=",
      tag,value.guest,po::StatusName(value.status),value.captured,unsigned(value.terminated),unsigned(value.truncated),unsigned(value.word_known),value.word);
  for(size_t i=0;i<value.captured;++i)std::printf("%02X",unsigned(value.bytes[i]));
  std::printf("\n");
}
bool PanicCodeMatches(po::GuestView view) {
  static constexpr uint32_t guards[][2]={
    {0x82390A20,0x7D8802A6},{0x82390A24,0x9181FFF8},{0x82390A44,0x9421FFA0},
    {0x82390A4C,0x3D408328},{0x82390A58,0x386AC318},{0x82390A5C,0x38801000},
    {0x82390A68,0x484E0111},{0x82390A6C,0x3900000D},{0x82390A70,0x91000003},{0x82390A80,0x4E800020},
    {0x82484490,0x3D409E2A},{0x82484494,0x813A0000},{0x82484498,0x3D60820B},
    {0x8248449C,0x614883C1},{0x824844A0,0x3B8BA120},{0x824844A4,0x7F094040},{0x824844A8,0x419A0054}};
  for(const auto& guard:guards){auto got=po::ReadWord(view,guard[0]);if(!got.word_known || got.word!=guard[1])return false;}
  return true;
}
void ObserveOriginalPanic(const EXCEPTION_RECORD& record,const PPCContext& c) {
  const char* requested=std::getenv("MC2_CAPTURE_PANIC");
  if(!requested || std::strcmp(requested,"1")!=0)return;
  po::GuestView view{guest_base,0x100001000ULL};
  const bool match=record.ExceptionCode==EXCEPTION_ACCESS_VIOLATION && record.NumberParameters>=2 &&
    record.ExceptionInformation[0]==1 && record.ExceptionInformation[1]==reinterpret_cast<uintptr_t>(guest_base)+3 &&
    c.lr==0x82390A6C && PanicCodeMatches(view);
  std::printf("PANIC_GATE requested=1 matched=%u lr=%08X\n",unsigned(match),unsigned(c.lr));
  if(!match)return;
  PPCContext before;std::memcpy(&before,&c,sizeof(c));
  PrintPanicRead("message",po::ReadUtf16(view,0x8327C318,4096));
  const uint64_t lr_address=uint64_t(c.r1.u32)+0x58;
  auto caller=lr_address<=UINT32_MAX-3?po::ReadWord(view,uint32_t(lr_address)):po::ReadWord(view,0);
  std::printf("PANIC_CALLER known=%u saved_lr=%08X r25=%08X r26=%08X r30=%08X\n",
    unsigned(caller.word_known),caller.word,c.r25.u32,c.r26.u32,c.r30.u32);
  if(caller.word_known && caller.word==0x824844F4){
    PrintPanicRead("header_word",po::ReadWord(view,c.r26.u32));
    PrintPanicRead("header_prefix",po::ReadBytes(view,c.r26.u32,16));
    const uint64_t args_address=uint64_t(c.r1.u32)+0x78;
    auto arg=args_address<=UINT32_MAX-7?po::ReadBytes(view,uint32_t(args_address),8):po::ReadBytes(view,0,8);
    PrintPanicRead("saved_first_arg",arg);
    if(arg.captured==8){
      uint64_t raw=0;for(size_t i=0;i<8;++i)raw=(raw<<8)|arg.bytes[i];
      std::printf("PANIC_FILENAME source=saved_first_arg raw=%016llX\n",static_cast<unsigned long long>(raw));
      PrintPanicRead("filename",po::ReadUtf16(view,uint32_t(raw),4096));
    }
    const uint64_t object_end=uint64_t(c.r30.u32)+0xE0;
    if(object_end<=UINT32_MAX-3){
      auto count=po::ReadWord(view,uint32_t(object_end));auto pointer=po::ReadWord(view,c.r30.u32+0xDC);
      std::printf("PANIC_FILENAME_CANDIDATE count_known=%u count=%08X pointer_known=%u pointer=%08X fallback=%08X\n",
        unsigned(count.word_known),count.word,unsigned(pointer.word_known),pointer.word,c.r25.u32);
    }
  }
  std::printf("PANIC_CAPTURE_END context_unchanged=%u resumes_guest=0\n",unsigned(std::memcmp(&before,&c,sizeof(c))==0));
}


// Opt-in post-fault observation only. Never alter guest/context state or recover AVs.
bool CriticalDataRange(uint32_t address,size_t count) {
  const uint64_t end=uint64_t(address)+count;
  return count && count<=64 && address>=0x10000 &&
    ((address<0x7F000000 && end<=0x7F000000) ||
     (address>=0x82000000 && end<=0x83330000)); // Exclude MMIO and physical aliases.
}
bool CriticalCallerMatches(po::GuestView view) {
  static constexpr uint8_t expected[]={0x7D,0x88,0x02,0xA6,0x48,0x4B,0x01,0x89,0x3B,0xE1,0xFF,0x40,0x94,0x21,0xFF,0x40,0x81,0x63,0x00,0x08,0x7C,0x7D,0x1B,0x78,0x7C,0x9C,0x23,0x78,0x3B,0xCB,0x00,0x04,0x7C,0xBB,0x2B,0x78,0x7F,0xC3,0xF3,0x78,0x7C,0xDA,0x33,0x78,0x91,0x7F,0x00,0x60,0x7C,0xF9,0x3B,0x78,0x7D,0x18,0x43,0x78,0x7D,0x37,0x4B,0x78,0x48,0xAC,0xEB,0x39,0x7F,0x0A,0xC3,0x78,0x92,0xE1,0x00,0x54,0x39,0x20,0x00,0x00,0x7F,0x28,0xCB,0x78,0x38,0xE0,0x00,0x00,0x7F,0x46,0xD3,0x78,0x7F,0x65,0xDB,0x78,0x7F,0x84,0xE3,0x78,0x7F,0xA3,0xEB,0x78,0x4B,0xFF,0xF7,0x15,0x7C,0x7D,0x1B,0x78,0x7F,0xC3,0xF3,0x78,0x48,0xAC,0xEB,0x15,0x7F,0xA3,0xEB,0x78,0x38,0x3F,0x00,0xC0,0x48,0x4B,0x01,0x60};
  auto actual=po::ReadBytes(view,0x823BF278,sizeof(expected));
  return actual.status==po::Status::ok && actual.captured==sizeof(expected) &&
    std::memcmp(actual.bytes.data(),expected,sizeof(expected))==0;
}
bool CriticalSdkBytes(uintptr_t entry) {
  static constexpr uint8_t expected[]={0x56,0x57,0x53,0x48,0x83,0xEC,0x30,0x48,0x89,0xCE,0xE8,0x91,0x40,0xE4,0xFF,0x8B,0x78,0x58,0x48,0x8B,0x0E,0x8B,0x41,0x18};
  uint8_t actual[sizeof(expected)]{};SIZE_T received=0;
  return entry && po::detail::Preflight(entry,sizeof(expected))==po::Status::ok &&
    ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<const void*>(entry),actual,sizeof(actual),&received) &&
    received==sizeof(actual) && std::memcmp(actual,expected,sizeof(expected))==0;
}
void PrintCriticalRead(const char* tag,po::GuestView view,uint32_t address,size_t count,bool word) {
  po::Result value{};value.guest=address;value.requested=count;
  if(CriticalDataRange(address,count))value=word?po::ReadWord(view,address):po::ReadBytes(view,address,count);
  else value.status=po::Status::outside_span;
  std::printf("CRITICAL_READ tag=%s guest=%08X requested=%zu status=%s captured=%zu word_known=%u word=%08X hex=",
    tag,value.guest,value.requested,po::StatusName(value.status),value.captured,unsigned(value.word_known),value.word);
  for(size_t i=0;i<value.captured;++i)std::printf("%02X",unsigned(value.bytes[i]));
  std::printf("\n");
}
void ObserveCriticalSectionFault(const EXCEPTION_RECORD& record,const PPCContext& c,const CONTEXT* host_context) {
  const char* requested=std::getenv("MC2_CAPTURE_CRITICAL_SECTION");
  if(!requested || std::strcmp(requested,"1")!=0 || critical_capture_active)return;
  if(record.ExceptionCode!=EXCEPTION_ACCESS_VIOLATION || record.NumberParameters<2 ||
      record.ExceptionInformation[0]!=0 || c.lr!=0x823BF2B8)return;
  if(critical_capture_count.fetch_add(1)>=4)return;
  critical_capture_active=true;
  struct Reset {~Reset(){critical_capture_active=false;}} reset;
  PPCContext before;std::memcpy(&before,&c,sizeof(c));
  CONTEXT host_before{};if(host_context)std::memcpy(&host_before,host_context,sizeof(host_before));
  po::GuestView view{guest_base,0x100001000ULL};
  auto module=GetModuleHandleA("rexruntime.dll");
  const auto entry=reinterpret_cast<uintptr_t>(module?GetProcAddress(module,
    "?RtlEnterCriticalSection_entry@xboxkrnl@kernel@rex@@YAXV?$MappedPtr@UX_RTL_CRITICAL_SECTION@xboxkrnl@kernel@rex@@@3@@Z"):nullptr);
  const bool sdk_pc=wait_sdk_verified && module && entry==reinterpret_cast<uintptr_t>(module)+0x408F80 &&
    reinterpret_cast<uintptr_t>(record.ExceptionAddress)==entry+0x15;
  const bool sdk_bytes=sdk_pc && CriticalSdkBytes(entry);
  const bool caller_bytes=sdk_bytes && c.lr==0x823BF2B8 && CriticalCallerMatches(view);
  const auto base=reinterpret_cast<uintptr_t>(guest_base);
  const bool host_range=guest_base && base<=UINTPTR_MAX-uint64_t(c.r3.u32)-0x18;
  const bool host_fault=host_range && record.ExceptionCode==EXCEPTION_ACCESS_VIOLATION &&
    record.NumberParameters>=2 && record.ExceptionInformation[0]==0 &&
    record.ExceptionInformation[1]==base+uint64_t(c.r3.u32)+0x18;
  const bool host_rcx=host_range && host_context && host_context->Rcx==base+uint64_t(c.r3.u32);
  const bool match=sdk_pc && sdk_bytes && caller_bytes && host_fault && host_rcx;
  std::printf("CRITICAL_GATE requested=1 matched=%u sdk_pc=%u sdk_bytes=%u caller_bytes=%u host_fault=%u host_rcx=%u lr=%08X\n",
    unsigned(match),unsigned(sdk_pc),unsigned(sdk_bytes),unsigned(caller_bytes),unsigned(host_fault),unsigned(host_rcx),unsigned(c.lr));
  if(match){
    std::printf("CRITICAL_PPC r3=%016llX r11=%016llX r29=%016llX r30=%016llX\n",
      static_cast<unsigned long long>(c.r3.u64),static_cast<unsigned long long>(c.r11.u64),
      static_cast<unsigned long long>(c.r29.u64),static_cast<unsigned long long>(c.r30.u64));
    const uint64_t field=uint64_t(c.r29.u32)+8;
    PrintCriticalRead("entry_word",view,field<=UINT32_MAX?uint32_t(field):0,4,true);
    PrintCriticalRead("entry_prefix",view,c.r29.u32,64,false);
    PrintCriticalRead("critical_prefix",view,c.r3.u32,32,false);
  }
  std::printf("CRITICAL_CAPTURE_END context_unchanged=%u host_context_unchanged=%u resumes_guest=0\n",
    unsigned(std::memcmp(&before,&c,sizeof(c))==0),
    unsigned(!host_context || std::memcmp(&host_before,host_context,sizeof(host_before))==0));
}

LONG CALLBACK RecordException(EXCEPTION_POINTERS* pointers) {
  if(critical_capture_active)return EXCEPTION_CONTINUE_SEARCH;
  if(mc2::host::EventTraceMemoryReadActive())return EXCEPTION_CONTINUE_SEARCH;
  auto* record = pointers->ExceptionRecord;
  if (!launch_phase || (record->ExceptionCode != EXCEPTION_ACCESS_VIOLATION &&
      record->ExceptionCode != EXCEPTION_BREAKPOINT && record->ExceptionCode != EXCEPTION_ILLEGAL_INSTRUCTION))
    return EXCEPTION_CONTINUE_SEARCH;
  std::printf("TITLE_EXCEPTION code=%08lX ip=%p phase=%ld thread=%lu\n",
      record->ExceptionCode, record->ExceptionAddress, launch_phase, GetCurrentThreadId());
  if(record->NumberParameters >= 2) {
    std::printf("TITLE_FAULT operation=%llu address=%016llX guest_offset=%016llX\n",
      static_cast<unsigned long long>(record->ExceptionInformation[0]),
      static_cast<unsigned long long>(record->ExceptionInformation[1]),
      static_cast<unsigned long long>(record->ExceptionInformation[1])-reinterpret_cast<uintptr_t>(guest_base));
  }
  void* frames[48]{};
  auto count = CaptureStackBackTrace(0, 48, frames, nullptr);
  for (USHORT i=0;i<count;++i) {
    HMODULE module = nullptr; char name[MAX_PATH]{};
    GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
      reinterpret_cast<LPCSTR>(frames[i]), &module);
    if(module) GetModuleFileNameA(module,name,MAX_PATH);
    std::printf("TITLE_STACK %u address=%p rva=%llX module=%s\n",i,frames[i],
      reinterpret_cast<uintptr_t>(frames[i])-reinterpret_cast<uintptr_t>(module),name);
  }
  if (auto* state = rex::runtime::ThreadState::Get()) {
    auto* c=state->context();
    std::printf("TITLE_PPC r1=%08X r3=%08X r4=%08X lr=%08X ctr=%08X\n",
      c->r1.u32,c->r3.u32,c->r4.u32,unsigned(c->lr),c->ctr.u32);
    ObserveOriginalPanic(*record,*c);
    ObserveCriticalSectionFault(*record,*c,pointers->ContextRecord);
  }
  NativeState();
  if(event_trace_requested)WriteEventTrace("fault");
    if(schedule_trace_requested)WriteScheduleTrace("fault");
    if(counter_trace_requested){WriteCounterTrace("fault");WriteQueueWatch("fault");}
    if(timeline_requested)WriteFrameTimeline("fault");
    if(input_trace_requested)WriteInputTrace("fault");
  std::fflush(stdout);
  return EXCEPTION_CONTINUE_SEARCH; // Record only: do not repair or resume guest faults.
}
}
int main(int argc,char** argv) {
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
  std::setvbuf(stdout,nullptr,_IONBF,0); std::setvbuf(stderr,nullptr,_IONBF,0);
  AddVectoredExceptionHandler(1,RecordException);
  try {
    const char* path=std::getenv("MC2_XEX_PATH");
    if(!path || !std::filesystem::is_regular_file(path)) return 20;
    const auto xex=std::filesystem::absolute(path);
    rex::LogConfig logging;logging.log_file="title-sdk.log";logging.default_level=spdlog::level::debug;
    logging.flush_level=spdlog::level::debug;logging.category_levels["apu"]=spdlog::level::warn;
    logging.extra_sinks.push_back(std::make_shared<FatalDiagnosticSink>());
    rex::InitLogging(logging);
    char loaded[MAX_PATH]{};
    auto dll=GetModuleHandleA("rexruntime.dll");
    if(!dll || !GetModuleFileNameA(dll,loaded,MAX_PATH))return 21;
    std::printf("RUNTIME_DLL %s\n",loaded);
    auto* root=std::getenv("MC2_GAME_ROOT");
    const auto game_root=root?std::filesystem::absolute(root):xex.parent_path();
    std::printf("TITLE_ROOT %s\n",game_root.string().c_str());
    event_trace_requested=std::getenv("MC2_EVENT_TRACE") && std::strcmp(std::getenv("MC2_EVENT_TRACE"),"1")==0;
    schedule_trace_requested=std::getenv("MC2_SCHEDULE_TRACE") && std::strcmp(std::getenv("MC2_SCHEDULE_TRACE"),"1")==0;
    counter_trace_requested=std::getenv("MC2_COUNTER_TRACE") && std::strcmp(std::getenv("MC2_COUNTER_TRACE"),"1")==0;
    timeline_requested=std::getenv("MC2_FRAME_TIMELINE") && std::strcmp(std::getenv("MC2_FRAME_TIMELINE"),"1")==0;
    capture_guest_output_requested=std::getenv("MC2_CAPTURE_GUEST_OUTPUT") && std::strcmp(std::getenv("MC2_CAPTURE_GUEST_OUTPUT"),"1")==0;
    scripted_start_requested=std::getenv("MC2_SCRIPTED_START") && std::strcmp(std::getenv("MC2_SCRIPTED_START"),"1")==0;
    scripted_neutral_requested=std::getenv("MC2_SCRIPTED_NEUTRAL") && std::strcmp(std::getenv("MC2_SCRIPTED_NEUTRAL"),"1")==0;
    input_trace_requested=scripted_start_requested || (std::getenv("MC2_TRACE_INPUT") && std::strcmp(std::getenv("MC2_TRACE_INPUT"),"1")==0);
    const bool present=std::getenv("MC2_PRESENTATION") && std::strcmp(std::getenv("MC2_PRESENTATION"),"1")==0;
    if(present) {
      rex::cvar::Init(argc,argv);rex::cvar::ApplyEnvironment();
      if(!rex::cvar::SetFlagByName("headless","false"))return 32;
      std::puts("TITLE_PRESENTATION headless_flag=false");
    }
    const char* sdk_hash=std::getenv("MC2_WAIT_SDK_SHA256");
    wait_sdk_verified=sdk_hash && std::strcmp(sdk_hash,mc2::host::kWaitObservationRuntimeSha256)==0;
    std::printf("TITLE_WAIT_SDK parent_attested=%u\n",unsigned(wait_sdk_verified));
    mc2::host::PresentationSession presentation;
    rex::Runtime runtime(game_root,"./user",{},"./cache");
    rex::RuntimeConfig config;config.tool_mode=false;
    config.kernel_init=rex::kernel::InitializeKernel;
    config.audio_factory=REX_AUDIO_BACKEND(rex::audio::sdl::SDLAudioSystem);
    config.input_factory=REX_INPUT_BACKEND(rex::input::CreateDefaultInputSystem);
    if(scripted_start_requested)config.input_factory=[](bool tool_mode)->std::unique_ptr<rex::system::IInputSystem>{
      if(tool_mode)return {};auto input=rex::input::CreateDefaultInputSystem(tool_mode);if(!input)return {};
      auto driver=mc2::host::MakeScriptedController(&mc2::host::scripted_controller::Now,scripted_neutral_requested);if(!driver)return {};const auto setup=driver->Setup();
      std::printf("SCRIPTED_CONTROLLER_SETUP status=%08X input_source=synthetic setup_before_add=1 default_drivers_retained=1\n",unsigned(setup));
      if(setup)return {};input->AddDriver(std::move(driver));return input;
    };

    const auto* gpu=std::getenv("MC2_GPU_PLUGIN");
    if(gpu && *gpu) {
      // Public SDK plugin ABI; keep its library loaded for the process lifetime.
      // The convenience C++ loader failure is retained as a separate experiment.
      std::puts("TITLE_GPU loading_plugin=xenos via=public_c_abi backend=any presentation=false");
      const auto plugin=LoadLibraryW(L"rexgpu-xenos.dll");
      if(!plugin){std::printf("TITLE_GPU load_error=%lu\n",GetLastError());return 28;}
      auto version=reinterpret_cast<rex::system::GpuAbiVersionFn>(GetProcAddress(plugin,rex::system::kGpuAbiVersionSymbol));
      auto create=reinterpret_cast<rex::system::GpuCreateFn>(GetProcAddress(plugin,rex::system::kGpuCreateSymbol));
      if(!version || !create || version()!=rex::system::kGpuPluginAbiVersion){std::puts("TITLE_GPU ABI_mismatch");return 29;}
      rex::system::GpuCreateInfo info{sizeof(rex::system::GpuCreateInfo),"any"};
      config.graphics.reset(create(rex::system::kGpuPluginAbiVersion,&info));
      if(!config.graphics){std::puts("TITLE_GPU factory_failed");return 30;}
      char loaded_plugin[MAX_PATH]{};GetModuleFileNameA(plugin,loaded_plugin,MAX_PATH);
      std::printf("TITLE_GPU plugin_loaded backend=any presentation=false path=%s\n",loaded_plugin);
    }
    if(present) {
      if(!config.graphics || !presentation.Initialize(config.graphics.get()))return 31;
      runtime.set_app_context(presentation.context());
      runtime.set_display_window(presentation.window());
      std::puts("TITLE_PRESENTATION bound_before_setup=1 hidden=1");
    }
    auto status=runtime.Setup(PPCImageConfig,std::move(config));
    std::printf("SETUP status=%08X\n",unsigned(status));if(status)return 22;
    std::printf("TITLE_SUBSYSTEMS graphics=%u audio=%u input=%u\n",unsigned(runtime.graphics_system()!=nullptr),
      unsigned(runtime.audio_system()!=nullptr),unsigned(runtime.input_system()!=nullptr));
    if(event_trace_requested) {
      const bool installed=mc2::host::InstallEventImportTrace(GetModuleHandleW(nullptr),dll,wait_sdk_verified);
      std::printf("TITLE_EVENT_TRACE installed=%u\n",unsigned(installed));
      if(!installed){WriteEventTrace("install");return 33;}
    }
    kernel_state=runtime.kernel_state();
    mc2_probe_RegisterFunctions(runtime.function_dispatcher());
    guest_base=runtime.virtual_membase();
    std::puts("TITLE_STAGE functions_registered");
    status=runtime.LoadXexImage("game:\\"+xex.filename().string());
    std::printf("TITLE_LOAD status=%08X\n",unsigned(status));if(status)return 23;
    std::puts("TITLE_STAGE image_loaded_no_probe_data_writes");
    if(schedule_trace_requested) {
      const bool code=mc2::host::schedule_observation::OriginalBytes({guest_base,0x100001000ULL});
      const bool installed=code && mc2::host::SetScheduleSampleHook(&mc2::host::schedule_observation::Sample) &&
        mc2::host::InstallScheduleImportTrace(GetModuleHandleW(nullptr),dll,wait_sdk_verified);
      std::printf("TITLE_SCHEDULE_TRACE installed=%u code_guard=%u\n",unsigned(installed),unsigned(code));
      if(!installed){WriteScheduleTrace("install");return 36;}
    }
    {
      bool code=false,binding=false;
      if(counter_trace_requested){
        code=wait_sdk_verified && mc2::host::counter_observation::OriginalBytes({guest_base,0x100001000ULL});
        binding=true;
        const uint32_t targets[]={0x82399650,0x82399738,0x822D0A68};
        PPCFunc* hooks[]={&sub_82399650,&sub_82399738,&sub_822D0A68};
        PPCFunc* originals[]={&__imp__sub_82399650,&__imp__sub_82399738,&__imp__sub_822D0A68};
        for(unsigned i=0;i<3;++i){const bool bound=runtime.function_dispatcher()->GetFunction(targets[i])==hooks[i];
          const bool distinct=hooks[i]!=originals[i];binding=binding&&bound&&distinct;
          std::printf("COUNTER_BIND target=%08X dispatcher_hook=%u distinct_original=%u\n",targets[i],unsigned(bound),unsigned(distinct));}
        uint64_t initial=0;const bool known=mc2::host::schedule_observation::Read({guest_base,0x100001000ULL},0x83265218,4,initial);
        std::printf("COUNTER_INITIAL counter=83265218 word_known=%u value=%08X\n",unsigned(known),unsigned(initial));
        if(!mc2::host::SetCounterLifecycleHook(&mc2::host::counter_observation::Sample))return 38;
      }
      const bool configured=mc2::host::ConfigureCounterLifecycleTrace(code&&binding,counter_trace_requested);
      std::printf("TITLE_COUNTER_TRACE enabled=%u code_guard=%u binding_guard=%u configured=%u\n",unsigned(counter_trace_requested),unsigned(code),unsigned(binding),unsigned(configured));
      if(!configured){WriteCounterTrace("install");return 38;}
      if(!mc2::host::ConfigureQueueWatch(code&&binding,counter_trace_requested))return 39;
    }
    {
      bool code=false,binding=false;
      if(timeline_requested){
        code=wait_sdk_verified && mc2::host::frame_timeline_observation::OriginalBytes({guest_base,0x100001000ULL});binding=true;
        const uint32_t targets[]={0x8277B6D8,0x8244A360,0x8286E618,0x82E20568,0x82399778};
        PPCFunc* hooks[]={&sub_8277B6D8,&sub_8244A360,&sub_8286E618,&sub_82E20568,&sub_82399778};
        PPCFunc* originals[]={&__imp__sub_8277B6D8,&__imp__sub_8244A360,&__imp__sub_8286E618,&__imp__sub_82E20568,&__imp__sub_82399778};
        for(unsigned i=0;i<5;++i){const bool bound=runtime.function_dispatcher()->GetFunction(targets[i])==hooks[i];
          const bool distinct=hooks[i]!=originals[i];binding=binding&&bound&&distinct;
          std::printf("TIMELINE_BIND target=%08X dispatcher_hook=%u distinct_original=%u\n",targets[i],unsigned(bound),unsigned(distinct));}
      }
      const bool configured=mc2::host::ConfigureFrameTimeline(code&&binding,timeline_requested);
      std::printf("TITLE_FRAME_TIMELINE enabled=%u code_guard=%u binding_guard=%u configured=%u\n",unsigned(timeline_requested),unsigned(code),unsigned(binding),unsigned(configured));
      if(!configured){WriteFrameTimeline("install");return 41;}
      const bool capture_ready=!capture_guest_output_requested || (wait_sdk_verified&&present&&runtime.graphics_system()&&runtime.graphics_system()->presenter());
      std::printf("TITLE_GUEST_OUTPUT_CAPTURE enabled=%u sdk_guard=%u configured=%u\n",unsigned(capture_guest_output_requested),unsigned(wait_sdk_verified),unsigned(capture_ready));
      if(!capture_ready)return 42;
    }
    {
      bool code=false,binding=false;
      if(input_trace_requested){
        code=wait_sdk_verified&&mc2::host::start_input_observation::OriginalBytes({guest_base,0x100001000ULL});binding=true;
        const uint32_t targets[]={0x82868178,0x827B4938};
        PPCFunc* hooks[]={&sub_82868178,&sub_827B4938};PPCFunc* originals[]={&__imp__sub_82868178,&__imp__sub_827B4938};
        for(unsigned i=0;i<2;++i){const bool bound=runtime.function_dispatcher()->GetFunction(targets[i])==hooks[i],distinct=hooks[i]!=originals[i];binding=binding&&bound&&distinct;
          std::printf("INPUT_BIND target=%08X dispatcher_hook=%u distinct_original=%u\n",targets[i],unsigned(bound),unsigned(distinct));}
      }
      const bool configured=mc2::host::ConfigureInputStateTrace(code&&binding,input_trace_requested)&&mc2::host::ConfigureStartEventTrace(code&&binding,input_trace_requested);
      std::printf("TITLE_INPUT_TRACE enabled=%u code_guard=%u binding_guard=%u configured=%u\n",unsigned(input_trace_requested),unsigned(code),unsigned(binding),unsigned(configured));
      if(!configured){WriteInputTrace("install");return 43;}
    }
    for(auto ordinal:{0x193,0x59}) {
      auto* exp=runtime.export_resolver()->GetExportByOrdinal("xboxkrnl.exe",uint16_t(ordinal));
      if(exp) std::printf("TITLE_EXPORT ordinal=%04X name=%s type=%u implemented=%u variable=%08X\n",
        ordinal,exp->name,unsigned(exp->type),unsigned(exp->is_implemented()),
        exp->type==rex::runtime::Export::Type::kVariable?exp->variable_ptr:0);
      else std::printf("TITLE_EXPORT ordinal=%04X missing\n",ordinal);
    }
    for(uint32_t slot:{0x82000708u,0x82000710u}) {
      uint32_t word;std::memcpy(&word,guest_base+slot,sizeof(word));
      std::printf("TITLE_IMPORT slot=%08X value=%08X\n",slot,__builtin_bswap32(word));
    }
    launch_phase=1;
    auto thread=runtime.PrepareModuleLaunch();
    if(!thread){std::puts("TITLE_PREPARE missing_thread");return 24;}
    auto* context=thread->thread_state()->context();
    std::printf("TITLE_PREPARED id=%u r1=%08X r13=%08X suspend_count=%u\n",
      thread->thread_id(),context->r1.u32,context->r13.u32,thread->suspend_count());
    if(event_trace_requested)std::printf("TITLE_MAIN_THREAD host=%lu context=%016llX guest=%u\n",
      GetThreadId(static_cast<HANDLE>(thread->thread()->native_handle())),
      static_cast<unsigned long long>(reinterpret_cast<uintptr_t>(context)),thread->thread_id());
    if(scripted_start_requested){const bool armed=wait_sdk_verified&&mc2::host::ArmScriptedController();
      std::printf("TITLE_SCRIPTED_START enabled=1 input_source=synthetic armed=%u sdk_guard=%u neutral_only=%u\n",unsigned(armed),unsigned(wait_sdk_verified),unsigned(scripted_neutral_requested));if(!armed)return 44;
    }else std::puts("TITLE_SCRIPTED_START enabled=0 input_source=default");
    launch_phase=2;
    status=thread->Resume();
    std::printf("TITLE_RESUMED status=%08X\n",unsigned(status));if(status)return 25;
    unsigned observation_seconds=20;
    if(const auto* value=std::getenv("MC2_OBSERVE_SECONDS")){
      char* end=nullptr;const auto parsed=std::strtoul(value,&end,10);
      if(!*value || !end || *end || parsed<20 || parsed>60)std::_Exit(35);
      observation_seconds=unsigned(parsed);
    }
    std::printf("TITLE_OBSERVATION seconds=%u\n",observation_seconds);
    std::jthread queue_monitor;
    if(counter_trace_requested)queue_monitor=std::jthread([&](std::stop_token stop){
      for(unsigned i=0;i<128&&!stop.stop_requested();++i){mc2::host::StoreQueueWatch(mc2::host::CaptureQueueWatch(guest_base));std::this_thread::sleep_for(std::chrono::milliseconds(500));}
    });
    auto wait=rex::thread::WaitResult::kTimeout;
    auto observe=[&] {
      wait=rex::thread::Wait(thread->thread(),false,std::chrono::seconds(observation_seconds));
      std::printf("TITLE_WAIT result=%u running=%u\n",unsigned(wait),unsigned(thread->is_running()));
      if(wait!=rex::thread::WaitResult::kSuccess)SampleThread(thread.get());
      if(capture_guest_output_requested){
        if(input_trace_requested)WriteInputTrace("pre_readback");
        if(timeline_requested)WriteFrameTimeline("pre_readback"); // Keep completed evidence if the SDK fence wait never returns.
        const auto start=GetTickCount64();mc2::host::CaptureGuestOutput(runtime.graphics_system()->presenter(),"guest-output.ppm");
        std::printf("GUEST_OUTPUT_CAPTURE_TIMING elapsed_ms=%llu scheduling_perturbed=1 visible_present_proof=0\n",(unsigned long long)(GetTickCount64()-start));
      }
      if(present)presentation.RequestStop();
    };
    if(present) {
      std::thread observer(observe);
      presentation.Pump();
      observer.join();
      std::puts("TITLE_PRESENTATION bounded_exit=1 guest_shutdown_verified=0");
    } else observe();
    if(event_trace_requested) {
      const bool restored=mc2::host::RestoreEventImportTrace();
      std::printf("TITLE_EVENT_TRACE restored=%u\n",unsigned(restored));
      WriteEventTrace("boundary");
      if(!restored){std::fflush(stdout);std::_Exit(34);}
    }
    if(schedule_trace_requested) {
      const bool restored=mc2::host::RestoreScheduleImportTrace();
      std::printf("TITLE_SCHEDULE_TRACE restored=%u\n",unsigned(restored));WriteScheduleTrace("boundary");
      if(!restored){std::fflush(stdout);std::_Exit(37);}
    }
    if(counter_trace_requested){queue_monitor.request_stop();queue_monitor.join();const bool paired=mc2::host::SampleCounterWorkers(guest_base);WriteCounterTrace("boundary");WriteQueueWatch("boundary");if(!paired){std::fflush(stdout);std::_Exit(40);}}
    if(timeline_requested && timeline_dump_index.load()==0)WriteFrameTimeline("boundary");
    if(input_trace_requested && input_dump_index.load()==0)WriteInputTrace("boundary");
    // The parent runner confines this diagnostic process. No forced guest continuation.
    std::fflush(stdout);rex::FlushLogging();
    std::_Exit(wait==rex::thread::WaitResult::kSuccess?0:26);
  } catch(const std::exception& error) {
    std::printf("TITLE_HOST_EXCEPTION %s\n",error.what());return 27;
  }
}
