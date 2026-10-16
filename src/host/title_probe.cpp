// Unmodified generated-module / SDK title-launch probe. No guest data fixtures.
#include "mc2_probe_init.h"
#include "presentation_probe.h"
#include "wait_observation.h"
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
LONG CALLBACK RecordException(EXCEPTION_POINTERS* pointers) {
  auto* record = pointers->ExceptionRecord;
  if (!launch_phase || (record->ExceptionCode != EXCEPTION_ACCESS_VIOLATION &&
      record->ExceptionCode != EXCEPTION_BREAKPOINT && record->ExceptionCode != EXCEPTION_ILLEGAL_INSTRUCTION))
    return EXCEPTION_CONTINUE_SEARCH;
  std::fprintf(stderr, "TITLE_EXCEPTION code=%08lX ip=%p phase=%ld thread=%lu\n",
      record->ExceptionCode, record->ExceptionAddress, launch_phase, GetCurrentThreadId());
  if(record->NumberParameters >= 2) {
    std::fprintf(stderr,"TITLE_FAULT operation=%llu address=%016llX guest_offset=%016llX\n",
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
    std::fprintf(stderr,"TITLE_STACK %u address=%p rva=%llX module=%s\n",i,frames[i],
      reinterpret_cast<uintptr_t>(frames[i])-reinterpret_cast<uintptr_t>(module),name);
  }
  if (auto* state = rex::runtime::ThreadState::Get()) {
    auto* c=state->context();
    std::fprintf(stderr,"TITLE_PPC r1=%08X r3=%08X r4=%08X lr=%08X ctr=%08X\n",
      c->r1.u32,c->r3.u32,c->r4.u32,unsigned(c->lr),c->ctr.u32);
  }
  NativeState();
  std::fflush(stderr);
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
    kernel_state=runtime.kernel_state();
    mc2_probe_RegisterFunctions(runtime.function_dispatcher());
    guest_base=runtime.virtual_membase();
    std::puts("TITLE_STAGE functions_registered");
    status=runtime.LoadXexImage("game:\\"+xex.filename().string());
    std::printf("TITLE_LOAD status=%08X\n",unsigned(status));if(status)return 23;
    std::puts("TITLE_STAGE image_loaded_no_probe_data_writes");
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
    launch_phase=2;
    status=thread->Resume();
    std::printf("TITLE_RESUMED status=%08X\n",unsigned(status));if(status)return 25;
    auto wait=rex::thread::WaitResult::kTimeout;
    auto observe=[&] {
      wait=rex::thread::Wait(thread->thread(),false,std::chrono::seconds(20));
      std::printf("TITLE_WAIT result=%u running=%u\n",unsigned(wait),unsigned(thread->is_running()));
      if(wait!=rex::thread::WaitResult::kSuccess)SampleThread(thread.get());
      if(present)presentation.RequestStop();
    };
    if(present) {
      std::thread observer(observe);
      presentation.Pump();
      observer.join();
      std::puts("TITLE_PRESENTATION bounded_exit=1 guest_shutdown_verified=0");
    } else observe();
    // The parent runner confines this diagnostic process. No forced guest continuation.
    std::fflush(stdout);rex::FlushLogging();
    std::_Exit(wait==rex::thread::WaitResult::kSuccess?0:26);
  } catch(const std::exception& error) {
    std::fprintf(stderr,"TITLE_HOST_EXCEPTION %s\n",error.what());return 27;
  }
}
