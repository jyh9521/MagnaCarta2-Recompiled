// Independent SDK concurrency diagnostic. No game image or resource is loaded.
#include <Windows.h>
#include <atomic>
#include <barrier>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <thread>
#include <rex/input/input_system.h>
#include "input_call_gate.h"
#include "input_probe_trace.h"
using namespace rex::input;
using rex::X_RESULT; using rex::X_STATUS;
class ProbeDriver final : public InputDriver {
 public:
  explicit ProbeDriver(size_t length) : InputDriver(nullptr, 0), length_(length) {}
  X_STATUS Setup() override { return 0; }
  void EnumerateDevices(std::vector<DeviceInfo>& out) override {
    mc2::input_probe::Record(3, &out);
    DeviceInfo d; d.id=static_cast<DeviceId>(0x1234); d.synthetic=true;
    d.name=std::string(length_, 'N'); d.guid=std::string(length_, 'G'); out.push_back(d);
    mc2::input_probe::Record(4, &out);
  }
  X_RESULT GetDeviceState(DeviceId, X_INPUT_STATE* state) override { *state={}; return 0; }
  X_RESULT GetDeviceCapabilities(DeviceId, uint32_t, X_INPUT_CAPABILITIES* caps) override { *caps={}; return 0; }
  X_RESULT SetDeviceVibration(DeviceId, X_INPUT_VIBRATION*) override { return 0; }
  X_RESULT GetDeviceKeystroke(DeviceId, uint32_t, X_INPUT_KEYSTROKE*) override { return 1167; }
 private: size_t length_;
};
static LONG CALLBACK Fault(EXCEPTION_POINTERS* p) {
  if(p->ExceptionRecord->ExceptionCode!=EXCEPTION_ACCESS_VIOLATION) return EXCEPTION_CONTINUE_SEARCH;
  HMODULE sdk=GetModuleHandleW(L"rexruntime.dll");
  std::fprintf(stderr,"SDK_PROBE_AV code=%08lX thread=%lu ip_rva=%llX operation=%llu address=%llX rcx=%llX rdi=%llX\n",
    p->ExceptionRecord->ExceptionCode,GetCurrentThreadId(),
    (unsigned long long)p->ExceptionRecord->ExceptionAddress-(unsigned long long)sdk,
    (unsigned long long)p->ExceptionRecord->ExceptionInformation[0],
    (unsigned long long)p->ExceptionRecord->ExceptionInformation[1],p->ContextRecord->Rcx,p->ContextRecord->Rdi);
  std::fflush(stderr); return EXCEPTION_CONTINUE_SEARCH;
}
int main(int argc,char** argv) {
  if(argc!=4 || (std::strcmp(argv[1],"concurrent") && std::strcmp(argv[1],"serialized"))) return 2;
  unsigned loops=std::strtoul(argv[2],nullptr,10); size_t length=std::strtoul(argv[3],nullptr,10);
  if(!loops || loops>100000 || length>16384) return 2;
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX); AddVectoredExceptionHandler(1,Fault);
  wchar_t trace_path[32768]{};
  const auto trace_size=GetEnvironmentVariableW(L"MC2_INPUT_PROBE_TRACE",trace_path,32768);
  if(trace_size && (trace_size>=32768 || !mc2::input_probe::Open(trace_path)))return 4;
  InputSystem input(nullptr); mc2::input_probe::object=&input; input.AddDriver(std::make_unique<ProbeDriver>(length));
  input.SetDeviceAssignment(std::make_unique<SlotAssignment>()); input.Setup();
  std::barrier ready(2); bool serial=!std::strcmp(argv[1],"serialized");
  std::atomic<unsigned> reads{0},writes{0},errors{0};
  std::printf("SDK_PROBE start mode=%s loops=%u string_length=%zu game_loaded=0\n",argv[1],loops,length);std::fflush(stdout);
  auto worker=[&](bool get){
    mc2::input_probe::worker=get?0:1;mc2::input_probe::api=get?1:2;
    mc2::input_probe::gated=serial;
    ready.arrive_and_wait();
    for(unsigned n=0;n<loops;++n) {
      X_INPUT_STATE state{}; X_INPUT_VIBRATION vibration{};
      mc2::input_probe::iteration=n;mc2::input_probe::Record(1);
      X_RESULT result=0;auto call=[&]{++mc2::input_probe::depth;mc2::input_probe::Record(2);
        result=get?input.GetState(0,&state):input.SetState(0,&vibration);
        mc2::input_probe::Record(5);--mc2::input_probe::depth;};
      if(serial)mc2::host::input_call_gate::Invoke(get?1:2,call);else call();
      mc2::input_probe::Record(6);
      if(result)++errors; if(get)++reads;else ++writes;
    }
  };
  std::thread a(worker,true),b(worker,false);a.join();b.join(); mc2::input_probe::Record(7);input.Shutdown();mc2::input_probe::Record(8);
  mc2::input_probe::Close();
  std::printf("SDK_PROBE completed reads=%u writes=%u errors=%u mode=%s\n",reads.load(),writes.load(),errors.load(),argv[1]);
  return errors?3:0;
}
